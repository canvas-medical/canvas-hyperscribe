from __future__ import annotations

from typing import Any

from hyperscribe.scribe.base import ScribeBackend
from hyperscribe.scribe.models import (
    AsyncJob,
    ClinicalNote,
    CodingEntry,
    Condition,
    NormalizedData,
    NoteSection,
    Observation,
    PatientContext,
    Transcript,
    TranscriptItem,
    TranscriptionStatus,
)
from hyperscribe.scribe.nabla.auth import NablaAuth
from hyperscribe.scribe.nabla.client import NablaClient

_SPEECH_LOCALE = "en-US"
_NOTE_TEMPLATE = "SOAP"


class NablaBackend(ScribeBackend):
    def __init__(self, *, region: str, client_id: str, client_secret: str) -> None:
        self._auth = NablaAuth(region=region, client_id=client_id, private_key=client_secret)
        self._client = NablaClient(self._auth)

    def transcribe(self, audio: bytes) -> Transcript:
        raw = self._client.transcribe_sync(audio, {"speech_locales": _SPEECH_LOCALE})
        return self._parse_transcript(raw)

    def transcribe_async_start(self, file_url: str) -> str:
        payload: dict[str, Any] = {
            "file_url": file_url,
            "speech_locales": [_SPEECH_LOCALE],
        }
        raw = self._client.transcribe_async_start(payload)
        job_id: str = raw["id"]
        return job_id

    def transcribe_async_poll(self, job_id: str) -> AsyncJob | Transcript:
        raw = self._client.transcribe_async_poll(job_id)
        status = raw.get("status", "").lower()
        if status == "succeeded":
            return self._parse_transcript(raw)
        return AsyncJob(
            id=raw.get("id", job_id),
            status=TranscriptionStatus(status) if status in ("ongoing", "failed") else TranscriptionStatus.ONGOING,
        )

    def generate_note(
        self,
        transcript: Transcript,
        *,
        patient_context: PatientContext | None = None,
    ) -> ClinicalNote:
        payload = self._build_note_payload(transcript, patient_context)
        raw = self._client.generate_note(payload)
        return self._parse_note(raw)

    def generate_normalized_data(self, note: ClinicalNote) -> NormalizedData:
        payload: dict[str, Any] = {
            "note": {
                "title": note.title,
                "sections": [{"key": s.key, "title": s.title, "text": s.text} for s in note.sections],
            },
        }
        raw = self._client.generate_normalized_data(payload)
        return self._parse_normalized_data(raw)

    @staticmethod
    def _parse_transcript(raw: dict[str, Any]) -> Transcript:
        items: list[TranscriptItem] = []
        for item in raw.get("items", []):
            items.append(
                TranscriptItem(
                    text=item.get("text", ""),
                    speaker=item.get("speaker", ""),
                    start_offset_ms=item.get("start_offset_ms", 0),
                    end_offset_ms=item.get("end_offset_ms", 0),
                )
            )
        return Transcript(items=items)

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
