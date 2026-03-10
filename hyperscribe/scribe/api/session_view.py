from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any, Union

from logger import log

from canvas_sdk.caching.plugins import get_cache
from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import JSONResponse, Response
from canvas_sdk.handlers.simple_api import SessionCredentials, SimpleAPI, StaffSessionAuthMixin, api

from canvas_sdk.v1.data.medication import Medication, MedicationCoding, Status
from canvas_sdk.v1.data.note import Note
from canvas_sdk.v1.data.staff import Staff
from canvas_sdk.v1.data.team import Team

from hyperscribe.libraries.canvas_science import CanvasScience

import hyperscribe.scribe.clients.nabla  # noqa: F401 — register backends
from hyperscribe.scribe.backend import (
    ClinicalNote,
    CodingEntry,
    NoteSection,
    PatientContext,
    ScribeError,
    Transcript,
    TranscriptItem,
    get_backend_from_secrets,
)
from hyperscribe.scribe.backend.models import CommandProposal
from hyperscribe.scribe.commands.builder import build_effects
from hyperscribe.scribe.commands.extractor import extract_commands


_CACHE_KEY_PREFIX = "scribe_transcript:"


def _save_transcript_to_cache(note_id: str, items: list[dict[str, Any]]) -> None:
    key = f"{_CACHE_KEY_PREFIX}{note_id}"
    log.info(f"cache save: key={key} items={len(items)}")
    try:
        cache = get_cache()
        cache.set(key, json.dumps(items))
        log.info(f"cache save OK: key={key}")
    except Exception:
        log.exception(f"cache save FAILED: key={key}")


def _load_transcript_from_cache(note_id: str) -> list[dict[str, Any]] | None:
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


def _annotate_medication_duplicates(proposals: list[CommandProposal], note_uuid: str) -> None:
    """Mark medication proposals that already exist in the patient's active medications."""
    med_proposals = [p for p in proposals if p.command_type == "medication_statement"]
    if not med_proposals:
        return
    try:
        note = Note.objects.select_related("patient").get(id=note_uuid)
    except Note.DoesNotExist:
        return
    patient = note.patient
    if patient is None:
        return
    active_meds = Medication.objects.for_patient(patient.id).filter(status=Status.ACTIVE)
    coding_qs = MedicationCoding.objects.filter(medication__in=active_meds)
    active_labels = {c.display.lower() for c in coding_qs if c.display}
    for proposal in med_proposals:
        med_text = proposal.data.get("medication_text", "").lower()
        if not med_text:
            continue
        for label in active_labels:
            if med_text in label or label in med_text:
                proposal.already_documented = True
                break


class ScribeSessionView(StaffSessionAuthMixin, SimpleAPI):
    """Scribe session management API."""

    PREFIX = "/scribe-session"

    def authenticate(self, credentials: SessionCredentials) -> bool:
        auth_result: bool = super().authenticate(credentials)
        self._staff_id: str = credentials.logged_in_user["id"]
        return auth_result

    @api.get("/config")
    def get_config(self) -> list[Union[Response, Effect]]:
        try:
            backend = get_backend_from_secrets(self.secrets)
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.BAD_REQUEST)]
        try:
            config = backend.get_transcription_config(user_external_id=self._staff_id)
        except ScribeError as exc:
            return [JSONResponse({"error": str(exc)}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
        return [JSONResponse(config, status_code=HTTPStatus.OK)]

    @api.get("/transcript")
    def get_transcript(self) -> list[Union[Response, Effect]]:
        note_id = self.request.query_params.get("note_id", "")
        if not note_id:
            return [JSONResponse({"error": "note_id is required"}, status_code=HTTPStatus.BAD_REQUEST)]
        items = _load_transcript_from_cache(note_id)
        if items is None:
            return [JSONResponse({"items": []}, status_code=HTTPStatus.OK)]
        return [JSONResponse({"items": items}, status_code=HTTPStatus.OK)]

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
        _save_transcript_to_cache(note_id, items)
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
        if not transcript_items:
            note_id = str(data.get("note_id", ""))
            if note_id:
                cached_items = _load_transcript_from_cache(note_id)
                if cached_items:
                    transcript_items = cached_items
                    transcript_data = {"items": transcript_items}

        if not transcript_items:
            return [JSONResponse({"error": "No transcript available"}, status_code=HTTPStatus.BAD_REQUEST)]

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
                    "conditions": [
                        {
                            "display": c.display,
                            "clinical_status": c.clinical_status,
                            "coding": [{"system": e.system, "code": e.code, "display": e.display} for e in c.coding],
                        }
                        for c in result.conditions
                    ],
                    "observations": [
                        {
                            "display": o.display,
                            "value": o.value,
                            "unit": o.unit,
                            "coding": [{"system": e.system, "code": e.code, "display": e.display} for e in o.coding],
                        }
                        for o in result.observations
                    ],
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
        if note_uuid:
            _annotate_medication_duplicates(proposals, note_uuid)
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
