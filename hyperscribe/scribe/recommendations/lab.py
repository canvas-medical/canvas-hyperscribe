from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any

from django.db.models import Q
from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.v1.data.lab import (
    LabPartner,
    LabPartnerTest,
    LabPartnerTestQuestion,
)
from canvas_sdk.v1.data.practicelocation import PracticeLocationSetting

from hyperscribe.scribe.backend.models import (
    ClinicalNote,
    CommandProposal,
    NoteSection,
    Transcript,
)
from hyperscribe.scribe.recommendations.base import BaseRecommender
from hyperscribe.scribe.recommendations.schemas import (
    AoeAnswer,
    AoeAnswerList,
    LabRecommendation,
    LabRecommendationList,
    LabTestEntry,
)

_RELEVANT_KEYS = {"assessment_and_plan", "plan", "history_of_present_illness"}
_PREFERRED_LAB_PARTNER_SETTING = "preferredLabPartner"
_SELECT_TYPES = {"select", "radio"}
_LOW_CONFIDENCE = "low"

_PASS1_SYSTEM_PROMPT = (
    "You are a clinical data extraction assistant. From the clinical note sections below, "
    "extract any lab orders the provider intends to place. Group tests that should be "
    "drawn on the same requisition into one order.\n\n"
    "Do NOT extract:\n"
    "- Lab results being reviewed (those are not new orders)\n"
    "- Imaging or procedures (handled separately)\n"
    "- Tests the provider explicitly declined or deferred\n\n"
    "For each order, provide:\n"
    "- tests: one entry per test with full name + comma-separated keyword synonyms "
    "(CPT name, common abbreviation, panel constituents) for compendium search (max 5 keywords)\n"
    "- fasting_required: true/false if mentioned; null otherwise\n"
    "- comment: brief note (max 128 chars)\n"
    "- reason: the note excerpt explaining the order\n\n"
    "Return empty list if no orders found."
)

_PASS2_SYSTEM_PROMPT = (
    "You extract AOE (Ask On Order Entry) answers from a patient encounter transcript.\n\n"
    "For each AOE question listed below, find the answer if the transcript supports one.\n"
    "- For select/radio questions: return the matching choice's `value`\n"
    "- For text questions: a short, faithful free-text answer\n"
    "- For date questions: ISO date if a clear date is given "
    "(e.g. 'last menstrual period was March 14' \u2192 '2026-03-14')\n"
    "- For boolean/numeric questions: the literal value\n\n"
    "Only return answers you are reasonably confident about. Skip questions with no transcript "
    "support \u2014 DO NOT guess. Mark each answer's confidence honestly: "
    "'high' if directly stated, 'medium' if clearly inferable, 'low' if guessed."
)


def _resolve_lab_partner() -> LabPartner | None:
    """Return the practice's preferred lab partner, falling back to the first active partner."""
    preferred = PracticeLocationSetting.objects.filter(name=_PREFERRED_LAB_PARTNER_SETTING).first()
    if preferred and preferred.value:
        match = LabPartner.objects.filter(name=preferred.value, active=True).first()
        if match:
            return match
    return LabPartner.objects.filter(active=True).first()


def _resolve_tests(
    lab_partner: LabPartner,
    test_entries: list[LabTestEntry],
    cache: dict[str, LabPartnerTest | None] | None = None,
) -> list[LabPartnerTest]:
    """Search the partner's compendium for each test entry; first non-null hit wins."""
    if cache is None:
        cache = {}
    resolved: list[LabPartnerTest] = []
    for entry in test_entries:
        candidates: list[str] = [entry.name] + [k for k in entry.keywords.split(",")]
        for raw in candidates:
            keyword = raw.strip()
            if not keyword:
                continue
            cache_key = keyword.lower()
            if cache_key not in cache:
                cache[cache_key] = (
                    LabPartnerTest.objects.filter(lab_partner=lab_partner)
                    .filter(Q(keywords__icontains=keyword) | Q(order_name__icontains=keyword))
                    .first()
                )
            match = cache[cache_key]
            if match is not None:
                resolved.append(match)
                break
        else:
            log.info(f"LabRecommender: could not resolve test '{entry.name}' for partner {lab_partner.name}")
    return resolved


