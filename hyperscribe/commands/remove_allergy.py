from canvas_sdk.commands.commands.remove_allergy import RemoveAllergyCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class RemoveAllergy(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_REMOVE_ALLERGY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        narrative = data.get("narrative") or "n/a"
        if allergy := (data.get("allergy") or {}).get("text"):
            return CodedItem(label=f"{allergy}: {narrative}", code="", uuid="")
        return None

    def command_from_json(self, instruction: InstructionWithParameters, chatter: LlmBase) -> InstructionWithCommand | None:
        allergy_uuid = ""
        if 0 <= (idx := instruction.parameters["allergyIndex"]) < len(current := self.cache.current_allergies()):
            allergy_uuid = current[idx].uuid
        return InstructionWithCommand.add_command(instruction, RemoveAllergyCommand(
            allergy_id=allergy_uuid,
            narrative=instruction.parameters["narrative"],
            note_uuid=self.identification.note_uuid,
        ))

    def command_parameters(self) -> dict:
        allergies = "/".join([f'{allergy.label} (index: {idx})' for idx, allergy in enumerate(self.cache.current_allergies())])
        return {
            "allergies": f"one of: {allergies}",
            "allergyIndex": "Index of the allergy to remove, or -1, as integer",
            "narrative": "explanation of why the allergy is removed, as free text",
        }

    def instruction_description(self) -> str:
        return ("Remove a previously diagnosed allergy. "
                "There can be only one allergy, with the explanation, to remove per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        text = ", ".join([allergy.label for allergy in self.cache.current_allergies()])
        return f"'{self.class_name()}' has to be related to one of the following allergies: {text}."

    def is_available(self) -> bool:
        return bool(self.cache.current_allergies())
