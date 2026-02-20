from canvas_sdk.commands.commands.diagnose import DiagnoseCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.selector_chat import SelectorChat
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Diagnose(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "diagnose"

    @classmethod
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_ASSESSMENT

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        assessment = data.get("today_assessment") or "n/a"
        diagnose = data.get("diagnose") or {}
        if (label := diagnose.get("text")) and (code := diagnose.get("value")):
            return CodedItem(label=f"{label} ({assessment})", code=code, uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        icd10_code = SelectorChat.condition_from(
            instruction,
            chatter,
            instruction.parameters["keywords"].split(","),
            instruction.parameters["ICD10"].split(","),
            "\n".join([instruction.parameters["rationale"], "", instruction.parameters["assessment"]]),
        )
        self.add_code2description(icd10_code.uuid, icd10_code.label)
        return InstructionWithCommand.add_command(
            instruction,
            DiagnoseCommand(
                icd10_code=icd10_code.code,
                background=instruction.parameters["rationale"],
                approximate_date_of_onset=Helper.str2date(instruction.parameters["onsetDate"]),
                today_assessment=instruction.parameters["assessment"],
                note_uuid=self.identification.note_uuid,
            ),
        )

    def command_parameters(self) -> dict:
        return {
            "keywords": "",
            "ICD10": "",
            "rationale": "",
            "onsetDate": "",
            "assessment": "",
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
                    "additionalProperties": False,
                    "required": ["keywords", "ICD10", "rationale", "onsetDate", "assessment"],
                    "properties": {
                        "keywords": {
                            "type": "string",
                            "description": "Comma-separated keywords to find the specific condition in a "
                            "database (using OR criteria), it is better to provide "
                            "more specific keywords rather than few broad ones.",
                        },
                        "ICD10": {
                            "type": "string",
                            "description": "Comma-separated ICD-10 codes (up to 5) for the condition",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "all reasoning leading to the diagnosis, it should be detailed but "
                            "limited to what is explicitly mentioned in the instruction.",
                            "minLength": 1,
                        },
                        "onsetDate": {
                            "type": "string",
                            "description": "Approximate onset date in YYYY-MM-DD.",
                            "format": "date",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                        },
                        "assessment": {
                            "type": "string",
                            "description": "Current assessment of the condition, as stated in the instruction, "
                            "without the reasoning.",
                            "minLength": 1,
                        },
                    },
                },
            }
        ]

    def instruction_description(self) -> str:
        return (
            "Medical condition identified, diagnosed, or referenced as pertaining to the patient "
            "by a provider; the necessary information to report includes: "
            "- the medical condition itself, "
            "- all reasoning explicitly mentioned in the transcript, "
            "- current detailed assessment as mentioned in the transcript, and "
            "- the approximate date of onset if mentioned in the transcript. "
            "If a condition is discussed in relation to the patient's treatment or medications "
            "(e.g., asking about a medication used for a specific condition), and that condition is not already "
            "in the patient's chart, create a Diagnose instruction for it. "
            "There is one and only one condition per instruction with all necessary information, "
            "and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([f"{condition.label}" for condition in self.cache.current_conditions()]):
            result = f"Only document '{self.class_name()}' for conditions outside the following list: {text}."
        return result

    def is_available(self) -> bool:
        return True
