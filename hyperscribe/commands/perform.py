from canvas_sdk.commands.commands.perform import PerformCommand

from hyperscribe.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.handlers.selector_chat import SelectorChat
from hyperscribe.structures.coded_item import CodedItem


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

    def command_from_json(self, chatter: LlmBase, parameters: dict) -> None | PerformCommand:
        result = PerformCommand(
            cpt_code="",
            notes=parameters["comment"],
            note_uuid=self.note_uuid,
        )
        # retrieve the procedure, or action, based on the keywords
        item = SelectorChat.procedure_from(
            chatter,
            self.settings,
            parameters["procedureKeywords"].split(","),
            parameters["comment"],
        )
        if item.code:
            result.cpt_code = item.code

        return result

    def command_parameters(self) -> dict:
        return {
            "procedureKeywords": "comma separated keywords of up to 5 synonyms of the procedure or action performed",
            "comment": "information related to the procedure or action performed, as free text",
        }

    def instruction_description(self) -> str:
        return ("Procedure or action performed during the encounter. "
                "There can be only one procedure or action performed per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
