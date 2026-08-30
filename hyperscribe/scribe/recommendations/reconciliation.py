"""Merge a visit template's exam scaffold with the findings Nabla generated.

One layer, not two. An earlier version ran a deterministic title-match floor first and
let the LLM refine it, on the theory that the floor was a safe fallback. Measurement
killed that idea: the floor matched 0-80% of systems depending on the template, because
operator templates disagree with each other about names (``CARDIOVASCULAR`` vs
``CARDIAC``) and two of them use a different taxonomy entirely (Neurology's PE names
exam components, Psychiatry's ROS names symptom domains). On a Neurology PE it matched
nothing, emitting seventeen rows that asserted a complete normal neurological exam
nobody performed, ``***`` placeholder and all. A fallback whose output is worse than
failing is not a fallback.

So the LLM owns matching and blending, and safety moved to ``validate_merge`` after the
fact. On failure the caller leaves generation's own findings alone, which is exactly the
behavior that shipped before the merge existed.

Auto-apply is gated per section kind by the ``ScribeExamTemplateMerge`` secret, parsed
here by ``parse_exam_merge_kinds``.
"""

from __future__ import annotations

import json
import re
from http import HTTPStatus
from typing import Any

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.clients.llms.structures.settings import LlmSettingsAnthropic

from hyperscribe.scribe.recommendations.schemas import ReconciliationResult

# Benchmarked 2026-08-30 against the two saved cases, judged by opus-5. opus-4-6 was
# chosen over opus-5 because it needs no client fix: it accepts `temperature` and returns
# tool_use at content[0], where 4.7+ models put a thinking block the SDK client misreads.
#
#                        seed ROS   seed PE   psych ROS   psych MSE   median
#   sonnet-4-5 (old)     40% / 5    15% / 0   -           -           -
#   sonnet-4-5           28% / 3    15% / 0   56% / 1     -           10.7s
#   opus-4-6             17% / 2     2% / 0   56% / 4     15% / 0     11.3s
#   opus-5                -          2% / 0   42% / 0     14% / 0      9.7s
#   (unearned-assertion rate / contradiction count)
#
# Latency is a wash. On the physical exam the prompt rewrite moved nothing (15% -> 15%)
# and the model took it to 2%, so that gain is entirely the model. The open exception is
# psychiatry ROS, where every model sits at 42-56% and opus-4-6 is the worst on
# contradictions; that section's template names symptom domains while Nabla names body
# systems, and no model reconciles that reliably. See the plan's out-of-scope note.
_MODEL = "claude-opus-4-6"

# Section kinds the ``ScribeExamTemplateMerge`` secret can enable. These are the
# plugin's own ``command_type`` names, matching ``_EXAM_KIND_TO_COMMAND_TYPE`` in
# session_view, not the Canvas schema_keys ("exam" / "ros").
SUPPORTED_MERGE_KINDS: frozenset[str] = frozenset({"ros", "physical_exam", "mental_status_exam"})

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Fill-in markers operators leave in templates for a human to complete. Copying one into
# a note is worse than omitting the row: "Alert and oriented to ***" reads as a finding.
_PLACEHOLDER = re.compile(r"\*{2,}|___+|<[^>]{0,40}>|\[[^\]]{0,40}\]")

# Share of an encounter finding's content words that must survive somewhere in the
# output for it to count as preserved. Loose on purpose: the merge legitimately rewords
# and relocates findings, so a strict threshold would reject good work.
_COVERAGE_THRESHOLD = 0.5

_STOPWORDS = frozenset(
    {
        "and",
        "or",
        "no",
        "not",
        "the",
        "a",
        "an",
        "of",
        "in",
        "on",
        "to",
        "with",
        "without",
        "denies",
        "reports",
        "normal",
        "intact",
        "bilaterally",
        "is",
        "are",
        "was",
        "were",
        "all",
        "any",
        "for",
        "at",
        "by",
    }
)


def parse_exam_merge_kinds(raw: str | None) -> set[str]:
    """Parse the ``ScribeExamTemplateMerge`` secret (comma-separated section kinds)
    into a normalized set of kinds whose card offers the provider a merge button. Blank
    entries and unknown names (typos, unsupported kinds) are dropped, so an unset
    or malformed secret turns the feature off everywhere rather than partially on."""
    return {entry.strip().lower() for entry in (raw or "").split(",") if entry.strip()} & SUPPORTED_MERGE_KINDS


