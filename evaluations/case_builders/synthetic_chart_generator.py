import json, re, uuid, argparse
from pathlib import Path
from typing import Any, Tuple, cast

from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.libraries.limited_cache import LimitedCache
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson
from evaluations.constants import Constants


class SyntheticChartGenerator:
    def __init__(self, vendor_key: VendorKey, profiles: dict[str, str]):
        self.vendor_key = vendor_key
        self.profiles = profiles

    @classmethod
    def load_json(cls, path: Path) -> dict[str, Any]:
        with path.open("r") as f:
            return cast(dict[str, Any], json.load(f))

    def schema_chart(self) -> dict[str, Any]:
        """Build a JSON Schema that enforces Canvas chart structure from Chart dataclass."""

        properties = {
            field_name: {
                "type": "string",
                "description": Constants.EXAMPLE_CHART_DESCRIPTIONS[field_name],
            }
            for field_name in Constants.EXAMPLE_CHART_DESCRIPTIONS.keys()
        }

        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "description": "Canvas-compatible chart structure",
            "type": "object",
            "properties": properties,
            "required": list(Constants.EXAMPLE_CHART_DESCRIPTIONS.keys()),
            "additionalProperties": False,
        }

    def generate_chart_for_profile(self, profile_text: str) -> dict[str, Any]:
        schema = self.schema_chart()

        system_prompt: list[str] = [
            "You are generating a Canvas-compatible `limited_chart.json` for a synthetic patient.",
            "Return your answer as JSON inside a fenced ```json ... ``` block.",
            "Only include fields shown in the example structure; leave irrelevant categories as empty arrays.",
        ]

        user_prompt: list[str] = [
            f"Patient profile: {profile_text}",
            "",
            "Generate a JSON object with the following fields (all string values):",
            "\n".join([f"• {field}: {desc}" for field, desc in Constants.EXAMPLE_CHART_DESCRIPTIONS.items()]),
            "",
            "Your JSON **must** conform to the following JSON Schema:",
            "```json",
            json.dumps(schema, indent=2),
            "```",
            "",
            "Be strict:",
            "• Include only conditions the patient *has or was diagnosed with*.",
            "• Include only medications the patient *is actually taking*.",
            "• Do not fabricate information beyond the profile.",
        ]

        chart_json = cast(
            dict[str, Any],
            HelperSyntheticJson.generate_json(
                vendor_key=self.vendor_key, system_prompt=system_prompt, user_prompt=user_prompt, schema=schema
            ),
        )

        return chart_json

    @classmethod
    def validate_chart(cls, chart_json: dict[str, Any]) -> bool:
        try:
            LimitedCache.load_from_json(chart_json)
            return True
        except Exception as e:
            print(f"[ERROR] invalid limited_chart.json structure: {e}")
            return False

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
        subset = list(self.profiles.items())[start - 1 : start - 1 + limit]
        output.mkdir(parents=True, exist_ok=True)
        for patient_name, profile_text in subset:
            safe_name = re.sub(r"\W+", "_", patient_name)
            patient_dir = output / safe_name
            patient_dir.mkdir(parents=True, exist_ok=True)

            print(f"Generating limited_chart.json for {patient_name}")
            chart = self.generate_chart_for_profile(profile_text)
            if not self.validate_chart(chart):
                print(f"[SKIPPED] Invalid chart for {patient_name}")
            chart = self.assign_valid_uuids(chart)

            out_path = patient_dir / "limited_chart.json"
            with out_path.open("w") as f:
                json.dump(chart, f, indent=2)
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
