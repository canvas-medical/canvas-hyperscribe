from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.clients.llms.structures.settings import LlmSettingsAnthropic
from canvas_sdk.commands.commands.questionnaire import QuestionnaireCommand
from canvas_sdk.commands.commands.questionnaire.question import ResponseOption
from canvas_sdk.v1.data.questionnaire import Questionnaire as QuestionnaireModel

from hyperscribe.scribe.backend.models import CommandProposal, Transcript
from hyperscribe.scribe.recommendations.schemas import QuestionnaireFillResult

_MODEL = "claude-sonnet-4-5-20250929"

_TYPE_LABELS = {
    ResponseOption.TYPE_TEXT: "free text (one written answer)",
    ResponseOption.TYPE_INTEGER: "integer (a single whole number)",
    ResponseOption.TYPE_RADIO: "single choice (pick exactly one option)",
    ResponseOption.TYPE_CHECKBOX: "multiple choice (pick every option that applies)",
}

_SYSTEM_PROMPT = """You are a clinical documentation assistant. You draft answers to a structured questionnaire from \
the transcript of a single patient encounter. Your output is a DRAFT for clinician review.

TWO RULES THAT OVERRIDE EVERYTHING ELSE:
1. Evidence or abstain. Answer a question ONLY when the transcript explicitly supports it, and attach the verbatim \
transcript turn(s) as evidence, each with the itemId it came from. If the transcript does not address a question, \
set status "not_assessed" and leave it blank. Never infer, assume, estimate, or round up.
2. "Denied" is not "not discussed". If the respondent explicitly declines or denies, set status "denied" (and for \
single/multiple choice select the option that records the denial). A topic that simply never came up is \
"not_assessed" - never read silence as a denial.

The respondent (patient), not the provider, must be the one affirming or denying. A bare "yes"/"no" is only \
interpretable together with the provider's question, so include both turns as evidence.

BY QUESTION TYPE:
- single choice: set selectedOptionDbid to exactly one option's dbid, or null.
- multiple choice: set selectedOptionDbids to the dbids of every option the respondent affirmed (may be empty).
- free text: set value to a grounded verbatim span, or null.
- integer: set value to the whole number the respondent stated, as a string, or null.

Return one item per question you answer or that is explicitly denied. Omit questions the transcript does not address."""


def _make_settings(api_key: str) -> LlmSettingsAnthropic:
    return LlmSettingsAnthropic(api_key=api_key, model=_MODEL, temperature=0.0, max_tokens=8192)


def load_questionnaire(questionnaire_dbid: int) -> tuple[str, list[dict[str, Any]]]:
    """Return (name, questions) for a questionnaire; each question carries dbid, label, type, options."""
    q_obj = QuestionnaireModel.objects.get(dbid=questionnaire_dbid)
    command = QuestionnaireCommand(questionnaire_id=str(q_obj.id), note_uuid="", command_uuid="")
    questions: list[dict[str, Any]] = []
    for question in command.questions:
        options = [{"dbid": option.dbid, "value": option.name} for option in question.options]
        questions.append({"dbid": int(question.id), "label": question.label, "type": question.type, "options": options})
    return q_obj.name, questions


def _render_transcript(transcript: Transcript) -> str:
    turns = [
        {"item_id": item.item_id, "speaker": item.speaker, "text": item.text}
        for item in transcript.items
        if item.text.strip()
    ]
    return json.dumps(turns, indent=1)


def _render_definition(name: str, questions: list[dict[str, Any]]) -> str:
    rendered = [
        {
            "question_dbid": question["dbid"],
            "prompt": question["label"],
            "type": _TYPE_LABELS.get(question["type"], str(question["type"])),
            "options": [{"option_dbid": o["dbid"], "label": o["value"]} for o in question["options"]],
        }
        for question in questions
    ]
    return json.dumps({"questionnaire": name, "questions": rendered}, indent=1)


def _apply_grounding_gate(result: QuestionnaireFillResult, transcript: Transcript) -> QuestionnaireFillResult:
    # Enforce "evidence or abstain": an answered/denied item whose evidence does not resolve to a real
    # transcript turn is dropped, so an ungrounded guess never reaches the chart.
    valid_item_ids = {item.item_id for item in transcript.items if item.item_id}
    kept = []
    for item in result.items:
        if item.status in ("answered", "denied") and not any(turn.item_id in valid_item_ids for turn in item.evidence):
            log.info(f"questionnaire fill: dropping ungrounded item {item.question_dbid}")
            continue
        kept.append(item)
    return result.model_copy(update={"items": kept})


