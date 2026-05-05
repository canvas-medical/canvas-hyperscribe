from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any, Union

from canvas_sdk.v1.data.medication import Status
from logger import log

from canvas_sdk.caching.plugins import get_cache
from canvas_sdk.effects import Effect
from canvas_sdk.effects.note.note import Note as NoteEffect
from canvas_sdk.effects.simple_api import Broadcast, JSONResponse, Response
from canvas_sdk.handlers.simple_api import SimpleAPI, StaffSessionAuthMixin, api

from django.db.models import Q

from canvas_sdk.commands.commands.allergy import AllergenType
from canvas_sdk.commands.commands.questionnaire import QuestionnaireCommand
from canvas_sdk.v1.data import AllergyIntolerance, ChargeDescriptionMaster, Medication, Note
from canvas_sdk.v1.data.prescription import Prescription
from canvas_sdk.v1.data.condition import Condition as ConditionModel
from canvas_sdk.v1.data.lab import LabPartner, LabPartnerTest
from canvas_sdk.v1.data.questionnaire import Questionnaire as QuestionnaireModel
from canvas_sdk.v1.data.staff import Staff, StaffRole
from canvas_sdk.v1.data.task import TaskLabel
from canvas_sdk.v1.data.team import Team

from hyperscribe.models.scribe import ScribeAuditLog, ScribeSummary, ScribeTranscript

from canvas_sdk.utils.http import pharmacy_http, science_http
from canvas_sdk.v1.data.patient import Patient

from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper

import hyperscribe.scribe.clients.nabla  # noqa: F401 — register backends
from hyperscribe.scribe.backend import (
    ClinicalNote,
    CodingEntry,
    Condition,
    NoteSection,
    PatientContext,
    ScribeError,
    Transcript,
    TranscriptItem,
    get_backend_from_secrets,
)
from hyperscribe.scribe.commands.ap_split import split_plan_into_diagnoses
from hyperscribe.scribe.commands.builder import (
    annotate_duplicates,
    build_effects,
    build_metadata_effects,
    validate_proposals,
)
from hyperscribe.scribe.commands.extractor import extract_commands, parse_ros_subsections
from hyperscribe.scribe.commands.prior_sections import get_prior_section_data
from hyperscribe.scribe.recommendations import recommend_commands
from hyperscribe.scribe.recommendations.diagnosis_suggestion import suggest_diagnoses
from hyperscribe.scribe.recommendations.reconciliation import reconcile_sections
from hyperscribe.scribe.recommendations.interactions import (
    check_recommendation_interactions,
    check_single_medication_interactions,
)


def _format_icd10_code(raw: str) -> str:
    code = raw.strip().replace(".", "").upper()
    if len(code) > 3:
        return code[:3] + "." + code[3:]
    return code


def _authorize_edit(note_uuid: str, request: Any) -> JSONResponse | None:
    """Return a JSONResponse to short-circuit when the staff cannot edit the note's Scribe tab.

    Authorized when the note exists, is in an editable state, and the logged-in
    staff (from `canvas-logged-in-user-id` request header) matches the note's
    provider. Returns None on success.

    Uses `.values()` to fetch only the two scalars we need — this runs on every
    mutating endpoint, so we want it cheap.
    """
    if not note_uuid:
        return JSONResponse({"error": "note_uuid is required"}, status_code=HTTPStatus.BAD_REQUEST)
    try:
        note = Note.objects.values("dbid", "provider__id").get(id=note_uuid)
    except Note.DoesNotExist:
        return JSONResponse({"error": "Note not found"}, status_code=HTTPStatus.NOT_FOUND)
    if not Helper.editable_note(note["dbid"]):
        return JSONResponse({"error": "Note is not editable"}, status_code=HTTPStatus.FORBIDDEN)
    headers = getattr(request, "headers", {}) or {}
    staff_id = headers.get("canvas-logged-in-user-id") or ""
    provider_id = note.get("provider__id")
    if not staff_id or not provider_id or str(provider_id) != str(staff_id):
        return JSONResponse(
            {"error": "Only the note author can modify the Scribe tab"},
            status_code=HTTPStatus.FORBIDDEN,
        )
    return None


def _authorize_read_as_author(note_uuid: str, request: Any) -> JSONResponse | None:
    """Same author-only check as `_authorize_edit`, minus the editability gate.

    Use on read-only endpoints (e.g. /verify-commands) that need probe defense
    — i.e. block staff who aren't the note's author from learning the existence
    of arbitrary command UUIDs — but must remain reachable AFTER the note is
    locked or signed (otherwise legit post-sign reloads by the actual author
    would 403 indefinitely).
    """
    if not note_uuid:
        return JSONResponse({"error": "note_uuid is required"}, status_code=HTTPStatus.BAD_REQUEST)
    try:
        note = Note.objects.values("provider__id").get(id=note_uuid)
    except Note.DoesNotExist:
        return JSONResponse({"error": "Note not found"}, status_code=HTTPStatus.NOT_FOUND)
    headers = getattr(request, "headers", {}) or {}
    staff_id = headers.get("canvas-logged-in-user-id") or ""
    provider_id = note.get("provider__id")
    if not staff_id or not provider_id or str(provider_id) != str(staff_id):
        return JSONResponse(
            {"error": "Only the note author can read this Scribe tab data"},
            status_code=HTTPStatus.FORBIDDEN,
        )
    return None


def audit_event(note_uuid: str, event_type: str, details: dict[str, Any] | None = None) -> None:
    """Append an audit event to the ScribeAuditLog from the backend."""
    from datetime import datetime, timezone

    try:
        note_dbid = Note.objects.values_list("dbid", flat=True).get(id=note_uuid)
        obj, created = ScribeAuditLog.objects.get_or_create(note_id=note_dbid, defaults={"events": []})
        event = {"ts": datetime.now(timezone.utc).isoformat(), "type": event_type, "details": details or {}}
        obj.events = list(obj.events) + [event]
        obj.save()
    except Exception:
        log.exception(f"Failed to write audit event: {event_type}")


_PROGRESS_CACHE_KEY_PREFIX = "scribe_progress:"

_PLAN_SECTION_KEYS = frozenset({"assessment_and_plan", "plan"})

SUMMARY_STEPS = [
    "Generating note",
    "Structuring the note",
    "Extracting commands",
    "Generating recommendations",
    "Suggesting diagnoses",
]


def _save_progress(note_id: str, step: int, total: int, label: str) -> None:
    key = f"{_PROGRESS_CACHE_KEY_PREFIX}{note_id}"
    try:
        cache = get_cache()
        cache.set(key, json.dumps({"step": step, "total": total, "label": label}))
    except Exception:
        log.exception(f"progress cache save FAILED: key={key}")


def _serialize_condition(condition: Condition) -> dict[str, Any]:
    result: dict[str, Any] = {
        "display": condition.display,
        "clinical_status": condition.clinical_status,
        "coding": [{"system": e.system, "code": e.code, "display": e.display} for e in condition.coding],
    }
    if condition.corresponding_note_problem is not None:
        result["corresponding_note_problem"] = condition.corresponding_note_problem
    return result


def _match_conditions_to_sections(
    note: ClinicalNote,
    conditions: list[Condition],
) -> dict[str, list[dict[str, Any]]]:
    """Map each note section to its relevant conditions.

    Assessment/plan sections get all conditions. Other sections get conditions
    whose display text appears as a case-insensitive substring in the section text.
    """
    result: dict[str, list[dict[str, Any]]] = {}
    for section in note.sections:
        key = section.key.lower()
        if key in _PLAN_SECTION_KEYS:
            matched = conditions
        else:
            section_lower = section.text.lower()
            matched = [c for c in conditions if c.display.lower() in section_lower]
        if matched:
            result[key] = [_serialize_condition(c) for c in matched]
    return result


def _save_transcript(
    note_id: str,
    items: list[dict[str, Any]],
    *,
    finalized: bool = False,
    provider_id: str = "",
) -> None:
    note_dbid = Note.objects.values_list("dbid", flat=True).get(id=note_id)
    defaults: dict[str, Any] = {"items": items, "finalized": finalized}
    if provider_id:
        defaults["provider_id"] = provider_id
    ScribeTranscript.objects.update_or_create(
        note_id=note_dbid,
        defaults=defaults,
    )


def _load_transcript(note_id: str) -> dict[str, Any]:
    note_dbid = Note.objects.values_list("dbid", flat=True).get(id=note_id)
    row = ScribeTranscript.objects.filter(note_id=note_dbid).values("items", "finalized").first()
    if row:
        return {"items": row["items"], "finalized": row["finalized"], "started": True}
    return {"items": [], "finalized": False, "started": False}


