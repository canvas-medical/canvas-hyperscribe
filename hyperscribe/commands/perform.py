import json

from canvas_sdk.commands.commands.perform import PerformCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Perform(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PERFORM

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        notes = data.get("notes") or "n/a"
        if text := (data.get("perform") or {}).get("text"):
            return CodedItem(label=f"{text}: {notes}", code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = PerformCommand(
            cpt_code="",
            notes=instruction.parameters["comment"],
            note_uuid=self.identification.note_uuid,
        )
        # retrieve the procedure, or action, based on the keywords
        if charges := self.cache.charge_descriptions():
            # ask the LLM to pick the most relevant charge
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to select the most relevant procedure performed on a patient "
                "out of a list of procedures.",
                "",
            ]
            user_prompt = [
                "Here is the comment provided by the healthcare provider in regards to the procedure performed "
                "on the patient:",
                "```text",
                f"keywords: {instruction.parameters['procedureKeywords']}",
                " -- ",
                instruction.parameters["comment"],
                "```",
                "",
                "Among the following procedures, select the most relevant one:",
                "",
                "\n".join(f" * {concept.short_name} (code: {concept.cpt_code})" for concept in charges),
                "",
                "Please, present your findings in a JSON format within a Markdown code block like:",
                "```json",
                json.dumps([{"code": "the procedure code", "label": "the procedure label"}]),
                "```",
                "",
            ]
            schemas = JsonSchema.get(["selector_lab_test"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
                procedure = response[0]
                result.cpt_code = procedure["code"]
                self.add_code2description(procedure["code"], procedure["label"])

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "procedureKeywords": "comma separated keywords of up to 5 synonyms of the procedure or action performed",
            "comment": "information related to the procedure or action performed, as free text",
        }

    def instruction_description(self) -> str:
        return (
            "Medical procedure, which is not an auscultation, performed during the encounter. "
            "There can be only one procedure performed per instruction, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        return f'"{self.class_name()}" supports only one procedure per instruction, auscultation are prohibited.'

    def is_available(self) -> bool:
        return True