def normalize_title(title: str) -> str:
    """Lowercase, drop non-alphanumerics, collapse whitespace.

    Used to match a template system against what the model returned. Matching on the
    raw ``key`` is what broke provenance for every slash-named system: the scaffold
    parser emits ``si/hi`` while the model returns ``si_hi``, the lookup missed, and
    ``template_text`` came back null for ``SI/HI``, ``DELUSIONS/PARANOIA``,
    ``Behavior/Rapport``, ``Attention/Concentration`` and the rest.
    """
    return _NON_ALNUM.sub(" ", (title or "").lower()).strip()


def content_words(text: str) -> set[str]:
    """Meaning-bearing words, for coverage comparison. Shared with the eval harness."""
    words = _NON_ALNUM.sub(" ", (text or "").lower()).split()
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _variants(word: str) -> set[str]:
    """The word plus crude de-pluralizations, so coverage measures content rather than
    inflection. Without this an encounter "No rashes" reads as absent from an output
    saying "rash"."""
    forms = {word}
    if word.endswith("es") and len(word) > 4:
        forms.add(word[:-2])
    if word.endswith("s") and len(word) > 3:
        forms.add(word[:-1])
    return forms


def overlap_ratio(needle: str, haystack: str) -> float:
    """Share of ``needle``'s content words present in ``haystack``, inflection-tolerant."""
    needles = content_words(needle)
    if not needles:
        return 1.0
    pool: set[str] = set()
    for word in content_words(haystack):
        pool |= _variants(word)
    return sum(1 for word in needles if _variants(word) & pool) / len(needles)


_SYSTEM_PROMPT = (
    "You are a clinical documentation assistant. You merge a visit template's default "
    "findings with the findings extracted from a real patient encounter, producing one "
    "exam section. You also get the other sections of the same note.\n\n"
    "The template and the encounter will usually name the same system differently, and "
    "sometimes use different vocabularies entirely (a template may name exam components "
    "like CRANIAL NERVES or symptom domains like SI/HI while the encounter names body "
    "systems). Matching them up is your job.\n\n"
    "RULES:\n"
    "1. The template supplies the section's systems, their names, and their order. Use "
    "the template's name and position for any system it lists. Systems found only in the "
    "encounter go at the end.\n"
    "2. CONSOLIDATE: when the template and the encounter refer to the same system under "
    "different names, emit ONE row for it, using the template's name. Several encounter "
    "rows may fold into one template row.\n"
    "3. BLEND WITHIN A SYSTEM: produce one coherent finding per system. Keep template "
    "language still true of this visit, replace what the encounter contradicts, and fold "
    "in encounter detail the template lacks. Never emit both side by side.\n"
    "4. NEVER WIDEN A DENIAL. This is the most important rule. If the encounter "
    "establishes a NARROWER denial than the template, use the narrower one. Encounter "
    '"No rashes" against template "Denies lumps/bumps, rash, or skin tear" must yield '
    '"No rashes" and NOT the template text, because lumps and skin tears were never '
    "assessed. Do not restore template detail the encounter did not establish.\n"
    "5. NEVER CONTRADICT THE REST OF THE NOTE. You are given the note's other sections. "
    "If a positive finding anywhere in the note refutes a denial you are about to write, "
    "drop or narrow that denial. A denial of leg swelling is wrong when the exam records "
    "ankle edema. A denial of weight loss is wrong when the vitals or the history record "
    "weight loss. A denial of fatigue is wrong when the history records exhaustion.\n"
    "6. A system the encounter did NOT address keeps its template text unchanged. That "
    "is the template doing its job.\n"
    "7. Do NOT invent findings. Use only what the inputs contain.\n"
    "8. Do NOT copy fill-in placeholders. Template text containing ***, ___, or "
    "bracketed blanks means the operator left it for a human; omit that fragment.\n"
    "9. Return plain text with no emphasis markers or asterisks.\n"
    "10. For every row, break the final text into clauses and label each one "
    '"template" (wording from the template alone), "encounter" (from the encounter '
    'alone), or "blended". Every clause of the row\'s text must appear exactly once '
    "across its clauses."
)


def _make_settings(api_key: str) -> LlmSettingsAnthropic:
    return LlmSettingsAnthropic(api_key=api_key, model=_MODEL, temperature=0.0, max_tokens=8192)


def _format_sections(sections: list[dict[str, Any]]) -> str:
    return "\n".join(f"{s.get('title', '')}: {s.get('text', '')}" for s in sections)


