import json

from canvas_sdk.commands.commands.immunization_statement import ImmunizationStatementCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class ImmunizationStatement(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_IMMUNIZATION

    @classmethod
    def note_section(cls) -> str:
        return Constants.SECTION_HISTORY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        on_date = (data.get("date") or {}).get("date")
        comments = data.get("comments")
        display = data.get("statement", {}).get("text")
        codes = [
            f"{coding.get('system')}: {coding.get('code')}"
            for coding in data.get("statement", {}).get("extra", {}).get("coding", [])
        ]

        if on_date or comments or display:
            return CodedItem(
                label=f"{on_date or 'n/a'} - {display or 'n/a'}: {codes} - {comments or 'n/a'}",
                code="",
                uuid="",
            )
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = ImmunizationStatementCommand(
            cpt_code="",
            cvx_code="",
            comments=instruction.parameters["comments"],
            approximate_date=Helper.str2date(instruction.parameters["onDate"]),
            note_uuid=self.identification.note_uuid,
        )
        # retrieve existing immunization defined in Canvas Science
        expressions = instruction.parameters["keywords"].split(",")
        if immunizations := CanvasScience.search_immunization(expressions):
            # retrieve the correct medication
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant immunization administrated to a patient "
                "out of a list of immunizations.",
                "",
            ]
            user_prompt = [
                "Here is the comment provided by the healthcare provider in regards to the immunization:",
                "```text",
                f"keywords: {instruction.parameters['keywords']}",
                " -- ",
                instruction.parameters["comments"],
                "```",
                "",
                "Among the following immunizations, identify the most relevant one:",
                "",
                "\n".join(
                    f" * {immunization.label} (cptCode: {immunization.code_cpt}, cvxCode: {immunization.code_cvx})"
                    for immunization in immunizations
                ),
                "",
                f"It may be important to take into account that {self.cache.demographic__str__(False)}.",
                "",
                "Please, present your findings in a JSON format within a Markdown code block like:",
                "```json",
                json.dumps([{"cptCode": "the CPT code", "cvxCode": "the CVX code", "label": "the label"}]),
                "```",
                "",
            ]
            schemas = JsonSchema.get(["selector_immunization_codes"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
                immunization = response[0]
                # cpt_code and cvx_code have to be set at the same time
                result = ImmunizationStatementCommand(
                    cpt_code=str(immunization["cptCode"]),
                    cvx_code=str(immunization["cvxCode"]),
                    comments=result.comments,
                    approximate_date=result.approximate_date,
                    note_uuid=result.note_uuid,
                )
                self.add_code2description(str(immunization["cptCode"]), immunization["label"])
                self.add_code2description(str(immunization["cvxCode"]), immunization["label"])

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "keywords": "",
            "onDate": None,
            "comments": "",
        }

    def command_parameters_schemas(self) -> list[dict]:
        return [
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "keywords": {
                            "type": "string",
                            "description": "Comma-separated keywords to find the specific immunization in a "
                            "database (using OR criteria), it is better to provide "
                            "more specific keywords rather than few broad ones.",
                        },
                        "onDate": {
                            "type": ["string", "null"],
                            "description": "Approximate date of the immunization in YYYY-MM-DD.",
                            "format": "date",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                        },
                        "comments": {
                            "type": "string",
                            "description": "provided information related to the immunization, as free text",
                            "maxLength": 255,
                        },
                    },
                    "required": ["keywords", "onDate", "comments"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        return (
            "Any past immunization. There can be one and only one immunization per instruction, "
            "and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join(
            [
                f"{item.label} (CPT: {item.code_cpt}, CVX: {item.code_cvx}) on {item.approximate_date_str()}"
                for item in self.cache.current_immunizations()
            ]
        ):
            result = f"Only document '{self.class_name()}' for information outside the following list: {text}."
        return result

    def is_available(self) -> bool:
        return True
