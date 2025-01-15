from typing import Type

from canvas_sdk.commands.commands.vitals import VitalsCommand

from commander.protocols.structures.commands.base import Base


class Vitals(Base):
    def command_from_json(self, parameters: dict) -> None | VitalsCommand:
        return VitalsCommand(
            height=self.valid_or_none(VitalsCommand, "height", parameters["height"]["inches"]),
            weight_lbs=self.valid_or_none(VitalsCommand, "weight_lbs", parameters["weight"]["pounds"]),
            waist_circumference=self.valid_or_none(VitalsCommand, "waist_circumference", parameters["waistCircumference"]["centimeters"]),
            body_temperature=self.valid_or_none(VitalsCommand, "body_temperature", parameters["temperature"]["fahrenheit"]),
            blood_pressure_systole=self.valid_or_none(VitalsCommand, "blood_pressure_systole", parameters["bloodPressure"]["systolicPressure"]),
            blood_pressure_diastole=self.valid_or_none(VitalsCommand, "blood_pressure_diastole", parameters["bloodPressure"]["diastolicPressure"]),
            pulse=self.valid_or_none(VitalsCommand, "pulse", parameters["pulseRate"]["beatPerMinute"]),
            respiration_rate=self.valid_or_none(VitalsCommand, "respiration_rate", parameters["respirationRate"]["beatPerMinute"]),
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        return {
            "height": {"inches": 0},
            "weight": {"pounds": 0},
            "waistCircumference": {"centimeters": 0},
            "temperature": {"fahrenheit": 0.0},
            "bloodPressure": {"systolicPressure": 0, "diastolicPressure": 0},
            "pulseRate": {"beatPerMinute": 0},
            "respirationRate": {"beatPerMinute": 0},
        }

    def instruction_description(self) -> str:
        return ("Vital sign measurements (height, weight, waist circumference, temperature, blood pressure, pulse rate, respiration rate). "
                "All measurements should be combined in one instruction.")

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
