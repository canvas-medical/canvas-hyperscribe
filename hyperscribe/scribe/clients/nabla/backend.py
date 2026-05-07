from __future__ import annotations

import re
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
_PSYCHIATRY_NOTE_TEMPLATE = "PSYCHIATRY_MULTIPLE_SECTIONS"

_PSYCHIATRY_TEMPLATE_NAMES: frozenset[str] = frozenset({"psychiatry", "psychiatry visit"})


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
        visit_template_name: str = "",
    ) -> ClinicalNote:
        is_psychiatry = visit_template_name.strip().lower() in _PSYCHIATRY_TEMPLATE_NAMES
        payload = self._build_note_payload(transcript, patient_context, visit_template_name=visit_template_name)
        raw = self._rest_client.generate_note(payload)
        self._last_raw_note_response = raw
        return self._parse_note(raw, merge_ap=is_psychiatry)

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
    def _parse_note(raw: dict[str, Any], *, merge_ap: bool = False) -> ClinicalNote:
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

        # When using the psychiatry template (merge_ap=True), merge separate
        # "assessment" and "plan" sections into a single "assessment_and_plan"
        # section formatted so that parse_ap_blocks() can split it into
        # header+body blocks for ICD-10 matching.
        #
        # The psychiatry template doesn't support split_by_problem, so the Plan
        # section comes back as flat bullets like "- Problem: plan details...".
        # We reformat Plan bullets into non-bullet headers + bullet bodies by
        # splitting on the first colon, which matches the structure that
        # parse_ap_blocks expects (non-bullet header → bullet body lines).
        keys = {s.key.lower() for s in sections}
        if merge_ap and "assessment" in keys and "plan" in keys and "assessment_and_plan" not in keys:
            assessment = next(s for s in sections if s.key.lower() == "assessment")
            plan = next(s for s in sections if s.key.lower() == "plan")
            merged_text = NablaBackend._reformat_plan_as_ap(assessment.text, plan.text)
            merged = NoteSection(
                key="assessment_and_plan",
                title="Assessment & Plan",
                text=merged_text,
            )
            sections = [s for s in sections if s.key.lower() not in ("assessment", "plan")]
            sections.append(merged)

        return ClinicalNote(title=note_data.get("title", ""), sections=sections)

    @staticmethod
    def _strip_bullet(line: str) -> str:
        """Remove leading bullet prefix (-, *, •) from a line."""
        stripped = line.strip()
        if re.match(r"^[-•*]\s", stripped):
            return stripped[2:].strip()
        return stripped

    @staticmethod
    def _reformat_plan_as_ap(assessment_text: str, plan_text: str) -> str:
        """Merge separate Assessment and Plan sections into a single A&P block.

        The psychiatry template returns Assessment as bullet-point impressions
        and Plan as bullets like "- Problem: plan details...".

        parse_ap_blocks() needs non-bullet headers to create blocks that
        match_condition() can map to ICD-10 codes. We produce:

            Depression and mood disturbance
            - Persistent depressive disorder with prominent bereavement
            - Initiate cross-taper from citalopram to sertraline 50 mg

        Each plan problem becomes a header. Assessment items are matched to
        plan blocks by word overlap and included as body content alongside
        plan details, so that both clinical impressions and actions appear
        under each diagnosis.
        """
        # Parse assessment items.
        assessment_items: list[str] = []
        for line in assessment_text.split("\n"):
            item = NablaBackend._strip_bullet(line)
            if item:
                assessment_items.append(item)

        # Parse plan items into (header, body) pairs.
        plan_blocks: list[tuple[str, str]] = []
        for line in plan_text.split("\n"):
            stripped = NablaBackend._strip_bullet(line)
            if not stripped:
                continue
            if ":" in stripped:
                header, body = stripped.split(":", 1)
                header = header.strip()
                body = body.strip()
                if header:
                    plan_blocks.append((header, body))
                elif body:
                    plan_blocks.append(("", body))
            else:
                plan_blocks.append((stripped, ""))

        if not plan_blocks:
            # No plan items — just return assessment as plain headers.
            return "\n\n".join(assessment_items)

        # Match each assessment item to the best plan block by word overlap.
        # Items with no overlap stay as standalone header-only blocks.
        block_assessments: dict[int, list[str]] = {i: [] for i in range(len(plan_blocks))}
        unmatched_assessments: list[str] = []
        for item in assessment_items:
            item_words = set(NablaBackend._significant_words(item))
            if not item_words:
                unmatched_assessments.append(item)
                continue
            best_idx = 0
            best_score = 0.0
            for i, (header, _) in enumerate(plan_blocks):
                header_words = set(NablaBackend._significant_words(header))
                if not header_words:
                    continue
                overlap = len(item_words & header_words) / min(len(item_words), len(header_words))
                if overlap > best_score:
                    best_score = overlap
                    best_idx = i
            if best_score > 0.0:
                block_assessments[best_idx].append(item)
            else:
                unmatched_assessments.append(item)

        # Build merged blocks: header + assessment bullets + plan bullets.
        output: list[str] = []
        for i, (header, body) in enumerate(plan_blocks):
            lines = [header] if header else []
            for a in block_assessments.get(i, []):
                lines.append(f"- {a}")
            if body:
                lines.append(f"- {body}")
            output.append("\n".join(lines))

        # Append unmatched assessment items as standalone header-only blocks.
        for item in unmatched_assessments:
            output.append(item)

        return "\n\n".join(output)

    @staticmethod
    def _significant_words(text: str) -> list[str]:
        """Extract lowercase words, filtering short and common ones."""
        _stop = {"a", "an", "the", "of", "and", "or", "with", "without", "in",
                 "on", "for", "to", "by", "is", "are", "was", "were", "not", "no",
                 "due", "related", "primarily", "currently", "approximately"}
        cleaned = re.sub(r"[^a-z0-9\s]", "", text.lower())
        return [w for w in cleaned.split() if len(w) > 2 and w not in _stop]

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
        *,
        visit_template_name: str = "",
    ) -> dict[str, Any]:
        is_psychiatry = visit_template_name.strip().lower() in _PSYCHIATRY_TEMPLATE_NAMES

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

        # Shared custom instructions for all templates.
        social_history_instruction = {
            "section_key": "SOCIAL_HISTORY",
            "custom_instruction": (
                "Document only the patient's own social history, and only what is actually "
                "discussed in this encounter. Do not attribute anyone else's family, children, "
                "activities, or history to the patient; exclude social details belonging to the "
                "clinician, a caregiver, or a companion in the room. Never state that a topic was "
                "not discussed or that no information was provided. If the patient's own social "
                "history is not discussed, leave this section empty."
            ),
        }
        family_history_instruction = {
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
        }
        physical_exam_instruction = {
            "section_key": "PHYSICAL_EXAM",
            "custom_instruction": (
                "Do not include any vital sign measurements in this section. "
                "Specifically, exclude heart rate (pulse, HR), "
                "blood pressure (BP), oxygen saturation (SpO2), and "
                "respiratory rate (breaths per minute, RR) — "
                "vital signs belong in the Vitals section."
            ),
        }

        if is_psychiatry:
            note_template = _PSYCHIATRY_NOTE_TEMPLATE
            sections_customization = [
                {"section_key": "ASSESSMENT", "style": "BULLET_POINTS"},
                {
                    "section_key": "PLAN",
                    "style": "BULLET_POINTS",
                    "custom_instruction": "Organize by problem, with the plan for each problem grouped together.",
                },
                {
                    "section_key": "HISTORY_OF_PRESENT_ILLNESS",
                    "style": "PARAGRAPH",
                    "custom_instruction": hpi_custom_instructions,
                },
                social_history_instruction,
                family_history_instruction,
                {
                    "section_key": "MENTAL_HEALTH_EXAM",
                    "custom_instruction": (
                        "Be thorough. Use these categories: "
                        "Depressive Symptoms, Anxiety Symptoms, Sleep, Appetite, "
                        "SI/HI, Hallucinations, Delusions/Paranoia, Manic Symptoms."
                    ),
                },
                physical_exam_instruction,
            ]
        else:
            note_template = _NOTE_TEMPLATE
            sections_customization = [
                {"section_key": "ASSESSMENT_AND_PLAN", "style": "BULLET_POINTS", "split_by_problem": True},
                {
                    "section_key": "HISTORY_OF_PRESENT_ILLNESS",
                    "style": "PARAGRAPH",
                    "level_of_detail": "DETAILED",
                    "custom_instruction": hpi_custom_instructions,
                },
                social_history_instruction,
                family_history_instruction,
                physical_exam_instruction,
            ]

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
            "note_template": note_template,
            "note_locale": _NOTE_LOCALE,
            "note_sections_customization": sections_customization,
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
