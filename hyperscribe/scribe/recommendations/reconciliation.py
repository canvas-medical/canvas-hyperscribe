"""Merge a visit template's exam scaffold with the findings Nabla generated.

Two layers, deliberately. ``merge_sections`` is pure Python and always runs: it
matches systems by normalized title, lets the encounter win where it has
something to say, and keeps the template default where it does not.
``refine_sections`` then hands that draft to Anthropic for the judgment the
mechanical match cannot do: blending template language with encounter findings
inside one system, and consolidating rows that name the same system differently
("Cardiovascular" vs "CV").

The deterministic layer is the floor. When Anthropic is unreachable, misconfigured,
or slow, the provider still gets a merged exam with full system coverage; only the
blending and the fuzzy consolidation are missing. ``reconcile_sections`` reports
which of the two produced the result so the caller can record it.

Auto-apply is gated per section kind by the ``ScribeExamTemplateMerge`` secret,
parsed here by ``parse_exam_merge_kinds``.
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

_MODEL = "claude-sonnet-4-5-20250929"

# Section kinds the ``ScribeExamTemplateMerge`` secret can enable. These are the
# plugin's own ``command_type`` names, matching ``_EXAM_KIND_TO_COMMAND_TYPE`` in
# session_view, not the Canvas schema_keys ("exam" / "ros").
SUPPORTED_MERGE_KINDS: frozenset[str] = frozenset({"ros", "physical_exam", "mental_status_exam"})

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def parse_exam_merge_kinds(raw: str | None) -> set[str]:
    """Parse the ``ScribeExamTemplateMerge`` secret (comma-separated section kinds)
    into a normalized set of kinds whose template auto-merges at generation. Blank
    entries and unknown names (typos, unsupported kinds) are dropped, so an unset
    or malformed secret turns the feature off everywhere rather than partially on."""
    return {entry.strip().lower() for entry in (raw or "").split(",") if entry.strip()} & SUPPORTED_MERGE_KINDS


def _normalize_title(title: str) -> str:
    """Lowercase, drop non-alphanumerics, collapse whitespace. Used only for matching
    a template system against an encounter system; the template's own casing and
    punctuation are what get displayed."""
    return _NON_ALNUM.sub(" ", (title or "").lower()).strip()


def merge_sections(
    template_sections: list[dict[str, str]],
    encounter_sections: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Deterministically merge template defaults with encounter findings.

    Template ordering wins. A template system the encounter also covers takes the
    encounter text and is marked ``updated=True``; one the encounter did not cover
    keeps its default text and is marked ``updated=False``. Encounter systems with
    no template counterpart are appended in their original order.

    ``template_text`` carries the original default on every template-derived row so
    the UI can badge it and the "Remove template defaults" toggle can count it. It
    is ``None`` on encounter-only rows, which have no template origin.

    A matched-but-EMPTY encounter section counts as not covered, so the template
    default stands. This is load-bearing for the Mental Status Exam: its Nabla
    prompt emits all 11 category labels even when a category was never addressed,
    so ``parse_ros_subsections`` returns those with ``text=""``. Without this rule
    the MSE prefill would depend on whether the LLM refinement happened to run.
    Physical Exam and ROS are unaffected, since Nabla only lists systems it has
    findings for.

    Passing ``[]`` for ``encounter_sections`` returns every template row unchanged
    with ``updated=False``, which is exactly the "Nabla produced nothing for this
    section" case. No separate injection branch is needed.
    """
    by_title: dict[str, dict[str, str]] = {}
    for section in encounter_sections:
        key = _normalize_title(section.get("title", ""))
        if key and key not in by_title:
            by_title[key] = section

    merged: list[dict[str, Any]] = []
    consumed: set[str] = set()
    for section in template_sections:
        template_text = section.get("text", "")
        title = section.get("title", "")
        normalized = _normalize_title(title)
        encounter = by_title.get(normalized)
        encounter_text = (encounter or {}).get("text", "").strip()
        if encounter is not None:
            consumed.add(normalized)
        if encounter_text:
            merged.append(
                {
                    "key": section.get("key", ""),
                    "title": title,
                    "text": encounter_text,
                    "updated": True,
                    "template_text": template_text,
                }
            )
        else:
            merged.append(
                {
                    "key": section.get("key", ""),
                    "title": title,
                    "text": template_text,
                    "updated": False,
                    "template_text": template_text,
                }
            )

    for section in encounter_sections:
        normalized = _normalize_title(section.get("title", ""))
        if normalized in consumed:
            continue
        consumed.add(normalized)
        text = section.get("text", "").strip()
        if not text:
            continue
        merged.append(
            {
                "key": section.get("key", ""),
                "title": section.get("title", ""),
                "text": text,
                "updated": True,
                "template_text": None,
            }
        )

    return merged


