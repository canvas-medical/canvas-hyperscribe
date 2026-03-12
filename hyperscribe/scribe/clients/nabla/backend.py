from __future__ import annotations

from typing import Any

from hyperscribe.scribe.backend import (
    ClinicalNote,
    CodingEntry,
    Condition,
    NormalizedData,
    NoteSection,
    Observation,
    PatientContext,
    ScribeBackend,
    Transcript,
)
from hyperscribe.scribe.clients.nabla.auth import NablaAuth
from hyperscribe.scribe.clients.nabla.client import NablaClient

_NABLA_API_VERSION = "2026-02-20"
_NOTE_LOCALE = "ENGLISH_US"
_NOTE_TEMPLATE = "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"


class NablaBackend(ScribeBackend):
    def __init__(self, *, client_id: str, client_secret: str) -> None:
        self._auth = NablaAuth(client_id=client_id, private_key=client_secret)
        self._rest_client = NablaClient(self._auth, api_version=_NABLA_API_VERSION)

    def get_transcription_config(self, *, user_external_id: str = "") -> dict[str, Any]:
        access_token, refresh_token = self._auth.get_user_tokens(user_external_id)
        hostname = self._auth.base_url.split("://", 1)[-1].split("/", 1)[0]
        return {
            "vendor": "nabla",
            "ws_url": f"wss://{hostname}/v1/core/user/transcribe-ws?nabla-api-version={_NABLA_API_VERSION}",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "sample_rate": 16000,
            "encoding": "PCM_S16LE",
            "speech_locales": ["ENGLISH_US"],
            "stream_id": "stream1",
            "split_by_sentence": True,
        }

    def generate_note(
        self,
        transcript: Transcript,
        *,
        patient_context: PatientContext | None = None,
    ) -> ClinicalNote:
        payload = self._build_note_payload(transcript, patient_context)
        raw = self._rest_client.generate_note(payload)
        return self._parse_note(raw)

    # Section keys that we synthesize locally and Nabla does not recognise.
    _LOCAL_ONLY_KEYS: frozenset[str] = frozenset({"review_of_systems"})

    def generate_normalized_data(self, note: ClinicalNote) -> NormalizedData:
        payload: dict[str, Any] = {
            "note": {
                "title": note.title,
                "sections": [
                    {"key": s.key, "title": s.title, "text": s.text}
                    for s in note.sections
                    if s.key not in self._LOCAL_ONLY_KEYS
                ],
                "locale": _NOTE_LOCALE,
                "template": _NOTE_TEMPLATE,
            },
        }
        raw = self._rest_client.generate_normalized_data(payload)
        return self._parse_normalized_data(raw)

    @staticmethod
    def _parse_note(raw: dict[str, Any]) -> ClinicalNote:
        # The note content may be nested under a "note" key (API >= 2026-02-20).
        note_data = raw.get("note", raw)
        sections: list[NoteSection] = []
        for section in note_data.get("sections", []):
            key = section.get("key", "")
            title = section.get("title", "")
            text = section.get("text", "")

            if key.lower() == "history_of_present_illness":
                hpi_text, ros_text = NablaBackend._split_ros(text)
                sections.append(NoteSection(key=key, title=title, text=hpi_text))
                if ros_text:
                    sections.append(
                        NoteSection(
                            key="review_of_systems",
                            title="Review of Systems",
                            text=ros_text,
                        )
                    )
            else:
                sections.append(NoteSection(key=key, title=title, text=text))

        return ClinicalNote(title=note_data.get("title", ""), sections=sections)

    @staticmethod
    def _normalize_marker(line: str) -> str:
        """Strip bullet prefixes (-, *, •) and trailing colons/whitespace."""
        s = line.strip()
        if s.startswith(("-", "*", "\u2022")):
            s = s[1:].strip()
        return s.rstrip(":").strip().lower()

    @staticmethod
    def _split_ros(text: str) -> tuple[str, str]:
        """Split ROS block from HPI text. Returns (hpi_text, ros_text)."""
        lines = text.split("\n")
        for i, line in enumerate(lines):
            marker = NablaBackend._normalize_marker(line)
            if marker == "ros" or marker == "review of systems":
                hpi_part = "\n".join(lines[:i]).rstrip()
                ros_part = "\n".join(lines[i + 1 :]).strip()
                return hpi_part, ros_part
        return text, ""

    @staticmethod
    def _parse_coding_entry(entry: Any) -> CodingEntry:
        """Parse a coding entry that may be a dict or a string."""
        if isinstance(entry, dict):
            return CodingEntry(
                system=entry.get("system", ""),
                code=entry.get("code", ""),
                display=entry.get("display", ""),
            )
        # Nabla may return coding as plain strings (e.g. "ICD-10:R51").
        text = str(entry)
        if ":" in text:
            system, code = text.split(":", 1)
            return CodingEntry(system=system.strip(), code=code.strip(), display="")
        return CodingEntry(system="", code=text, display="")

    @staticmethod
    def _normalize_coding(raw_coding: Any) -> list[Any]:
        """Ensure coding is always a list (Nabla may return a single dict)."""
        if isinstance(raw_coding, list):
            return raw_coding
        if isinstance(raw_coding, dict):
            return [raw_coding]
        return []

    @staticmethod
    def _parse_normalized_data(raw: dict[str, Any]) -> NormalizedData:
        conditions: list[Condition] = []
        for cond in raw.get("conditions", []):
            entries = NablaBackend._normalize_coding(cond.get("coding"))
            coding = [NablaBackend._parse_coding_entry(c) for c in entries]
            conditions.append(
                Condition(
                    display=cond.get("display", ""),
                    clinical_status=cond.get("clinical_status", ""),
                    coding=coding,
                )
            )

        observations: list[Observation] = []
        for obs in raw.get("observations", []):
            entries = NablaBackend._normalize_coding(obs.get("coding"))
            coding = [NablaBackend._parse_coding_entry(c) for c in entries]
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
        ros_custom_instructions = (
            "Include ROS at the end of this section and add positive and negative symptoms as mentioned.\n"
            "ROS\n"
            "General:\n"
            "Skin:\n"
            "HEENT:\n"
            "Cardiovascular:\n"
            "Respiratory:\n"
            "Gastrointestinal:\n"
            "Genitourinary:\n"
            "Musculoskeletal:"
        )

        payload: dict[str, Any] = {
            "transcript_items": [
                {
                    "text": item.text,
                    "speaker_type": item.speaker or "UNSPECIFIED",
                    "start_offset_ms": item.start_offset_ms,
                    "end_offset_ms": item.end_offset_ms,
                }
                for item in transcript.items
            ],
            "note_template": _NOTE_TEMPLATE,
            "note_locale": _NOTE_LOCALE,
            "note_sections_customization": [
                {"section_key": "ASSESSMENT_AND_PLAN", "style": "BULLET_POINTS", "split_by_problem": True},
                {
                    "section_key": "HISTORY_OF_PRESENT_ILLNESS",
                    "custom_instruction": ros_custom_instructions,
                },
            ],
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
