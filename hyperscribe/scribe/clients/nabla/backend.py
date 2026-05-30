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

# Visit templates that route to the PSYCHIATRY_MULTIPLE_SECTIONS Nabla template
# and trigger the psych-specific note customization (Mental Health Exam, no
# medical ROS scaffold, A&P merge for ICD-10 matching).
#
# Exact match is intentional: the visit template name comes from the
# server-controlled /visit-templates endpoint, so we never see whitespace or
# casing drift from the frontend. Normalizing (lowercase/strip) would only
# create false positives when an operator adds a template literally named
# "Psychiatry " or "psychiatry" for an unrelated workflow.
_PSYCHIATRY_TEMPLATE_NAMES: frozenset[str] = frozenset({"Psychiatry"})


class NablaBackend(ScribeBackend):
    def __init__(self, *, client_id: str, client_secret: str) -> None:
        self._auth = NablaAuth(client_id=client_id, private_key=client_secret)
        self._rest_client = NablaClient(self._auth, api_version=_NABLA_API_VERSION)

    @staticmethod
    def is_psychiatry_template(visit_template_name: str) -> bool:
        """Return True when ``visit_template_name`` selects the psychiatry Nabla template.

        Public helper so callers (e.g. ``session_view``) can route extractor /
        audit logic without importing the private template-name set. The match
        is intentionally exact (see ``_PSYCHIATRY_TEMPLATE_NAMES``); operator
        templates whose name *looks* like psychiatry but isn't a literal match
        are surfaced via the PSYCH_TEMPLATE_NEAR_MISS audit event instead.
        """
        return visit_template_name in _PSYCHIATRY_TEMPLATE_NAMES

    @staticmethod
    def is_psychiatry_template_near_miss(visit_template_name: str) -> bool:
        """Return True when the template name *looks* like psychiatry but does not exact-match.

        The audit emitter in session_view uses this to surface customer
        admins who added e.g. "Psychiatry Follow-up" or "psychiatry "
        templates that won't trigger the psych Nabla customization. The
        check is case-insensitive and only fires when the template name
        contains "psych" — operator-set names, no PHI.
        """
        if not visit_template_name:
            return False
        if visit_template_name in _PSYCHIATRY_TEMPLATE_NAMES:
            return False
        return "psych" in visit_template_name.lower()

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
        is_psychiatry = self.is_psychiatry_template(visit_template_name)
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
        if merge_ap and ("assessment" in keys or "plan" in keys) and "assessment_and_plan" not in keys:
            assessment_text = next((s.text for s in sections if s.key.lower() == "assessment"), "")
            plan_text = next((s.text for s in sections if s.key.lower() == "plan"), "")
            merged_text = NablaBackend._reformat_plan_as_ap(assessment_text, plan_text)
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
        """Remove leading bullet prefix (-, *, •) from a line, after trimming whitespace.

        Indentation is stripped here, so callers that need to distinguish
        top-level bullets from nested sub-bullets must inspect the raw line
        themselves *before* calling this. ``_reformat_plan_as_ap`` is the one
        caller that cares about indent: it computes the indent prefix on the
        raw line and routes nested sub-bullets to the preceding header's
        body so we don't emit phantom diagnose blocks for category labels
        (Pharmacotherapy / Psychotherapy / Follow-up) that sit under a
        parent diagnosis like ``- Major Depressive Disorder:``.
        """
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

        Nested sub-bullets (e.g. ``- MDD:\\n  - Pharmacotherapy: ...``) are
        detected by raw-line indent and attached to the preceding parent's
        body. Without this guard, indented category labels would become
        phantom diagnose blocks downstream.
        """
        # Short-circuit: when Nabla returns assessment but no plan (e.g. an
        # emergency or deferred-plan visit), return the assessment unchanged.
        # If we merge-with-empty-plan we'd emit each assessment item as a
        # bare line, which parse_ap_blocks treats as a header-only block →
        # one phantom diagnose command per line. Returning the bullet-prefixed
        # original keeps bullets as bodies, so parse_ap_blocks produces zero
        # header-only blocks.
        if not plan_text.strip():
            return assessment_text

        # Parse assessment items.
        assessment_items: list[str] = []
        for line in assessment_text.split("\n"):
            item = NablaBackend._strip_bullet(line)
            if item:
                assessment_items.append(item)

        # Parse plan items into (header, bodies) groups, coalescing duplicate
        # headers so that multiple bullets for the same problem (e.g.
        # "- Depression: Start sertraline" + "- Depression: Titrate weekly")
        # produce a single block instead of duplicate diagnose commands.
        plan_groups: dict[str, list[str]] = {}
        plan_order: list[str] = []
        for raw_line in plan_text.split("\n"):
            # Indent-aware: nested sub-bullets (indent >= 2 chars) belong to
            # the most recent header's body, not as new headers. Threshold is
            # 2 (not 1) so a stray single-space prefix on a top-level bullet
            # from Nabla format drift doesn't get misclassified as nested.
            # Standard markdown nesting is 2 spaces; tabs treated identically.
            stripped_line = raw_line.lstrip()
            indent = len(raw_line) - len(stripped_line)
            stripped = NablaBackend._strip_bullet(raw_line)
            if not stripped:
                continue
            is_nested = indent >= 2 and bool(plan_order)
            if is_nested:
                # Sub-bullet under an existing parent — append as body.
                # Drop the colon-prefix label if present, but keep the
                # whole line so downstream readers see what was nested.
                plan_groups[plan_order[-1]].append(stripped)
                continue
            if ":" in stripped:
                header, body = stripped.split(":", 1)
                header = header.strip()
                body = body.strip()
                key = header.lower() if header else ""
                if key not in plan_groups:
                    plan_groups[key] = []
                    plan_order.append(key)
                if body:
                    plan_groups[key].append(body)
            else:
                # Colon-less bullets (e.g. "Order CBC" or "Schedule follow-up")
                # are cross-cutting actions, not diagnoses. Attach to the most
                # recent plan group's body to avoid phantom diagnose commands.
                if plan_order:
                    plan_groups[plan_order[-1]].append(stripped)
                else:
                    # No prior group exists — treat as a standalone header.
                    key = stripped.lower()
                    plan_groups[key] = []
                    plan_order.append(key)

        # Build coalesced (header, bodies) list preserving first-seen order.
        plan_blocks: list[tuple[str, list[str]]] = []
        for key in plan_order:
            # Use the original-cased header from the first top-level occurrence.
            display_header = key  # fallback
            for raw_line in plan_text.split("\n"):
                indent = len(raw_line) - len(raw_line.lstrip())
                if indent > 0:
                    continue  # skip nested lines when picking the header label
                s = NablaBackend._strip_bullet(raw_line)
                if s and ":" in s:
                    h = s.split(":", 1)[0].strip()
                    if h.lower() == key:
                        display_header = h
                        break
                elif s and s.lower() == key:
                    display_header = s
                    break
            plan_blocks.append((display_header, plan_groups[key]))

        if not plan_blocks:
            # Plan had no parseable bullets (e.g. only whitespace markers).
            # Return assessment unchanged — same reasoning as the empty-plan
            # short-circuit above: emitting bare lines would create phantom
            # header-only blocks downstream.
            return assessment_text

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
            if best_score >= 0.5:
                block_assessments[best_idx].append(item)
            else:
                unmatched_assessments.append(item)

        # Build merged blocks: header + assessment bullets + plan bullets.
        output: list[str] = []
        for i, (header, bodies) in enumerate(plan_blocks):
            lines = [header] if header else []
            for a in block_assessments.get(i, []):
                lines.append(f"- {a}")
            for b in bodies:
                lines.append(f"- {b}")
            output.append("\n".join(lines))

        # Append unmatched assessment items as standalone header-only blocks.
        for item in unmatched_assessments:
            output.append(item)

        return "\n\n".join(output)

    @staticmethod
    def _significant_words(text: str) -> list[str]:
        """Extract lowercase words, filtering short, common, and generic medical ones."""
        _stop = {
            "a",
            "an",
            "the",
            "of",
            "and",
            "or",
            "with",
            "without",
            "in",
            "on",
            "for",
            "to",
            "by",
            "is",
            "are",
            "was",
            "were",
            "not",
            "no",
            "due",
            "related",
            "primarily",
            "currently",
            "approximately",
            # Generic medical wildcards — aligned with ap_split._STOP_WORDS
            # to avoid false matches on shared diagnostic nouns.
            "disorder",
            "disease",
            "syndrome",
            "condition",
            "type",
            "acute",
            "chronic",
            "primary",
            "secondary",
            "possible",
            "probable",
            "likely",
            "suspected",
            "unspecified",
            "specified",
            "other",
        }
        cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
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
        is_psychiatry = NablaBackend.is_psychiatry_template(visit_template_name)

        # Build the HPI opening line with concrete demographics when available.
        if patient_context is not None:
            name = patient_context.name or "[PATIENT_NAME]"
            age = NablaBackend._age_from_birth_date(patient_context.birth_date)
            age_str = str(age) if age is not None else "[AGE]"
            gender_str = NablaBackend._display_gender(patient_context.gender) or "[GENDER]"
            opening = f"'{name} is a {age_str}-year-old {gender_str} who presents today for [CHIEF COMPLAINT].'"
        else:
            opening = "'[PATIENT_NAME] is a [AGE]-year-old [GENDER] who presents today for [CHIEF COMPLAINT].'"

        # HPI base guidance, shared by all templates.
        hpi_base_instructions = (
            f"Open with one sentence in this exact format: {opening}\n"
            "After it, write complete sentences with a clear subject; do not restate the name or "
            "age, and avoid fragments. Use any dictated structured summary as the PRIMARY source."
        )

        # Generic visits embed a medical ROS at the end of the HPI; psychiatry
        # visits get their ROS from the dedicated MENTAL_HEALTH_EXAM section, so
        # the HPI omits the redundant medical ROS block. The ROS is no longer a
        # fixed system list — Nabla picks clinically-appropriate systems — but
        # the format is constrained so the downstream parsers still work: a
        # standalone "ROS" marker line (for _split_ros) and "System: findings"
        # rows with 1-3 word labels (for parse_ros_subsections).
        if is_psychiatry:
            hpi_custom_instructions = hpi_base_instructions
        else:
            hpi_custom_instructions = (
                hpi_base_instructions + "\n"
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

        sections_customization: list[dict[str, Any]]
        if is_psychiatry:
            note_template = _PSYCHIATRY_NOTE_TEMPLATE
            # PHYSICAL_EXAM customization is retained for the psych branch as
            # belt-and-braces: it instructs Nabla to keep vital signs out of
            # the PE section *if* the PSYCHIATRY template emits one. Nabla's
            # current documentation does not enumerate whether
            # PSYCHIATRY_MULTIPLE_SECTIONS includes physical_exam by default.
            # Brigade UAT to confirm: capture a real-instance Nabla payload
            # under the Psychiatry template and check for a physical_exam
            # section. If it never emits one, the customization is harmless;
            # if it does, this instruction prevents BP/HR leaking into PE
            # (the same drift bug that motivated the generic branch).
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
