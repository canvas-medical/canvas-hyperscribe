from __future__ import annotations

import json
from http import HTTPStatus

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.clients.llms.structures.settings import LlmSettingsAnthropic
from canvas_sdk.utils.http import science_http

from hyperscribe.scribe.recommendations.schemas import DiagnosisSuggestionList

_MODEL = "claude-sonnet-4-5-20250929"

_SYSTEM_PROMPT = (
    "You are a clinical coding assistant. "
    "For each condition description provided, suggest 2-3 ICD-10-CM codes that best match. "
    "Return only the ICD-10 codes without dots (e.g. R519 not R51.9)."
)


def _make_settings(api_key: str) -> LlmSettingsAnthropic:
    return LlmSettingsAnthropic(
        api_key=api_key,
        model=_MODEL,
        temperature=0.0,
        max_tokens=2048,
    )


def _validate_code(code: str) -> dict[str, str] | None:
    """Search the science service to confirm an ICD-10 code exists. Return resolved info or None."""
    try:
        resp = science_http.get_json(f"/search/condition/?query={code}&limit=5")
        data = resp.json() or {}
    except Exception:
        log.exception(f"Science search failed for code {code}")
        return None

    clean = code.replace(".", "").upper()
    for r in data.get("results", []):
        result_code = (r.get("icd10_code") or "").replace(".", "").upper()
        if result_code == clean:
            raw = r["icd10_code"]
            formatted = raw[:3] + "." + raw[3:] if len(raw) > 3 else raw
            return {
                "code": raw,
                "display": r.get("icd10_text", ""),
                "formatted_code": formatted,
            }
    return None


def suggest_diagnoses(conditions: list[str], api_key: str) -> dict[str, list[dict[str, str]]]:
    """Call Anthropic LLM to suggest ICD-10 codes for each condition, then validate via science service."""
    if not conditions:
        return {}

    client = LlmAnthropic(_make_settings(api_key))
    client.reset_prompts()
    client.set_system_prompt([_SYSTEM_PROMPT])

    user_prompt = "Suggest ICD-10 codes for each condition:\n"
    for i, cond in enumerate(conditions, 1):
        user_prompt += f"{i}. {cond}\n"
    client.set_user_prompt([user_prompt])
    client.set_schema(DiagnosisSuggestionList)

    try:
        response = client.request()
    except Exception:
        log.exception("LLM request failed for diagnosis suggestions")
        return {}

    if response.code != HTTPStatus.OK:
        log.info(f"LLM returned {response.code} for diagnosis suggestions: {response.response}")
        return {}

    try:
        parsed = DiagnosisSuggestionList.model_validate(json.loads(response.response))
    except Exception:
        log.exception(f"Failed to parse diagnosis suggestion LLM response: {response.response}")
        return {}

    # Build a lookup to map LLM-returned condition_text back to the original input strings.
    originals_lower = {c.strip().lower(): c for c in conditions}

    result: dict[str, list[dict[str, str]]] = {}
    for suggestion in parsed.suggestions:
        validated: list[dict[str, str]] = []
        for code in suggestion.icd10_codes:
            info = _validate_code(code)
            if info:
                validated.append(info)
        if not validated:
            continue

        # Use the original condition string as the key so the frontend can match exactly.
        llm_text = suggestion.condition_text.strip().lower()
        key = originals_lower.get(llm_text)
        if not key:
            # Fallback: partial substring match.
            for orig_lower, orig in originals_lower.items():
                if llm_text in orig_lower or orig_lower in llm_text:
                    key = orig
                    break
        result[key or suggestion.condition_text] = validated

    return result
