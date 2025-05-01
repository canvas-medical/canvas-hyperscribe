import json
from typing import Type

from canvas_sdk.commands.commands.questionnaire import QuestionnaireCommand
from canvas_sdk.commands.commands.questionnaire.question import (TextQuestion, IntegerQuestion, CheckboxQuestion, ResponseOption, RadioQuestion,
                                                                 BaseQuestion)

from hyperscribe.commands.base import Base
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.line import Line
from hyperscribe.structures.question import Question
from hyperscribe.structures.question_type import QuestionType
from hyperscribe.structures.questionnaire import Questionnaire as QuestionnaireDefinition
from hyperscribe.structures.response import Response


class BaseQuestionnaire(Base):
    def include_skipped(self) -> bool:
        raise NotImplementedError

    def sdk_command(self) -> Type[QuestionnaireCommand]:
        raise NotImplementedError

    @classmethod
    def staged_command_extract(cls, data: dict) -> CodedItem | None:
        questionnaire = data.get("questionnaire", {}).get("extra", {})
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
                str(o["pk"]): {
                                  "dbid": o["pk"],
                                  "value": o["label"],
                                  "selected": False,
                              } | default
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

            questions.append(Question(
                dbid=question["pk"],
                label=question["label"],
                type=question_type,
                skipped=data.get(f'skip-{question["pk"]}'),  # true/false/none
                responses=[Response.load_from(option) for option in options.values()],
            ))
        result = QuestionnaireDefinition(
            name=questionnaire["name"],
            dbid=questionnaire["pk"],
            questions=questions,
        )
        return CodedItem(label=json.dumps(result.to_json()), code="", uuid="")

    @classmethod
    def json_schema(cls, include_skipped: bool) -> dict:
        properties = {
            "questionId": {"type": "integer"},
            "question": {"type": "string"},
            "questionType": {
                "type": "string",
                "enum": list(QuestionType.llm_readable().values()),
            },
            "responses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "responseId": {"type": "integer"},
                        "value": {"type": "string"},
                        "selected": {"type": "boolean"},
                        "comment": {
                            "type": "string",
                            "description": "any relevant information expanding the answer",
                        },
                    },
                    "required": ["responseId", "value", "selected"],
                }
            }
        }
        if include_skipped:
            properties |= {"skipped": {"type": ["boolean", "null"]}}

        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": properties,
                "required": list(properties.keys()),
            }
        }

    def update_from_transcript(
            self,
            discussion: list[Line],
            instruction: Instruction,
            chatter: LlmBase,
    ) -> QuestionnaireDefinition | None:
        questionnaire = QuestionnaireDefinition.load_from(json.loads(instruction.information))
        system_prompt = [
            "The conversation is in the context of a clinical encounter between patient and licensed healthcare provider.",
            f"The healthcare provider is editing a questionnaire '{questionnaire.name}', potentially without notifying the patient to prevent biased answers.",
            "The user will submit two JSON Markdown blocks:",
            "- the current state of the questionnaire,",
            "- a partial transcript of the visit of a patient with the healthcare provider.",
            "",
            "Your task is to identifying from the transcript which questions the healthcare provider is referencing and what responses the patient is giving.",
            "Since this is only a part of the transcript, it may have no reference to the questionnaire at all.",
            "",
            "Your response must be the JSON Markdown block of the questionnaire, with all the necessary changes to reflect the transcript content.",
            "",
        ]
        transcript = json.dumps([line.to_json() for line in discussion], indent=1)

        user_prompt = [
            "Below is a part of the transcript between the patient and the healthcare provider:",
            "```json",
            transcript,
            "```",
            "",
            f"The questionnaire '{questionnaire.name}' is currently as follow,:",
            "```json",
            json.dumps(questionnaire.for_llm(self.include_skipped())),
            "```",
            "",
            "Your task is to replace the values of the JSON object as necessary.",
            "Since the current questionnaire's state is based on previous parts of the transcript, the changes should based on explicit information only.",
            "",
        ]
        schemas = [self.json_schema(self.include_skipped())]
        if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
            return QuestionnaireDefinition.load_from_llm(
                questionnaire.dbid,
                questionnaire.name,
                response,
            )
        return None

    def command_from_questionnaire(
            self,
            command_uuid: str,
            questionnaire: QuestionnaireDefinition,
    ) -> QuestionnaireCommand:
        command = self.sdk_command()(
            note_uuid=self.identification.note_uuid,
            command_uuid=command_uuid,
        )
        cmd_questions: list[BaseQuestion] = []
        for question in questionnaire.questions:
            options = [
                ResponseOption(
                    dbid=response.dbid,
                    name=response.value,
                    value=response.value,
                    code=response.value,
                )
                for response in question.responses
            ]
            question_name = f"question-{question.dbid}"
            if question.type == QuestionType.TYPE_INTEGER:
                cmd_question = IntegerQuestion(question_name, question.label, {}, options)
                cmd_question.add_response(integer=int(question.responses[0].value))
            elif question.type == QuestionType.TYPE_CHECKBOX:
                cmd_question = CheckboxQuestion(question_name, question.label, {}, options)
                for idx, response in enumerate(question.responses):
                    cmd_question.add_response(
                        option=options[idx],
                        selected=response.selected,
                        comment=response.comment,
                    )
            elif question.type == QuestionType.TYPE_RADIO:
                cmd_question = RadioQuestion(question_name, question.label, {}, options)
                for idx, response in enumerate(question.responses):
                    if response.selected:
                        cmd_question.add_response(option=options[idx])
            else:  # question.type == QuestionType.TYPE_TEXT:
                cmd_question = TextQuestion(question_name, question.label, {}, options)
                cmd_question.add_response(text=question.responses[0].value)

            cmd_questions.append(cmd_question)

        # SDK may (should?) offer a more elegant way to provide the responses without accessing the database
        command.questions = cmd_questions

        return command

    # vvv methods should not be called: calling them will raise an exception
    # def command_from_json(self, instruction: InstructionWithParameters, chatter: LlmBase) -> InstructionWithCommand | None:
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
