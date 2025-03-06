from canvas_sdk.commands.commands.remove_allergy import RemoveAllergyCommand

from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.llms.llm_base import LlmBase
from hyperscribe.handlers.structures.coded_item import CodedItem


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

    def command_from_json(self, chatter: LlmBase, parameters: dict) -> None | RemoveAllergyCommand:
        allergy_uuid = ""
        if 0 <= (idx := parameters["allergyIndex"]) < len(current := self.cache.current_allergies()):
            allergy_uuid = current[idx].uuid
        return RemoveAllergyCommand(
            allergy_id=allergy_uuid,
            narrative=parameters["narrative"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        allergies = "/".join([f'{allergy.label} (index: {idx})' for idx, allergy in enumerate(self.cache.current_allergies())])
        return {
            "allergies": f"one of: {allergies}",
            "allergyIndex": "Index of the allergy to remove, as integer",
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