def _format_transcript(transcript: Transcript) -> str:
    """Format transcript items as 'Speaker: text' lines."""
    lines: list[str] = []
    for item in transcript.items:
        speaker = item.speaker.capitalize() if item.speaker else "Unknown"
        lines.append(f"{speaker}: {item.text}")
    return "\n".join(lines)


def _build_pass1_user_prompt(sections: list[NoteSection]) -> str:
    parts: list[str] = []
    for section in sections:
        parts.append(f"## {section.title}\n{section.text}")
    return "\n\n".join(parts)


def _build_pass2_user_prompt(
    transcript_text: str,
    test_questions: dict[str, tuple[str, list[LabPartnerTestQuestion]]],
) -> str:
    """Build the AOE answer-extraction prompt with the full transcript and per-test question blocks."""
    parts: list[str] = ["## Transcript\n", transcript_text, "", "## Lab Tests with AOE Questions"]
    for test_code, (test_name, questions) in test_questions.items():
        parts.append(f"\n### {test_name} (order_code: {test_code})")
        for question in questions:
            parts.append(f"- code: {question.code}")
            parts.append(f"  body: {question.body}")
            parts.append(f"  type: {question.type}")
            parts.append(f"  required: {question.required}")
            choices = list(question.choices.all())
            if choices:
                parts.append("  choices:")
                for choice in choices:
                    parts.append(f"    - label: {choice.label}, value: {choice.value}")
    return "\n".join(parts)


def _run_pass2(
    client: LlmAnthropic,
    transcript_text: str,
    test_questions: dict[str, tuple[str, list[LabPartnerTestQuestion]]],
    valid_keys: set[tuple[str, str]],
) -> dict[tuple[str, str], AoeAnswer]:
    """Run the AOE extraction LLM call. Returns a map of (test_order_code, question_code) -> answer."""
    client.reset_prompts()
    client.set_system_prompt([_PASS2_SYSTEM_PROMPT])
    client.set_user_prompt([_build_pass2_user_prompt(transcript_text, test_questions)])
    client.set_schema(AoeAnswerList)

    try:
        response = client.request()
    except Exception:
        log.exception("LLM request failed for lab AOE extraction")
        return {}

    if response.code != HTTPStatus.OK:
        log.info(f"LLM returned {response.code} for lab AOE extraction: {response.response}")
        return {}

    try:
        parsed = AoeAnswerList.model_validate(json.loads(response.response))
    except Exception:
        log.exception(f"Failed to parse AOE answer response: {response.response}")
        return {}

    answers: dict[tuple[str, str], AoeAnswer] = {}
    for answer in parsed.answers:
        if answer.confidence == _LOW_CONFIDENCE:
            continue
        key = (answer.test_order_code, answer.question_code)
        if key in valid_keys:
            answers[key] = answer
    return answers