_SYSTEM_PROMPT = (
    "You are a clinical documentation assistant. You are given a DRAFT merge of a "
    "visit template's default findings with the findings extracted from a real "
    "patient encounter, plus both of the sources it was built from. The draft was "
    "produced by an exact system-name match, so it is structurally correct but "
    "clinically naive. Your job is to improve it.\n\n"
    "RULES:\n"
    "1. The template represents BASELINE normal findings. Do NOT change template text "
    "unless the encounter clearly provides DIFFERENT or ADDITIONAL findings for that "
    "specific system.\n"
    "2. BLEND WITHIN A SYSTEM: when the template and the encounter both speak to the "
    "same system, produce ONE coherent finding for it. Keep the template language "
    "that is still true of this visit, replace any template language the encounter "
    "contradicts, and fold in encounter detail the template does not have. Do not "
    "emit the two side by side, and do not simply discard one of them. Set "
    "updated=true for any system whose text you changed from the template.\n"
    "3. If the encounter does NOT mention a system, keep the template text EXACTLY "
    "as-is and set updated=false.\n"
    "4. CONSOLIDATE DUPLICATE SYSTEMS: the draft was built by exact name matching, so "
    "the same system may appear twice under different names (e.g. 'Cardiovascular' "
    "from the template and 'CV' or 'Heart' from the encounter). Merge those into a "
    "single entry using the TEMPLATE's name and position, blending the text per rule 2.\n"
    "5. Preserve the template's system ordering. Systems that exist only in the "
    "encounter stay at the end, in the order the draft has them, with updated=true.\n"
    "6. Do NOT invent findings. Only use information present in the inputs.\n"
    "7. Keep the clinical writing style consistent with the template.\n"
    "8. Be CONSERVATIVE: when in doubt, keep the template text unchanged "
    "(updated=false).\n"
    "9. Return plain text. Do NOT add emphasis markers, asterisks, or any other "
    "formatting to the findings."
)


def _make_settings(api_key: str) -> LlmSettingsAnthropic:
    return LlmSettingsAnthropic(
        api_key=api_key,
        model=_MODEL,
        temperature=0.0,
        max_tokens=4096,
    )


def _format_sections(sections: list[dict[str, Any]]) -> str:
    return "\n".join(f"{s.get('title', '')}: {s.get('text', '')}" for s in sections)


def _build_user_prompt(
    section_type: str,
    merged: list[dict[str, Any]],
    template_sections: list[dict[str, str]],
    encounter_sections: list[dict[str, str]],
) -> str:
    return (
        f"Improve this draft {section_type} merge.\n\n"
        f"## Draft merge (exact-name match, needs your judgement):\n{_format_sections(merged)}\n\n"
        f"## Template (baseline defaults):\n{_format_sections(template_sections)}\n\n"
        f"## Encounter (from transcript):\n{_format_sections(encounter_sections)}\n\n"
        "Return the improved sections. Set updated=true ONLY for systems whose text "
        "differs from the template default."
    )


def refine_sections(
    merged: list[dict[str, Any]],
    template_sections: list[dict[str, str]],
    encounter_sections: list[dict[str, str]],
    api_key: str,
    section_type: str,
) -> list[dict[str, Any]] | None:
    """Ask Anthropic to improve the deterministic merge.

    Returns ``None`` on a missing key, a non-200, a transport exception, or an
    unparseable response. The caller keeps the deterministic merge in that case,
    so this failing degrades quality rather than losing the merge.
    """
    if not api_key:
        log.info("refine %s: skipped - no API key", section_type)
        return None
    if not merged:
        return None

    template_by_key: dict[str, str] = {s.get("key", ""): s.get("text", "") for s in template_sections}

    client = LlmAnthropic(_make_settings(api_key))
    client.reset_prompts()
    client.set_system_prompt([_SYSTEM_PROMPT])
    client.set_user_prompt([_build_user_prompt(section_type, merged, template_sections, encounter_sections)])
    client.set_schema(ReconciliationResult)

    try:
        response = client.request()
    except Exception:
        log.exception("LLM request failed for %s refinement", section_type)
        return None

    if response.code != HTTPStatus.OK:
        log.warning("LLM returned %s for %s refinement", response.code, section_type)
        return None

    try:
        parsed = ReconciliationResult.model_validate(json.loads(response.response))
    except Exception:
        log.exception("Failed to parse %s refinement response", section_type)
        return None

    if not parsed.sections:
        log.warning("LLM returned no sections for %s refinement", section_type)
        return None

    return [
        {
            "key": s.key,
            "title": s.title,
            "text": s.text,
            "updated": s.updated,
            "template_text": template_by_key.get(s.key),
        }
        for s in parsed.sections
    ]


def reconcile_sections(
    template_sections: list[dict[str, str]],
    encounter_sections: list[dict[str, str]],
    api_key: str,
    section_type: str,
    *,
    allow_refine: bool = True,
) -> tuple[list[dict[str, Any]], bool]:
    """Merge template defaults with encounter findings, refined by the LLM when possible.

    Returns ``(sections, refined)``. ``sections`` is never ``None``: the
    deterministic merge always produces a result, and the LLM only replaces it on
    success. ``refined`` says which layer produced the returned sections, so the
    caller can emit it to the audit log.

    ``allow_refine=False`` skips the LLM call entirely. The caller uses this as a
    per-request circuit breaker: once one section kind has failed to refine, the
    remaining kinds take the deterministic merge rather than each burning the
    SDK's 30-second HTTP timeout.
    """
    merged = merge_sections(template_sections, encounter_sections)
    log.info(
        "reconcile %s: template=%d, encounter=%d, merged=%d sections",
        section_type,
        len(template_sections),
        len(encounter_sections),
        len(merged),
    )
    if not allow_refine:
        return merged, False

    refined = refine_sections(merged, template_sections, encounter_sections, api_key, section_type)
    if refined is None:
        return merged, False
    return refined, True
