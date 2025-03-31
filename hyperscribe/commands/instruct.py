import json

from canvas_sdk.commands.commands.instruct import InstructCommand
from canvas_sdk.commands.constants import CodeSystems, Coding

from hyperscribe.handlers.canvas_science import CanvasScience
from hyperscribe.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem


class Instruct(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_INSTRUCT

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        narrative = data.get("narrative") or "n/a"
        if instruct := (data.get("instruct") or {}).get("text"):
            return CodedItem(label=f"{instruct} ({narrative})", code="", uuid="")
        return None

    def command_from_json(self, chatter: LlmBase, parameters: dict) -> None | InstructCommand:
        result = InstructCommand(
            comment=parameters["comment"],
            note_uuid=self.note_uuid,
        )
        # retrieve existing instructions defined in Canvas Science
        expressions = parameters["keywords"].split(",")
        if concepts := CanvasScience.instructions(self.settings.science_host, expressions):
            # ask the LLM to pick the most relevant instruction
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant direction.",
                "",
            ]
            user_prompt = [
                'Here is the description of a direction instructed by a healthcare provider to a patient:',
                '```text',
                f"keywords: {parameters['keywords']}",
                " -- ",
                parameters["comment"],
                '```',
                'Among the following expressions, identify the most relevant one:',
                '',
                "\n".join(f' * {concept.term} ({concept.concept_id})' for concept in concepts),
                '',
                'Please, present your findings in a JSON format within a Markdown code block like:',
                '```json',
                json.dumps([{"conceptId": "the concept ID", "term": "the expression"}]),
                '```',
                '',
            ]
            schemas = JsonSchema.get(["selector_concept"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas):
                result.coding = Coding(
                    code=str(response[0]["conceptId"]),
                    system=CodeSystems.SNOMED,
                    display=response[0]["term"],
                )

        return result

    def command_parameters(self) -> dict:
        return {
            "keywords": "comma separated single keywords of up to 5 synonyms to the specific direction",
            "comment": "directions from the provider, as free text",
        }

    def instruction_description(self) -> str:
        return ("Specific or standard direction. "
                "There can be only one direction per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
