"""Layer 2: clause-level judging of a merged exam section.

Row-level provenance is not enough. On the seed case the CARDIAC row is marked
``updated: true`` (the encounter did change it, by adding "palpitations") while still
carrying two unearned template clauses: "shortness of breath with exertion", which the
transcript contradicts, and "swelling in the legs", which the physical exam
contradicts. Counting ``updated: false`` rows finds 2 over-attestations on that note;
splitting rows into clauses finds at least 4.

So each row is decomposed into atomic assertions and every assertion has to earn its
place with a verbatim transcript citation. No citation means unsupported, not
"probably fine" - that default is the whole point.

The model proposes provenance; ``verify_provenance`` then checks the claim against the
actual template and encounter strings and flags disagreements, so a confidently wrong
provenance label does not pass silently.
"""

from __future__ import annotations

from typing import Any

from evaluations.exam_merge.case import ExamMergeCase, MergeKindData
from evaluations.exam_merge.invariants import normalize_title
from evaluations.structures.clause_verdict import (
    PROVENANCE_BLENDED,
    PROVENANCE_ENCOUNTER,
    PROVENANCE_TEMPLATE,
    PROVENANCE_UNKNOWN,
    ClauseVerdict,
)

# The judge must not be the same model that produced the merge, or shared blind spots
# go unreported. The merge runs on Sonnet (see reconciliation._MODEL), so the judge runs
# on Opus. This is deliberately NOT inherited from Constants.ANTHROPIC_REASONING_TEXT,
# both because that constant is pinned to a model that no longer exists and because the
# judge's model is its own concern, not the legacy eval pipeline's.
JUDGE_MODEL = "claude-opus-5"


def schema() -> dict[str, Any]:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "row": {"type": "string", "description": "the section row title this assertion came from"},
                "assertion": {"type": "string", "description": "one atomic clinical assertion"},
                "provenance": {
                    "type": "string",
                    "enum": [PROVENANCE_TEMPLATE, PROVENANCE_ENCOUNTER, PROVENANCE_BLENDED, PROVENANCE_UNKNOWN],
                },
                "supported": {
                    "type": "boolean",
                    "description": "true ONLY if a verbatim transcript quote establishes this assertion",
                },
                "transcript_citation": {
                    "type": "string",
                    "description": "verbatim transcript quote, or empty string when unsupported",
                },
                "contradicted_by": {
                    "type": "string",
                    "description": "SECTION/ROW of the same note that conflicts, or empty string",
                },
                "note": {"type": "string", "description": "one short sentence of reasoning"},
            },
            "required": [
                "row",
                "assertion",
                "provenance",
                "supported",
                "transcript_citation",
                "contradicted_by",
                "note",
            ],
            "additionalProperties": False,
        },
    }


SYSTEM_PROMPT = [
    "You audit clinical documentation for unearned assertions.",
    "",
    "You are given one exam section of a generated note. Each row was produced by merging a "
    "visit template's default findings with findings extracted from a real encounter, so any "
    "row may contain a mix of both. You also get the full visit transcript and the other "
    "sections of the same note.",
    "",
    "For every row, split the text into ATOMIC assertions. One assertion is one clinical claim. "
    '"Denies chest pain, palpitations, or swelling in the legs" is THREE assertions, not one.',
    "",
    "For each assertion decide:",
    "1. provenance: did the wording come from the template, from the encounter, or a blend of both? "
    "You are given both source strings per row.",
    "2. supported: is the assertion established by the transcript? Set true ONLY if you can quote a "
    "verbatim line from the transcript that establishes it, and put that quote in "
    "transcript_citation. If no line establishes it, set supported=false and leave the citation "
    "empty. A plausible or clinically-likely assertion with no transcript line is UNSUPPORTED. "
    "Do not treat the template's presence as evidence.",
    "3. contradicted_by: does any other section of this note conflict with this assertion? If so, "
    "name it as SECTION/ROW. A denial of a symptom that the exam positively found is a "
    "contradiction.",
    "",
    "Be precise about scope. If the transcript establishes a narrow denial and the assertion states "
    "a broader one, the broader part is unsupported. If the patient reported a symptom and the "
    "assertion denies it, that is both unsupported and a contradiction.",
]


def build_user_prompt(
    data: MergeKindData,
    transcript_text: str,
    note_sections: list[dict[str, str]],
) -> list[str]:
    lines = [f"## Section under audit: {data.label}", ""]
    for section in data.final_sections:
        template_text = section.get("template_text")
        lines.append(f"### ROW: {section.get('title', '')}")
        lines.append(f"FINAL TEXT: {section.get('text', '')}")
        lines.append(f"TEMPLATE SOURCE: {template_text if template_text else '(none, this row is encounter-only)'}")
        lines.append("")

    # The encounter output is given whole rather than matched per row. The refinement
    # renames and relocates findings across rows on purpose (Cardiovascular becomes
    # CARDIAC, flat affect moves out of NEUROLOGIC into PSYCH), so a per-row lookup by
    # title returns nothing for exactly the consolidated rows that most need auditing.
    lines.append("## Encounter findings before the merge, for this same section")
    for section in data.encounter_sections:
        lines.append(f"{section.get('title', '')}: {section.get('text', '')}")
    lines.append("")

    other = [s for s in note_sections if str(s.get("key", "")).lower() not in _own_note_keys(data.kind)]
    lines.append("## Other sections of the same note, for contradiction checking")
    for section in other:
        lines.append(f"### {section.get('key', '')}")
        lines.append(str(section.get("text", "")))
        lines.append("")

    lines.append("## Visit transcript")
    lines.append(transcript_text)
    lines.append("")
    lines.append("Return one entry per atomic assertion across every row above.")
    return lines