def _build_aoe_payload(
    resolved_tests: list[LabPartnerTest],
    test_questions: dict[str, tuple[str, list[LabPartnerTestQuestion]]],
    aoe_answers_by_key: dict[tuple[str, str], AoeAnswer],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (aoe_answers, missing_required_aoes) lists for the proposal data."""
    aoe_answers: list[dict[str, Any]] = []
    missing_required: list[dict[str, Any]] = []
    for test in resolved_tests:
        entry = test_questions.get(test.order_code)
        if entry is None:
            continue
        _, questions = entry
        for question in questions:
            answer = aoe_answers_by_key.get((test.order_code, question.code))
            if answer is None:
                if question.required:
                    missing_required.append(
                        {
                            "test_order_code": test.order_code,
                            "question_code": question.code,
                            "question_body": question.body,
                        },
                    )
                continue
            answer_label: str | None = None
            if question.type in _SELECT_TYPES:
                for choice in question.choices.all():
                    if choice.value == answer.answer:
                        answer_label = choice.label
                        break
            aoe_answers.append(
                {
                    "test_order_code": test.order_code,
                    "question_code": question.code,
                    "answer_value": answer.answer,
                    "answer_label": answer_label,
                    "question_body": question.body,
                    "confidence": answer.confidence,
                },
            )
    return aoe_answers, missing_required


class LabRecommender(BaseRecommender):
    def recommend(
        self,
        note: ClinicalNote,
        client: LlmAnthropic,
        transcript: Transcript | None = None,
    ) -> list[CommandProposal]:
        sections = [s for s in note.sections if s.key.lower() in _RELEVANT_KEYS and s.text.strip()]
        if not sections:
            log.info("LabRecommender: no relevant sections, skipping")
            return []

        lab_partner = _resolve_lab_partner()
        if lab_partner is None:
            log.info("LabRecommender: no lab partner resolvable, skipping")
            return []

        client.reset_prompts()
        client.set_system_prompt([_PASS1_SYSTEM_PROMPT])
        client.set_user_prompt([_build_pass1_user_prompt(sections)])
        client.set_schema(LabRecommendationList)

        try:
            response = client.request()
        except Exception:
            log.exception("LLM request failed for lab order extraction")
            return []

        if response.code != HTTPStatus.OK:
            log.info(f"LLM returned {response.code} for lab order extraction: {response.response}")
            return []

        try:
            parsed = LabRecommendationList.model_validate(json.loads(response.response))
        except Exception:
            log.exception(f"Failed to parse lab order response: {response.response}")
            return []

        if not parsed.orders:
            return []

        cache: dict[str, LabPartnerTest | None] = {}
        order_resolutions: list[tuple[LabRecommendation, list[LabPartnerTest]]] = []
        for order in parsed.orders:
            tests = _resolve_tests(lab_partner, order.tests, cache)
            if tests:
                order_resolutions.append((order, tests))

        if not order_resolutions:
            return []

        unique_tests: dict[int, LabPartnerTest] = {}
        for _, tests in order_resolutions:
            for test in tests:
                unique_tests.setdefault(test.dbid, test)
        all_resolved_tests = list(unique_tests.values())

        questions = list(
            LabPartnerTestQuestion.objects.filter(
                lab_partner_test__in=all_resolved_tests,
            ).prefetch_related("choices"),
        )

        test_questions: dict[str, tuple[str, list[LabPartnerTestQuestion]]] = {}
        valid_keys: set[tuple[str, str]] = set()
        for question in questions:
            test = question.lab_partner_test
            entry = test_questions.setdefault(test.order_code, (test.order_name, []))
            entry[1].append(question)
            valid_keys.add((test.order_code, question.code))

        aoe_answers_by_key: dict[tuple[str, str], AoeAnswer] = {}
        if test_questions and transcript and transcript.items:
            transcript_text = _format_transcript(transcript)
            aoe_answers_by_key = _run_pass2(client, transcript_text, test_questions, valid_keys)

        proposals: list[CommandProposal] = []
        for order, resolved_tests in order_resolutions:
            aoe_answers, missing_required = _build_aoe_payload(
                resolved_tests,
                test_questions,
                aoe_answers_by_key,
            )
            display = ", ".join(t.order_name for t in resolved_tests)
            proposals.append(
                CommandProposal(
                    command_type="lab_order",
                    display=display,
                    data={
                        "lab_partner": str(lab_partner.id),
                        "lab_partner_name": lab_partner.name,
                        "tests_order_codes": [t.order_code for t in resolved_tests],
                        "test_names": [t.order_name for t in resolved_tests],
                        "fasting_required": bool(order.fasting_required),
                        "comment": (order.comment or "")[:128] or None,
                        "diagnosis_codes": [],
                        "diagnosis_displays": [],
                        "aoe_answers": aoe_answers,
                        "missing_required_aoes": missing_required,
                        "reason": order.reason,
                    },
                    section_key="_recommended",
                ),
            )
        return proposals
