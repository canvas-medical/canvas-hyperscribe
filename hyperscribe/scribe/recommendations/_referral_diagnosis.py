"""Attach a validated ICD-10 indication to generic referral recommendations.

Referrals are recommended generically (specialty only, no provider). To be
commit-ready a ``refer`` command needs at least one indication (diagnosis code)
— see ``ReferParser.validate``. Rather than generate a new code (and risk an
LLM-hallucinated ICD-10), this links each referral to a code **already present
and validated in the note**, matched by the condition the referral addresses.

Sources are consulted in priority order:

1. ``diagnose`` commands that already carry a populated ``icd10_code`` — the
   note's own coded assessment, the most authoritative source.
2. ``diagnosis_suggestions`` — science-service-validated codes suggested for the
   note's still-uncoded problem headers.
3. ``unmatched_conditions`` — the patient's active problem list codings.

It never fabricates: a referral whose indication matches nothing keeps its
existing (empty) ``diagnosis_codes`` and remains a non-blocking, provider-review
item. The function is pure (operates on plain dicts) so it is trivially
unit-testable.
"""

from __future__ import annotations

from typing import Any


def _normalize(text: str | None) -> str:
    """Normalize a condition/problem string for matching (drop trailing colon, casefold)."""
    return (text or "").strip().rstrip(":").strip().lower()


def _match(indication: str, table: dict[str, str]) -> str | None:
    """Return the code whose condition key matches ``indication`` (exact, then containment)."""
    if not indication:
        return None
    if indication in table:
        return table[indication]
    for key, code in table.items():
        if key and (indication in key or key in indication):
            return code
    return None


def _codes_from_diagnose_commands(commands: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for command in commands or []:
        if command.get("command_type") != "diagnose":
            continue
        data = command.get("data") or {}
        code = (data.get("icd10_code") or "").strip()
        if not code:
            continue
        for key in (_normalize(data.get("condition_header")), _normalize(data.get("icd10_display"))):
            if key:
                result.setdefault(key, code)
    return result


def _codes_from_suggestions(diagnosis_suggestions: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for header, suggestions in (diagnosis_suggestions or {}).items():
        if not suggestions:
            continue
        first = suggestions[0]
        code = first.get("formatted_code") or first.get("code")
        key = _normalize(header)
        if code and key:
            result.setdefault(key, code)
    return result


def _codes_from_unmatched_conditions(unmatched_conditions: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for condition in unmatched_conditions or []:
        code = ""
        display = ""
        for entry in condition.get("coding") or []:
            if entry.get("code"):
                code = entry["code"]
                display = entry.get("display") or ""
                break
        if not code:
            continue
        for key in (_normalize(condition.get("corresponding_note_problem")), _normalize(display)):
            if key:
                result.setdefault(key, code)
    return result


def link_referral_diagnoses(
    recommendations: list[dict[str, Any]],
    commands: list[dict[str, Any]],
    unmatched_conditions: list[dict[str, Any]],
    diagnosis_suggestions: dict[str, Any],
) -> None:
    """Attach a validated ICD-10 code to each generic ``refer`` proposal, in place.

    Mutates ``recommendations``: for every ``refer`` proposal that has an
    ``indication`` but no ``diagnosis_codes`` yet, sets ``data["diagnosis_codes"]``
    to a single best-matched validated code. Leaves proposals untouched when no
    match is found (no fabrication).
    """
    diagnose_codes = _codes_from_diagnose_commands(commands)
    suggestion_codes = _codes_from_suggestions(diagnosis_suggestions)
    unmatched_codes = _codes_from_unmatched_conditions(unmatched_conditions)

    for proposal in recommendations:
        if proposal.get("command_type") != "refer":
            continue
        data = proposal.get("data") or {}
        if data.get("diagnosis_codes"):
            continue
        indication = _normalize(data.get("indication"))
        if not indication:
            continue
        code = (
            _match(indication, diagnose_codes)
            or _match(indication, suggestion_codes)
            or _match(indication, unmatched_codes)
        )
        if code:
            data["diagnosis_codes"] = [code]
            proposal["data"] = data
