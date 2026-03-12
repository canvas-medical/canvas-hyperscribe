from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any, Union

from logger import log

from canvas_sdk.caching.plugins import get_cache
from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import JSONResponse, Response
from canvas_sdk.handlers.simple_api import SimpleAPI, StaffSessionAuthMixin, api

from django.db.models import Q

from canvas_sdk.commands.commands.allergy import AllergenType
from canvas_sdk.v1.data.condition import Condition as ConditionModel
from canvas_sdk.v1.data.lab import LabPartner, LabPartnerTest
from canvas_sdk.v1.data.note import Note
from canvas_sdk.v1.data.patient import PatientAddress
from canvas_sdk.v1.data.staff import Staff, StaffRole
from canvas_sdk.v1.data.team import Team

from canvas_sdk.utils.http import science_http

from hyperscribe.libraries.canvas_science import CanvasScience

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
from hyperscribe.scribe.commands.builder import annotate_duplicates, build_effects
from hyperscribe.scribe.commands.extractor import extract_commands
from hyperscribe.scribe.recommendations import recommend_commands
from hyperscribe.scribe.recommendations.diagnosis_suggestion import suggest_diagnoses


def _format_icd10_code(raw: str) -> str:
    code = raw.strip().upper()
    if len(code) > 3:
        return code[:3] + "." + code[3:]
    return code


_CACHE_KEY_PREFIX = "scribe_transcript:"
_SUMMARY_CACHE_KEY_PREFIX = "scribe_summary:"

_PLAN_SECTION_KEYS = frozenset({"assessment_and_plan", "plan"})


def _serialize_condition(condition: Condition) -> dict[str, Any]:
    return {
        "display": condition.display,
        "clinical_status": condition.clinical_status,
        "coding": [{"system": e.system, "code": e.code, "display": e.display} for e in condition.coding],
    }


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


def _save_transcript_to_cache(note_id: str, items: list[dict[str, Any]], *, finalized: bool = False) -> None:
    key = f"{_CACHE_KEY_PREFIX}{note_id}"
    log.info(f"cache save: key={key} items={len(items)} finalized={finalized}")
    try:
        cache = get_cache()
        cache.set(key, json.dumps({"items": items, "finalized": finalized}))
        log.info(f"cache save OK: key={key}")
    except Exception:
        log.exception(f"cache save FAILED: key={key}")


def _load_transcript_from_cache(note_id: str) -> dict[str, Any] | None:
    key = f"{_CACHE_KEY_PREFIX}{note_id}"
    log.info(f"cache load: key={key}")
    try:
        cache = get_cache()
        raw = cache.get(key)
        log.info(f"cache load result: key={key} found={raw is not None}")
    except Exception:
        log.exception(f"cache load FAILED: key={key}")
        return None
    if raw is None:
        return None
    data = json.loads(raw)
    # Backwards compat: old cache entries are bare lists of items.
    if isinstance(data, list):
        return {"items": data, "finalized": False}
    return data  # type: ignore[no-any-return]


def _save_summary_to_cache(
    note_id: str, note_data: dict[str, Any], commands: list[dict[str, Any]], *, approved: bool = False
) -> None:
    key = f"{_SUMMARY_CACHE_KEY_PREFIX}{note_id}"
    log.info(f"summary cache save: key={key} approved={approved}")
    try:
        cache = get_cache()
        cache.set(key, json.dumps({"note": note_data, "commands": commands, "approved": approved}))
    except Exception:
        log.exception(f"summary cache save FAILED: key={key}")


