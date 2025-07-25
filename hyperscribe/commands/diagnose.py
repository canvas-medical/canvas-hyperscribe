from canvas_sdk.commands.commands.diagnose import DiagnoseCommand

from hyperscribe.commands.base import Base
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
            self.settings,
            instruction.parameters["keywords"].split(","),
            instruction.parameters["ICD10"].split(","),
            "\n".join([instruction.parameters["rationale"], "", instruction.parameters["assessment"]]),
        )
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
            "keywords": "comma separated keywords of up to 5 synonyms of the diagnosed condition",
            "ICD10": "comma separated keywords of up to 5 ICD-10 codes of the diagnosed condition",
            "rationale": "rationale about the diagnosis, as free text",
            "onsetDate": "YYYY-MM-DD",
            "assessment": "today's assessment of the condition, as free text",
        }

    def instruction_description(self) -> str:
        return (
            "Medical condition identified by the provider, including reasoning, current assessment, and onset date. "
            "There is one instruction per condition, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([f"{condition.label}" for condition in self.cache.current_conditions()]):
            result = f"'{self.class_name()}' cannot include: {text}."
        return result

    def is_available(self) -> bool:
        return True
