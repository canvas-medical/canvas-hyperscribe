from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any, Union

from logger import log

from canvas_sdk.caching.plugins import get_cache
from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import JSONResponse, Response
from canvas_sdk.handlers.simple_api import SimpleAPI, StaffSessionAuthMixin, api

from canvas_sdk.commands.commands.allergy import AllergenType
from canvas_sdk.v1.data.staff import Staff
from canvas_sdk.v1.data.team import Team

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
        if section.key in _PLAN_SECTION_KEYS:
            matched = conditions
        else:
            section_lower = section.text.lower()
            matched = [c for c in conditions if c.display.lower() in section_lower]
        if matched:
            result[section.key] = [_serialize_condition(c) for c in matched]
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
        return [
            JSONResponse(
                {
                    "results": [{"fdb_code": r.fdb_code, "description": r.description} for r in results],
                },
                status_code=HTTPStatus.OK,
            )
        ]

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
