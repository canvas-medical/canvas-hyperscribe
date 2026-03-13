from __future__ import annotations

import re
from typing import Any


_STOP_WORDS = frozenset(
    {
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
        "possible",
        "probable",
        "likely",
        "suspected",
    }
)

_PLAN_SECTION_KEYS = frozenset({"assessment_and_plan", "plan"})


class APBlock:
    def __init__(self, header: str, body: list[str] | None = None) -> None:
        self.header = header
        self.body: list[str] = body if body is not None else []


def parse_ap_blocks(text: str) -> list[APBlock]:
    """Split A&P narrative text into header+body blocks.

    Mirrors the JavaScript ``parseAPBlocks`` in soap-group.js.
    """
    if not text:
        return []
    lines = text.split("\n")
    blocks: list[APBlock] = []
    current: APBlock | None = None

    for line in lines:
        trimmed = line.strip()
        if trimmed == "":
            if current is not None:
                blocks.append(current)
                current = None
            continue
        is_bullet = bool(re.match(r"^[-•*]", trimmed))
        if not is_bullet and current is None:
            current = APBlock(header=trimmed)
        elif not is_bullet and current is not None and len(current.body) == 0:
            current.header = current.header + "\n" + trimmed
        elif current is not None:
            current.body.append(trimmed)
        else:
            current = APBlock(header="", body=[trimmed])

    if current is not None:
        blocks.append(current)
    return blocks


def significant_words(text: str) -> list[str]:
    """Extract meaningful words, filtering stop words."""
    cleaned = re.sub(r"[^a-z0-9\s]", "", text.lower())
    return [w for w in cleaned.split() if len(w) > 1 and w not in _STOP_WORDS]


def word_overlap(a: str, b: str) -> float:
    """Calculate word-overlap similarity between two strings."""
    set_a = set(significant_words(a))
    words_b = significant_words(b)
    if not set_a or not words_b:
        return 0.0
    matches = sum(1 for w in words_b if w in set_a)
    return matches / min(len(set_a), len(words_b))


def match_condition(header: str, conditions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Fuzzy-match a block header to a condition from normalized data.

    Two-pass algorithm matching the JavaScript ``matchCondition`` in soap-group.js:
    1. Exact substring match (case-insensitive) in either direction.
    2. Significant-word overlap >= 50%.
    """
    if not conditions or not header:
        return None
    norm = header.lower()

    # Pass 1: exact substring.
    for c in conditions:
        display = (c.get("display") or "").lower()
        if display and (norm in display or display in norm):
            return c
        for code in c.get("coding") or []:
            cd = (code.get("display") or "").lower()
            if cd and (norm in cd or cd in norm):
                return c

    # Pass 2: word overlap.
    best: dict[str, Any] | None = None
    best_score = 0.0
    for c in conditions:
        display = c.get("display") or ""
        scores = [word_overlap(header, display)]
        for code in c.get("coding") or []:
            scores.append(word_overlap(header, code.get("display") or ""))
        score = max(scores)
        if score > best_score:
            best_score = score
            best = c

    return best if best_score >= 0.5 else None


def _serialize_proposal(
    command_type: str,
    display: str,
    data: dict[str, Any],
    section_key: str,
) -> dict[str, Any]:
    return {
        "command_type": command_type,
        "display": display,
        "data": data,
        "selected": True,
        "section_key": section_key,
        "already_documented": False,
    }


def split_plan_into_diagnoses(
    commands: list[dict[str, Any]],
    section_conditions: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Replace the plan/assessment_and_plan command with per-condition diagnose commands.

    Returns ``(updated_commands, unmatched_conditions)`` where *unmatched_conditions*
    are conditions from normalized data that did not match any A&P block header.
    """
    ap_idx = -1
    for i, c in enumerate(commands):
        if c.get("command_type") == "plan" and c.get("section_key") in _PLAN_SECTION_KEYS:
            ap_idx = i
            break

    if ap_idx == -1:
        return commands, []

    ap_cmd = commands[ap_idx]
    codes = section_conditions.get("assessment_and_plan") or section_conditions.get("plan") or []
    blocks = parse_ap_blocks(ap_cmd.get("data", {}).get("narrative", ""))
    if not blocks:
        return commands, []

    diagnose_commands: list[dict[str, Any]] = []
    matched_set: set[int] = set()

    for block in blocks:
        matched = match_condition(block.header, codes)
        icd: dict[str, Any] | None = None
        if matched:
            icd = next((cd for cd in (matched.get("coding") or []) if cd.get("code")), None)
            matched_set.add(id(matched))
        if icd and matched:
            display = icd.get("display") or matched.get("display") or block.header
            icd10_code: str | None = icd["code"]
            icd10_display = icd.get("display") or matched.get("display") or ""
        else:
            display = block.header
            icd10_code = None
            icd10_display = ""
        diagnose_commands.append(
            _serialize_proposal(
                command_type="diagnose",
                display=display,
                data={
                    "icd10_code": icd10_code,
                    "icd10_display": icd10_display,
                    "condition_header": block.header,
                    "today_assessment": "\n".join(block.body),
                    "accepted": bool(icd),
                },
                section_key=ap_cmd.get("section_key", "assessment_and_plan"),
            )
        )

    unmatched = [c for c in codes if id(c) not in matched_set]
    updated = [*commands[:ap_idx], *diagnose_commands, *commands[ap_idx + 1 :]]
    return updated, unmatched
