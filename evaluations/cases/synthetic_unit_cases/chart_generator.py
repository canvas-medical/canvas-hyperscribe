import json, re, uuid, os, argparse
import re
import uuid
from pathlib import Path
from hyperscribe.llms.llm_openai_o3 import LlmOpenaiO3
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.libraries.limited_cache import LimitedCache
from typing import Any, cast

class ChartGenerator:
    def __init__(self, llm_key: str, input_profiles_path: str, output_root_path: str, example_chart_path: str) -> None:
        self.llm_key = llm_key
        self.input_profiles_path = Path(input_profiles_path).expanduser()
        self.output_root = Path(output_root_path).expanduser()
        self.example_chart_path = Path(example_chart_path).expanduser()
        self.profiles = self._load_profiles()
        self.example_chart = self._load_example_chart()

    @classmethod
    def _load_profiles(self) -> dict[str, str]:
        with self.input_profiles_path.open('r') as f:
            return cast(dict[str, str], json.load(f))

    def _load_example_chart(self) -> dict[str, str | list[dict[str, str]]]:
        with self.example_chart_path.open('r') as f:
            return cast(dict[str, str | list[dict[str, str]]], json.load(f))

    def _create_llm(self) -> LlmOpenaiO3:
        return LlmOpenaiO3(
            MemoryLog.dev_null_instance(),
            self.llm_key,
            with_audit=False
        )

    def generate_chart_for_profile(self, profile_text: str) -> Any:
        llm = self._create_llm()

        llm.add_prompt(LlmTurn(
            role='system',
            text=[
                "You are generating a Canvas Medical compatible limited_chart.json for a synthetic patient.",
                "Your output must match the JSON structure provided. Do not add unrelated fields or categories.",
                "Leave any unrelated categories as empty arrays. Do not fabricate information beyond what the patient profile describes."
            ]
        ))

        llm.add_prompt(LlmTurn(
            role='user',
            text=[
                f"Patient profile: {profile_text}",
                f"Here is an example structure:\n{json.dumps(self.example_chart, indent=2)}",
                "Generate a valid limited_chart.json for this patient. Only output raw JSON — no markdown, no commentary.",
                "Be strict about including only information that is clearly **already known or documented** in the profile. "
                "Do not speculate or infer anything that could happen in the future.",
                "Include only conditions the patient **has had or is actively diagnosed with**, not symptoms or possibilities.",
                "Include only medications the patient is **actually taking**, not medications they might take, are considering, or could be prescribed.",
                "Everything in the chart must be written from a factual, retrospective standpoint — it should reflect the patient’s clinical record, "
                "not a future possibility or plan."
            ]
        ))


        response = llm.request()
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()
        return json.loads(cleaned)

    def validate_chart(self, chart_json: dict[str, str | list[dict[str, str]]]) -> None:
        try:
            LimitedCache.load_from_json(chart_json)
        except Exception as e:
            raise ValueError(f"Invalid limited_chart.json structure: {e}")

    def assign_valid_uuids(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: str(uuid.uuid4()) if k.lower() == 'uuid' else self.assign_valid_uuids(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [self.assign_valid_uuids(item) for item in obj]
        else:
            return obj

    def run(self, start_index: int = 1, limit: int | None = None) -> None:
        items = self.profiles.values()
        items = items[start_index - 1:]
        if limit is not None:
            items = items[:limit]

        for patient_name, profile_text in items:
            safe_name = re.sub(r'\W+', '_', patient_name)
            patient_dir = self.output_root / safe_name
            patient_dir.mkdir(parents=True, exist_ok=True)

            print(f"Generating limited_chart.json for {patient_name} in {patient_dir}")
            chart_json = self.generate_chart_for_profile(profile_text)

            #chart validation and formatting.
            self.validate_chart(chart_json)
            chart_json = self.assign_valid_uuids(chart_json)

            #saving. 
            chart_path = patient_dir / "limited_chart.json"
            with chart_path.open('w') as f:
                json.dump(chart_json, f, indent=2)
            print(f"Saved limited_chart.json to {chart_path}")

if __name__ == "__main__":
    settings = Settings.from_dictionary(os.environ)
    vendor_key: VendorKey = settings.llm_text

    parser = argparse.ArgumentParser(
        description="Generate Canvas-compatible limited_chart.json files.")
    parser.add_argument("--start", type=int, default=1,
                        help="1-based patient index to start from (default 1)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N patients (default: all)")
    parser.add_argument("--profiles", type=str, required=False,
                        help="Path to patient_profiles.json")
    parser.add_argument("--out", type=str, required=False,
                        help="Root folder to write Patient_X/limited_chart.json")
    parser.add_argument("--example", type=str, required=False,
                        help="Example limited_chart structure")

    args = parser.parse_args()

    generator = ChartGenerator(vendor_key.api_key, args.profiles,
                        args.out, args.example)
    generator.run(args.start, args.limit)

