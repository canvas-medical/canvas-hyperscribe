from canvas_sdk.commands.commands.diagnose import DiagnoseCommand

from commander.protocols.structures.commands.base import Base


class Diagnose(Base):
    def from_json(self, parameters: dict) -> DiagnoseCommand:
        # TODO use the `condition` field to retrieve the actual ICD-10 through the science service
        return DiagnoseCommand(
            icd10_code=parameters["ICD10"],
            background=parameters["background"],
            approximate_date_of_onset=self.str2date(parameters["onsetDate"]).date(),
            today_assessment=parameters["assessment"],
        )

    def parameters(self) -> dict:
        return {
            "condition": "medical name of the condition",
            "ICD10": "ICD-10 code of the condition",
            "background": "free text",
            "onsetDate": "YYYY-MM-DD",
            "assessment": "free text",
        }

    def information(self) -> str:
        return ("Medical condition identified by the provider, including reasoning, current assessment, and onset date. "
                "There is one instruction per condition, and no instruction in the lack of.")

    def is_available(self) -> bool:
        return True