def fill_questionnaire(
    name: str,
    questions: list[dict[str, Any]],
    transcript: Transcript,
    client: LlmAnthropic,
) -> QuestionnaireFillResult | None:
    """Ask the model to complete the questionnaire from the transcript and return the grounded result."""
    if not transcript.items:
        return None
    user_prompt = "\n".join(
        [
            "TRANSCRIPT (one object per turn):",
            "```json",
            _render_transcript(transcript),
            "```",
            "",
            f"QUESTIONNAIRE DEFINITION '{name}':",
            "```json",
            _render_definition(name, questions),
            "```",
        ]
    )
    client.reset_prompts()
    client.set_system_prompt([_SYSTEM_PROMPT])
    client.set_user_prompt([user_prompt])
    client.set_schema(QuestionnaireFillResult)
    try:
        response = client.request()
    except Exception:
        log.exception("LLM request failed for questionnaire fill")
        return None
    if response.code != HTTPStatus.OK:
        log.info(f"LLM returned {response.code} for questionnaire fill: {response.response}")
        return None
    try:
        result = QuestionnaireFillResult.model_validate(json.loads(response.response))
    except Exception:
        log.exception(f"Failed to parse questionnaire fill LLM response: {response.response}")
        return None
    return _apply_grounding_gate(result, transcript)


def build_fill_command_data(result: QuestionnaireFillResult, questions: list[dict[str, Any]]) -> dict[str, Any]:
    """Map the rich LLM result to the thin questionnaire command payload QuestionnaireParser.build consumes.

    Only answered/denied questions are written; not_assessed questions are omitted and left blank. Denial is
    lossy by design - it is stored as selecting the option the model chose (e.g. a "none"/"not at all" option),
    while the full status and evidence are preserved separately in the audit log.
    """
    by_dbid = {item.question_dbid: item for item in result.items}
    out_questions: list[dict[str, Any]] = []
    for question in questions:
        item = by_dbid.get(question["dbid"])
        if item is None or item.status == "not_assessed":
            continue
        question_type = question["type"]
        options = question["options"]
        if question_type == ResponseOption.TYPE_TEXT:
            if not item.value:
                continue
            responses = [{"value": item.value, "selected": True, "comment": None}]
        elif question_type == ResponseOption.TYPE_INTEGER:
            if item.value is None or not str(item.value).strip():
                continue
            responses = [{"value": str(item.value), "selected": True, "comment": None}]
        elif question_type == ResponseOption.TYPE_RADIO:
            chosen = item.selected_option_dbid
            responses = [{"value": o["value"], "selected": o["dbid"] == chosen, "comment": None} for o in options]
            if not any(r["selected"] for r in responses):
                continue
        else:  # ResponseOption.TYPE_CHECKBOX
            affirmed = set(item.selected_option_dbids or [])
            if not affirmed:
                continue
            responses = [{"value": o["value"], "selected": o["dbid"] in affirmed, "comment": None} for o in options]
        out_questions.append({"dbid": question["dbid"], "responses": responses})
    return {"questionnaire_dbid": result.questionnaire_dbid, "questions": out_questions}


def fill_questionnaire_command(
    questionnaire_dbid: int,
    transcript: Transcript,
    api_key: str,
    client: LlmAnthropic | None = None,
) -> tuple[CommandProposal | None, QuestionnaireFillResult | None]:
    """Load the questionnaire, run the fill, and return (proposal, result); proposal is None when nothing was filled."""
    name, questions = load_questionnaire(questionnaire_dbid)
    if client is None:
        client = LlmAnthropic(_make_settings(api_key))
    result = fill_questionnaire(name, questions, transcript, client)
    if result is None:
        return None, None
    data = build_fill_command_data(result, questions)
    if not data["questions"]:
        return None, result
    proposal = CommandProposal(command_type="questionnaire", display=name, data=data, section_key="_recommended")
    return proposal, result