def _load_summary_from_cache(note_id: str) -> dict[str, Any] | None:
    key = f"{_SUMMARY_CACHE_KEY_PREFIX}{note_id}"
    try:
        cache = get_cache()
        raw = cache.get(key)
    except Exception:
        log.exception(f"summary cache load FAILED: key={key}")
        return None
    if raw is None:
        return None
    return json.loads(raw)  # type: ignore[no-any-return]


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
        transcript = _load_transcript_from_cache(note_id)
        summary = _load_summary_from_cache(note_id)
        return [
            JSONResponse(
                {
                    "transcript": transcript,
                    "summary": summary,
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
            cache = get_cache()
            if key_type in ("all", "transcript"):
                cache.delete(f"{_CACHE_KEY_PREFIX}{note_id}")
            if key_type in ("all", "summary"):
                cache.delete(f"{_SUMMARY_CACHE_KEY_PREFIX}{note_id}")
        except Exception:
            log.exception(f"debug cache delete FAILED: note_id={note_id}")
            return [JSONResponse({"error": "Cache delete failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
        return [JSONResponse({"status": "ok", "deleted": key_type}, status_code=HTTPStatus.OK)]

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
        data = _load_transcript_from_cache(note_id)
        if data is None:
            return [JSONResponse({"items": [], "finalized": False}, status_code=HTTPStatus.OK)]
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
        items = data.get("transcript", {}).get("items", [])
        finalized = bool(data.get("finalized", False))
        _save_transcript_to_cache(note_id, items, finalized=finalized)
        return [JSONResponse({"status": "ok"}, status_code=HTTPStatus.OK)]

    @api.get("/summary")
    def get_summary(self) -> list[Union[Response, Effect]]:
        note_id = self.request.query_params.get("note_id", "")
        if not note_id:
            return [JSONResponse({"error": "note_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        data = _load_summary_from_cache(note_id)
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
        note_data = data.get("note", {})
        commands = data.get("commands", [])
        approved = bool(data.get("approved", False))
        _save_summary_to_cache(note_id, note_data, commands, approved=approved)
        return [JSONResponse({"status": "ok"}, status_code=HTTPStatus.OK)]

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

        # If no transcript items in body, load from cache using note_id.
        note_id = str(data.get("note_id", ""))
        cached_data: dict[str, Any] | None = None
        if not transcript_items and note_id:
            cached_data = _load_transcript_from_cache(note_id)
            if cached_data:
                transcript_items = cached_data["items"]
                transcript_data = {"items": transcript_items}

        if not transcript_items:
            return [JSONResponse({"error": "No transcript available"}, status_code=HTTPStatus.BAD_REQUEST)]

        # Only allow generation from finalized transcripts.
        is_finalized = (cached_data or {}).get("finalized", False) if not data.get("transcript") else True
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
        try:
            proposals = recommend_commands(note, api_key)
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

    @api.post("/insert-commands")
    def post_insert_commands(self) -> list[Union[Response, Effect]]:
        try:
            data: dict[str, Any] = json.loads(self.request.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]
        note_uuid = str(data.get("note_uuid", ""))
        if not note_uuid:
            return [JSONResponse({"error": "note_uuid is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        commands = data.get("commands", [])
        effects = build_effects(commands, note_uuid)
        return [JSONResponse({"inserted": len(effects)}, status_code=HTTPStatus.OK), *effects]

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
        assignees: list[dict[str, Any]] = []
        for s in (
            Staff.objects.filter(active=True)
            .order_by("last_name", "first_name")
            .values("dbid", "first_name", "last_name")
        ):
            label = f"{s['first_name']} {s['last_name']}".strip()
            assignees.append({"type": "staff", "id": s["dbid"], "label": label})
        for t in Team.objects.all().order_by("name").values("dbid", "name"):
            assignees.append({"type": "team", "id": t["dbid"], "label": t["name"]})
        return [JSONResponse({"assignees": assignees}, status_code=HTTPStatus.OK)]

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
                staffrole__role_type=StaffRole.RoleType.PROVIDER,
                staffrole__domain__in=StaffRole.RoleDomain.clinical_domains(),
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
        query = self.request.query_params.get("query", "").strip()
        if not query:
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]

        # Resolve zip codes: patient address first, then note location as fallback.
        zip_codes: list[str] = []
        patient_id = self.request.query_params.get("patient_id", "").strip()
        note_id = self.request.query_params.get("note_id", "").strip()
        if patient_id:
            patient_zip = (
                PatientAddress.objects.filter(patient__id=patient_id).values_list("postal_code", flat=True).first()
            )
            if patient_zip:
                zip_codes = [patient_zip]
        if not zip_codes and note_id:
            try:
                note = Note.objects.select_related("location").get(id=note_id)
                if note.location:
                    loc_zip = note.location.addresses.values_list("postal_code", flat=True).first()
                    if loc_zip:
                        zip_codes = [loc_zip]
            except Note.DoesNotExist:
                pass

        params = f"?search={query}&job_title__icontains=radiology"
        if zip_codes:
            params += f"&business_postal_code__in={','.join(zip_codes)}"
        try:
            resp = science_http.get_json(f"/contacts/{params}")
            data = resp.json() or {}
        except Exception:
            log.exception("Imaging center search failed")
            return [JSONResponse({"results": []}, status_code=HTTPStatus.OK)]
        results = []
        for c in data.get("results", []):
            first = c.get("firstName", "")
            last = c.get("lastName", "")
            practice = c.get("practiceName", "")
            specialty = c.get("specialty", "")
            # Build display name matching Canvas convention.
            parts = []
            if first and first != "(TBD)":
                parts.append(first)
            if last and last != first:
                parts.append(last)
            if practice and practice != "(TBD)":
                parts.append(f"({practice}),")
            if specialty and specialty not in (first, last, practice):
                parts.append(specialty)
            if first == "(TBD)":
                parts.append(first)
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