def _own_note_keys(kind: str) -> frozenset[str]:
    """Note-section keys that ARE the section under audit, excluded from the
    contradiction corpus so a row is never reported as contradicting itself."""
    return {
        "ros": frozenset({"review_of_systems"}),
        "physical_exam": frozenset({"physical_exam"}),
        "mental_status_exam": frozenset({"mental_health_exam", "mental_status_exam"}),
    }[kind]


def verify_provenance(verdicts: list[ClauseVerdict], data: MergeKindData) -> list[ClauseVerdict]:
    """Check each claimed provenance against the actual source strings.

    The model is the only thing that can split clauses, but it should not be the only
    thing deciding where a clause came from. Where an assertion's key words appear in
    the template text and nowhere in the encounter text, provenance is template
    regardless of what the model said, and vice versa. Disagreements are recorded in
    ``note`` rather than silently overwritten, so a reviewer can see the conflict.
    """
    # Template text is per-row, because that is where it lives. Encounter text is taken
    # as a whole for the section: the refinement deliberately moves findings between
    # rows, so a clause is encounter-sourced if it appears anywhere in the pre-merge
    # output, not only in the row that happens to carry it now.
    encounter_text = " ".join(str(s.get("text", "")) for s in data.encounter_sections).lower()
    template_by_title = {
        normalize_title(str(s.get("title", ""))): str(s.get("template_text") or "").lower() for s in data.final_sections
    }

    checked: list[ClauseVerdict] = []
    for verdict in verdicts:
        assertion = verdict.assertion.lower()
        words = {w for w in assertion.replace(",", " ").split() if len(w) > 3}
        if not words:
            checked.append(verdict)
            continue
        template_text = template_by_title.get(normalize_title(verdict.row), "")
        in_template = bool(words) and sum(1 for w in words if w in template_text) / len(words) >= 0.5
        in_encounter = bool(words) and sum(1 for w in words if w in encounter_text) / len(words) >= 0.5

        if in_template and not in_encounter:
            derived = PROVENANCE_TEMPLATE
        elif in_encounter and not in_template:
            derived = PROVENANCE_ENCOUNTER
        elif in_encounter and in_template:
            derived = PROVENANCE_BLENDED
        else:
            checked.append(verdict)
            continue

        if derived == verdict.provenance:
            checked.append(verdict)
            continue
        note = f"{verdict.note} [provenance disputed: model said {verdict.provenance}, strings say {derived}]"
        checked.append(verdict._replace(provenance=derived, note=note.strip()))
    return checked


def judge_metrics(verdicts: list[ClauseVerdict]) -> dict[str, Any]:
    total = len(verdicts)
    unsupported = [v for v in verdicts if not v.supported]
    contradicted = [v for v in verdicts if v.contradicted_by]
    template_unsupported = [v for v in unsupported if v.provenance in (PROVENANCE_TEMPLATE, PROVENANCE_BLENDED)]
    return {
        "assertions": total,
        "unsupported": len(unsupported),
        "unearned_assertion_rate": round(len(unsupported) / total, 3) if total else None,
        "template_sourced_unsupported": len(template_unsupported),
        "contradictions": len(contradicted),
    }


def judge_kind(case: ExamMergeCase, data: MergeKindData, model: str = JUDGE_MODEL) -> list[ClauseVerdict]:
    """One LLM call for one section kind. Imported lazily so Layer 1 never needs LLM config."""
    from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson

    raw = HelperSyntheticJson.generate_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(data, case.transcript_text(), case.note_sections()),
        schema=schema(),
        returned_class=ClauseVerdict,
        model=model,
        # The plugin's Anthropic client cannot talk to 4.7+ models at all: it sends a
        # deprecated `temperature` and reads content[0]["text"], which is a thinking
        # block on those models. See the flag's docstring.
        anthropic_4_7_compat=True,
    )
    verdicts = [v for v in raw if isinstance(v, ClauseVerdict)]
    return verify_provenance(verdicts, data)


def judge_case(case: ExamMergeCase, model: str = JUDGE_MODEL) -> tuple[dict[str, list[ClauseVerdict]], dict[str, Any]]:
    """Judge every evaluable kind. Returns (verdicts by kind, metrics by kind)."""
    verdicts: dict[str, list[ClauseVerdict]] = {}
    metrics: dict[str, Any] = {}
    for data in case.merge_kinds():
        kind_verdicts = judge_kind(case, data, model=model)
        verdicts[data.kind] = kind_verdicts
        metrics[data.kind] = judge_metrics(kind_verdicts)
        metrics[data.kind]["judge_model"] = model
    return verdicts, metrics