def _build_user_prompt(
    section_type: str,
    template_sections: list[dict[str, str]],
    encounter_sections: list[dict[str, str]],
    note_sections: list[dict[str, str]],
    prior_errors: list[str],
) -> str:
    parts = [
        f"Merge the {section_type} for this visit.",
        "",
        f"## Template systems, in order (names and order to use):\n{_format_sections(template_sections)}",
        "",
        f"## Encounter findings (from the transcript):\n{_format_sections(encounter_sections)}",
    ]
    if note_sections:
        other = "\n\n".join(f"### {s.get('key', '')}\n{s.get('text', '')}" for s in note_sections)
        parts += ["", f"## Other sections of this note, for rule 5:\n{other}"]
    if prior_errors:
        parts += [
            "",
            "## Your previous attempt was rejected. Fix these and return a corrected merge:",
            "\n".join(f"- {e}" for e in prior_errors),
        ]
    return "\n".join(parts)


def coverage_gaps(
    sections: list[dict[str, Any]],
    encounter_sections: list[dict[str, str]],
) -> list[str]:
    """Encounter findings that appear to have vanished from the merge. ADVISORY ONLY.

    Deliberately not part of ``validate_merge``, because lexical matching cannot tell a
    genuine drop from a synonym. A measured example: the encounter said "Psychosis: none"
    and the merge covered it with "Denies auditory hallucinations" and "Denies delusional
    thinking", which share no tokens with "psychosis". Rejecting on that would cost the
    note its whole merge and fall back to raw Nabla, which is worse than shipping a merge
    that dropped one negative. So the caller logs and audits these instead.

    The row title joins the text in the comparison. Findings whose text is a bare "none"
    carry no distinguishing words otherwise, which is what made "Homicidal ideation: none"
    read as absent when the merge had in fact folded it into SI/HI.
    """
    # Titles on both sides, or the comparison is asymmetric: an encounter
    # "Respiratory: no trouble breathing" folded into a RESPIRATORY row reads as 40%
    # present when the word "respiratory" is in the needle but only the row texts are
    # searched.
    haystack = " ".join(f"{s.get('title', '')} {s.get('text', '')}" for s in sections)
    gaps: list[str] = []
    for section in encounter_sections:
        needle = f"{section.get('title', '')} {section.get('text', '')}"
        if not content_words(needle):
            continue
        if overlap_ratio(needle, haystack) < _COVERAGE_THRESHOLD:
            gaps.append(str(section.get("title", "")))
    return gaps


def validate_merge(
    sections: list[dict[str, Any]],
    template_sections: list[dict[str, str]],
    encounter_sections: list[dict[str, str]],
) -> list[str]:
    """Structural checks on a candidate merge. Returns error strings, empty when valid.

    Rejection is limited to what code can guarantee without clinical judgement: shape,
    placeholders, ordering, duplicates. Coverage is advisory and lives in
    ``coverage_gaps``; whether a denial is clinically too broad is the prompt's job, and
    the eval harness measures how often that judgement fails.

    ``encounter_sections`` is accepted but unused, kept so the signature reads as the
    full input to a merge and so callers do not have to change if coverage is ever
    promoted to a hard check.
    """
    errors: list[str] = []
    if not sections:
        return ["the merge returned no sections"]

    titles = [normalize_title(str(s.get("title", ""))) for s in sections]
    if len(set(titles)) != len(titles):
        errors.append("duplicate system rows in the output")

    for section in sections:
        text = str(section.get("text", ""))
        if _PLACEHOLDER.search(text):
            errors.append(f"row {section.get('title', '')!r} contains a fill-in placeholder")
        if not str(section.get("title", "")).strip():
            errors.append("a row has no title")

    # Template ordering. The merge may consolidate a template row away, but it must not
    # reshuffle the operator's scaffold.
    template_order = [normalize_title(str(s.get("title", ""))) for s in template_sections]
    present = [t for t in titles if t in template_order]
    expected = [t for t in template_order if t in present]
    if present != expected:
        errors.append("template systems are out of the template's order")

    return errors


