from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Union
from urllib.parse import urlencode

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
from canvas_sdk.v1.data.command import Command
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
    Observation,
    PatientContext,
    ScribeError,
    Transcript,
    TranscriptItem,
    get_backend_from_secrets,
)
from hyperscribe.scribe.commands.ap_split import split_plan_into_diagnoses
from hyperscribe.scribe.commands.builder import (
    DIRECT_EDIT_SECTIONS,
    EDITABLE_AMEND_SECTIONS,
    NON_EDITABLE_AMEND_COMMAND_TYPES,
    annotate_duplicates,
    build_amend_delete_effects,
    build_amend_edit_effects,
    build_effects,
    build_metadata_effects,
    prefill_assess_backgrounds,
    prefill_assess_backgrounds_for_proposals,
    validate_proposals,
)
from hyperscribe.scribe.commands.carry_forward import carry_forward_assess_background
from hyperscribe.scribe.commands.extractor import (
    extract_commands,
    extract_vitals_with_telemetry,
    parse_ros_subsections,
)
from hyperscribe.scribe.commands.prior_sections import get_prior_section_data
from hyperscribe.scribe.commands.problem_list_match import (
    ActivePatientCondition,
    prefer_patient_specific_codes,
)
from hyperscribe.scribe.recommendations import recommend_commands
from hyperscribe.scribe.recommendations.diagnosis_suggestion import suggest_diagnoses
from hyperscribe.scribe.recommendations.reconciliation import reconcile_sections
from hyperscribe.scribe.recommendations.interactions import (
    check_recommendation_interactions,
    check_single_medication_interactions,
)
from hyperscribe.scribe.contacts import (
    resolve_zip_codes,
    search_imaging_centers,
    search_refer_providers,
)


def _ensure_str(value: Any) -> str:
    """Convert None to empty string while preserving 0 / False as their stringified form. Used when
    serializing questionnaire scoring metadata where integer 0 carries clinical meaning ("Not at all")
    and must not be conflated with absent data via the falsy-coerce `or ""` idiom."""
    return "" if value is None else str(value)


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
    except Exception:
        # Catches django.core.exceptions.ValidationError raised when
        # note_uuid isn't a syntactically valid UUID — Django's UUIDField
        # to_python raises during query preparation. We can't import
        # ValidationError directly because the plugin-runner sandbox blocks
        # `django.core.exceptions`. ValidationError inherits straight from
        # Exception (not ValueError), so a narrower catch wouldn't work
        # either. Body of the try is a single ORM call, so the broad catch
        # can only mask UUID-coercion or transient DB errors, both of which
        # are appropriately routed to 404 from a defensive auth-helper.
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
    except Exception:
        # Catches django.core.exceptions.ValidationError on malformed UUID;
        # see _authorize_edit for the full sandbox-allowlist rationale.
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

# HIPAA defense-in-depth: explicit key whitelist for the AMEND_EXISTING_COMMANDS
# audit entries. The audit payload is built by ``{k: a[k] for k in whitelist if k in a}``
# rather than by destructuring ``attempted`` records by name in an inline dict
# literal. Mechanism: if a future change adds a new key to ``attempted`` records
# (e.g., ``display``, which was historically present and carries free-text
# clinical narrative for HPI / ROS / PE / lab_results / current_medications),
# it CANNOT silently propagate into the audit log - only the whitelisted
# structural identifiers can. Pinned by
# ``test_amend_audit_payload_does_not_propagate_new_attempted_keys``.
_AMEND_AUDIT_ENTRY_KEYS = (
    "section_key",
    "command_type",
    "old_command_uuid",
    "new_command_uuid",
    "command_uuid",  # KOALA-5485 delete: uses command_uuid (no new uuid minted).
    "mode",
)

# All commands synced from the note body land in this single section in the
# Scribe tab, regardless of schema_key. Each renders with the same locked,
# read-only card — no per-type routing into the existing SOAP groups.
FROM_THE_NOTE_SECTION = "from_the_note"

_CAMEL_BOUNDARY_RE = re.compile(r"([a-z0-9])([A-Z])")

# Canonical labels for schema_keys whose humanized form would look wrong
# (acronyms title-cased to 'Hpi', or Canvas keys that read better with
# preposition lowercasing). Everything not in this map falls through to
# _humanize_schema_key.
_LABEL_OVERRIDES: dict[str, str] = {
    "hpi": "HPI",
    "rfv": "RFV",
    "ros": "ROS",
    "reasonForVisit": "Reason for Visit",
    "historyOfPresentIllness": "History of Present Illness",
    "reviewOfSystems": "Review of Systems",
}


def _humanize_schema_key(schema_key: str) -> str:
    """Turn 'medicationStatement' / 'medication_statement' into 'Medication Statement'.

    Python's str.title alone produces 'Medicationstatement' for camelCase
    input because it treats the entire token as one word — we have to split
    on the camelCase boundary first.
    """
    override = _LABEL_OVERRIDES.get(schema_key)
    if override:
        return override
    spaced = _CAMEL_BOUNDARY_RE.sub(r"\1 \2", schema_key).replace("_", " ")
    return spaced.strip().title() or "Command"


