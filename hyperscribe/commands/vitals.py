from typing import Type

from canvas_sdk.commands.commands.vitals import VitalsCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Vitals(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_VITALS

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if text := ", ".join([f"{k}: {v}" for k, v in data.items() if v]):
            return CodedItem(label=text, code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        return InstructionWithCommand.add_command(
            instruction,
            VitalsCommand(
                height=self.valid_or_none(VitalsCommand, "height", instruction.parameters["height"]["inches"]),
                weight_lbs=self.valid_or_none(VitalsCommand, "weight_lbs", instruction.parameters["weight"]["pounds"]),
                waist_circumference=self.valid_or_none(
                    VitalsCommand,
                    "waist_circumference",
                    instruction.parameters["waistCircumference"]["centimeters"],
                ),
                body_temperature=self.valid_or_none(
                    VitalsCommand,
                    "body_temperature",
                    instruction.parameters["temperature"]["fahrenheit"],
                ),
                blood_pressure_systole=self.valid_or_none(
                    VitalsCommand,
                    "blood_pressure_systole",
                    instruction.parameters["bloodPressure"]["systolicPressure"],
                ),
                blood_pressure_diastole=self.valid_or_none(
                    VitalsCommand,
                    "blood_pressure_diastole",
                    instruction.parameters["bloodPressure"]["diastolicPressure"],
                ),
                pulse=self.valid_or_none(VitalsCommand, "pulse", instruction.parameters["pulseRate"]["beatPerMinute"]),
                respiration_rate=self.valid_or_none(
                    VitalsCommand,
                    "respiration_rate",
                    instruction.parameters["respirationRate"]["beatPerMinute"],
                ),
                note_uuid=self.identification.note_uuid,
            ),
        )

    def command_parameters(self) -> dict:
        return {
            "important": "all values are integers or null",
            "height": {"inches": 0},
            "weight": {"pounds": 0},
            "waistCircumference": {"centimeters": 0},
            "temperature": {"fahrenheit": 0},
            "bloodPressure": {"systolicPressure": 0, "diastolicPressure": 0},
            "pulseRate": {"beatPerMinute": 0},
            "respirationRate": {"beatPerMinute": 0},
        }

    def instruction_description(self) -> str:
        return (
            "Vital sign measurements (height, weight, waist circumference, "
            "temperature, blood pressure, pulse rate, respiration rate). "
            "All measurements should be combined in one instruction."
        )

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True

    @classmethod
    def valid_or_none(cls, model: Type[VitalsCommand], field: str, value: int | float) -> int | float | None:
        try:
            model.model_validate({field: value})
            return value
        except Exception:  # ATTENTION should be ValidationError but cannot do: from pydantic import ValidationError
            return None
