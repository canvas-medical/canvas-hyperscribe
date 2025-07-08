import json, re, uuid, os, argparse
from pathlib import Path
from hyperscribe.llms.llm_openai_o3 import LlmOpenaiO3
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.libraries.limited_cache import LimitedCache
from typing import Any

class ChartGenerator:
    def __init__(self, llm_key: str, profiles: dict[str, str], output_root: Path, example_chart: dict[str, Any]):
        self.llm_key = llm_key
        self.profiles = profiles
        self.output_root = output_root
        self.example_chart = example_chart

    @classmethod
    def load_json(path: Path) -> Any:
        with path.open('r') as f:
            return json.load(f)

    def generate_chart_for_profile(self, profile_text: str) -> Any:
        llm = LlmOpenaiO3(MemoryLog.dev_null_instance(), self.llm_key, with_audit=False)
        llm.add_prompt(LlmTurn(role='system', text=[
            "You are generating a Canvas Medical compatible limited_chart.json for a synthetic patient.",
            "Your output must match the JSON structure provided. Do not add unrelated fields or categories.",
            "Leave any unrelated categories as empty arrays. Do not fabricate information beyond what the patient profile describes."
        ]))
        llm.add_prompt(LlmTurn(role='user', text=[
            f"Patient profile: {profile_text}",
            f"Here is an example structure:\n{json.dumps(self.example_chart, indent=2)}",
            "Generate a valid limited_chart.json for this patient. Only output raw JSON — no markdown, no commentary.",
            "Be strict about including only information that is clearly **already known or documented** in the profile. "
            "Do not speculate or infer anything that could happen in the future.",
            "Include only conditions the patient **has had or is actively diagnosed with**, not symptoms or possibilities.",
            "Include only medications the patient is **actually taking**, not medications they might take, are considering, or could be prescribed.",
            "Everything in the chart must be written from a factual, retrospective standpoint — it should reflect the patient’s clinical record, "
            "not a future possibility or plan."
        ]))
        response = llm.request()
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()
        return json.loads(cleaned)

    def validate_chart(self, chart_json: dict[str, Any]) -> None:
        try:
            LimitedCache.load_from_json(chart_json)
        except Exception as e:
            raise ValueError(f"Invalid limited_chart.json structure: {e}")

    def assign_valid_uuids(self, obj: Any) -> Any:
        stack = [(None, obj)]
        while stack:
            parent, current = stack.pop()
            if isinstance(current, dict):
                for k, v in current.items():
                    if k.lower() == 'uuid':
                        current[k] = str(uuid.uuid4())
                    else:
                        stack.append((current, v))
            elif isinstance(current, list):
                for item in current:
                    stack.append((current, item))
        return obj

    def run_range(self, start_index: int, limit: int) -> None:
        items = list(self.profiles.items())[start_index - 1 : start_index - 1 + limit]
        for patient_name, profile_text in items:
            safe_name = re.sub(r'\W+', '_', patient_name)
            patient_dir = self.output_root / safe_name
            patient_dir.mkdir(parents=True, exist_ok=True)

            print(f"Generating limited_chart.json for {patient_name} in {patient_dir}")
            chart_json = self.generate_chart_for_profile(profile_text)
            self.validate_chart(chart_json)
            chart_json = self.assign_valid_uuids(chart_json)

            chart_path = patient_dir / "limited_chart.json"
            with chart_path.open('w') as f:
                json.dump(chart_json, f, indent=2)
            print(f"Saved limited_chart.json to {chart_path}")


def main() -> None:
    settings = Settings.from_dictionary(os.environ)
    vendor_key: VendorKey = settings.llm_text

    parser = argparse.ArgumentParser(description="Generate Canvas-compatible limited_chart.json files.")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--limit", type=int, required=True)
    parser.add_argument("--profiles", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--example", type=str, required=True)

    args = parser.parse_args()

    profiles = ChartGenerator.load_json(args.profiles)
    example_chart = ChartGenerator.load_json(args.example)
    generator = ChartGenerator(vendor_key.api_key, profiles, Path(args.out), example_chart)
    generator.run_range(args.start, args.limit)


if __name__ == "__main__":
    main()