def _extract_coded_display(value: Any) -> str:
    """Pull a display string out of canvas-core's coded-value shape.

    Most non-narrative commands (medication_statement, allergy, diagnose,
    prescribe, perform, etc.) store their primary value as a dict shaped like
    ``{value, text, extra: {coding: [{code, display, system}]}}`` — that's
    what `CommandAdapter.get_command_object_field_values` produces (see
    home-app's `builtin_content/core_types/adapters/*.py`). Pull the
    user-facing `text` first, then fall back to the first coding's display.
    """
    if not isinstance(value, dict):
        return ""
    text = (value.get("text") or "").strip() if isinstance(value.get("text"), str) else ""
    if text:
        return text
    extra = value.get("extra")
    if isinstance(extra, dict):
        coding = extra.get("coding")
        if isinstance(coding, list) and coding and isinstance(coding[0], dict):
            display = coding[0].get("display")
            if isinstance(display, str) and display.strip():
                return display.strip()
    return ""


def _humanize_field_name(name: str) -> str:
    """'blood_pressure_systole' / 'fdbCode' → 'Blood Pressure Systole' / 'Fdb Code'."""
    spaced = _CAMEL_BOUNDARY_RE.sub(r"\1 \2", name).replace("_", " ")
    return spaced.strip().title()


def _stringify_field(value: Any) -> str:
    """Best-effort conversion of a JSON value to a single-line renderable string.

    Booleans collapse to empty (they're almost always internal toggles like
    ``disabled`` or ``show_in_condition_list`` — not useful to surface).
    Dicts use the coded-value `text` when present, then a generic flatten of
    their entries. Lists join their stringified items with ' · '.
    """
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        coded = _extract_coded_display(value)
        if coded:
            return coded
        parts: list[str] = []
        for k, v in value.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            inner = _stringify_field(v)
            if inner:
                parts.append(f"{_humanize_field_name(str(k))}: {inner}")
        return ", ".join(parts)
    if isinstance(value, list):
        parts = [_stringify_field(v) for v in value]
        return " · ".join(p for p in parts if p)
    return ""


def _details_for_command(data: dict[str, Any]) -> list[dict[str, str]]:
    """Flatten Command.data into a list of ``{label, value}`` rows for the
    ADDITIONAL COMMANDS card. Empty values and internal keys are skipped so
    every row carries real information."""
    details: list[dict[str, str]] = []
    for key, value in data.items():
        if isinstance(key, str) and key.startswith("_"):
            continue
        text = _stringify_field(value)
        if text:
            details.append({"label": _humanize_field_name(str(key)), "value": text})
    return details


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


def _load_active_patient_conditions(patient_id: str) -> list[ActivePatientCondition]:
    """Return the patient's active problem-list entries, narrowed to the
    fields :func:`prefer_patient_specific_codes` needs.

    Used by :func:`post_generate_summary` (to hint Nabla codes toward the
    patient-specific code already on file) AND by :meth:`get_patient_conditions`
    (the endpoint the frontend's diagnose -> assess belt fetches against).
    Both call sites go through this helper so a problem-list selection
    change can never be visible to one and invisible to the other; without
    that constraint the rewrite hint and the frontend belt would drift and
    a patient's specific code would silently stop landing in their chart.

    PHI note: the returned ``ActivePatientCondition`` carries clinical data;
    callers must not log codes or display strings beyond aggregate counts.
    """
    if not patient_id:
        return []
    conditions = (
        ConditionModel.objects.active().for_patient(patient_id).prefetch_related("codings").order_by("-onset_date")
    )
    results: list[ActivePatientCondition] = []
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
            ActivePatientCondition(
                condition_id=str(c.id),
                code=chosen.code,
                display=chosen.display or c.clinical_status,
                system=chosen.system or "",
            )
        )
    return results


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
    }
    # One-way latch: was_finalized goes True the first time approved=True
    # is written and is never reset to False. Achieved by only putting it
    # in defaults when approved is True; update_or_create leaves the column
    # alone when the key isn't in defaults.
    if payload.get("approved"):
        defaults["was_finalized"] = True
    if "selected_template_name" in payload:
        defaults["selected_template_name"] = payload["selected_template_name"] or ""
    if "mode" in payload:
        defaults["mode"] = payload["mode"] or ""
    if "raw_response" in payload:
        defaults["raw_response"] = payload["raw_response"]
    ScribeSummary.objects.update_or_create(note_id=note_dbid, defaults=defaults)


def _infer_mode_for_heal(note_dbid: int, has_user_content: bool) -> str:
    """Pick the user's mode from session artifacts. '' means no signal — don't heal."""
    events = (ScribeAuditLog.objects.filter(note_id=note_dbid).values_list("events", flat=True).first()) or []
    last_start = ""
    for event in events:
        event_type = event.get("type") if isinstance(event, dict) else None
        if event_type == "START_AI":
            last_start = "ai"
        elif event_type == "START_MANUAL":
            last_start = "manual"
        elif event_type in ("START_AI_FAILED", "START_MANUAL_FAILED"):
            last_start = ""
    if last_start:
        return last_start
    if ScribeTranscript.objects.filter(note_id=note_dbid).values_list("items", flat=True).first():
        return "ai"
    return "manual" if has_user_content else ""


def _has_user_authored_content(row: dict[str, Any]) -> bool:
    """True iff the row has note content the user actually authored.

    Template-inserted commands (carrying ``_template_inserted: true``) are
    mechanical artifacts of a template selection, not evidence of manual
    authorship — they must not trip the "content without recording → manual"
    fallback in the heal.
    """
    if row["note_data"]:
        return True
    commands = row["commands"] or []
    return any(isinstance(cmd, dict) and not cmd.get("_template_inserted") for cmd in commands)


