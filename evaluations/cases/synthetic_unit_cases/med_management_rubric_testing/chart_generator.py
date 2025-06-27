import json
import re
import uuid
from pathlib import Path
import os
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.libraries.limited_cache import LimitedCache


class ChartGenerator:
    def __init__(self, llm_key, input_profiles_path, output_root_path, example_chart_path):
        self.llm_key = llm_key
        self.input_profiles_path = Path(input_profiles_path).expanduser()
        self.output_root = Path(output_root_path).expanduser()
        self.example_chart_path = Path(example_chart_path).expanduser()

        self.profiles = self._load_profiles()
        self.example_chart = self._load_example_chart()

    def _load_profiles(self):
        with self.input_profiles_path.open('r') as f:
            return json.load(f)

    def _load_example_chart(self):
        with self.example_chart_path.open('r') as f:
            return json.load(f)

    def _create_llm(self):
        return LlmOpenai(
            MemoryLog.dev_null_instance(),
            self.llm_key,
            Constants.OPENAI_CHAT_TEXT,
            False
        )

    def generate_chart_for_profile(self, profile_text):
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
                "Be strict about including only information that is clearly **already known or documented** in the profile. Do not speculate or infer anything that could happen in the future.",
                "Include only conditions the patient **has had or is actively diagnosed with**, not symptoms or possibilities.",
                "Include only medications the patient is **actually taking**, not medications they might take, are considering, or could be prescribed.",
                "Everything in the chart must be written from a factual, retrospective standpoint — it should reflect the patient’s clinical record, not a future possibility or plan."
            ]
        ))


        response = llm.request()
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()
        return json.loads(cleaned)

    def validate_chart(self, chart_json):
        try:
            LimitedCache.load_from_json(chart_json)
        except Exception as e:
            raise ValueError(f"Invalid limited_chart.json structure: {e}")

    def assign_valid_uuids(self, obj):
        """
        Recursively walk the JSON dict/list and replace any 'uuid' field with a generated UUID4.
        """
        if isinstance(obj, dict):
            return {
                k: str(uuid.uuid4()) if k.lower() == 'uuid' else self.assign_valid_uuids(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [self.assign_valid_uuids(item) for item in obj]
        else:
            return obj

    def run(self):
        for patient_name, profile_text in self.profiles.items():
            safe_name = re.sub(r'\W+', '_', patient_name)
            patient_dir = self.output_root / safe_name
            patient_dir.mkdir(parents=True, exist_ok=True)

            print(f"Generating limited_chart.json for {patient_name} → {patient_dir}")
            chart_json = self.generate_chart_for_profile(profile_text)

            # Validate
            self.validate_chart(chart_json)

            # Replace UUIDs
            chart_json = self.assign_valid_uuids(chart_json)

            # Save
            chart_path = patient_dir / "limited_chart.json"
            with chart_path.open('w') as f:
                json.dump(chart_json, f, indent=2)
            print(f"Saved limited_chart.json to {chart_path}")


if __name__ == "__main__":
    llm_key = os.getenv('KeyTextLLM')
    if not llm_key:
        raise RuntimeError("KeyTextLLM environment variable is not set.")

    generator = ChartGenerator(
        llm_key=llm_key,
        input_profiles_path="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management_collated/patient_profiles.json",
        output_root_path="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management_collated",
        example_chart_path="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/representative_limited_chart.json"
    )
    generator.run()
