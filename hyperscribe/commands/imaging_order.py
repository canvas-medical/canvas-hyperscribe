import json

from canvas_sdk.commands.commands.imaging_order import ImagingOrderCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.libraries.selector_chat import SelectorChat
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class ImagingOrder(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_IMAGING_ORDER

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        comment = data.get("comment") or "n/a"
        priority = data.get("priority") or "n/a"
        imaging = (data.get("image") or {}).get("text")
        indications = (
            "/".join([indication for item in (data.get("indications") or []) if (indication := item.get("text"))])
            or "n/a"
        )
        if imaging:
            return CodedItem(
                label=f"{imaging}: {comment} (priority: {priority}, related conditions: {indications})",
                code="",
                uuid="",
            )
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = ImagingOrderCommand(
            note_uuid=self.identification.note_uuid,
            ordering_provider_key=self.identification.provider_uuid,
            diagnosis_codes=[],
            comment=instruction.parameters["comment"],
            additional_details=instruction.parameters["noteToRadiologist"],
            priority=Helper.enum_or_none(instruction.parameters["priority"], ImagingOrderCommand.Priority),
            linked_items_urns=[],
        )
        # retrieve the linked conditions
        for condition in instruction.parameters["conditions"]:
            item = SelectorChat.condition_from(
                instruction,
                chatter,
                self.settings,
                condition["conditionKeywords"].split(","),
                condition["ICD10"].split(","),
                instruction.parameters["comment"],
            )
            if item.code:
                result.diagnosis_codes.append(item.code)

        # retrieve existing imaging orders defined in Canvas Science
        expressions = instruction.parameters["imagingKeywords"].split(",")
        if concepts := CanvasScience.search_imagings(self.settings.science_host, expressions):
            # ask the LLM to pick the most relevant imaging
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant imaging order for a patient out of a list of "
                "imaging orders.",
                "",
            ]
            user_prompt = [
                "Here is the comments provided by the healthcare provider in regards to the imaging to order "
                "for a patient:",
                "```text",
                f"keywords: {instruction.parameters['imagingKeywords']}",
                " -- ",
                f"note: {instruction.parameters['comment']}",
                " -- ",
                f"note to the radiologist: {instruction.parameters['imagingKeywords']}",
                "```",
                "Among the following imaging orders, identify the most relevant one:",
                "",
                "\n".join(f" * {concept.name} ({concept.code})" for concept in concepts),
                "",
                "Please, present your findings in a JSON format within a Markdown code block like:",
                "```json",
                json.dumps([{"conceptId": "the code ID", "term": "the name of the imaging"}]),
                "```",
                "",
            ]
            schemas = JsonSchema.get(["selector_concept"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
                result.image_code = response[0]["conceptId"]

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        priorities = "/".join([priority.value for priority in ImagingOrderCommand.Priority])
        return {
            "imagingKeywords": "comma separated keywords of up to 5 synonyms of the imaging to order",
            "conditions": [
                {
                    "conditionKeywords": "comma separated keywords of up to 5 synonyms of each condition "
                    "targeted by the imaging",
                    "ICD10": "comma separated keywords of up to 5 ICD-10 codes of each condition targeted "
                    "by the imaging",
                },
            ],
            "comment": "rationale of the imaging order, as free text",
            "noteToRadiologist": "information to be sent to the radiologist, as free text",
            "priority": f"mandatory, one of: {priorities}",
        }

    def instruction_description(self) -> str:
        return (
            "Imaging ordered, including all necessary comments and the targeted conditions. "
            "There can be only one imaging order per instruction, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