def _load_summary(note_id: str) -> dict[str, Any] | None:
    note_dbid = Note.objects.values_list("dbid", flat=True).get(id=note_id)
    row = (
        ScribeSummary.objects.filter(note_id=note_dbid)
        .values(
            "note_data",
            "commands",
            "approved",
            "was_finalized",
            "recommendations",
            "unmatched_conditions",
            "diagnosis_suggestions",
            "selected_template_name",
            "mode",
        )
        .first()
    )
    if not row:
        return None
    mode = row["mode"] or ""
    if not mode:
        inferred = _infer_mode_for_heal(note_dbid, _has_user_authored_content(row))
        if inferred:
            updated = ScribeSummary.objects.filter(note_id=note_dbid, mode="").update(mode=inferred)
            if updated:
                mode = inferred
    return {
        "note": row["note_data"] or None,
        "commands": row["commands"] or [],
        "approved": row["approved"],
        "was_finalized": row["was_finalized"],
        "recommendations": row["recommendations"] or [],
        "unmatched_conditions": row["unmatched_conditions"] or [],
        "diagnosis_suggestions": row["diagnosis_suggestions"] or {},
        "selected_template_name": row["selected_template_name"] or None,
        "mode": mode or None,
    }


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
            options = [
                {
                    "dbid": o.dbid,
                    "value": o.name,
                    "code": _ensure_str(getattr(o, "code", None)),
                    "score_value": _ensure_str(getattr(o, "value", None)),
                }
                for o in q.options
            ]
            questions.append({"dbid": int(q.id), "label": q.label, "type": q.type, "options": options})
        scoring_function_name = getattr(q_obj, "scoring_function_name", "") or ""
        return {
            "questionnaire_dbid": q_obj.dbid,
            "questionnaire_name": q_obj.name,
            "is_scored": bool(scoring_function_name),
            "scoring_function_name": scoring_function_name,
            "questions": questions,
        }

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
            return [
                JSONResponse(
                    {"note": None, "commands": [], "approved": False, "was_finalized": False}, status_code=HTTPStatus.OK
                )
            ]
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
        if "recommendations" in data:
            payload["recommendations"] = data["recommendations"]
        if "unmatched_conditions" in data:
            payload["unmatched_conditions"] = data["unmatched_conditions"]
        if "diagnosis_suggestions" in data:
            payload["diagnosis_suggestions"] = data["diagnosis_suggestions"]
        if "interaction_warnings" in data:
            payload["interaction_warnings"] = data["interaction_warnings"]
        if "selected_template_name" in data:
            payload["selected_template_name"] = data["selected_template_name"]
        if "mode" in data:
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
        normalized_observations: list[Observation] = []
        note_uuid = str(data.get("note_uuid", ""))
        try:
            normalized = backend.generate_normalized_data(note)
            # KOALA-5603: prefer the patient's specific active-problem-list code
            # when Nabla emitted an unspecified-parent (e.g. E11.9 -> E11.65).
            # The downstream frontend belt converts a diagnose to an assess
            # only on EXACT ICD-10 match, so the rewrite has to land before
            # _match_conditions_to_sections / split_plan_into_diagnoses run.
            patient_id_for_hint = str(data.get("patient_id", ""))
            active_conditions = _load_active_patient_conditions(patient_id_for_hint)
            normalized.conditions = prefer_patient_specific_codes(
                normalized.conditions,
                active_conditions,
            )
            section_conditions = _match_conditions_to_sections(note, normalized.conditions)
            normalized_observations = normalized.observations
        except Exception:
            log.exception("generate_normalized_data failed (non-critical)")
            # Surface the upstream failure to prod observability without leaking
            # PHI: payload carries only the step identifier so we can
            # distinguish "Nabla returned no observations" (silent path
            # divergence) from "Nabla call raised" (outage / rate limit /
            # credential issue).
            if note_uuid:
                audit_event(note_uuid, "NORMALIZED_DATA_FAILED", {"step": "normalized"})

        # ── Step 2: Extract commands + A&P split ──
        _save_progress(note_id, 2, total, SUMMARY_STEPS[2])
        # Emit vitals telemetry from a single extraction pass:
        #  * VITALS_SOURCE — which parser populated the proposal
        #    (observations / regex / both / none). Classifies off the FINAL
        #    surviving fields so a fully-refused observation panel doesn't
        #    inflate the observations side of the metric.
        #  * VITALS_FIELD_REFUSED — fields the parser dropped during
        #    validation (out_of_range / ambiguous_unit / atomic_bp_partial).
        #    Only emitted when refusals are non-empty: silent on the happy
        #    path so the audit log stays signal-dense.
        # No values, no PHI — just field names + reason categories.
        if note_uuid:
            vitals_telemetry = extract_vitals_with_telemetry(note, normalized_observations)
            audit_event(
                note_uuid,
                "VITALS_SOURCE",
                {"source": vitals_telemetry.source},
            )
            if vitals_telemetry.refusals:
                audit_event(
                    note_uuid,
                    "VITALS_FIELD_REFUSED",
                    {
                        "refused_fields": [r.field for r in vitals_telemetry.refusals],
                        "reasons": [r.reason for r in vitals_telemetry.refusals],
                    },
                )
        proposals = extract_commands(note, observations=normalized_observations)
        annotate_duplicates(proposals, note_uuid)
        prefill_assess_backgrounds_for_proposals(proposals, note_uuid)
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
                patient_id = str(data.get("patient_id", ""))
                zip_codes = resolve_zip_codes(patient_id, note_id) or None
                rec_proposals = recommend_commands(note, api_key, zip_codes=zip_codes, transcript=transcript)
                annotate_duplicates(rec_proposals, note_uuid)
                prefill_assess_backgrounds_for_proposals(rec_proposals, note_uuid)
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
        # `mode` and `selected_template_name` are owned by the session lifecycle
        # (Start AI / Start Manual, template picker) — generate-summary only
        # forwards them when the frontend explicitly sends them. Omitting the
        # key here lets `_save_summary`'s guard preserve the DB column.
        summary_payload: dict[str, Any] = {
            "note": note_dict,
            "commands": commands_list,
            "approved": False,
            "recommendations": recommendations_list,
            "unmatched_conditions": unmatched_conditions,
            "diagnosis_suggestions": diagnosis_suggestions,
            "interaction_warnings": interaction_warnings,
        }
        if "mode" in data:
            summary_payload["mode"] = data["mode"]
        if "selected_template_name" in data:
            summary_payload["selected_template_name"] = data["selected_template_name"]
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
        prefill_assess_backgrounds_for_proposals(proposals, note_uuid)
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
        prefill_assess_backgrounds_for_proposals(proposals, note_uuid)
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
        # Pass the note_uuid so refill / adjust_prescription parsers can verify
        # the source medication is active on the patient before we ORIGINATE.
        # This catches the failure mode where REVIEW raises ValidationError and
        # rolls back the transaction while insert-commands still returns 200.
        validation_errors = validate_proposals(commands, note_uuid=note_uuid)
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
        # Carry-forward assess backgrounds from prior signed notes BEFORE building
        # effects, so the SDK command constructor sees the prefilled value. This
        # mirrors the symmetric placement of ``annotate_duplicates`` (called by
        # the same callers, parallel to the build/validate pipeline).
        prefill_assess_backgrounds(commands, note_uuid)
        effects, metadata_pending, attempted, build_errors = build_effects(commands, note_uuid, feature_flags)
        if build_errors:
            audit_event(
                note_uuid,
                "VALIDATION_FAILED",
                {"errors": build_errors, "source": "build"},
            )
            return [
                JSONResponse(
                    {"error": "Validation failed", "validation_errors": build_errors},
                    status_code=HTTPStatus.BAD_REQUEST,
                )
            ]
        # HIPAA: the audit payload intentionally omits ``display``. For
        # HPI / ROS / PE / lab_results / current_medications, ``display`` is
        # free-text clinical narrative; persisting it into the audit log would
        # be PHI in a log, even with 80-char truncation. Structural identifiers
        # (command_type, section_key) and aggregate counts carry enough signal
        # for incident triage without leaking content. Mirrors the
        # AMEND_EXISTING_COMMANDS hardening (KOALA-5485).
        audit_event(
            note_uuid,
            "INSERT_COMMANDS",
            {
                "command_count": len(commands),
                "effect_count": len(effects),
                "commands": [
                    {
                        "type": c.get("command_type", ""),
                        "section_key": c.get("section_key", ""),
                    }
                    for c in commands
                ],
                "alert_facility_enabled": feature_flags[Constants.SECRET_ALERT_FACILITY_ENABLED],
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

    @api.post("/carry-forward-background")
    def post_carry_forward_background(self) -> list[Union[Response, Effect]]:
        """Return the carried-forward ``background`` for one (note, condition).

        Why this exists as its own endpoint (vs. relying on the /insert-commands
        belt that already prefills): the user needs to SEE the carried value in
        the assess command's edit drawer BEFORE clicking Approve. The
        /insert-commands belt fires server-side at approval time, so it never
        reaches the UI. This endpoint lets the frontend pull the value when the
        provider creates an assess command client-side (handleAddCondition).

        Read-only — no audit event, no PHI logged. The auth gate matches every
        other mutating-shaped endpoint in this view because a leak would expose
        ``has prior assessment for this condition``-shaped metadata about
        another provider's patient.
        """
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]
        note_uuid = str(data.get("note_uuid", ""))
        if not note_uuid:
            return [JSONResponse({"error": "note_uuid is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        condition_id = str(data.get("condition_id", "")).strip()
        if not condition_id:
            return [JSONResponse({"error": "condition_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        if denial := _authorize_edit(note_uuid, self.request):
            return [denial]
        try:
            # ``ValueError`` covers a malformed UUID that slips past _authorize_edit
            # (unlikely — auth's ``Note.objects.values().get(id=...)`` catches it
            # first — but keep the defensive net so a future auth refactor doesn't
            # turn this into a 500). Mirrors ``prefill_assess_backgrounds``.
            note = Note.objects.select_related("patient").get(id=note_uuid)
        except (Note.DoesNotExist, ValueError):
            return [JSONResponse({"error": "Note not found"}, status_code=HTTPStatus.NOT_FOUND)]
        # Reuse the same helper /insert-commands uses, so the carry-forward
        # contract is single-sourced (changes to scoping rules land in one place).
        # The helper mutates the dict in place when a prior is found and leaves
        # it untouched otherwise — read the result via ``.get`` rather than
        # branching on a separate return value.
        scratch: dict[str, Any] = {"condition_id": condition_id}
        carry_forward_assess_background(scratch, note)
        return [JSONResponse({"background": scratch.get("background")}, status_code=HTTPStatus.OK)]

    @api.post("/edit-existing-commands")
    def post_edit_existing_commands(self) -> list[Union[Response, Effect]]:
        """Amend already-documented commands in the editable sections (KOALA-5485).

        Accepts proposals carrying an existing ``command_uuid`` and a ``section_key``
        in ``EDITABLE_AMEND_SECTIONS``. RFV (chief_complaint) routes through a
        direct EDIT; CustomCommand-routed sections route through EnterInError(old)
        + Originate(new) (home-app auto-commits); dedicated SDK class sections
        (HPI, medication_statement) route through EnterInError + Originate +
        Commit. See ``build_amend_edit_effects`` for the routing rationale.

        Returns ``attempted``: a list with ``old_command_uuid``,
        ``new_command_uuid`` (equal to old for direct_edit), ``section_key``,
        ``command_type``, ``mode``, ``display``. The frontend re-stamps
        ``ScribeSummary.commands`` from this list before calling
        ``/verify-commands``.

        Returns ``conflicts`` when a proposal's current Command.state on the
        server is incompatible with the requested operation (e.g., the user has
        a stale tab and is trying to amend an already-voided row). The frontend
        surfaces this so the user can reload before retrying.

        Concurrency (residual race): the eligibility check and effect emission
        are NOT atomic. The plugin sandbox bans ``from django.db import
        transaction`` (only ``from django.db.transaction import atomic`` is
        whitelisted), and even if it didn't, ``select_for_update()`` against
        the ``commands_command`` plugin view fails at the SQL layer (Postgres
        rejects ``FOR UPDATE`` on a view containing outer joins). More
        fundamentally, plugin effects are emitted onto the home-app effect
        bus and processed in a separate transaction, so a plugin-side
        ``atomic()`` would not bound the EnterInError lifecycle anyway.

        The pre-check catches the *common* case (one tab is genuinely stale -
        its submit arrives well after Tab A's EIE has landed). It cannot
        close the microsecond window between two near-simultaneous submits
        against a still-``committed`` row: both reads can see the valid
        state, both branches emit EnterInError(X) + Originate(Y1)/Originate(Y2),
        and the user ends up with two amended commands where they expected
        one. Home-app's idempotent handling of a duplicate EnterInError
        against an already-voided row is the safety net for the EIE side;
        the duplicate Originate(Y2) is the visible artifact and is accepted
        as an extremely rare residual race. Closing it from the plugin side
        would require a cross-repo home-app change (out of scope here).

        Audit writes fire AFTER the state read and effect emission. The
        ``audit_event()`` helper catches broad ``Exception`` via
        ``log.exception(...)``; the historical ordering (state read first,
        audit last) is preserved so that an audit-write failure cannot
        suppress the response. Pinned by
        ``test_edit_existing_commands_audit_fires_after_state_check``.

        ``was_finalized`` interaction: once a note has been approved at least
        once, ``ScribeSummary.was_finalized`` is True (one-way latch in
        ``_save_summary``). The frontend uses this to pin amendment-mode UI on
        re-Approve. If ``/insert-commands`` fails AFTER a successful
        ``/edit-existing-commands``, the frontend rolls back ``approved``
        in-memory but persists the re-stamped command uuids in cache; the
        amendment-mode UI stays pinned because ``was_finalized`` is sticky.
        That's intentional - the user can retry insertion without losing the
        amended state.
        """
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
        # Re-use the existing per-field length validation so amendment edits
        # can't smuggle past, e.g., 10k-char narratives.
        validation_errors = validate_proposals(commands)
        if validation_errors:
            audit_event(note_uuid, "VALIDATION_FAILED", {"errors": validation_errors})
            return [
                JSONResponse(
                    {"error": "Validation failed", "validation_errors": validation_errors},
                    status_code=HTTPStatus.BAD_REQUEST,
                )
            ]

        # KOALA-5485 cross-tab concurrency check: reject any proposal whose
        # underlying Command row is in an incompatible state. This catches the
        # case where Tab A amends HPI X -> Y, and stale Tab B then submits
        # its own amend against X (already entered_in_error). Without this
        # check we'd happily emit EIE(X) on a voided row.
        #
        # Valid eligible (allowlisted + uuid present) proposals get their
        # state fetched in one query, then bucketed:
        #   - DIRECT_EDIT (RFV/chief_complaint): row must be 'staged'.
        #   - void+recreate (everything else): row must NOT be 'entered_in_error'.
        # Missing rows in the DB (e.g., uuid never landed) are treated as
        # conflicts so a buggy or stale frontend doesn't get a silent no-op.
        # NOTE on ``command_not_found``: this corner case can fire legitimately
        # in an Originate-then-Amend race (the originate effect has been
        # accepted server-side but the Command row hasn't been written yet,
        # or the originate was reverted). The user sees a 409 with reason
        # ``command_not_found`` and reloads - benign UX cost for the
        # defense-in-depth guard against stale frontends.
        #
        # NO atomic guarantee. The state read and effect emission are NOT
        # serialized at the DB level: (a) the sandbox bans ``from django.db
        # import transaction`` (only ``from django.db.transaction import
        # atomic`` is whitelisted), (b) ``select_for_update()`` on the
        # commands_command plugin view fails at the SQL layer (FOR UPDATE on
        # an outer-joined view), and (c) the EnterInError effect is processed
        # by home-app in its own transaction so a plugin-side ``atomic()``
        # would not bound the EIE lifecycle anyway. The pre-check serializes
        # the *common* stale-tab case (Tab B's submit arrives after Tab A's
        # EIE has landed). It does NOT close the microsecond race window
        # between two near-simultaneous submits against a still-``committed``
        # row - both reads pass, both branches emit. Residual artifact: a
        # duplicate Originate(Y2) on the same row. Home-app idempotent
        # handling of duplicate EnterInError is the only safety net we have
        # for now; closing the Originate side requires home-app changes.
        # An order (prescribe/refill/refer/imaging_order/lab_order/
        # adjust_prescription) ad-hoc'd into the note shares the _ad_hoc
        # section_key with editable command_types like ``task`` and ``plan``;
        # filter denied command_types out of the eligibility set here so the
        # conflict pre-check doesn't issue a Command-state lookup for them
        # AND so they're silently dropped (consistent with the existing
        # section-not-allowlisted behavior) rather than surfacing a
        # ``state_mismatch`` 409.
        eligible = [
            c
            for c in commands
            if c.get("section_key", "") in EDITABLE_AMEND_SECTIONS
            and c.get("command_type", "") not in NON_EDITABLE_AMEND_COMMAND_TYPES
            and c.get("command_uuid", "")
        ]
        conflicts: list[dict[str, Any]] = []
        effects: list[Effect] = []
        attempted: list[dict[str, Any]] = []
        if eligible:
            wanted_uuids = [c["command_uuid"] for c in eligible]
            # ``Command.id`` is a UUIDField backed by Postgres ``uuid``, so
            # ``.values_list("id", ...)`` yields ``uuid.UUID`` objects, not
            # strings. ``hash(UUID(x)) != hash(str(x))``, so a dict keyed by
            # the raw values misses every lookup against the string
            # ``command_uuid`` we get from JSON - turning every proposal into a
            # spurious ``command_not_found`` 409. Coerce to ``str`` here so the
            # dict shape matches ``state_by_uuid``'s declared type and the
            # lookups below. ``post_verify_commands`` further down already
            # follows this convention.
            state_by_uuid: dict[str, str] = {
                str(uid): state for uid, state in Command.objects.filter(id__in=wanted_uuids).values_list("id", "state")
            }
            for proposal in eligible:
                section_key = proposal.get("section_key", "")
                cmd_uuid = proposal.get("command_uuid", "")
                current_state = state_by_uuid.get(cmd_uuid)
                reason: str | None = None
                if current_state is None:
                    reason = "command_not_found"
                elif section_key in DIRECT_EDIT_SECTIONS:
                    if current_state != "staged":
                        reason = "state_mismatch_expected_staged"
                else:
                    if current_state == "entered_in_error":
                        reason = "state_mismatch_already_voided"
                if reason:
                    conflicts.append(
                        {
                            "section_key": section_key,
                            "command_type": proposal.get("command_type", ""),
                            "command_uuid": cmd_uuid,
                            "current_state": current_state or "missing",
                            "reason": reason,
                        }
                    )
        if not conflicts:
            # Non-eligible proposals (section not allowlisted, no uuid) are
            # silently dropped by build_amend_edit_effects and logged at WARN
            # there. We don't surface them in the response - they signal a
            # stale or buggy frontend, not a user-facing condition.
            effects, attempted = build_amend_edit_effects(commands, note_uuid)

        # Audit fires after the state read + effect-emission step. ``audit_event``
        # catches broad Exception via log.exception, so an audit-write failure
        # cannot suppress the response.
        if conflicts:
            audit_event(
                note_uuid,
                "AMEND_CONFLICT",
                {"conflicts": conflicts, "submitted_count": len(commands)},
            )
            return [
                JSONResponse(
                    {
                        "error": "State mismatch - reload required",
                        "conflicts": conflicts,
                    },
                    status_code=HTTPStatus.CONFLICT,
                )
            ]

        # HIPAA: the audit payload intentionally omits ``display``. For
        # HPI / ROS / PE / lab_results / current_medications, ``display``
        # is free-text clinical narrative; persisting it into the audit log
        # would be PHI in a log, even truncated. The audit entries are built
        # via dict comprehension over ``_AMEND_AUDIT_ENTRY_KEYS`` (a fixed
        # module-level whitelist) so that a future change adding new keys to
        # ``attempted`` records cannot silently propagate PHI here. Pinned
        # by ``test_amend_audit_payload_does_not_propagate_new_attempted_keys``.
        audit_event(
            note_uuid,
            "AMEND_EXISTING_COMMANDS",
            {
                "edit_count": len(attempted),
                "effect_count": len(effects),
                "entries": [{k: a[k] for k in _AMEND_AUDIT_ENTRY_KEYS if k in a} for a in attempted],
            },
        )
        return [
            JSONResponse(
                {"attempted": attempted},
                status_code=HTTPStatus.OK,
            ),
            *effects,
        ]

    @api.post("/delete-existing-commands")
    def post_delete_existing_commands(self) -> list[Union[Response, Effect]]:
        """Amend-mode delete of already-documented commands (KOALA-5485 charge regression).

        Driver: perform (charge) commands render as a checkbox list (no
        ChargeRow), so the only amend gesture available is "uncheck the box."
        Without this endpoint the uncheck silently no-ops - handleInsert
        filters the deselected command out of the insertable list, and because
        no edit happened the ``_amend_edited`` tag is never set either, so the
        existing amend POST drops it. The chart stays committed.

        Accepts proposals carrying an existing ``command_uuid`` and a
        ``section_key`` in ``EDITABLE_AMEND_SECTIONS``. Each valid proposal
        emits exactly ONE ``EnterInError`` effect - no Originate, no Commit.
        The frontend filters deleted commands out of its working array after
        success; they never reach ``/insert-commands``.

        Sibling-not-merged design: kept distinct from ``/edit-existing-commands``
        because (a) the conflict-check has ONE state bucket (not two) -
        ``state != 'entered_in_error'``; (b) the audit payload is structurally
        different (no new uuid to record); (c) the frontend already sends two
        POSTs (delete first, then edit) so collapsing them into one
        round-trip buys nothing.

        Audit-log event_type is the SHARED ``AMEND_EXISTING_COMMANDS`` to
        keep the trail readable; payload carries a ``deleted`` array instead
        of ``entries``. Same PHI whitelist guards the entries (no ``display``).

        Returns ``conflicts`` when a proposal's underlying Command row is
        already in ``entered_in_error`` (cross-tab race or stale UI). Frontend
        prompts reload.
        """
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
        # Re-use the existing per-field length validation. A delete proposal
        # carries (cpt_code, description, notes) for perform but the per-field
        # rules don't trip on it; pass through anyway for defense in depth so a
        # mis-routed malformed proposal can't smuggle past.
        validation_errors = validate_proposals(commands)
        if validation_errors:
            audit_event(note_uuid, "VALIDATION_FAILED", {"errors": validation_errors})
            return [
                JSONResponse(
                    {"error": "Validation failed", "validation_errors": validation_errors},
                    status_code=HTTPStatus.BAD_REQUEST,
                )
            ]

        # Cross-tab concurrency check. Same shape as ``/edit-existing-commands``
        # but with ONE state bucket: the row must NOT be ``entered_in_error``.
        # Missing row -> conflict (don't silently no-op on a stale frontend).
        # Same residual race caveats apply (state read + effect emission are
        # not atomic), same defenses (idempotent EIE on home-app side).
        eligible = [
            c
            for c in commands
            if c.get("section_key", "") in EDITABLE_AMEND_SECTIONS
            and c.get("command_type", "") not in NON_EDITABLE_AMEND_COMMAND_TYPES
            and c.get("command_uuid", "")
        ]
        conflicts: list[dict[str, Any]] = []
        effects: list[Effect] = []
        attempted: list[dict[str, Any]] = []
        if eligible:
            wanted_uuids = [c["command_uuid"] for c in eligible]
            # See ``post_edit_existing_commands`` for the UUID->str coercion
            # rationale. Postgres ``UUIDField`` returns ``uuid.UUID``, dict keys
            # are strings - hash mismatch would turn every legitimate delete
            # into a spurious ``command_not_found`` 409.
            state_by_uuid: dict[str, str] = {
                str(uid): state for uid, state in Command.objects.filter(id__in=wanted_uuids).values_list("id", "state")
            }
            for proposal in eligible:
                section_key = proposal.get("section_key", "")
                cmd_uuid = proposal.get("command_uuid", "")
                current_state = state_by_uuid.get(cmd_uuid)
                reason: str | None = None
                if current_state is None:
                    reason = "command_not_found"
                elif current_state == "entered_in_error":
                    reason = "state_mismatch_already_voided"
                if reason:
                    conflicts.append(
                        {
                            "section_key": section_key,
                            "command_type": proposal.get("command_type", ""),
                            "command_uuid": cmd_uuid,
                            "current_state": current_state or "missing",
                            "reason": reason,
                        }
                    )
        if not conflicts:
            effects, attempted = build_amend_delete_effects(commands, note_uuid)

        if conflicts:
            audit_event(
                note_uuid,
                "AMEND_CONFLICT",
                {"conflicts": conflicts, "submitted_count": len(commands), "operation": "delete"},
            )
            return [
                JSONResponse(
                    {
                        "error": "State mismatch - reload required",
                        "conflicts": conflicts,
                    },
                    status_code=HTTPStatus.CONFLICT,
                )
            ]

        # HIPAA: the audit payload uses the same ``_AMEND_AUDIT_ENTRY_KEYS``
        # whitelist as ``AMEND_EXISTING_COMMANDS`` (no ``display``). Carries a
        # ``deleted`` array alongside the existing ``entries`` shape so the
        # combined event_type stays readable but a future change adding new
        # keys to ``attempted`` records cannot silently leak PHI.
        audit_event(
            note_uuid,
            "AMEND_EXISTING_COMMANDS",
            {
                "delete_count": len(attempted),
                "effect_count": len(effects),
                "deleted": [{k: a[k] for k in _AMEND_AUDIT_ENTRY_KEYS if k in a} for a in attempted],
            },
        )
        return [
            JSONResponse(
                {"attempted": attempted},
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

        # Filter to dicts so a malformed payload (string/None/list element)
        # can't AttributeError on `.get()` downstream. Per-item authorization
        # and visibility-race tolerance both live inside build_metadata_effects
        # so they share a single retry policy (see _wait_for_command_in_note).
        pending = [p for p in pending if isinstance(p, dict)]
        pending_count = len(pending)

        audit_event(
            note_uuid,
            "INSERT_METADATA_REQUEST",
            {
                "pending_count": pending_count,
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
        effects, rejected_count = build_metadata_effects(pending, note_uuid)
        audit_event(
            note_uuid,
            "INSERT_METADATA_RESULT",
            {
                "requested": pending_count,
                "effects_built": len(effects),
                "rejected_count": rejected_count,
            },
        )
        return [JSONResponse({"ok": True, "metadata_count": len(effects)}, status_code=HTTPStatus.OK), *effects]

    @api.post("/verify-commands")
    def post_verify_commands(self) -> list[Union[Response, Effect]]:
        """Verify that attempted commands exist on the note with anchor objects."""
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

        # Skip malformed entries so a bad client payload doesn't 500. Three
        # shapes to defend against: non-dict elements (strings, None, lists —
        # any of which would AttributeError on `.get`); dict elements missing
        # a `command_uuid`; and dict elements whose `command_uuid` isn't a
        # syntactically valid UUID (Django's UUIDField raises ValidationError
        # on coercion failure, which would otherwise 500 the endpoint).
        import uuid as _uuid_mod

        def _is_uuid(s: Any) -> bool:
            try:
                _uuid_mod.UUID(str(s))
                return True
            except (ValueError, AttributeError, TypeError):
                return False

        attempted = [a for a in attempted if isinstance(a, dict)]
        uuids = [a["command_uuid"] for a in attempted if a.get("command_uuid") and _is_uuid(a["command_uuid"])]
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

        # HIPAA: ``display`` is intentionally omitted - it carries free-text
        # clinical narrative for many command types. The audit retains the
        # structural identifier (``command_uuid``) and ``type``; that's enough
        # for incident triage without leaking PHI. Mirrors INSERT_COMMANDS /
        # AMEND_EXISTING_COMMANDS hardening (KOALA-5485).
        audit_event(
            note_uuid,
            "COMMANDS_VERIFIED",
            {
                "total": len(verified) + len(failed),
                "verified": [
                    {
                        "type": v.get("command_type", ""),
                        "command_uuid": v.get("command_uuid", ""),
                    }
                    for v in verified
                ],
                "failed": [
                    {
                        "type": f.get("command_type", ""),
                        "command_uuid": f.get("command_uuid", ""),
                        "reason": f.get("reason", ""),
                    }
                    for f in failed
                ],
            },
        )
        return [JSONResponse({"verified": verified, "failed": failed}, status_code=HTTPStatus.OK)]

    @api.get("/note-commands")
    def get_note_commands(self) -> list[Union[Response, Effect]]:
        """Return every Command on the note for sync into the Scribe tab.

        The Scribe normally only knows about commands it generated or inserted
        itself (cached in ``ScribeSummary.commands``). This endpoint reflects
        whatever's actually on the note's command rail — including ad-hoc
        commands added via the EHR's note-body editor outside the Scribe iframe.

        Every synced command goes into the ``from_the_note`` section as a
        single, uniform locked card — no routing into the existing SOAP groups
        or per-type render branches.
        """
        from canvas_sdk.v1.data.command import Command

        note_uuid = str(self.request.query_params.get("note_id", ""))
        if not note_uuid:
            return [JSONResponse({"error": "note_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        if denial := _authorize_edit(note_uuid, self.request):
            return [denial]

        rows = list(
            Command.objects.filter(note__id=note_uuid)
            .exclude(state="entered_in_error")
            .values("id", "schema_key", "data")
        )
        commands: list[dict[str, Any]] = []
        for row in rows:
            schema_key = row.get("schema_key") or ""
            data = row.get("data") or {}
            commands.append(
                {
                    "command_uuid": str(row["id"]),
                    "command_type": schema_key,
                    "section_key": FROM_THE_NOTE_SECTION,
                    "label": _humanize_schema_key(schema_key),
                    "details": _details_for_command(data),
                    "already_documented": True,
                    "_from_note": True,
                }
            )
        return [JSONResponse({"commands": commands}, status_code=HTTPStatus.OK)]

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
        """Return committed, non-entered-in-error conditions for a patient.

        Shape: ``{"conditions": [{condition_id, code, formatted_code, display, system}, ...]}``.
        The frontend's diagnose -> assess belt fetches against this endpoint
        and matches on ``code``; share :func:`_load_active_patient_conditions`
        with ``post_generate_summary`` so any change to "what counts as an
        active problem-list entry" lands in both places simultaneously."""
        patient_id = self.request.query_params.get("patient_id", "").strip()
        if not patient_id:
            return [JSONResponse({"error": "patient_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        active = _load_active_patient_conditions(patient_id)
        results = [
            {
                "condition_id": a.condition_id,
                "code": a.code,
                "formatted_code": _format_icd10_code(a.code),
                "display": a.display,
                "system": a.system,
            }
            for a in active
        ]
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
            params = urlencode({"query": query, "limit": "25"})
            resp = science_http.get_json(f"/parse-templates/imaging-reports/?{params}")
            data = resp.json() or {}
        except Exception as exc:
            # Scrub query+URL from logs — the typed query may carry patient
            # identifiers (HIPAA). Log only the exception class so ops sees
            # the failure shape without the PHI-bearing context.
            log.error("Imaging search failed: %s", type(exc).__name__)
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
        providers = [{"id": str(s.id), "label": s.credentialed_name} for s in qs]
        return [JSONResponse({"providers": providers}, status_code=HTTPStatus.OK)]

    @api.get("/search-imaging-centers")
    def get_search_imaging_centers(self) -> list[Union[Response, Effect]]:
        """Search for radiology imaging centers via the science service."""
        query = self.request.query_params.get("query", "").strip()
        if not query:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]

        patient_id = self.request.query_params.get("patient_id", "").strip()
        note_id = self.request.query_params.get("note_id", "").strip()
        zip_codes = resolve_zip_codes(patient_id, note_id)

        results = search_imaging_centers(query, zip_codes or None)
        return [JSONResponse({"results": results}, status_code=HTTPStatus.OK)]

    @api.get("/search-refer-providers")
    def get_search_refer_providers(self) -> list[Union[Response, Effect]]:
        """Search for providers to refer to via the science service."""
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
            options = [
                {
                    "dbid": o.dbid,
                    "value": o.name,
                    "code": _ensure_str(getattr(o, "code", None)),
                    "score_value": _ensure_str(getattr(o, "value", None)),
                }
                for o in q.options
            ]
            questions.append(
                {
                    "dbid": int(q.id),
                    "label": q.label,
                    "type": q.type,
                    "options": options,
                }
            )
        scoring_function_name = getattr(questionnaire, "scoring_function_name", "") or ""
        return [
            JSONResponse(
                {
                    "questionnaire_dbid": questionnaire.dbid,
                    "questionnaire_name": questionnaire.name,
                    "is_scored": bool(scoring_function_name),
                    "scoring_function_name": scoring_function_name,
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
