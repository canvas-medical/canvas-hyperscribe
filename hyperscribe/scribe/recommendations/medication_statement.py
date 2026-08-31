from __future__ import annotations

import json
from http import HTTPStatus

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.commands.constants import CodeSystems

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal, NoteSection, Transcript
from hyperscribe.scribe.recommendations._medication_match import resolve_medication_detail, sanitize_sig
from hyperscribe.scribe.recommendations._transcript_windows import (
    PRN_PATTERN,
    build_user_prompt,
    collect_windows,
    note_documents_as_needed,
)
from hyperscribe.scribe.recommendations.base import BaseRecommender
from hyperscribe.scribe.recommendations.schemas import MedicationRecommendationList
from hyperscribe.structures.medication_detail import MedicationDetail

_RELEVANT_KEYS = {"current_medications", "history_of_present_illness", "assessment_and_plan", "plan"}

# Appended to the base prompt only when PRN transcript excerpts are actually supplied, so a
# visit with no as-needed language sends exactly the prompt it sent before (KOALA-6644).
_PRN_RECOVERY_PROMPT = (
    " COMPLETENESS: prioritize capturing every medication discussed. Omitting one compromises "
    "patient care, so prefer including a medication you are unsure about over leaving it out. "
    "AS-NEEDED (PRN) ORDERS: the transcript excerpts below are the parts of the visit recording "
    "where as-needed language was heard. The clinical note is a summary and sometimes omits PRN "
    "medications entirely. Extract any medication that appears in the transcript excerpts even "
    "when it is absent from the note sections, and set from_transcript=true for exactly those "
    "entries (false for anything present in the note). Set is_prn=true for as-needed orders. "
    "SAME DRUG, TWO ORDERS: a patient may take the same medication BOTH on a fixed schedule AND "
    "as needed — for example a scheduled nightly dose plus '0.5 mg every four hours as needed for "
    "agitation'. Those are two distinct entries and you must emit both; never merge them, and "
    "never let a scheduled order stand in for an as-needed one. "
    "Do NOT extract a medication from an excerpt where the as-needed phrase does not refer to a "
    "drug at all (e.g. 'follow up as needed', 'call us if needed')."
)

_SYSTEM_PROMPT = (
    "You are a clinical data extraction assistant. "
    "Extract all medications mentioned in the clinical note sections below. "
    "Include medications the patient is currently taking or that were mentioned as part of their medication history. "
    "Do NOT include medications that are being newly prescribed — only include existing/current medications. "
    "For each medication, provide the full name with strength, the sig (directions), "
    "and a comma-separated list of search keywords (synonyms, brand/generic names) for database lookup (max 5). "
    "CRITICAL: preserve the exact strength/dose as stated in the note (e.g. '20 mg'); "
    "never round it or substitute a different strength. "
    "If the note does not state directions for a medication, leave the sig null rather than "
    "guessing or inferring a frequency."
)


def _build_user_prompt(sections: list[NoteSection], windows_text: str = "") -> str:
    return build_user_prompt(sections, windows_text)


def _resolve_medication(
    medication_name: str,
    keywords: str,
    cache: dict[str, list[MedicationDetail]] | None = None,
) -> MedicationDetail | None:
    """Resolve the stated medication to the FDB candidate matching its strength.

    Delegates to the shared strength-aware resolver so the medication-statement
    and prescription recommenders stay in sync.
    """
    return resolve_medication_detail(medication_name, keywords, cache)


class MedicationRecommender(BaseRecommender):
    def recommend(
        self, note: ClinicalNote, client: LlmAnthropic, transcript: Transcript | None = None
    ) -> list[CommandProposal]:
        all_keys = [s.key for s in note.sections]
        log.info(f"MedicationRecommender: note section keys={all_keys}, filtering by {_RELEVANT_KEYS}")
        sections = [s for s in note.sections if s.key.lower() in _RELEVANT_KEYS and s.text.strip()]
        # The note is a Nabla summary and drops PRN medications as the list grows, so pull the
        # as-needed moments straight from the transcript as a recall backstop (KOALA-6644).
        windows_text = collect_windows(transcript, PRN_PATTERN)
        if not sections and not windows_text:
            log.info("MedicationRecommender: no matching sections and no PRN transcript windows, skipping")
            return []

        client.reset_prompts()
        client.set_system_prompt([_SYSTEM_PROMPT + (_PRN_RECOVERY_PROMPT if windows_text else "")])
        client.set_user_prompt([_build_user_prompt(sections, windows_text)])
        client.set_schema(MedicationRecommendationList)

        try:
            response = client.request()
        except Exception:
            log.exception("LLM request failed for medication recommendations")
            return []

        if response.code != HTTPStatus.OK:
            # Do not log response.response: it is derived from the note and may contain PHI.
            log.info(
                f"LLM returned {response.code} for medication recommendations "
                f"(response length: {len(response.response or '')})"
            )
            return []

        try:
            parsed = MedicationRecommendationList.model_validate(json.loads(response.response))
        except Exception:
            # Do not log response.response: it is derived from the note and may contain PHI.
            log.exception(f"Failed to parse medication LLM response (response length: {len(response.response or '')})")
            return []

        lookup_cache: dict[str, list[MedicationDetail]] = {}
        proposals: list[CommandProposal] = []
        for med in parsed.medications:
            resolved = _resolve_medication(med.medication_name, med.keywords, lookup_cache)
            fdb_code: dict[str, str] | None = None
            display = med.medication_name
            if resolved:
                fdb_code = {
                    "system": CodeSystems.FDB,
                    "code": resolved.fdb_code,
                    "display": resolved.description,
                }
                display = resolved.description

            proposals.append(
                CommandProposal(
                    command_type="medication_statement",
                    display=display,
                    data={
                        "medication_text": display,
                        "fdb_code": fdb_code,
                        "sig": sanitize_sig(med.sig),
                    },
                    section_key="_recommended",
                    # No `selected` gating: every recommendation already requires an explicit
                    # provider Accept before insertion (handleInsert filters `accepted`), so a
                    # transcript-recovered medication is never charted on their behalf.
                    # `from_transcript` drives the review-UI badge telling them it came from
                    # what was said rather than from the generated note.
                    #
                    # Provenance has to be a fact we establish, not one the LLM asserts. Two
                    # deterministic corrections, both measured on real notes:
                    #  * windows_text — the model sets the flag even when no excerpts were
                    #    supplied, which would badge a medication as recovered on a note where
                    #    no transcript was ever read.
                    #  * note_documents_as_needed — on partial loss (Nabla drops the PRN from
                    #    CURRENT_MEDICATIONS but keeps it in ASSESSMENT_AND_PLAN) the model
                    #    reports recovery even though the note still carries the order. Roughly
                    #    half the affected notes in the ticket are partial, so this is the
                    #    common case, not an edge.
                    from_transcript=(
                        med.from_transcript
                        and bool(windows_text)
                        and not note_documents_as_needed(sections, med.medication_name)
                    ),
                )
            )
        return proposals
