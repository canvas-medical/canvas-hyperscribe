from __future__ import annotations

from typing import Any

from hyperscribe.scribe.base import ScribeBackend
from hyperscribe.scribe.errors import ScribeTranscriptionError
from hyperscribe.scribe.models import (
    ClinicalNote,
    CodingEntry,
    Condition,
    NormalizedData,
    NoteSection,
    Observation,
    PatientContext,
    Transcript,
    TranscriptItem,
)
from hyperscribe.scribe.nabla.auth import NablaAuth
from hyperscribe.scribe.nabla.client import NablaClient
from hyperscribe.scribe.nabla.ws_client import NablaWsClient

_SPEECH_LOCALE = "en-US"
_NOTE_TEMPLATE = "SOAP"


class NablaBackend(ScribeBackend):
    def __init__(self, *, region: str, client_id: str, client_secret: str) -> None:
        self._auth = NablaAuth(region=region, client_id=client_id, private_key=client_secret)
        self._rest_client = NablaClient(self._auth)
        self._ws_client: NablaWsClient | None = None
        self._session_items: list[TranscriptItem] = []

    def start_session(self) -> None:
        self._ws_client = NablaWsClient(auth=self._auth)
        self._ws_client.connect()
        self._session_items = []

    def send_audio(self, audio: bytes) -> None:
        if self._ws_client is None:
            raise ScribeTranscriptionError("No active session")
        self._ws_client.send_audio_chunk(audio)

    def get_transcript_updates(self) -> list[TranscriptItem]:
        if self._ws_client is None:
            return []
        items = self._ws_client.drain_items()
        self._session_items.extend(items)
        return items

    def end_session(self) -> Transcript:
        if self._ws_client is None:
            raise ScribeTranscriptionError("No active session")
        self._ws_client.end()
        remaining = self._ws_client.drain_items()
        self._session_items.extend(remaining)
        final_items = [item for item in self._session_items if item.is_final]
        self._ws_client = None
        self._session_items = []
        return Transcript(items=final_items)

    def generate_note(
        self,
        transcript: Transcript,
        *,
        patient_context: PatientContext | None = None,
    ) -> ClinicalNote:
        payload = self._build_note_payload(transcript, patient_context)
        raw = self._rest_client.generate_note(payload)
        return self._parse_note(raw)

    def generate_normalized_data(self, note: ClinicalNote) -> NormalizedData:
        payload: dict[str, Any] = {
            "note": {
                "title": note.title,
                "sections": [{"key": s.key, "title": s.title, "text": s.text} for s in note.sections],
            },
        }
        raw = self._rest_client.generate_normalized_data(payload)
        return self._parse_normalized_data(raw)

    @staticmethod
    def _parse_note(raw: dict[str, Any]) -> ClinicalNote:
        sections: list[NoteSection] = []
        for section in raw.get("sections", []):
            sections.append(
                NoteSection(
                    key=section.get("key", ""),
                    title=section.get("title", ""),
                    text=section.get("text", ""),
                )
            )
        return ClinicalNote(title=raw.get("title", ""), sections=sections)

    @staticmethod
    def _parse_normalized_data(raw: dict[str, Any]) -> NormalizedData:
        conditions: list[Condition] = []
        for cond in raw.get("conditions", []):
            coding = [
                CodingEntry(system=c.get("system", ""), code=c.get("code", ""), display=c.get("display", ""))
                for c in cond.get("coding", [])
            ]
            conditions.append(
                Condition(
                    display=cond.get("display", ""),
                    clinical_status=cond.get("clinical_status", ""),
                    coding=coding,
                )
            )

        observations: list[Observation] = []
        for obs in raw.get("observations", []):
            coding = [
                CodingEntry(system=c.get("system", ""), code=c.get("code", ""), display=c.get("display", ""))
                for c in obs.get("coding", [])
            ]
            observations.append(
                Observation(
                    display=obs.get("display", ""),
                    value=obs.get("value", ""),
                    unit=obs.get("unit", ""),
                    coding=coding,
                )
            )

        return NormalizedData(conditions=conditions, observations=observations)

    @staticmethod
    def _build_note_payload(
        transcript: Transcript,
        patient_context: PatientContext | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "transcript": {
                "items": [
                    {
                        "text": item.text,
                        "speaker": item.speaker,
                        "start_offset_ms": item.start_offset_ms,
                        "end_offset_ms": item.end_offset_ms,
                    }
                    for item in transcript.items
                ],
            },
            "note_template": _NOTE_TEMPLATE,
            "locale": _SPEECH_LOCALE,
        }
        if patient_context is not None:
            payload["patient_context"] = {
                "name": patient_context.name,
                "birth_date": patient_context.birth_date,
                "gender": patient_context.gender,
                "encounter_diagnoses": [
                    {"system": c.system, "code": c.code, "display": c.display}
                    for c in patient_context.encounter_diagnoses
                ],
            }
        return payload
