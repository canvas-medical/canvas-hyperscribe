from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.questionnaire import QuestionnaireCommand
from canvas_sdk.effects import Effect
from canvas_sdk.commands.commands.questionnaire.question import (
    BaseQuestion,
    CheckboxQuestion,
    IntegerQuestion,
    RadioQuestion,
    ResponseOption,
    TextQuestion,
)
from canvas_sdk.v1.data.questionnaire import Questionnaire

from hyperscribe.scribe.backend.models import CommandProposal
from hyperscribe.scribe.commands.base import CommandParser

QUESTION_CLASSES: dict[str, type[BaseQuestion]] = {
    ResponseOption.TYPE_TEXT: TextQuestion,
    ResponseOption.TYPE_INTEGER: IntegerQuestion,
    ResponseOption.TYPE_RADIO: RadioQuestion,
    ResponseOption.TYPE_CHECKBOX: CheckboxQuestion,
}


class QuestionnaireParser(CommandParser):
    """Parser for ad-hoc questionnaire commands in scribe mode."""

    command_type = "questionnaire"
    data_field = None

    def extract(self, text: str) -> CommandProposal | None:
        return None  # questionnaires are only added ad-hoc, never extracted from note text

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        questionnaire_dbid = data["questionnaire_dbid"]
        questionnaire = Questionnaire.objects.get(dbid=questionnaire_dbid)
        cmd = QuestionnaireCommand(
            questionnaire_id=str(questionnaire.id),
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
        # Build question objects manually with responses baked in (same pattern as
        # base_questionnaire.py:command_from_questionnaire) instead of relying on
        # SDK auto-loaded questions, to ensure responses survive originate+commit.
        response_map = {q["dbid"]: q for q in data.get("questions", [])}
        cmd_questions: list[BaseQuestion] = []
        for question in cmd.questions:
            q_data = response_map.get(int(question.id))
            if not q_data:
                cmd_questions.append(question)
                continue
            responses = q_data.get("responses", [])
            options = [ResponseOption(dbid=o.dbid, name=o.name, value=o.value, code=o.code) for o in question.options]
            question_id = str(question.id)
            question_name = question.name
            question_label = question.label
            coding = question.coding

            if question.type == ResponseOption.TYPE_INTEGER:
                q_obj = IntegerQuestion(question_id, question_name, question_label, coding, options)
                val = responses[0]["value"] if responses else 0
                q_obj.add_response(integer=int(val))
            elif question.type == ResponseOption.TYPE_CHECKBOX:
                q_obj = CheckboxQuestion(question_id, question_name, question_label, coding, options)
                for idx, option in enumerate(options):
                    r = responses[idx] if idx < len(responses) else {"selected": False, "comment": ""}
                    q_obj.add_response(
                        option=option,
                        selected=r.get("selected", False),
                        comment=r.get("comment", "") or "",
                    )
            elif question.type == ResponseOption.TYPE_RADIO:
                q_obj = RadioQuestion(question_id, question_name, question_label, coding, options)
                for idx, option in enumerate(options):
                    r = responses[idx] if idx < len(responses) else {"selected": False}
                    if r.get("selected"):
                        q_obj.add_response(option=option)
            else:  # TYPE_TEXT
                q_obj = TextQuestion(question_id, question_name, question_label, coding, options)
                val = responses[0]["value"] if responses else ""
                q_obj.add_response(text=str(val))
            cmd_questions.append(q_obj)

        cmd.questions = cmd_questions
        return cmd

    def to_effects(self, command: _BaseCommand) -> list[Effect]:
        """Questionnaires require originate + edit (not commit) to apply responses."""
        return [command.originate(), command.edit(), command.commit()]
