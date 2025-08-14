import json, re, uuid, argparse
from pathlib import Path
from typing import Any, Tuple, cast

from hyperscribe.structures.vendor_key import VendorKey
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson
from evaluations.constants import Constants
from evaluations.structures.patient_profile import PatientProfile
from evaluations.structures.chart import Chart


class SyntheticChartGenerator:
    def __init__(self, vendor_key: VendorKey, profiles: list[PatientProfile]):
        self.vendor_key = vendor_key
        self.profiles = profiles

    @classmethod
    def load_json(cls, path: Path) -> list[PatientProfile]:
        with path.open("r") as f:
            profiles_dict = cast(dict[str, str], json.load(f))
        return [PatientProfile(name=name, profile=profile) for name, profile in profiles_dict.items()]

    @classmethod
    def schema_chart(cls) -> dict[str, Any]:
        """Build a JSON Schema that enforces Canvas chart structure with ChartItem arrays."""

        # Schema for ChartItem structure
        chart_item_schema = {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Medical code (ICD-10, CPT, RxNorm, etc.)"},
                "label": {"type": "string", "description": "Human-readable description"},
                "uuid": {"type": "string", "description": "Unique identifier - will be populated automatically"},
            },
            "required": ["code", "label", "uuid"],
            "additionalProperties": False,
        }

        # Schema for MedicationCached structure
        medication_cached_schema = {
            "type": "object",
            "properties": {
                "uuid": {"type": "string", "description": "Unique identifier - will be populated automatically"},
                "label": {"type": "string", "description": "Human-readable medication name"},
                "codeRxNorm": {"type": "string", "description": "RxNorm code for the medication"},
                "codeFdb": {"type": "string", "description": "FDB code for the medication"},
                "nationalDrugCode": {"type": "string", "description": "National Drug Code (NDC)"},
                "potencyUnitCode": {"type": "string", "description": "Potency unit code"},
            },
            "required": ["uuid", "label", "codeRxNorm", "codeFdb", "nationalDrugCode", "potencyUnitCode"],
            "additionalProperties": False,
        }

        properties: dict[str, Any] = {
            "demographicStr": {"type": "string", "description": "String describing patient demographics"}
        }

        # Chart item fields use the generic schema
        chart_item_fields = [
            "conditionHistory",
            "currentAllergies",
            "currentConditions",
            "currentGoals",
            "familyHistory",
            "surgeryHistory",
        ]

        for field_name in chart_item_fields:
            properties[field_name] = {
                "type": "array",
                "description": Constants.EXAMPLE_CHART_DESCRIPTIONS[field_name],
                "items": chart_item_schema,
            }

        # Current medications uses the MedicationCached schema
        properties["currentMedications"] = {
            "type": "array",
            "description": Constants.EXAMPLE_CHART_DESCRIPTIONS["currentMedications"],
            "items": medication_cached_schema,
        }

        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "description": "Canvas-compatible chart structure with structured ChartItems",
            "type": "object",
            "properties": properties,
            "required": list(Constants.EXAMPLE_CHART_DESCRIPTIONS.keys()),
            "additionalProperties": False,
        }

    def generate_chart_for_profile(self, patient_profile: PatientProfile) -> Chart:
        schema = self.schema_chart()

        system_prompt: list[str] = [
            "You are generating a Canvas-compatible `limited_chart.json` for a synthetic patient.",
            "The chart uses structured data with medical codes for clinical items.",
            "Return your answer as JSON inside a fenced ```json ... ``` block.",
            "Each clinical item must have: code, label, and uuid fields.",
        ]

        user_prompt: list[str] = [
            f"Patient profile: {patient_profile.profile}",
            "",
            "Generate a structured limited_chart.json with these fields:",
            "- demographicStr: Simple string describing patient demographics",
            "- conditionHistory, currentAllergies, currentConditions, currentMedications, "
            "currentGoals, familyHistory, surgeryHistory: Arrays of objects",
            "",
            "Each array item, except for currentMedications, must be an object with:",
            "- code: medical code (ICD-10 for conditions/allergies, "
            "RxNorm for medications, CPT for procedures, empty string if no specific code)",
            "- label: Human-readable description",
            "- uuid: Use empty string (will be populated automatically)",
            "For currentMedications, the array item must be an object with:",
            "- uuid: Use empty string (will be populated automatically)",
            "- label: Human-readable medication name",
            "- codeRxNorm: RxNorm code for the medication",
            "- codeFdb: FDB code for the medication",
            "- nationalDrugCode: National Drug Code (NDC)",
            "- potencyUnitCode: Potency unit code",
            "",
            "Your JSON **must** conform to the following JSON Schema:",
            "```json",
            json.dumps(schema, indent=2),
            "```",
            "",
            "Be strict:",
            "- Include only conditions the patient *has or was diagnosed with*.",
            "- Include only medications the patient *is actually taking*.",
            "- Use empty arrays [] for categories not mentioned in the profile.",
            "- Do not fabricate information beyond the profile.",
            "- Use realistic medical codes when possible, empty string otherwise.",
        ]

        return cast(
            Chart,
            HelperSyntheticJson.generate_json(
                vendor_key=self.vendor_key,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
                returned_class=Chart,
            ),
        )

    @classmethod
    def assign_valid_uuids(cls, obj: Any) -> Any:
        stack: list[Tuple[Any, Any]] = [(None, obj)]
        while stack:
            parent, current = stack.pop()
            if isinstance(current, dict):
                for k, v in current.items():
                    if k.lower() == "uuid":
                        current[k] = str(uuid.uuid4())
                    else:
                        stack.append((current, v))
            elif isinstance(current, list):
                for item in current:
                    stack.append((current, item))
        return obj

    def run_range(self, start: int, limit: int, output: Path) -> None:
        subset = self.profiles[start - 1 : start - 1 + limit]
        output.mkdir(parents=True, exist_ok=True)
        for patient_profile in subset:
            safe_name = re.sub(r"\W+", "_", patient_profile.name)
            patient_dir = output / safe_name
            patient_dir.mkdir(parents=True, exist_ok=True)

            print(f"Generating limited_chart.json for {patient_profile.name}")
            chart = self.generate_chart_for_profile(patient_profile)
            chart_json = chart.to_json()
            chart_json = self.assign_valid_uuids(chart_json)

            out_path = patient_dir / "limited_chart.json"
            with out_path.open("w") as f:
                json.dump(chart_json, f, indent=2)
            print(f"Saved limited_chart.json to {out_path}")

    @staticmethod
    def main() -> None:
        parser = argparse.ArgumentParser(description="Generate Canvas-compatible limited_chart.json files.")
        parser.add_argument("--input", type=Path, required=True, help="Path to combined profiles JSON")
        parser.add_argument("--output", type=Path, required=True, help="Directory to write per-patient folders")
        parser.add_argument("--start", type=int, default=1, help="1-based index of first profile to process")
        parser.add_argument("--limit", type=int, required=True, help="Number of profiles to generate charts for")
        args = parser.parse_args()

        settings = HelperEvaluation.settings()
        vendor_key = settings.llm_text
        profiles = SyntheticChartGenerator.load_json(args.input)

        generator = SyntheticChartGenerator(
            vendor_key=vendor_key,
            profiles=profiles,
        )
        generator.run_range(start=args.start, limit=args.limit, output=args.output)


if __name__ == "__main__":
    SyntheticChartGenerator.main()