def _save_summary(note_id: str, payload: dict[str, Any]) -> None:
    note_dbid = Note.objects.values_list("dbid", flat=True).get(id=note_id)
    defaults: dict[str, Any] = {
        "note_data": payload.get("note") or {},
        "commands": payload.get("commands") or [],
        "approved": payload.get("approved", False),
        "recommendations": payload.get("recommendations") or [],
        "unmatched_conditions": payload.get("unmatched_conditions") or [],
        "diagnosis_suggestions": payload.get("diagnosis_suggestions") or {},
        "selected_template_name": payload.get("selected_template_name") or "",
        "mode": payload.get("mode") or "",
    }
    if "raw_response" in payload:
        defaults["raw_response"] = payload["raw_response"]
    ScribeSummary.objects.update_or_create(note_id=note_dbid, defaults=defaults)


def _load_summary(note_id: str) -> dict[str, Any] | None:
    note_dbid = Note.objects.values_list("dbid", flat=True).get(id=note_id)
    row = (
        ScribeSummary.objects.filter(note_id=note_dbid)
        .values(
            "note_data",
            "commands",
            "approved",
            "recommendations",
            "unmatched_conditions",
            "diagnosis_suggestions",
            "selected_template_name",
            "mode",
        )
        .first()
    )
    if row:
        return {
            "note": row["note_data"] or None,
            "commands": row["commands"] or [],
            "approved": row["approved"],
            "recommendations": row["recommendations"] or [],
            "unmatched_conditions": row["unmatched_conditions"] or [],
            "diagnosis_suggestions": row["diagnosis_suggestions"] or {},
            "selected_template_name": row["selected_template_name"] or None,
            "mode": row["mode"] or None,
        }
    return None


def _load_assignees() -> list[dict[str, Any]]:
    """Load active staff members and teams for task assignment."""
    assignees: list[dict[str, Any]] = []
    for s in (
        Staff.objects.filter(active=True).order_by("last_name", "first_name").values("dbid", "first_name", "last_name")
    ):
        label = f"{s['first_name']} {s['last_name']}".strip()
        assignees.append({"type": "staff", "id": s["dbid"], "label": label})
    for t in Team.objects.all().order_by("name").values("dbid", "name"):
        assignees.append({"type": "team", "id": t["dbid"], "label": t["name"]})
    return assignees


def _load_templates(secrets: dict[str, str]) -> list[dict[str, Any]]:
    """Load and resolve visit templates from secrets config."""
    raw = secrets.get(Constants.SECRET_VISIT_TEMPLATES, "{}")
    try:
        config = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        log.warning("visit-templates: malformed JSON in %s secret", Constants.SECRET_VISIT_TEMPLATES)
        return []

    templates_config: list[dict[str, Any]] = config.get("templates", [])
    if not templates_config:
        return []

    all_cpt_codes: set[str] = set()
    for tmpl in templates_config:
        for code in tmpl.get("charges", []):
            code = str(code).strip()
            if code:
                all_cpt_codes.add(code)

    cdm_by_code: dict[str, Any] = {}
    if all_cpt_codes:
        for record in ChargeDescriptionMaster.objects.filter(cpt_code__in=all_cpt_codes):
            cdm_by_code[record.cpt_code] = record

    all_q_names: list[str] = []
    for tmpl in templates_config:
        all_q_names.extend(tmpl.get("questionnaires", []))

    q_by_name: dict[str, Any] = {}
    if all_q_names:
        q_filter = Q()
        for qn in set(all_q_names):
            q_filter |= Q(name__iexact=qn)
        for q_obj in QuestionnaireModel.objects.filter(q_filter, status="AC"):
            q_by_name[q_obj.name.lower()] = q_obj

    def _resolve_questionnaire(q_obj: Any) -> dict[str, Any]:
        cmd = QuestionnaireCommand(questionnaire_id=str(q_obj.id), note_uuid="", command_uuid="")
        questions: list[dict[str, Any]] = []
        for q in cmd.questions:
            options = [{"dbid": o.dbid, "value": o.name} for o in q.options]
            questions.append({"dbid": int(q.id), "label": q.label, "type": q.type, "options": options})
        return {"questionnaire_dbid": q_obj.dbid, "questionnaire_name": q_obj.name, "questions": questions}

    result_templates: list[dict[str, Any]] = []
    for tmpl in templates_config:
        q_names: list[str] = tmpl.get("questionnaires", [])
        resolved: list[dict[str, Any]] = []
        for q_name in q_names:
            q_obj = q_by_name.get(q_name.lower())
            if not q_obj:
                log.warning("visit-templates: questionnaire %r not found", q_name)
                continue
            try:
                resolved.append(_resolve_questionnaire(q_obj))
            except Exception:
                log.exception("visit-templates: failed to resolve %r", q_name)
        ros_sections: list[dict[str, str]] | None = None
        if raw_ros := tmpl.get("ros_template"):
            ros_sections = parse_ros_subsections(raw_ros)
        pe_sections: list[dict[str, str]] | None = None
        if raw_pe := tmpl.get("pe_template"):
            pe_sections = parse_ros_subsections(raw_pe)
        resolved_charges: list[dict[str, str]] = []
        for code in tmpl.get("charges", []):
            code = str(code).strip()
            record = cdm_by_code.get(code)
            if not record:
                log.warning("visit-templates: charge CPT code %r not found", code)
                continue
            resolved_charges.append({"cpt_code": record.cpt_code, "description": record.short_name or record.name})
        result_templates.append(
            {
                "name": tmpl.get("name", ""),
                "questionnaires": resolved,
                "ros_sections": ros_sections,
                "pe_sections": pe_sections,
                "charges": resolved_charges,
            }
        )

    return result_templates


def _load_initial_data(note_id: str, secrets: dict[str, str]) -> dict[str, Any]:
    """Compile all data needed for the Scribe UI initial render."""
    # Best-effort: never let prior_sections lookup break the Scribe UI render.
    try:
        prior_sections = get_prior_section_data(note_id)
    except Exception:
        log.exception("_load_initial_data: prior_sections lookup failed for note %s", note_id)
        prior_sections = {"physical_exam": None, "review_of_systems": None}
    return {
        "transcript": _load_transcript(note_id),
        "summary": _load_summary(note_id),
        "assignees": _load_assignees(),
        "templates": _load_templates(secrets),
        "prior_sections": prior_sections,
    }


def _parse_transcript(data: dict[str, Any]) -> Transcript:
    items: list[TranscriptItem] = []
    for item in data.get("items", []):
        items.append(
            TranscriptItem(
                text=str(item.get("text", "")),
                speaker=str(item.get("speaker", "")),
                start_offset_ms=int(item.get("start_offset_ms", 0)),
                end_offset_ms=int(item.get("end_offset_ms", 0)),
                item_id=str(item.get("item_id", "")),
                is_final=bool(item.get("is_final", True)),
            )
        )
    return Transcript(items=items)


def _parse_patient_context(data: dict[str, Any]) -> PatientContext | None:
    ctx = data.get("patient_context")
    if ctx is None:
        return None
    diagnoses = [
        CodingEntry(
            system=str(d.get("system", "")),
            code=str(d.get("code", "")),
            display=str(d.get("display", "")),
        )
        for d in ctx.get("encounter_diagnoses", [])
    ]
    return PatientContext(
        name=str(ctx.get("name", "")),
        birth_date=str(ctx.get("birth_date", "")),
        gender=str(ctx.get("gender", "")),
        encounter_diagnoses=diagnoses,
    )


def _parse_note(data: dict[str, Any]) -> ClinicalNote:
    sections = [
        NoteSection(
            key=str(s.get("key", "")),
            title=str(s.get("title", "")),
            text=str(s.get("text", "")),
        )
        for s in data.get("sections", [])
    ]
    return ClinicalNote(title=str(data.get("title", "")), sections=sections)


