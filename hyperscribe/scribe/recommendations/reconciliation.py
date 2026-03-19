from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.clients.llms.structures.settings import LlmSettingsAnthropic

from hyperscribe.scribe.recommendations.schemas import ReconciliationResult

_MODEL = "claude-sonnet-4-5-20250929"

_SYSTEM_PROMPT = (
    "You are a clinical documentation assistant. You reconcile a visit template's "
    "default findings with findings extracted from a real patient encounter.\n\n"
    "RULES:\n"
    "1. The template represents BASELINE normal findings. Do NOT change template text "
    "unless the encounter clearly provides DIFFERENT or ADDITIONAL findings for that "
    "specific system.\n"
    "2. If the encounter has specific findings for a system that DIFFER from the "
    "template defaults, use the encounter text and set updated=true.\n"
    "3. If the encounter does NOT mention a system, keep the template text EXACTLY "
    "as-is and set updated=false.\n"
    "4. If the encounter merely confirms what the template already says (e.g. both "
    "say 'denies fever'), keep the template text and set updated=false.\n"
    "5. Preserve the template's system ordering. If the encounter introduces a NEW "
    "system not in the template, append it at the end with updated=true.\n"
    "6. Do NOT invent findings. Only use information present in the inputs.\n"
    "7. Keep the clinical writing style consistent with the template.\n"
    "8. Be CONSERVATIVE: when in doubt, keep the template text unchanged "
    "(updated=false)."
)


def _make_settings(api_key: str) -> LlmSettingsAnthropic:
    return LlmSettingsAnthropic(
        api_key=api_key,
        model=_MODEL,
        temperature=0.0,
        max_tokens=4096,
    )


def _format_sections(sections: list[dict[str, str]]) -> str:
    return "\n".join(f"{s['title']}: {s['text']}" for s in sections)


def _build_user_prompt(
    section_type: str,
    template_sections: list[dict[str, str]],
    encounter_sections: list[dict[str, str]],
) -> str:
    return (
        f"Reconcile the following {section_type} sections.\n\n"
        f"## Template (baseline defaults):\n{_format_sections(template_sections)}\n\n"
        f"## Encounter (from transcript):\n{_format_sections(encounter_sections)}\n\n"
        "Return the reconciled sections. Set updated=true ONLY for systems where "
        "the encounter provides meaningfully different information from the template."
    )


def reconcile_sections(
    template_sections: list[dict[str, str]],
    encounter_sections: list[dict[str, str]],
    api_key: str,
    section_type: str,
) -> list[dict[str, Any]] | None:
    """Merge template defaults with encounter-generated findings via Anthropic.

    Returns sections with 'updated' bool and 'template_text' (original) for comparison,
    or None if reconciliation fails (caller should fall back to encounter sections).
    """
    if not template_sections or not encounter_sections:
        log.info(
            "reconcile %s: skipped — template=%d, encounter=%d sections",
            section_type,
            len(template_sections) if template_sections else 0,
            len(encounter_sections) if encounter_sections else 0,
        )
        return None

    log.info(
        "reconcile %s: template=%d sections, encounter=%d sections — calling LLM",
        section_type,
        len(template_sections),
        len(encounter_sections),
    )

    # Build lookup of original template text by key for diff display.
    template_by_key: dict[str, str] = {s["key"]: s["text"] for s in template_sections}

    client = LlmAnthropic(_make_settings(api_key))
    client.reset_prompts()
    client.set_system_prompt([_SYSTEM_PROMPT])
    client.set_user_prompt([_build_user_prompt(section_type, template_sections, encounter_sections)])
    client.set_schema(ReconciliationResult)

    try:
        response = client.request()
    except Exception:
        log.exception("LLM request failed for %s reconciliation", section_type)
        return None

    if response.code != HTTPStatus.OK:
        log.warning("LLM returned %s for %s reconciliation: %s", response.code, section_type, response.response)
        return None

    try:
        parsed = ReconciliationResult.model_validate(json.loads(response.response))
    except Exception:
        log.exception("Failed to parse %s reconciliation response: %s", section_type, response.response)
        return None

    updated_count = sum(1 for s in parsed.sections if s.updated)
    log.info("reconcile %s: success — %d sections, %d updated", section_type, len(parsed.sections), updated_count)

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
