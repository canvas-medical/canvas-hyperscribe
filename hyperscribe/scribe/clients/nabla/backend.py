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
    ScribeError,
    Transcript,
)
from hyperscribe.scribe.clients.nabla.auth import NablaAuth
from hyperscribe.scribe.clients.nabla.client import NablaClient


_NABLA_API_VERSION = "2026-06-12"
_NOTE_LOCALE = "ENGLISH_US"
_NOTE_TEMPLATE = "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"
_PSYCHIATRY_NOTE_TEMPLATE = "PSYCHIATRY_MULTIPLE_SECTIONS_AP_MERGED"

# Visit templates that route to the PSYCHIATRY_MULTIPLE_SECTIONS_AP_MERGED Nabla
# template and trigger the psych-specific note customization (Mental Health Exam,
# no medical ROS scaffold).
#
# The AP-merged template (available since nabla-api-version 2026-06-12) returns a
# single ASSESSMENT_AND_PLAN section structured by problem (split_by_problem), so
# the A&P parses through the same path as generic visits — no local re-merge. The
# legacy separate-section re-merge in _parse_note is kept as a dormant fallback
# (its guard self-disables when assessment_and_plan is present).
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

    @staticmethod
    def _template_supports_option(template_detail: dict[str, Any], section_key: str, option: str) -> bool:
        """Return True if ``section_key`` lists ``option`` among its supported customization options.

        Tolerant of the GET /generate-note/templates/{key} response shape (doc-unconfirmed,
        pinned at UAT): sections may live at the top level or nested under ``template``;
        each section's key may be ``key`` or ``section_key``; the options list may be
        ``supported_customization_options`` or ``customization_options``, holding either
        plain strings or dicts with a ``name``/``key``. Matching ignores case and
        underscores (so "SPLIT_BY_PROBLEM" / "split_by_problem" / "splitByProblem" match).
        """

        def _norm(value: str) -> str:
            return value.replace("_", "").lower()

        sections = template_detail.get("sections")
        if not sections and isinstance(template_detail.get("template"), dict):
            sections = template_detail["template"].get("sections")
        target = _norm(section_key)
        want = _norm(option)
        for section in sections or []:
            if not isinstance(section, dict):
                continue
            key = section.get("key") or section.get("section_key") or ""
            if _norm(str(key)) != target:
                continue
            options = section.get("supported_customization_options") or section.get("customization_options") or []
            for opt in options:
                name = opt if isinstance(opt, str) else (opt.get("name") or opt.get("key") or "")
                if _norm(str(name)) == want:
                    return True
        return False

    def supports_psychiatry_ap_split_by_problem(self, *, locale: str = _NOTE_LOCALE) -> bool:
        """Best-effort capability check: does the psychiatry AP-merged template support
        ``split_by_problem`` on ASSESSMENT_AND_PLAN at the current API version?

        This is the premise of the AP-merged psychiatry path (the local A&P re-merge is
        only a fallback). Intended for diagnostics/UAT — call it after a version bump to
        confirm the template honors the option, rather than discovering a 400 at
        generate-note time. Returns False (rather than raising) on any lookup failure so a
        caller can log/alert without breaking the request path.
        """
        try:
            detail = self._rest_client.get_note_template(_PSYCHIATRY_NOTE_TEMPLATE, locale=locale)
        except ScribeError:
            return False
        return self._template_supports_option(detail, "ASSESSMENT_AND_PLAN", "split_by_problem")

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
                # API 2026-06-12 renamed the template identifier to *_key. The nested
                # note.template field here is doc-unconfirmed for normalized-data —
                # VERIFY against the live API/Postman; flip back to "template" if Nabla 400s.
                "template_key": _NOTE_TEMPLATE,
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
        """Remove a leading bullet prefix (-, *, •) from a line, after trimming whitespace."""
        stripped = line.strip()
        if re.match(r"^[-•*]\s", stripped):
            return stripped[2:].strip()
        return stripped

    @staticmethod
    def _reformat_plan_as_ap(assessment_text: str, plan_text: str) -> str:
        """Merge separate Assessment and Plan sections into a single A&P block.

        The non-merged psychiatry template returns ASSESSMENT as a bullet list of
        diagnoses/impressions and PLAN as a bullet list of free-form *actions* (it
        does NOT organize the plan by problem, despite the section instruction).

        Downstream, parse_ap_blocks() turns every non-bullet line into a block
        header and split_plan_into_diagnoses() turns each header into a diagnosis
        (ICD-10 matched). So the ASSESSMENT items must be the headers (diagnoses)
        and the PLAN actions must be bullet bodies. Critically, ONLY assessment
        items may become headers — a plan action promoted to a header becomes a
        phantom diagnosis (e.g. "Increase escitalopram to 15 mg"), and a catch-all
        header like "General Plan" gets matched to a bogus ICD-10 too.

        This mirrors the standard (generic) flow, where Nabla's split_by_problem
        already groups each problem with its plan. Here we approximate that
        association: every plan action attaches to the assessment diagnosis it
        overlaps most (argmax of significant-word overlap), so it rides along as
        that diagnosis's body. Actions with no overlap attach to the last
        diagnosis block — never their own header. We produce, e.g.:

            Generalized anxiety disorder
            - Referral to CBT for anxiety and panic
            Panic disorder with episodic attacks
            - Slow breathing techniques during panic
            Generalized anxiety disorder
            - Referral to CBT for anxiety and panic
            - Schedule follow-up in four weeks   (no overlap → first/primary block)
        """
        assessment_items = [item for line in assessment_text.split("\n") if (item := NablaBackend._strip_bullet(line))]
        plan_items = [item for line in plan_text.split("\n") if (item := NablaBackend._strip_bullet(line))]

        # No plan: each assessment line already becomes a header downstream, so
        # return it unchanged (also covers the both-empty case → "").
        if not plan_items:
            return assessment_text

        # No assessment diagnoses to anchor to: emit the plan as header-less
        # bullets. parse_ap_blocks yields one header-less block, which
        # match_condition ignores — so no phantom *named* diagnosis is minted.
        if not assessment_items:
            return "\n".join(f"- {p}" for p in plan_items)

        # Attach each plan action to the assessment diagnosis it overlaps most.
        # No threshold and no catch-all header: actions only ever land as bodies
        # under a real diagnosis. Cross-cutting actions with no diagnosis words
        # (e.g. "Safety plan...", "Follow-up...") have zero overlap and default to
        # the FIRST block — Nabla lists the primary/chief diagnosis first, so an
        # orphan action reads far better there than under an incidental
        # last-listed problem (e.g. a well-controlled comorbidity).
        header_words = [set(NablaBackend._significant_words(a)) for a in assessment_items]
        block_bodies: dict[int, list[str]] = {i: [] for i in range(len(assessment_items))}
        for action in plan_items:
            action_words = set(NablaBackend._significant_words(action))
            best_idx = 0  # zero-overlap actions → first (primary) diagnosis block
            best_score = 0.0
            if action_words:
                for i, words in enumerate(header_words):
                    if not words:
                        continue
                    overlap = len(action_words & words) / min(len(action_words), len(words))
                    if overlap > best_score:
                        best_score = overlap
                        best_idx = i
            block_bodies[best_idx].append(action)

        # Build blocks: assessment diagnosis as header, matched actions as bullets.
        output = [
            "\n".join([header, *(f"- {b}" for b in block_bodies[i])]) for i, header in enumerate(assessment_items)
        ]

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

        # Both branches append a dynamic ROS to the HPI: Nabla picks the
        # clinically-appropriate categories, but the format is constrained so the
        # downstream parsers still work — a standalone "ROS" marker line (for
        # _split_ros) and "Label: findings" rows with 1-3 word names (for
        # parse_ros_subsections). Generic visits get a medical ROS
        # ("System: findings"); psychiatry visits get a psychiatric ROS
        # ("Category: findings"), distinct from the structured Mental Health Exam
        # section.
        if is_psychiatry:
            hpi_custom_instructions = (
                hpi_base_instructions + "\n"
                "End with a complete psychiatric Review of Systems covering whatever psychiatric "
                "categories are clinically appropriate (you choose them), with positive and negative "
                'findings. Output a line containing only "ROS", then each category on its own line as '
                '"Category: findings", with a 1-3 word name. Never exceed three words.'
            )
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
                "vital signs belong in the Vitals section.\n"
                "Organize the exam by system, with each system on its own line as "
                '"System: findings" — a 1-3 word system name (e.g. General, HEENT, '
                "Cardiovascular, Musculoskeletal), then a colon, then the findings. "
                "Never exceed three words in the system name."
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
            #
            # The AP-merged template returns a single ASSESSMENT_AND_PLAN section
            # structured by problem (split_by_problem) — same customization as the
            # generic branch — so the A&P parses through the shared PlanParser path
            # with no local re-merge.
            sections_customization = [
                {"section_key": "ASSESSMENT_AND_PLAN", "style": "BULLET_POINTS", "split_by_problem": True},
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
                        "Complete the Mental Status Exam using ONLY info explicitly stated in the "
                        'transcript. Do not infer, assume, or add boilerplate (e.g., "normal," "WNL"). '
                        "If a category isn't addressed, leave it blank. Output all 11 labels below in "
                        "this exact order, none added, merged, or renamed. To parse it: each category "
                        'on its own line as "Category: findings".\n'
                        "Appearance:\n"
                        "Behavior/Rapport:\n"
                        "Movement:\n"
                        "Speech:\n"
                        "Mood:\n"
                        "Orientation:\n"
                        "Attention/Concentration:\n"
                        "Thought Process:\n"
                        "Thought Content:\n"
                        "Insight:\n"
                        "Judgment:"
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
            "note_template_key": note_template,
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