class ScribeSessionView(StaffSessionAuthMixin, SimpleAPI):
    """Scribe session management API."""

    PREFIX = "/scribe-session"

    @api.get("/debug-cache")
    def get_debug_cache(self) -> list[Union[Response, Effect]]:
        note_id = self.request.query_params.get("note_id", "")
        if not note_id:
            return [JSONResponse({"error": "note_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        try:
            note_dbid = Note.objects.values_list("dbid", flat=True).get(id=note_id)
        except Note.DoesNotExist:
            return [JSONResponse({"error": "Note not found"}, status_code=HTTPStatus.NOT_FOUND)]
        transcript_row = (
            ScribeTranscript.objects.filter(note_id=note_dbid)
            .values(
                "items",
                "finalized",
                "provider_id",
                "updated_at",
            )
            .first()
        )
        summary_row = (
            ScribeSummary.objects.filter(note_id=note_dbid)
            .values(
                "note_data",
                "commands",
                "recommendations",
                "unmatched_conditions",
                "diagnosis_suggestions",
                "approved",
                "selected_template_name",
                "mode",
                "raw_response",
                "updated_at",
            )
            .first()
        )
        audit_row = (
            ScribeAuditLog.objects.filter(note_id=note_dbid)
            .values(
                "events",
                "updated_at",
            )
            .first()
        )
        # Serialize datetimes to ISO strings.
        for row in (transcript_row, summary_row, audit_row):
            if row and "updated_at" in row and row["updated_at"]:
                row["updated_at"] = row["updated_at"].isoformat()
        return [
            JSONResponse(
                {
                    "note_dbid": note_dbid,
                    "transcript": transcript_row,
                    "summary": summary_row,
                    "audit_log": audit_row,
                },
                status_code=HTTPStatus.OK,
            )
        ]

    @api.delete("/debug-cache")
    def delete_debug_cache(self) -> list[Union[Response, Effect]]:
        note_id = self.request.query_params.get("note_id", "")
        if not note_id:
            return [JSONResponse({"error": "note_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        key_type = self.request.query_params.get("type", "all")
        try:
            note_dbid = Note.objects.values_list("dbid", flat=True).get(id=note_id)
            if key_type in ("all", "transcript"):
                ScribeTranscript.objects.filter(note_id=note_dbid).delete()
            if key_type in ("all", "summary"):
                ScribeSummary.objects.filter(note_id=note_dbid).delete()
            if key_type in ("all", "audit_log"):
                ScribeAuditLog.objects.filter(note_id=note_dbid).delete()
        except Note.DoesNotExist:
            pass
        except Exception:
            log.exception(f"debug cache delete FAILED: note_id={note_id}")
            return [JSONResponse({"error": "Cache delete failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
        return [JSONResponse({"status": "ok", "deleted": key_type}, status_code=HTTPStatus.OK)]

    @api.put("/debug-cache")
    def put_debug_cache(self) -> list[Union[Response, Effect]]:
        """Update a model record's fields for debugging/testing."""
        try:
            body: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError):
            return [JSONResponse({"error": "Invalid JSON"}, status_code=HTTPStatus.BAD_REQUEST)]
        note_id = body.get("note_id", "")
        model_type = body.get("type", "")
        fields = body.get("fields", {})
        if not note_id or not model_type or not fields:
            return [
                JSONResponse({"error": "note_id, type, and fields are required"}, status_code=HTTPStatus.BAD_REQUEST)
            ]
        model_map: dict[str, type[ScribeTranscript] | type[ScribeSummary] | type[ScribeAuditLog]] = {
            "transcript": ScribeTranscript,
            "summary": ScribeSummary,
            "audit_log": ScribeAuditLog,
        }
        model_cls = model_map.get(model_type)
        if not model_cls:
            return [JSONResponse({"error": f"Unknown type: {model_type}"}, status_code=HTTPStatus.BAD_REQUEST)]
        try:
            note_dbid = Note.objects.values_list("dbid", flat=True).get(id=note_id)
            # Filter out non-editable fields.
            fields.pop("updated_at", None)
            model_cls.objects.update_or_create(note_id=note_dbid, defaults=fields)
        except Note.DoesNotExist:
            return [JSONResponse({"error": "Note not found"}, status_code=HTTPStatus.NOT_FOUND)]
        except Exception:
            log.exception(f"debug cache update FAILED: note_id={note_id}, type={model_type}")
            return [JSONResponse({"error": "Update failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
        return [JSONResponse({"status": "ok"}, status_code=HTTPStatus.OK)]

    @api.get("/config")
    def get_config(self) -> list[Union[Response, Effect]]:
        try:
            backend = get_backend_from_secrets(self.secrets)
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.BAD_REQUEST)]
        try:
            staff_id = self.request.headers.get("canvas-logged-in-user-id")
            config = backend.get_transcription_config(user_external_id=staff_id)
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
        return [JSONResponse(config, status_code=HTTPStatus.OK)]

    @api.get("/transcript")
    def get_transcript(self) -> list[Union[Response, Effect]]:
        note_id = self.request.query_params.get("note_id", "")
        if not note_id:
            return [JSONResponse({"error": "note_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        data = _load_transcript(note_id)
        return [JSONResponse(data, status_code=HTTPStatus.OK)]

    @api.post("/save-transcript")
    def post_save_transcript(self) -> list[Union[Response, Effect]]:
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]
        note_id = str(data.get("note_id", ""))
        if not note_id:
            return [JSONResponse({"error": "note_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        if denial := _authorize_edit(note_id, self.request):
            return [denial]
        staff_id = self.request.headers.get("canvas-logged-in-user-id") or ""
        items = data.get("transcript", {}).get("items", [])
        finalized = bool(data.get("finalized", False))
        _save_transcript(note_id, items, finalized=finalized, provider_id=staff_id)
        return [JSONResponse({"status": "ok"}, status_code=HTTPStatus.OK)]

    @api.get("/summary")
    def get_summary(self) -> list[Union[Response, Effect]]:
        note_id = self.request.query_params.get("note_id", "")
        if not note_id:
            return [JSONResponse({"error": "note_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        data = _load_summary(note_id)
        if data is None:
            return [JSONResponse({"note": None, "commands": [], "approved": False}, status_code=HTTPStatus.OK)]
        return [JSONResponse(data, status_code=HTTPStatus.OK)]

    @api.post("/save-summary")
    def post_save_summary(self) -> list[Union[Response, Effect]]:
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]
        note_id = str(data.get("note_id", ""))
        if not note_id:
            return [JSONResponse({"error": "note_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        if denial := _authorize_edit(note_id, self.request):
            return [denial]
        payload: dict[str, Any] = {
            "note": data.get("note", {}),
            "commands": data.get("commands", []),
            "approved": bool(data.get("approved", False)),
        }
        if data.get("recommendations") is not None:
            payload["recommendations"] = data["recommendations"]
        if data.get("unmatched_conditions") is not None:
            payload["unmatched_conditions"] = data["unmatched_conditions"]
        if data.get("diagnosis_suggestions") is not None:
            payload["diagnosis_suggestions"] = data["diagnosis_suggestions"]
        if data.get("interaction_warnings") is not None:
            payload["interaction_warnings"] = data["interaction_warnings"]
        if data.get("selected_template_name") is not None:
            payload["selected_template_name"] = data["selected_template_name"]
        if data.get("mode") is not None:
            payload["mode"] = data["mode"]
        _save_summary(note_id, payload)
        return [JSONResponse({"status": "ok"}, status_code=HTTPStatus.OK)]

    @api.get("/summary-progress")
    def get_summary_progress(self) -> list[Union[Response, Effect]]:
        """Return current progress of the generate-summary pipeline."""
        note_id = self.request.query_params.get("note_id", "")
        key = f"{_PROGRESS_CACHE_KEY_PREFIX}{note_id}"
        try:
            cache = get_cache()
            raw = cache.get(key)
        except Exception:
            raw = None
        if raw is None:
            return [JSONResponse({"step": -1, "total": 0, "label": ""}, status_code=HTTPStatus.OK)]
        return [JSONResponse(json.loads(raw), status_code=HTTPStatus.OK)]

    @api.post("/generate-summary")
    def post_generate_summary(self) -> list[Union[Response, Effect]]:
        """Run the full summary pipeline: note → commands → recommendations → diagnoses.

        Returns the complete summary in one response and caches it.
        """
        try:
            backend = get_backend_from_secrets(self.secrets)
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.BAD_REQUEST)]
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]

        note_id = str(data.get("note_id", ""))
        if not note_id:
            return [JSONResponse({"error": "note_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        if denial := _authorize_edit(note_id, self.request):
            return [denial]

        total = len(SUMMARY_STEPS)

        # ── Step 0: Generate note ──
        _save_progress(note_id, 0, total, SUMMARY_STEPS[0])

        transcript_data = data.get("transcript", {})
        transcript_items = transcript_data.get("items", [])
        loaded_data: dict[str, Any] | None = None
        if not transcript_items:
            loaded_data = _load_transcript(note_id)
            if loaded_data and loaded_data["items"]:
                transcript_items = loaded_data["items"]
                transcript_data = {"items": transcript_items}

        if not transcript_items:
            return [JSONResponse({"error": "No transcript available"}, status_code=HTTPStatus.BAD_REQUEST)]

        is_finalized = (loaded_data or {}).get("finalized", False) if not data.get("transcript") else True
        if not is_finalized:
            return [
                JSONResponse(
                    {"error": "Transcript is still in progress. Finish recording before generating a summary."},
                    status_code=HTTPStatus.BAD_REQUEST,
                )
            ]

        transcript = _parse_transcript(transcript_data)
        patient_context = _parse_patient_context(data)
        try:
            note = backend.generate_note(transcript, patient_context=patient_context)
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]

        raw_response = getattr(backend, "_last_raw_note_response", None)
        note_dict: dict[str, Any] = {
            "title": note.title,
            "sections": [{"key": s.key, "title": s.title, "text": s.text} for s in note.sections],
        }

        # ── Step 1: Generate normalized data ──
        _save_progress(note_id, 1, total, SUMMARY_STEPS[1])
        section_conditions: dict[str, list[dict[str, Any]]] = {}
        try:
            normalized = backend.generate_normalized_data(note)
            section_conditions = _match_conditions_to_sections(note, normalized.conditions)
        except Exception:
            log.exception("generate_normalized_data failed (non-critical)")

        # ── Step 2: Extract commands + A&P split ──
        _save_progress(note_id, 2, total, SUMMARY_STEPS[2])
        note_uuid = str(data.get("note_uuid", ""))
        proposals = extract_commands(note)
        annotate_duplicates(proposals, note_uuid)
        commands_list: list[dict[str, Any]] = [
            {
                "command_type": p.command_type,
                "display": p.display,
                "data": p.data,
                "selected": p.selected,
                "section_key": p.section_key,
                "already_documented": p.already_documented,
            }
            for p in proposals
        ]
        # A&P split: replace plan command with per-condition diagnose commands.
        commands_list, unmatched_conditions = split_plan_into_diagnoses(commands_list, section_conditions)

        # ── Step 2.5: Reconcile template ROS/PE with Nabla-generated ones ──
        template_ros: list[dict[str, str]] | None = data.get("template_ros_sections")
        template_pe: list[dict[str, str]] | None = data.get("template_pe_sections")
        reconciliation_api_key = self.secrets.get("AnthropicAPIKey", "")
        cmd_types = [c["command_type"] for c in commands_list]
        log.info(
            "step 2.5: template_ros=%s, template_pe=%s, api_key=%s, cmd_types=%s",
            len(template_ros) if template_ros else None,
            len(template_pe) if template_pe else None,
            bool(reconciliation_api_key),
            cmd_types,
        )
        if template_ros or template_pe:
            has_ros = any(c["command_type"] == "ros" for c in commands_list)
            has_pe = any(c["command_type"] == "physical_exam" for c in commands_list)

            # If Nabla didn't generate ROS/PE but the template has them,
            # inject the template sections as commands (all unchanged).
            if template_ros and not has_ros:
                ros_display = " | ".join(s["title"] for s in template_ros)
                ros_secs: list[dict[str, Any]] = [
                    {
                        "key": s["key"],
                        "title": s["title"],
                        "text": s["text"],
                        "updated": False,
                        "template_text": s["text"],
                    }
                    for s in template_ros
                ]
                commands_list.append(
                    {
                        "command_type": "ros",
                        "display": ros_display,
                        "data": {"sections": ros_secs},
                        "selected": True,
                        "section_key": "_ros",
                        "already_documented": False,
                    }
                )
            if template_pe and not has_pe:
                pe_display = " | ".join(s["title"] for s in template_pe)
                pe_secs: list[dict[str, Any]] = [
                    {
                        "key": s["key"],
                        "title": s["title"],
                        "text": s["text"],
                        "updated": False,
                        "template_text": s["text"],
                    }
                    for s in template_pe
                ]
                commands_list.append(
                    {
                        "command_type": "physical_exam",
                        "display": pe_display,
                        "data": {"sections": pe_secs},
                        "selected": True,
                        "section_key": "physical_exam",
                        "already_documented": False,
                    }
                )

            # Reconcile when both template and Nabla versions exist.
            if reconciliation_api_key:
                for cmd in commands_list:
                    if cmd["command_type"] == "ros" and template_ros and has_ros:
                        reconciled = reconcile_sections(
                            template_ros,
                            cmd["data"].get("sections", []),
                            reconciliation_api_key,
                            "Review of Systems",
                        )
                        if reconciled:
                            cmd["data"]["sections"] = reconciled
                            cmd["display"] = " | ".join(s["title"] for s in reconciled)
                    elif cmd["command_type"] == "physical_exam" and template_pe and has_pe:
                        reconciled = reconcile_sections(
                            template_pe,
                            cmd["data"].get("sections", []),
                            reconciliation_api_key,
                            "Physical Exam",
                        )
                        if reconciled:
                            cmd["data"]["sections"] = reconciled
                            cmd["display"] = " | ".join(s["title"] for s in reconciled)

        # ── Step 3: Recommend commands ──
        _save_progress(note_id, 3, total, SUMMARY_STEPS[3])
        recommendations_list: list[dict[str, Any]] = []
        api_key = self.secrets.get("AnthropicAPIKey", "")
        if api_key:
            try:
                from hyperscribe.scribe.contacts import resolve_zip_codes

                patient_id = str(data.get("patient_id", ""))
                zip_codes = resolve_zip_codes(patient_id, note_id) or None
                rec_proposals = recommend_commands(note, api_key, zip_codes=zip_codes, transcript=transcript)
                annotate_duplicates(rec_proposals, note_uuid)
                recommendations_list = [
                    {
                        "command_type": p.command_type,
                        "display": p.display,
                        "data": p.data,
                        "selected": p.selected,
                        "section_key": p.section_key,
                        "already_documented": p.already_documented,
                    }
                    for p in rec_proposals
                ]
            except Exception:
                log.exception("recommend_commands failed (non-critical)")

        # ── Step 3b: Check medication interactions ──
        interaction_warnings: list[dict[str, Any]] = []
        if recommendations_list:
            try:
                interaction_warnings = check_recommendation_interactions(recommendations_list, note_uuid)
            except Exception:
                log.exception("interaction check failed (non-critical)")

        # ── Step 4: Suggest diagnoses for unmatched blocks ──
        _save_progress(note_id, 4, total, SUMMARY_STEPS[4])
        diagnosis_suggestions: dict[str, Any] = {}
        unmatched_headers = [
            c["data"].get("condition_header", "")
            for c in commands_list
            if c.get("command_type") == "diagnose" and not c.get("data", {}).get("icd10_code")
        ]
        unmatched_headers = [h for h in unmatched_headers if h]
        if unmatched_headers and api_key:
            try:
                diagnosis_suggestions = suggest_diagnoses(unmatched_headers, api_key)
            except Exception:
                log.exception("suggest_diagnoses failed (non-critical)")

        # ── Save to database ──
        summary_payload: dict[str, Any] = {
            "note": note_dict,
            "commands": commands_list,
            "approved": False,
            "recommendations": recommendations_list,
            "unmatched_conditions": unmatched_conditions,
            "diagnosis_suggestions": diagnosis_suggestions,
            "interaction_warnings": interaction_warnings,
        }
        if raw_response is not None:
            summary_payload["raw_response"] = raw_response
        _save_summary(note_id, summary_payload)

        return [
            JSONResponse(
                {
                    "note": note_dict,
                    "commands": commands_list,
                    "recommendations": recommendations_list,
                    "section_conditions": section_conditions,
                    "unmatched_conditions": unmatched_conditions,
                    "diagnosis_suggestions": diagnosis_suggestions,
                    "interaction_warnings": interaction_warnings,
                },
                status_code=HTTPStatus.OK,
            )
        ]

    @api.post("/generate-note")
    def post_generate_note(self) -> list[Union[Response, Effect]]:
        try:
            backend = get_backend_from_secrets(self.secrets)
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.BAD_REQUEST)]
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]

        transcript_data = data.get("transcript", {})
        transcript_items = transcript_data.get("items", [])

        # If no transcript items in body, load from database using note_id.
        note_id = str(data.get("note_id", ""))
        loaded_data: dict[str, Any] | None = None
        if not transcript_items and note_id:
            loaded_data = _load_transcript(note_id)
            if loaded_data and loaded_data["items"]:
                transcript_items = loaded_data["items"]
                transcript_data = {"items": transcript_items}

        if not transcript_items:
            return [JSONResponse({"error": "No transcript available"}, status_code=HTTPStatus.BAD_REQUEST)]

        # Only allow generation from finalized transcripts.
        is_finalized = (loaded_data or {}).get("finalized", False) if not data.get("transcript") else True
        if not is_finalized:
            return [
                JSONResponse(
                    {"error": "Transcript is still in progress. Finish recording before generating a summary."},
                    status_code=HTTPStatus.BAD_REQUEST,
                )
            ]

        transcript = _parse_transcript(transcript_data)
        patient_context = _parse_patient_context(data)
        try:
            note = backend.generate_note(transcript, patient_context=patient_context)
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
        return [
            JSONResponse(
                {
                    "title": note.title,
                    "sections": [{"key": s.key, "title": s.title, "text": s.text} for s in note.sections],
                },
                status_code=HTTPStatus.OK,
            )
        ]

    @api.post("/generate-normalized-data")
    def post_generate_normalized_data(self) -> list[Union[Response, Effect]]:
        try:
            backend = get_backend_from_secrets(self.secrets)
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.BAD_REQUEST)]
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]
        note = _parse_note(data.get("note", {}))
        try:
            result = backend.generate_normalized_data(note)
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
        return [
            JSONResponse(
                {
                    "conditions": [_serialize_condition(c) for c in result.conditions],
                    "observations": [
                        {
                            "display": o.display,
                            "value": o.value,
                            "unit": o.unit,
                            "coding": [{"system": e.system, "code": e.code, "display": e.display} for e in o.coding],
                        }
                        for o in result.observations
                    ],
                    "section_conditions": _match_conditions_to_sections(note, result.conditions),
                },
                status_code=HTTPStatus.OK,
            )
        ]

    @api.post("/extract-commands")
    def post_extract_commands(self) -> list[Union[Response, Effect]]:
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]
        note = _parse_note(data.get("note", {}))
        proposals = extract_commands(note)
        note_uuid = str(data.get("note_uuid", ""))
        annotate_duplicates(proposals, note_uuid)
        return [
            JSONResponse(
                {
                    "commands": [
                        {
                            "command_type": p.command_type,
                            "display": p.display,
                            "data": p.data,
                            "selected": p.selected,
                            "section_key": p.section_key,
                            "already_documented": p.already_documented,
                        }
                        for p in proposals
                    ],
                },
                status_code=HTTPStatus.OK,
            )
        ]

    @api.post("/recommend-commands")
    def post_recommend_commands(self) -> list[Union[Response, Effect]]:
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]
        api_key = self.secrets.get("AnthropicAPIKey", "")
        if not api_key:
            return [
                JSONResponse(
                    {"error": "AnthropicAPIKey secret is not configured"},
                    status_code=HTTPStatus.BAD_REQUEST,
                )
            ]
        note = _parse_note(data.get("note", {}))
        from hyperscribe.scribe.contacts import resolve_zip_codes

        patient_id = str(data.get("patient_id", ""))
        rec_note_id = str(data.get("note_id", ""))
        zip_codes = resolve_zip_codes(patient_id, rec_note_id) or None
        try:
            proposals = recommend_commands(note, api_key, zip_codes=zip_codes)
        except Exception:
            log.exception("recommend_commands failed")
            return [
                JSONResponse(
                    {"error": "Recommendation generation failed"},
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            ]
        note_uuid = str(data.get("note_uuid", ""))
        annotate_duplicates(proposals, note_uuid)
        return [
            JSONResponse(
                {
                    "commands": [
                        {
                            "command_type": p.command_type,
                            "display": p.display,
                            "data": p.data,
                            "selected": p.selected,
                            "section_key": p.section_key,
                            "already_documented": p.already_documented,
                        }
                        for p in proposals
                    ],
                },
                status_code=HTTPStatus.OK,
            )
        ]

    @api.post("/suggest-diagnoses")
    def post_suggest_diagnoses(self) -> list[Union[Response, Effect]]:
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]
        conditions = data.get("conditions", [])
        if not conditions or not isinstance(conditions, list):
            return [JSONResponse({"suggestions": {}}, status_code=HTTPStatus.OK)]
        api_key = self.secrets.get("AnthropicAPIKey", "")
        if not api_key:
            return [
                JSONResponse(
                    {"error": "AnthropicAPIKey secret is not configured"},
                    status_code=HTTPStatus.BAD_REQUEST,
                )
            ]
        try:
            suggestions = suggest_diagnoses(conditions, api_key)
        except Exception:
            log.exception("suggest_diagnoses failed")
            return [
                JSONResponse(
                    {"error": "Diagnosis suggestion failed"},
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            ]
        return [JSONResponse({"suggestions": suggestions}, status_code=HTTPStatus.OK)]

    @api.get("/check-interactions")
    def get_check_interactions(self) -> list[Union[Response, Effect]]:
        """Check a single medication for drug-drug and drug-allergy interactions."""
        fdb_code = self.request.query_params.get("fdb_code", "").strip() or None
        medication_name = self.request.query_params.get("medication_name", "").strip()
        note_id = self.request.query_params.get("note_id", "").strip()
        if not note_id:
            return [JSONResponse({"error": "note_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        if not fdb_code and not medication_name:
            return [
                JSONResponse(
                    {"drug_interactions": [], "allergy_interactions": [], "medication_display": ""},
                    status_code=HTTPStatus.OK,
                )
            ]
        try:
            result = check_single_medication_interactions(fdb_code, medication_name, note_id)
        except Exception:
            log.exception("check_single_medication_interactions failed")
            return [
                JSONResponse(
                    {"drug_interactions": [], "allergy_interactions": [], "medication_display": medication_name},
                    status_code=HTTPStatus.OK,
                )
            ]
        return [JSONResponse(result, status_code=HTTPStatus.OK)]

    @api.post("/insert-commands")
    def post_insert_commands(self) -> list[Union[Response, Effect]]:
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]
        note_uuid = str(data.get("note_uuid", ""))
        if not note_uuid:
            return [JSONResponse({"error": "note_uuid is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        if denial := _authorize_edit(note_uuid, self.request):
            return [denial]
        commands = data.get("commands", [])
        validation_errors = validate_proposals(commands)
        if validation_errors:
            audit_event(note_uuid, "VALIDATION_FAILED", {"errors": validation_errors})
            return [
                JSONResponse(
                    {"error": "Validation failed", "validation_errors": validation_errors},
                    status_code=HTTPStatus.BAD_REQUEST,
                )
            ]
        feature_flags = {
            Constants.SECRET_ALERT_FACILITY_ENABLED: bool(self.secrets.get(Constants.SECRET_ALERT_FACILITY_ENABLED)),
        }
        effects, metadata_pending, attempted = build_effects(commands, note_uuid, feature_flags)
        audit_event(
            note_uuid,
            "INSERT_COMMANDS",
            {
                "command_count": len(commands),
                "effect_count": len(effects),
                "commands": [
                    {
                        "type": c.get("command_type", ""),
                        "display": (c.get("display") or "")[:80],
                        "section_key": c.get("section_key", ""),
                    }
                    for c in commands
                ],
                "metadata_pending_count": len(metadata_pending),
                "alert_facility_enabled": feature_flags[Constants.SECRET_ALERT_FACILITY_ENABLED],
                "metadata_pending_keys": [
                    {
                        "command_type": p.get("command_type", ""),
                        "keys": list((p.get("metadata") or {}).keys()),
                    }
                    for p in metadata_pending
                ],
            },
        )
        return [
            JSONResponse(
                {
                    "inserted": len(effects),
                    "metadata_pending": metadata_pending,
                    "attempted": attempted,
                },
                status_code=HTTPStatus.OK,
            ),
            *effects,
        ]

    @api.post("/insert-metadata")
    def post_insert_metadata(self) -> list[Union[Response, Effect]]:
        """Phase 2: upsert command metadata after commands have been created."""
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]
        note_uuid = str(data.get("note_uuid", ""))
        if not note_uuid:
            return [JSONResponse({"error": "note_uuid is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        if denial := _authorize_edit(note_uuid, self.request):
            audit_event(note_uuid, "INSERT_METADATA_DENIED", {})
            return [denial]
        pending = data.get("pending", [])
        if not pending:
            return [JSONResponse({"ok": True}, status_code=HTTPStatus.OK)]

        audit_event(
            note_uuid,
            "INSERT_METADATA_REQUEST",
            {
                "pending_count": len(pending),
                "items": [
                    {
                        "command_uuid": str(p.get("command_uuid", "")),
                        "command_type": p.get("command_type", ""),
                        "metadata_keys": list((p.get("metadata") or {}).keys()),
                    }
                    for p in pending
                ],
            },
        )
        effects = build_metadata_effects(pending)
        audit_event(
            note_uuid,
            "INSERT_METADATA_RESULT",
            {"requested": len(pending), "effects_built": len(effects)},
        )
        return [JSONResponse({"ok": True, "metadata_count": len(effects)}, status_code=HTTPStatus.OK), *effects]

    @api.post("/verify-commands")
    def post_verify_commands(self) -> list[Union[Response, Effect]]:
        """Verify that attempted commands exist on the note with anchor objects."""
        from canvas_sdk.v1.data.command import Command

        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]
        note_uuid = str(data.get("note_uuid", ""))
        attempted: list[dict[str, Any]] = data.get("attempted", [])
        if not note_uuid or not attempted:
            return [JSONResponse({"verified": [], "failed": []}, status_code=HTTPStatus.OK)]
        # Note-author authorization. Uses the read-only variant
        # (`_authorize_read_as_author`) — NOT `_authorize_edit` — because
        # /verify-commands is a read-only endpoint and must stay reachable
        # for the legitimate author after the note transitions to LKD/SGN.
        # The auto-verify-on-load effect calls this on every reload of an
        # approved note; gating on editability would 403 every legit
        # post-sign reload, render a misleading "All 0 commands inserted"
        # banner (because fetch resolves on 4xx and `data.failed` is
        # missing), and pollute the probe-defense audit signal with rows
        # from real authors. Audit-log the denial for parity with
        # /insert-metadata so probe attempts still have a trail.
        if denial := _authorize_read_as_author(note_uuid, self.request):
            audit_event(note_uuid, "VERIFY_COMMANDS_DENIED", {})
            return [denial]

        # Skip malformed entries (missing or falsy command_uuid) so a bad
        # client payload doesn't 500 the request.
        uuids = [a["command_uuid"] for a in attempted if a.get("command_uuid")]
        cmd_rows = {
            str(row["id"]): row
            for row in Command.objects.filter(
                id__in=uuids,
                note__id=note_uuid,
            ).values("id", "anchor_object_type", "anchor_object_dbid")
        }
        verified: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for a in attempted:
            uuid = a.get("command_uuid")
            row = cmd_rows.get(uuid) if uuid else None
            if row and row["anchor_object_dbid"]:
                verified.append(a)
            else:
                reason = "no_anchor" if row else "not_found"
                failed.append({**a, "reason": reason})

        audit_event(
            note_uuid,
            "COMMANDS_VERIFIED",
            {
                "total": len(verified) + len(failed),
                "verified": [
                    {"type": v.get("command_type", ""), "display": (v.get("display") or "")[:80]} for v in verified
                ],
                "failed": [
                    {
                        "type": f.get("command_type", ""),
                        "display": (f.get("display") or "")[:80],
                        "reason": f.get("reason", ""),
                    }
                    for f in failed
                ],
            },
        )
        return [JSONResponse({"verified": verified, "failed": failed}, status_code=HTTPStatus.OK)]

    @api.post("/sign-note")
    def post_sign_note(self) -> list[Union[Response, Effect]]:
        """Sign the note after all commands have been inserted (no prescriptions)."""
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]
        note_uuid = str(data.get("note_uuid", ""))
        if not note_uuid:
            return [JSONResponse({"error": "note_uuid is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        if denial := _authorize_edit(note_uuid, self.request):
            return [denial]
        audit_event(note_uuid, "SIGN_NOTE", {})
        note_effect = NoteEffect(instance_id=note_uuid)
        return [JSONResponse({"ok": True}, status_code=HTTPStatus.OK), note_effect.lock(), note_effect.sign()]

    @api.get("/search-medications")
    def get_search_medications(self) -> list[Union[Response, Effect]]:
        query = self.request.query_params.get("query", "").strip()
        if not query:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        results = CanvasScience.medication_details([query])
        serialized = [
            {
                "fdb_code": r.fdb_code,
                "description": r.description,
                "quantities": [
                    {
                        "quantity": q.quantity,
                        "representative_ndc": q.representative_ndc,
                        "clinical_quantity_description": q.clinical_quantity_description,
                        "ncpdp_quantity_qualifier_code": q.ncpdp_quantity_qualifier_code,
                        "ncpdp_quantity_qualifier_description": q.ncpdp_quantity_qualifier_description,
                    }
                    for q in r.quantities
                ],
            }
            for r in results
        ]
        return [JSONResponse({"results": serialized}, status_code=HTTPStatus.OK)]

    @api.get("/search-allergies")
    def get_search_allergies(self) -> list[Union[Response, Effect]]:
        query = self.request.query_params.get("query", "").strip()
        if not query:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        results = CanvasScience.search_allergy(
            [query],
            [AllergenType.ALLERGEN_GROUP, AllergenType.MEDICATION, AllergenType.INGREDIENT],
        )
        return [
            JSONResponse(
                {
                    "results": [
                        {
                            "concept_id": r.concept_id_value,
                            "description": r.concept_id_description,
                            "concept_id_type": r.concept_id_type,
                        }
                        for r in results
                    ],
                },
                status_code=HTTPStatus.OK,
            )
        ]

    @api.get("/lab-partners")
    def get_lab_partners(self) -> list[Union[Response, Effect]]:
        """Return active lab partners."""
        partners = [
            {"id": str(p["id"]), "name": p["name"]}
            for p in LabPartner.objects.filter(active=True).order_by("name").values("id", "name")
        ]
        return [JSONResponse({"lab_partners": partners}, status_code=HTTPStatus.OK)]

    @api.get("/lab-partner-tests")
    def get_lab_partner_tests(self) -> list[Union[Response, Effect]]:
        """Return tests for a lab partner, optionally filtered by search query."""
        partner_id = self.request.query_params.get("partner_id", "").strip()
        if not partner_id:
            return [JSONResponse({"error": "partner_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        query = self.request.query_params.get("query", "").strip()
        qs = LabPartnerTest.objects.filter(lab_partner__id=partner_id).order_by("order_name")
        if query:
            qs = qs.filter(order_name__icontains=query)
        tests = [
            {"order_code": t["order_code"], "order_name": t["order_name"]}
            for t in qs.values("order_code", "order_name")[:50]
        ]
        return [JSONResponse({"tests": tests}, status_code=HTTPStatus.OK)]

    @api.get("/assignees")
    def get_assignees(self) -> list[Union[Response, Effect]]:
        """Return a merged list of active staff members and teams for task assignment."""
        return [JSONResponse({"assignees": _load_assignees()}, status_code=HTTPStatus.OK)]

    @api.get("/task-labels")
    def get_task_labels(self) -> list[Union[Response, Effect]]:
        """Return active task labels."""
        labels = [
            {"name": tl["name"], "color": tl["color"]}
            for tl in TaskLabel.objects.filter(
                Q(modules__contains=["tasks"]) | Q(modules=[]) | Q(modules__isnull=True),
                active=True,
            )
            .order_by("position")
            .values("name", "color")
        ]
        return [JSONResponse({"labels": labels}, status_code=HTTPStatus.OK)]

    @api.get("/patient-conditions")
    def get_patient_conditions(self) -> list[Union[Response, Effect]]:
        """Return committed, non-entered-in-error conditions for a patient."""
        patient_id = self.request.query_params.get("patient_id", "").strip()
        if not patient_id:
            return [JSONResponse({"error": "patient_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        conditions = (
            ConditionModel.objects.active().for_patient(patient_id).prefetch_related("codings").order_by("-onset_date")
        )
        results = []
        for c in conditions:
            codings = list(c.codings.all())
            if not codings:
                continue
            icd10 = next(
                (coding for coding in codings if "icd" in (coding.system or "").lower()),
                None,
            )
            chosen = icd10 or codings[0]
            results.append(
                {
                    "condition_id": str(c.id),
                    "code": chosen.code,
                    "formatted_code": _format_icd10_code(chosen.code),
                    "display": chosen.display or c.clinical_status,
                    "system": chosen.system,
                }
            )
        return [JSONResponse({"conditions": results}, status_code=HTTPStatus.OK)]

    @api.get("/patient-medications")
    def get_patient_medications(self) -> list[Union[Response, Effect]]:
        """Return active medications for a patient."""
        patient_id = self.request.query_params.get("patient_id", "").strip()
        if not patient_id:
            return [JSONResponse({"error": "patient_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        medications = Medication.objects.filter(
            patient__id=patient_id, status=Status.ACTIVE, committer__isnull=False
        ).prefetch_related("codings")
        results = []
        for m in medications:
            coding = m.codings.first()
            if not coding:
                continue
            results.append({"id": str(m.id), "name": coding.display})
        return [JSONResponse({"medications": results}, status_code=HTTPStatus.OK)]

    @api.get("/patient-allergies")
    def get_patient_allergies(self) -> list[Union[Response, Effect]]:
        """Return active allergies for a patient."""
        patient_id = self.request.query_params.get("patient_id", "").strip()
        if not patient_id:
            return [JSONResponse({"error": "patient_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        allergies = AllergyIntolerance.objects.filter(
            patient__id=patient_id, status=Status.ACTIVE, committer__isnull=False
        ).prefetch_related("codings")
        results = []
        for a in allergies:
            coding = a.codings.first()
            if not coding:
                continue
            results.append({"id": str(a.id), "name": coding.display})
        return [JSONResponse({"allergies": results}, status_code=HTTPStatus.OK)]

    @api.get("/patient-medications-for-refill")
    def get_patient_medications_for_refill(self) -> list[Union[Response, Effect]]:
        """Return active medications with their latest prescription data for refill."""
        patient_id = self.request.query_params.get("patient_id", "").strip()
        if not patient_id:
            return [JSONResponse({"error": "patient_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        medications = Medication.objects.filter(
            patient__id=patient_id, status=Status.ACTIVE, committer__isnull=False
        ).prefetch_related("codings")
        results: list[dict[str, Any]] = []
        for m in medications:
            fdb_coding = next(
                (c for c in m.codings.all() if "fdb" in (c.system or "").lower()),
                None,
            )
            if not fdb_coding:
                continue
            rx = (
                Prescription.objects.filter(medication__id=str(m.id), committer__isnull=False)
                .order_by("-written_date")
                .first()
            )
            results.append(
                {
                    "medication_name": fdb_coding.display,
                    "fdb_code": fdb_coding.code,
                    "national_drug_code": m.national_drug_code,
                    "potency_unit_code": m.potency_unit_code,
                    "sig": rx.sig_original_input if rx else "",
                    "quantity_to_dispense": rx.dispense_quantity if rx else None,
                    "days_supply": rx.duration_in_days if rx else None,
                    "refills": rx.count_of_refills_allowed if rx else None,
                    "substitutions": "allowed" if (rx and rx.generic_substitutions_allowed) else "not_allowed",
                    "note_to_pharmacist": rx.note_to_pharmacist if rx else "",
                }
            )
        return [JSONResponse({"medications": results}, status_code=HTTPStatus.OK)]

    @api.get("/search-diagnoses")
    def get_search_diagnoses(self) -> list[Union[Response, Effect]]:
        """Search ICD-10 diagnosis codes via the science service."""
        query = self.request.query_params.get("query", "").strip()
        if not query:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        try:
            resp = science_http.get_json(f"/search/condition/?query={query}&limit=25")
            data = resp.json() or {}
        except Exception:
            log.exception("Diagnosis search failed")
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        sorted_results = sorted(data.get("results", []), key=lambda r: r.get("score", 0), reverse=True)
        results = [
            {
                "code": r["icd10_code"],
                "display": r.get("icd10_text", ""),
                "formatted_code": _format_icd10_code(r["icd10_code"]),
            }
            for r in sorted_results
            if r.get("icd10_code")
        ]
        return [JSONResponse({"results": results}, status_code=HTTPStatus.OK)]

    @api.get("/search-charges")
    def get_search_charges(self) -> list[Union[Response, Effect]]:
        """Search CPT codes by code or description."""
        query = self.request.query_params.get("query", "").strip()
        if not query:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]

        exclude_raw = self.request.query_params.get("exclude", "")
        exclude_codes = [c.strip() for c in exclude_raw.split(",") if c.strip()] if exclude_raw else []

        qs = ChargeDescriptionMaster.objects.filter(Q(cpt_code__icontains=query) | Q(short_name__icontains=query))
        if exclude_codes:
            qs = qs.exclude(cpt_code__in=exclude_codes)
        qs = qs.order_by("cpt_code")[:20]
        results = [{"cpt_code": r.cpt_code, "short_name": r.short_name, "full_name": r.name} for r in qs]
        return [JSONResponse({"results": results}, status_code=HTTPStatus.OK)]

    @api.get("/search-family-history")
    def get_search_family_history(self) -> list[Union[Response, Effect]]:
        """Search family history conditions (SNOMED) via the science service."""
        query = self.request.query_params.get("query", "").strip()
        if not query:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        try:
            resp = science_http.get_json(f"/search/family-history/?query={query}&limit=25")
            data = resp.json() or {}
        except Exception:
            log.exception("Family history search failed")
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        results = [
            {
                "code": str(r.get("concept_id", "")),
                "display": r.get("term", ""),
                "system": "http://snomed.info/sct",
            }
            for r in data.get("results", [])
            if r.get("concept_id") or r.get("term")
        ]
        return [JSONResponse({"results": results}, status_code=HTTPStatus.OK)]

    @api.get("/search-family-relation")
    def get_search_family_relation(self) -> list[Union[Response, Effect]]:
        """Search family relation types (SNOMED CT) via the science service."""
        query = self.request.query_params.get("query", "").strip()
        if not query:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        try:
            resp = science_http.get_json(f"/search/family-relation/?query={query}&limit=25")
            data = resp.json() or {}
        except Exception:
            log.exception("Family relation search failed")
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        results = [
            {
                "code": str(r.get("concept_id", "")),
                "display": r.get("term", ""),
                "system": "http://snomed.info/sct",
            }
            for r in data.get("results", [])
            if r.get("concept_id") or r.get("term")
        ]
        return [JSONResponse({"results": results}, status_code=HTTPStatus.OK)]

    @api.get("/search-medical-history")
    def get_search_medical_history(self) -> list[Union[Response, Effect]]:
        """Search medical history conditions (ICD-10) via the science service."""
        query = self.request.query_params.get("query", "").strip()
        if not query:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        try:
            resp = science_http.get_json(f"/search/medical-history-condition/?query={query}&limit=100")
            data = resp.json() or {}
        except Exception:
            log.exception("Medical history search failed")
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        results = [
            {
                "code": r.get("icd10_code", ""),
                "display": r.get("icd10_text", ""),
                "system": "http://hl7.org/fhir/sid/icd-10-cm",
            }
            for r in data.get("results", [])
            if r.get("icd10_code") or r.get("icd10_text")
        ]
        return [JSONResponse({"results": results}, status_code=HTTPStatus.OK)]

    @api.get("/search-surgical-history")
    def get_search_surgical_history(self) -> list[Union[Response, Effect]]:
        """Search surgical history procedures (SNOMED) via the science service."""
        query = self.request.query_params.get("query", "").strip()
        if not query:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        try:
            resp = science_http.get_json(f"/search/surgical-history-procedure/?query={query}&limit=100")
            data = resp.json() or {}
        except Exception:
            log.exception("Surgical history search failed")
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        results = [
            {
                "code": str(r.get("concept_id", "")),
                "display": r.get("term", ""),
                "system": "http://snomed.info/sct",
            }
            for r in data.get("results", [])
            if r.get("concept_id") or r.get("term")
        ]
        return [JSONResponse({"results": results}, status_code=HTTPStatus.OK)]

    @api.get("/search-imaging")
    def get_search_imaging(self) -> list[Union[Response, Effect]]:
        """Search imaging codes via the science service."""
        query = self.request.query_params.get("query", "").strip()
        if not query:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        try:
            resp = science_http.get_json(f"/parse-templates/imaging-reports/?query={query}&limit=25")
            data = resp.json() or {}
        except Exception:
            log.exception("Imaging search failed")
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        results = []
        for r in data.get("results", []):
            name = r.get("name")
            if not name:
                continue
            code_system = r.get("code_system")
            code = r.get("code")
            display = f"{name} ({code_system}: {code})" if code_system or code else name
            results.append({"value": code or name, "display": display})
        return [JSONResponse({"results": results}, status_code=HTTPStatus.OK)]

    @api.get("/ordering-providers")
    def get_ordering_providers(self) -> list[Union[Response, Effect]]:
        """Return active staff who are prescribers, optionally filtered by search term."""
        query = self.request.query_params.get("query", "").strip()
        qs = (
            Staff.objects.filter(
                active=True,
                roles__role_type=StaffRole.RoleType.PROVIDER,
                roles__domain__in=StaffRole.RoleDomain.clinical_domains(),
            )
            .distinct()
            .order_by("last_name", "first_name")
        )
        if query:
            qs = qs.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query))
        providers = [{"id": str(s.id), "label": s.credentialed_name} for s in qs[:50]]
        return [JSONResponse({"providers": providers}, status_code=HTTPStatus.OK)]

    @api.get("/search-imaging-centers")
    def get_search_imaging_centers(self) -> list[Union[Response, Effect]]:
        """Search for radiology imaging centers via the science service."""
        from hyperscribe.scribe.contacts import resolve_zip_codes

        query = self.request.query_params.get("query", "").strip()
        if not query:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]

        patient_id = self.request.query_params.get("patient_id", "").strip()
        note_id = self.request.query_params.get("note_id", "").strip()
        zip_codes = resolve_zip_codes(patient_id, note_id)

        base_params = f"?search={query}&job_title__icontains=radiology"
        try:
            # Try zip-filtered first for local results, fall back to unfiltered.
            raw_results: list[dict] = []
            if zip_codes:
                params = base_params + f"&business_postal_code__in={','.join(zip_codes)}"
                resp = science_http.get_json(f"/contacts/{params}")
                raw_results = (resp.json() or {}).get("results", [])
            if not raw_results:
                resp = science_http.get_json(f"/contacts/{base_params}")
                raw_results = (resp.json() or {}).get("results", [])
        except Exception:
            log.exception("Imaging center search failed")
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        results = []
        for c in raw_results:
            first = c.get("firstName", "")
            last = c.get("lastName", "")
            practice = c.get("practiceName", "")
            specialty = c.get("specialty", "")
            # Build display name matching Canvas convention.
            parts = []
            if first:
                parts.append(first)
            if last and last != first:
                parts.append(last)
            if practice and practice != first:
                parts.append(f"({practice}),")
            if specialty and specialty not in (first, last, practice):
                parts.append(specialty)
            name = " ".join(parts).strip()
            # Build description with contact details.
            desc_parts = []
            phone = c.get("businessPhone")
            fax = c.get("businessFax")
            address = c.get("businessAddress")
            if phone:
                desc_parts.append(f"Phone: {phone}")
            if fax:
                desc_parts.append(f"Fax: {fax}")
            if address:
                desc_parts.append(f"Address: {address}")
            results.append(
                {
                    "name": name,
                    "description": " ".join(desc_parts),
                    "data": {
                        "first_name": first,
                        "last_name": last,
                        "specialty": specialty,
                        "practice_name": practice,
                        "business_fax": fax,
                        "business_phone": phone,
                        "business_address": address,
                    },
                }
            )
        return [JSONResponse({"results": results}, status_code=HTTPStatus.OK)]

    @api.get("/search-refer-providers")
    def get_search_refer_providers(self) -> list[Union[Response, Effect]]:
        """Search for providers to refer to via the science service."""
        from hyperscribe.scribe.contacts import resolve_zip_codes, search_refer_providers

        query = self.request.query_params.get("query", "").strip()
        if not query:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]

        patient_id = self.request.query_params.get("patient_id", "").strip()
        note_id = self.request.query_params.get("note_id", "").strip()
        zip_codes = resolve_zip_codes(patient_id, note_id)

        results = search_refer_providers(query, zip_codes or None)
        return [JSONResponse({"results": results}, status_code=HTTPStatus.OK)]

    @api.get("/search-questionnaires")
    def get_search_questionnaires(self) -> list[Union[Response, Effect]]:
        """Search active questionnaires by name or search tags."""
        query = self.request.query_params.get("query", "").strip()
        qs = QuestionnaireModel.objects.filter(status="AC", use_case_in_charting="QUES")
        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(search_tags__icontains=query))
        questionnaires = qs.order_by("name")[:25]
        results = [{"dbid": q.dbid, "name": q.name} for q in questionnaires]
        return [JSONResponse({"results": results}, status_code=HTTPStatus.OK)]

    @api.get("/search-pharmacies")
    def get_search_pharmacies(self) -> list[Union[Response, Effect]]:
        """Search pharmacies. Returns patient preferred pharmacies when no query is provided."""
        query = self.request.query_params.get("query", "").strip()
        patient_id = self.request.query_params.get("patient_id", "").strip()

        def _format_pharmacy(details: dict) -> dict:
            name = details.get("organization_name") or ""
            address = details.get("address_line_1") or ""
            city = details.get("city") or ""
            state = details.get("state") or ""
            address_parts = [p for p in [address, city, state] if p]
            return {
                "ncpdp_id": details.get("ncpdp_id") or "",
                "name": name,
                "address": ", ".join(address_parts) if address_parts else "",
            }

        if query:
            try:
                search_results = pharmacy_http.search_pharmacies(search_term=query)
                results = [_format_pharmacy(r) for r in search_results]
                results = [r for r in results if r["ncpdp_id"] and (r["name"] or r["address"])]
            except Exception:
                results = []
            return [JSONResponse({"results": results}, status_code=HTTPStatus.OK)]

        # No query — return the patient's preferred pharmacies.
        if not patient_id:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]

        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]

        preferred_pharmacy = patient.preferred_pharmacy
        results = []
        if preferred_pharmacy:
            ncpdp_id = preferred_pharmacy.get("pharmacy_ncpdp_id", "")
            if ncpdp_id:
                results.append(
                    {
                        "ncpdp_id": ncpdp_id,
                        "name": preferred_pharmacy.get("pharmacy_name", "") or ncpdp_id,
                        "address": preferred_pharmacy.get("pharmacy_address", ""),
                        "preferred": True,
                    }
                )

        return [JSONResponse({"results": results}, status_code=HTTPStatus.OK)]

    @api.get("/questionnaire-details")
    def get_questionnaire_details(self) -> list[Union[Response, Effect]]:
        """Load a questionnaire's full definition (questions + response options)."""
        dbid = self.request.query_params.get("dbid", "").strip()
        if not dbid:
            return [JSONResponse({"error": "dbid required"}, status_code=HTTPStatus.BAD_REQUEST)]
        try:
            questionnaire = QuestionnaireModel.objects.get(dbid=int(dbid))
        except (QuestionnaireModel.DoesNotExist, ValueError):
            return [JSONResponse({"error": "not found"}, status_code=HTTPStatus.NOT_FOUND)]

        cmd = QuestionnaireCommand(
            questionnaire_id=str(questionnaire.id),
            note_uuid="",
            command_uuid="",
        )
        questions = []
        for q in cmd.questions:
            options = [{"dbid": o.dbid, "value": o.name} for o in q.options]
            questions.append(
                {
                    "dbid": int(q.id),
                    "label": q.label,
                    "type": q.type,
                    "options": options,
                }
            )
        return [
            JSONResponse(
                {
                    "questionnaire_dbid": questionnaire.dbid,
                    "questionnaire_name": questionnaire.name,
                    "questions": questions,
                },
                status_code=HTTPStatus.OK,
            )
        ]

    @api.get("/visit-templates")
    def get_visit_templates(self) -> list[Union[Response, Effect]]:
        """Load visit templates with resolved questionnaire definitions."""
        return [JSONResponse({"templates": _load_templates(self.secrets)}, status_code=HTTPStatus.OK)]

    @api.post("/save-audit-log")
    def post_save_audit_log(self) -> list[Union[Response, Effect]]:
        """Append audit events to the per-note audit log."""
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError):
            return [JSONResponse({"error": "Invalid JSON"}, status_code=HTTPStatus.BAD_REQUEST)]
        note_id = data.get("note_id", "")
        new_events = data.get("events", [])
        if not note_id or not new_events:
            return [JSONResponse({"ok": True}, status_code=HTTPStatus.OK)]
        note_dbid = Note.objects.values_list("dbid", flat=True).get(id=note_id)
        obj, created = ScribeAuditLog.objects.get_or_create(note_id=note_dbid, defaults={"events": new_events})
        if not created:
            obj.events = list(obj.events) + new_events
            obj.save()
        broadcast = Broadcast(
            channel=f"scribe-{note_id}",
            message={"type": "AUDIT_EVENTS", "note_id": note_id, "events": new_events},
        )
        return [JSONResponse({"ok": True}, status_code=HTTPStatus.OK), broadcast.apply()]

    @api.get("/audit-log")
    def get_audit_log(self) -> list[Union[Response, Effect]]:
        """Return the audit event log for a note."""
        note_id = self.request.query_params.get("note_id", "")
        if not note_id:
            return [JSONResponse({"events": []}, status_code=HTTPStatus.OK)]
        note_dbid = Note.objects.values_list("dbid", flat=True).get(id=note_id)
        row = ScribeAuditLog.objects.filter(note_id=note_dbid).values("events").first()
        events = row["events"] if row else []
        return [JSONResponse({"events": events}, status_code=HTTPStatus.OK)]
