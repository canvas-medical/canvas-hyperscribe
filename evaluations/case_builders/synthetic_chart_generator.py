import json, os, re, uuid, argparse
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast

from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.libraries.limited_cache import LimitedCache
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson

class SyntheticChartGenerator:
    def __init__(self,
        vendor_key: VendorKey,
        profiles: Dict[str, str],
        output: Path,
        example_chart: Dict[str, Any]
    ):
        self.vendor_key = vendor_key
        self.profiles = profiles
        self.output = output
        self.example_chart = example_chart
        self.output.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_json(cls, path: Path) -> Dict[str, Any]:
        with path.open("r") as f:
            return cast(Dict[str, Any], json.load(f))


    def schema_chart(self) -> Dict[str, Any]:
        """A minimal JSON Schema object that is further validated in validate_chart()."""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object"
        }

    def generate_chart_for_profile(self, profile_text: str) -> Dict[str, Any]:
        system_prompt = [
            "You are generating a Canvas Medical compatible limited_chart.json "
            "for a synthetic patient.",
            "Your output must match the JSON structure provided. Do not add unrelated fields or categories.",
            "Leave any unrelated categories as empty arrays. Do not fabricate information "
            "beyond what the patient profile describes."]
        
        user_prompt = [
            f"Patient profile: {profile_text}",
            "Here is an example structure:",
            "```json",
            json.dumps(self.example_chart, indent=2),
            "```",
            "Generate a valid limited_chart.json for this patient. "
            "Only output raw JSON — no markdown, no commentary.",
            "Be strict about including only information that is clearly **already known** in the profile.",
            "Include only conditions the patient **has had or is diagnosed with**, not symptoms or possibilities.",
            "Include only medications the patient is **actually taking**, not ones they might take.",
            "Everything in the chart must be retrospective and factual."]
        
        schema = self.schema_chart()
        chart_json = cast(Dict[str, Any], HelperSyntheticJson.generate_json(
            vendor_key=self.vendor_key,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
            retries=3))

        return chart_json

    @classmethod
    def validate_chart(self, chart_json: Dict[str, Any]) -> None:
        try:
            LimitedCache.load_from_json(chart_json)
        except Exception as e:
            raise ValueError(f"Invalid limited_chart.json structure: {e}")

    @classmethod
    def assign_valid_uuids(self, obj: Any) -> Any:
        stack: List[Tuple[Any, Any]] = [(None, obj)]
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

    def run_range(self, start: int, limit: int) -> None:
        subset = list(self.profiles.items())[start-1 : start-1 + limit]
        for patient_name, profile_text in subset:
            safe_name  = re.sub(r"\W+", "_", patient_name)
            patient_dir = self.output / safe_name
            patient_dir.mkdir(parents=True, exist_ok=True)

            print(f"Generating limited_chart.json for {patient_name}")
            chart = self.generate_chart_for_profile(profile_text)
            self.validate_chart(chart)
            chart = self.assign_valid_uuids(chart)

            out_path = patient_dir / "limited_chart.json"
            with out_path.open("w") as f:
                json.dump(chart, f, indent=2)
            print(f"Saved limited_chart.json to {out_path}")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Canvas-compatible limited_chart.json files.")
    parser.add_argument("--input",  type=Path, required=True,
        help="Path to combined profiles JSON")
    parser.add_argument("--output", type=Path, required=True,
        help="Directory to write per-patient folders")
    parser.add_argument("--start", type=int, default=1,
        help="1-based index of first profile to process")
    parser.add_argument( "--limit", type=int, required=True,
        help="Number of profiles to generate charts for")
    parser.add_argument("--example", type=Path, required=True,
        help="Path to representative limited_chart.json example")
    args = parser.parse_args()

    settings = HelperEvaluation.settings()
    vendor_key = settings.llm_text
    profiles = SyntheticChartGenerator.load_json(args.input)
    example_chart = SyntheticChartGenerator.load_json(args.example)

    generator = SyntheticChartGenerator(
        vendor_key=vendor_key,
        profiles=profiles,
        output=args.output,
        example_chart=example_chart)
    generator.run_range(start=args.start, limit=args.limit)

if __name__ == "__main__":
    main()