def _unwrap(payload: Any) -> Any:
    """Recover a doubly-encoded tool result.

    Some models return ``{"sections": "<the whole JSON object as a string>"}`` instead of
    populating the array, serializing their entire answer into the first field. Measured:
    claude-sonnet-5 did this on 4 of 4 merge calls, and the content inside was perfectly
    good. Without this the model is unusable here for a reason that has nothing to do
    with the quality of its clinical reasoning.
    """
    if not isinstance(payload, dict):
        return payload
    sections = payload.get("sections")
    if not isinstance(sections, str):
        return payload
    try:
        inner = json.loads(sections)
    except (json.JSONDecodeError, ValueError):
        return payload
    if isinstance(inner, dict) and "sections" in inner:
        return inner
    if isinstance(inner, list):
        return {"sections": inner}
    return payload


def _call_llm(
    api_key: str,
    section_type: str,
    template_sections: list[dict[str, str]],
    encounter_sections: list[dict[str, str]],
    note_sections: list[dict[str, str]],
    prior_errors: list[str],
) -> list[dict[str, Any]] | None:
    """One merge attempt. ``None`` on a missing key, non-200, transport error, or
    unparseable response. Provenance is attached here by normalized title."""
    if not api_key:
        log.info("merge %s: skipped - no API key", section_type)
        return None

    template_by_title = {normalize_title(str(s.get("title", ""))): str(s.get("text", "")) for s in template_sections}

    client = LlmAnthropic(_make_settings(api_key))
    client.reset_prompts()
    client.set_system_prompt([_SYSTEM_PROMPT])
    client.set_user_prompt(
        [_build_user_prompt(section_type, template_sections, encounter_sections, note_sections, prior_errors)]
    )
    client.set_schema(ReconciliationResult)

    try:
        response = client.request()
    except Exception:
        log.exception("merge %s: LLM request raised", section_type)
        return None

    if response.code != HTTPStatus.OK:
        log.warning("merge %s: LLM returned %s", section_type, response.code)
        return None

    try:
        parsed = ReconciliationResult.model_validate(_unwrap(json.loads(response.response)))
    except Exception:
        log.exception("merge %s: unparseable response", section_type)
        return None

    result: list[dict[str, Any]] = []
    for section in parsed.sections:
        template_text = template_by_title.get(normalize_title(section.title))
        clauses = [{"text": c.text, "provenance": c.provenance} for c in (section.clauses or [])]
        result.append(
            {
                "key": section.key,
                "title": section.title,
                "text": section.text,
                # Kept for saved summaries written before clauses existed. Derived rather
                # than trusted: the model's own ``updated`` flag disagreed with the text
                # often enough to be worth recomputing.
                "updated": template_text is not None and section.text.strip() != template_text.strip(),
                "template_text": template_text,
                "clauses": clauses,
            }
        )
    return result


def reconcile_sections(
    template_sections: list[dict[str, str]],
    encounter_sections: list[dict[str, str]],
    api_key: str,
    section_type: str,
    *,
    note_sections: list[dict[str, str]] | None = None,
    allow_llm: bool = True,
) -> tuple[list[dict[str, Any]], bool]:
    """Merge the template scaffold with the encounter findings.

    Returns ``(sections, merged)``. ``sections`` is ``[]`` and ``merged`` is ``False``
    when the merge did not happen, which tells the caller to leave generation's own
    output alone. That end state is what shipped before this feature existed, so a
    failure lands somewhere known-good rather than somewhere new.

    One retry, with the validation errors fed back. ``allow_llm=False`` skips the call
    entirely and is the caller's per-request circuit breaker: once one section kind has
    exhausted its attempts, the rest do not each burn the SDK's 30-second ceiling twice.
    """
    if not allow_llm or not template_sections:
        return [], False

    errors: list[str] = []
    for attempt in (1, 2):
        candidate = _call_llm(api_key, section_type, template_sections, encounter_sections, note_sections or [], errors)
        if candidate is None:
            log.warning("merge %s: attempt %d failed to produce a response", section_type, attempt)
            errors = []
            continue
        errors = validate_merge(candidate, template_sections, encounter_sections)
        if not errors:
            gaps = coverage_gaps(candidate, encounter_sections)
            if gaps:
                log.warning("merge %s: encounter findings possibly dropped: %s", section_type, ", ".join(gaps))
            log.info(
                "merge %s: template=%d encounter=%d -> %d sections (attempt %d)",
                section_type,
                len(template_sections),
                len(encounter_sections),
                len(candidate),
                attempt,
            )
            return candidate, True
        log.warning("merge %s: attempt %d rejected: %s", section_type, attempt, "; ".join(errors))

    return [], False
