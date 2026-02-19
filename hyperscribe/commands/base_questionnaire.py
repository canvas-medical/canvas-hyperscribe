import json
from typing import Type

from canvas_sdk.commands.commands.questionnaire import QuestionnaireCommand
from canvas_sdk.commands.commands.questionnaire.question import (
    TextQuestion,
    IntegerQuestion,
    CheckboxQuestion,
    ResponseOption,
    RadioQuestion,
    BaseQuestion,
)
from logger import log

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.line import Line
from hyperscribe.structures.question import Question
from hyperscribe.structures.question_type import QuestionType
from hyperscribe.structures.question_used import QuestionUsed
from hyperscribe.structures.questionnaire import Questionnaire as QuestionnaireDefinition
from hyperscribe.structures.response import Response


class BaseQuestionnaire(Base):
    def include_skipped(self) -> bool:
        raise NotImplementedError

    def sdk_command(self) -> Type[QuestionnaireCommand]:
        raise NotImplementedError

    def additional_instructions(self) -> list[str]:
        return []

    def skipped_field_instruction(self) -> str:
        return (
            "CRITICAL: If a question already has 'skipped' set to 'false', you MUST keep it as 'false'. "
            "Never change 'skipped' from 'false' back to 'true' or 'null'. "
            "You may only change 'skipped' from 'true' to 'false' if the question is clearly addressed "
            "in the transcript. Questions that are already enabled must stay enabled."
        )

    @classmethod
    def staged_command_extract(cls, data: dict) -> CodedItem | None:
        questionnaire = ((data.get("questionnaire") or {}).get("extra")) or {}
        if not questionnaire:
            return None

        questions: list[Question] = []
        for question in questionnaire.get("questions", []):
            question_type = QuestionType(question["type"])

            default = {}
            if question_type == QuestionType.TYPE_CHECKBOX:
                default = {"comment": ""}
            elif question_type == QuestionType.TYPE_TEXT:
                default = {"value": ""}

            options = {
                str(o["pk"]): {"dbid": o["pk"], "value": o["label"], "selected": False} | default
                for o in question["options"]
            }

            answers = data.get(question["name"])  # should be data.get(f'question-{question["pk"]}')
            if isinstance(answers, list):
                for response in answers:
                    for key in options.keys():
                        if options[key]["value"] == response["text"]:
                            options[key]["selected"] = response["selected"]
                            options[key]["comment"] = response["comment"]
                            break
            elif isinstance(answers, int) and question_type == QuestionType.TYPE_RADIO:
                options[str(answers)]["selected"] = True
            elif isinstance(answers, int) and question_type == QuestionType.TYPE_INTEGER:
                for key in options.keys():
                    options[key]["value"] = answers
            elif isinstance(answers, str):
                for key in options.keys():
                    options[key]["value"] = answers

            skipped = data.get(f"skip-{question['pk']}")
            if skipped is not None:
                skipped = not skipped  # the current boolean is inverted in home-app

            questions.append(
                Question(
                    dbid=question["pk"],
                    label=question["label"],
                    type=question_type,
                    skipped=skipped,  # true/false/none
                    responses=[Response.load_from(option) for option in options.values()],
                ),
            )
        result = QuestionnaireDefinition(name=questionnaire["name"], dbid=questionnaire["pk"], questions=questions)
        return CodedItem(label=json.dumps(result.to_json()), code="", uuid="")

    @classmethod
    def json_schema_questionnaire(cls, include_skipped: bool) -> dict:
        properties = {
            "questionId": {"type": "integer"},
            "question": {"type": "string"},
            "questionType": {"type": "string", "enum": list(QuestionType.llm_readable().values())},
            "responses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "responseId": {"type": "integer"},
                        "value": {"type": "string"},
                        "selected": {"type": "boolean"},
                        "comment": {"type": "string", "description": "any relevant information expanding the answer"},
                    },
                    "required": ["responseId", "value", "selected"],
                },
            },
        }
        if include_skipped:
            properties |= {
                "skipped": {
                    "type": ["boolean", "null"],
                    "description": "indicates if the question is skipped or used",
                }
            }

        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {"type": "object", "properties": properties, "required": list(properties.keys())},
        }

    @classmethod
    def json_schema_question_list(cls) -> dict:
        properties = {
            "questionId": {"type": "integer"},
            "question": {"type": "string"},
            "usedInTranscript": {"type": "boolean"},
        }
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": properties,
                "required": list(properties.keys()),
            },
        }

    @classmethod
    def relevant_question_ids(
        cls,
        discussion: list[Line],
        chatter: LlmBase,
        questionnaire: QuestionnaireDefinition,
    ) -> list[int]:
        result: list[int] = [q.dbid for q in questionnaire.questions]
        if len(result) > Constants.QUESTIONNAIRE_1STEP_MAX_QUESTIONS:
            # which questions of the questionnaire are relevant based on the transcript?
            result = []
            system_prompt = [
                "The conversation is in the context of a clinical encounter between patient and licensed "
                "healthcare provider.",
                f"The healthcare provider is editing a questionnaire '{questionnaire.name}', potentially without "
                f"notifying the patient to prevent biased answers.",
                "The user will submit two JSON Markdown blocks:",
                "- the questions of the questionnaire,",
                "- a partial transcript of the visit of a patient with the healthcare provider.",
                "",
                "Your task is to identifying from the transcript which questions the healthcare provider is "
                "referencing, if any.",
                "Since this is only a part of the transcript, it may have no reference to the questionnaire at all.",
                "",
                "Your response must be the updated JSON Markdown block of the list of questions.",
                "",
            ]
            transcript = json.dumps([line.to_json() for line in discussion], indent=1)

            user_prompt = [
                "Below is a part of the transcript between the patient and the healthcare provider:",
                "```json",
                transcript,
                "```",
                "",
                f"The questionnaire '{questionnaire.name}' has the following questions:",
                "```json",
                json.dumps(questionnaire.used_questions()),
                "```",
                "",
                "Return this JSON in a Markdown block after setting to 'true' the questions "
                "referenced in the transcript.",
                "",
            ]
            schemas = [cls.json_schema_question_list()]
            chatter.set_system_prompt(system_prompt)
            chatter.set_user_prompt(user_prompt)
            response = chatter.chat(schemas)
            if not response.has_error:
                result = [q.dbid for q in QuestionUsed.load_from_llm(response.content[0]) if q.used]
        return result

    def update_from_transcript(
        self,
        discussion: list[Line],
        instruction: Instruction,
        chatter: LlmBase,
    ) -> QuestionnaireDefinition | None:
        # TODO identify the questionnaire on the fly and provide the actual definition
        try:
            json_data = json.loads(instruction.information)
        except json.JSONDecodeError:
            return None
        questionnaire = QuestionnaireDefinition.load_from(json_data)
        if used_question_ids := self.relevant_question_ids(discussion, chatter, questionnaire):
            include_skipped = self.include_skipped()
            # what are the updates, if any?
            system_prompt = [
                "The conversation is in the context of a clinical encounter between patient and licensed "
                "healthcare provider.",
                f"The healthcare provider is editing a questionnaire '{questionnaire.name}', potentially without "
                f"notifying the patient to prevent biased answers.",
                "The user will submit two JSON Markdown blocks:",
                "- the current state of the questionnaire,",
                "- a partial transcript of the visit of a patient with the healthcare provider.",
                "",
                "Your task is to identifying from the transcript which questions the healthcare provider is "
                "referencing and what responses the patient is giving.",
                "Since this is only a part of the transcript, it may have no reference to the questionnaire at all.",
                "",
                "Your response must be the JSON Markdown block of the questionnaire, with all the necessary "
                "changes to reflect the transcript content.",
                "",
            ] + self.additional_instructions()
            transcript = json.dumps([line.to_json() for line in discussion], indent=1)

            user_prompt = [
                "Below is a part of the transcript between the patient and the healthcare provider:",
                "```json",
                transcript,
                "```",
                "",
                f"The questionnaire '{questionnaire.name}' is currently as follow,:",
                "```json",
                json.dumps(questionnaire.for_llm_limited_to(include_skipped, used_question_ids)),
                "```",
                "",
                "Your task is to replace the values of the JSON object as necessary.",
                "Since the current questionnaire's state is based on previous parts of the transcript, "
                "the changes should be based on explicit information only.",
            ]
            if include_skipped:
                user_prompt.append(self.skipped_field_instruction())
            user_prompt.append("")
            schemas = [self.json_schema_questionnaire(include_skipped)]
            chatter.reset_prompts()
            chatter.set_system_prompt(system_prompt)
            chatter.set_user_prompt(user_prompt)
            response = chatter.chat(schemas)
            if not response.has_error:
                updated = questionnaire.update_from_llm_with(response.content[0])
                return self.post_process_questionnaire(questionnaire, updated)
        return None

    def post_process_questionnaire(
        self,
        original: QuestionnaireDefinition,
        updated: QuestionnaireDefinition,
    ) -> QuestionnaireDefinition:
        """Prevent the LLM from clearing existing findings or disabling questions."""
        original_by_id = {q.dbid: q for q in original.questions}
        fixed_questions: list[Question] = []

        for upd_ques in updated.questions:
            orig_ques = original_by_id.get(upd_ques.dbid)
            if orig_ques is None:
                fixed_questions.append(upd_ques)
                continue

            # Never disable a question that was already enabled - normalize None to False,
            # and never let the LLM flip an enabled question to skipped
            skipped = upd_ques.skipped
            if orig_ques.skipped is not True and upd_ques.skipped is True:
                log.info(f"[POST-PROCESS] Preserving enabled state for question {upd_ques.dbid} ({upd_ques.label})")
                skipped = orig_ques.skipped
            if skipped is None:
                skipped = False

            # Preserve non-empty text - never let the LLM clear existing findings
            fixed_responses: list[Response] = []
            for upd_resp, orig_resp in zip(upd_ques.responses, orig_ques.responses):
                value = upd_resp.value
                if (
                    isinstance(orig_resp.value, str)
                    and orig_resp.value.strip()
                    and (not isinstance(upd_resp.value, str) or not upd_resp.value.strip())
                ):
                    log.info(f"[POST-PROCESS] Preserving text for question {upd_ques.dbid} ({upd_ques.label})")
                    value = orig_resp.value
                fixed_responses.append(
                    Response(dbid=upd_resp.dbid, value=value, selected=upd_resp.selected, comment=upd_resp.comment)
                )

            fixed_questions.append(
                Question(
                    dbid=upd_ques.dbid,
                    label=upd_ques.label,
                    type=upd_ques.type,
                    skipped=skipped,
                    responses=fixed_responses,
                )
            )

        return QuestionnaireDefinition(dbid=updated.dbid, name=updated.name, questions=fixed_questions)

    def command_from_questionnaire(
        self,
        command_uuid: str,
        questionnaire: QuestionnaireDefinition,
    ) -> QuestionnaireCommand:
        include_skipped = self.include_skipped()
        command = self.sdk_command()(note_uuid=self.identification.note_uuid, command_uuid=command_uuid)
        cmd_questions: list[BaseQuestion] = []
        for question in questionnaire.questions:
            options = [
                ResponseOption(dbid=response.dbid, name=response.value, value=response.value, code=response.value)
                for response in question.responses
            ]
            question_name = f"question-{question.dbid}"
            question_id = str(question.dbid)
            if question.type == QuestionType.TYPE_INTEGER:
                cmd_question = IntegerQuestion(question_id, question_name, question.label, {}, options)
                cmd_question.add_response(integer=int(question.responses[0].value))
            elif question.type == QuestionType.TYPE_CHECKBOX:
                cmd_question = CheckboxQuestion(question_id, question_name, question.label, {}, options)
                for idx, response in enumerate(question.responses):
                    cmd_question.add_response(option=options[idx], selected=response.selected, comment=response.comment)
            elif question.type == QuestionType.TYPE_RADIO:
                cmd_question = RadioQuestion(question_id, question_name, question.label, {}, options)
                for idx, response in enumerate(question.responses):
                    if response.selected:
                        cmd_question.add_response(option=options[idx])
            else:  # question.type == QuestionType.TYPE_TEXT:
                cmd_question = TextQuestion(question_id, question_name, question.label, {}, options)
                cmd_question.add_response(text=question.responses[0].value)
            cmd_questions.append(cmd_question)

            if include_skipped and hasattr(command, "set_question_enabled"):
                command.set_question_enabled(question_id, question.skipped is not True)

        # SDK may (should?) offer a more elegant way to provide the responses without accessing the database
        command.questions = cmd_questions

        return command

    # vvv methods should not be called: calling them will raise an exception
    # def command_from_json(
    #         self,
    #         instruction: InstructionWithParameters,
    #         chatter: LlmBase,
    # ) -> InstructionWithCommand | None:
    #     return None
    #
    # def command_parameters(self) -> dict:
    #     return {}
    #
    # def instruction_description(self) -> str:
    #     return ""
    #
    # def instruction_constraints(self) -> str:
    #     return ""
    # ^^^ methods should not be called: calling them will raise an exception

    def is_available(self) -> bool:
        return True
