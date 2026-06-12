from __future__ import annotations

from datetime import date
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
        self._last_raw_note_response = raw
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
            "include_corresponding_note_problems": True,
        }
        raw = self._rest_client.generate_normalized_data(payload)
        return self._parse_normalized_data(raw)

    # Remap section titles from Nabla to user-facing labels.
    _TITLE_OVERRIDES: dict[str, str] = {
        "current_medications": "Meds Discussed",
        "allergies": "Allergies Discussed",
        "past_medical_history": "Past Medical History Discussed During Encounter",
    }

    @staticmethod
    def _parse_note(raw: dict[str, Any]) -> ClinicalNote:
        # The note content may be nested under a "note" key (API >= 2026-02-20).
        note_data = raw.get("note", raw)
        sections: list[NoteSection] = []
        for section in note_data.get("sections", []):
            key = section.get("key", "")
            title = NablaBackend._TITLE_OVERRIDES.get(key, section.get("title", ""))
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
            if marker in ("ros", "review of systems", "review of systems (ros)"):
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
                    corresponding_note_problem=cond.get("corresponding_note_problem"),
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
    def _age_from_birth_date(birth_date: str) -> int | None:
        """Calculate age in years from a YYYY-MM-DD birth date string."""
        try:
            dob = date.fromisoformat(birth_date)
        except (ValueError, TypeError):
            return None
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @staticmethod
    def _display_gender(gender: str) -> str | None:
        """Map a gender value to a lowercase display string for the HPI opening line."""
        gender_display = {"M": "male", "F": "female", "MALE": "male", "FEMALE": "female"}
        return gender_display.get(gender) or gender.lower() or None

    _GENDER_API_MAP: dict[str, str] = {"M": "MALE", "F": "FEMALE", "male": "MALE", "female": "FEMALE"}

    @staticmethod
    def _build_note_payload(
        transcript: Transcript,
        patient_context: PatientContext | None,
    ) -> dict[str, Any]:
        # Build the HPI opening line with concrete demographics when available.
        if patient_context is not None:
            name = patient_context.name or "[PATIENT_NAME]"
            age = NablaBackend._age_from_birth_date(patient_context.birth_date)
            age_str = str(age) if age is not None else "[AGE]"
            gender_str = NablaBackend._display_gender(patient_context.gender) or "[GENDER]"
            opening = f"'{name} is a {age_str}-year-old {gender_str} who presents today for [CHIEF COMPLAINT].'"
        else:
            opening = "'[PATIENT_NAME] is a [AGE]-year-old [GENDER] who presents today for [CHIEF COMPLAINT].'"

        # Combined HPI + ROS instruction. Nabla folds ROS into the end of HPI, so this
        # one string drives both; it is subject to a 700-character limit. The ROS is no
        # longer a fixed system list — Nabla picks clinically-appropriate systems — but
        # the format is constrained so the downstream parsers still work: a standalone
        # "ROS" marker line (for _split_ros) and "System: findings" rows with 1-3 word
        # labels (for parse_ros_subsections).
        hpi_custom_instructions = (
            f"Open with one sentence in this exact format: {opening}\n"
            "After it, write complete sentences with a clear subject; do not restate the name or "
            "age, and avoid fragments. Use any dictated structured summary as the PRIMARY source.\n"
            "End with a complete Review of Systems covering whatever systems are clinically "
            "appropriate (you choose them), with positive and negative findings. To parse it: a "
            'line containing only "ROS", then each system on its own line as "System: findings", '
            "with a 1-3 word name (e.g. General, HEENT, Cardiovascular). Never exceed three words."
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
                    "style": "PARAGRAPH",
                    "level_of_detail": "DETAILED",
                    "custom_instruction": hpi_custom_instructions,
                },
                {
                    "section_key": "SOCIAL_HISTORY",
                    "custom_instruction": (
                        "Document only the patient's own social history, and only what is actually "
                        "discussed in this encounter. Do not attribute anyone else's family, children, "
                        "activities, or history to the patient; exclude social details belonging to the "
                        "clinician, a caregiver, or a companion in the room. Never state that a topic was "
                        "not discussed or that no information was provided. If the patient's own social "
                        "history is not discussed, leave this section empty."
                    ),
                },
                {
                    "section_key": "FAMILY_HISTORY",
                    "custom_instruction": (
                        "Family history covers medical conditions or causes of death in the patient's "
                        "own biological relatives — not social anecdotes or a healthy relative's "
                        "activities. Document only what is actually discussed; name the relative and "
                        "relationship. Do not attribute the relatives of the clinician, a caregiver, or "
                        "a companion in the room to the patient; when the relationship or speaker is "
                        'unclear, omit rather than guess. Never add filler such as "no other family '
                        'history discussed." If none is discussed, leave empty.'
                    ),
                },
                {
                    "section_key": "PHYSICAL_EXAM",
                    "custom_instruction": (
                        "Do not include any vital sign measurements in this section. "
                        "Specifically, exclude heart rate (pulse, HR), "
                        "blood pressure (BP), oxygen saturation (SpO2), and "
                        "respiratory rate (breaths per minute, RR) — "
                        "vital signs belong in the Vitals section."
                    ),
                },
            ],
        }
        if patient_context is not None:
            structured_context: dict[str, Any] = {
                "patient_demographics": {
                    "name": patient_context.name,
                },
            }
            if patient_context.birth_date:
                structured_context["patient_demographics"]["birth_date"] = patient_context.birth_date
            mapped_gender = NablaBackend._GENDER_API_MAP.get(patient_context.gender, "")
            if mapped_gender:
                structured_context["patient_demographics"]["gender"] = mapped_gender
            payload["structured_context"] = structured_context
        return payload
