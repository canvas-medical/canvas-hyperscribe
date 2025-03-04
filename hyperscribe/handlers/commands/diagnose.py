from canvas_sdk.commands.commands.diagnose import DiagnoseCommand

from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.selector_chat import SelectorChat
from hyperscribe.handlers.structures.coded_item import CodedItem


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

    def command_from_json(self, parameters: dict) -> None | DiagnoseCommand:
        icd10_code = SelectorChat.condition_from(
            self.settings,
            parameters["keywords"].split(","),
            parameters["ICD10"].split(","),
            "\n".join([
                parameters["rationale"],
                "",
                parameters["assessment"],
            ]),
        )
        result = DiagnoseCommand(
            icd10_code=icd10_code.code,
            background=parameters["rationale"],
            approximate_date_of_onset=Helper.str2date(parameters["onsetDate"]),
            today_assessment=parameters["assessment"],
            note_uuid=self.note_uuid,
        )
        return result

    def command_parameters(self) -> dict:
        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the diagnosed condition",
            "ICD10": "comma separated keywords of up to 5 ICD-10 codes of the diagnosed condition",
            "rationale": "rationale about the diagnosis, as free text",
            "onsetDate": "YYYY-MM-DD",
            "assessment": "today's assessment of the condition, as free text",
        }

    def instruction_description(self) -> str:
        return ("Medical condition identified by the provider, including reasoning, current assessment, and onset date. "
                "There is one instruction per condition, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([f'{condition.label}' for condition in self.cache.current_conditions()]):
            result = f"'{self.class_name()}' cannot include: {text}."
        return result

    def is_available(self) -> bool:
        return True
