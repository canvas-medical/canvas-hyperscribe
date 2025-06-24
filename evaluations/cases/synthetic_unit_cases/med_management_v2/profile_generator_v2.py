import re
import json
from pathlib import Path
import os
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog


class PatientProfile:
    def __init__(self, name, narrative):
        self.name = name
        self.narrative = narrative

    def summarize_scenario(self):
        #Returns first sentence to ensure profile diversity with downstream seen_scenarios variable.
        return self.narrative.split(".")[0][:100]


class PatientProfileGenerator:
    def __init__(self, llm_key):
        self.llm_key = llm_key
        self.seen_scenarios = []

    def _create_llm(self):
        return LlmOpenai(
            MemoryLog.dev_null_instance(),
            self.llm_key,
            Constants.OPENAI_CHAT_TEXT,
            False
        )

    def generate_batch(self, batch_num, count=5):
        llm = self._create_llm()

        llm.add_prompt(LlmTurn(
            role='system',
            text=[
                "You are a clinical informatics expert designing synthetic patient profiles for medical education on medication management."
            ]
        ))

        llm.add_prompt(LlmTurn(
            role='user',
            text=[
                (
                    f"Generate a JSON object with {count} key-value pairs. "
                    f"Each key should be \"Patient {1 + (batch_num - 1) * count}\", "
                    f"\"Patient {2 + (batch_num - 1) * count}\", ..., "
                    f"\"Patient {batch_num * count}\". "
                    "Each value should be a realistic narrative (4-6 sentences) describing a distinct patient profile. "
                    "The narrative should focus only on the patient’s medical history, past diagnoses, current medication list, and relevant family or allergy history. "
                    "Do not describe any clinic visit, evaluation, current symptoms, or plan. "
                    "Do not include any recommendations, advice, or care team actions."
                ),
                (
                    "Ensure this batch spans diverse medication management scenarios, including: "
                    "common chronic conditions (e.g., hypertension, hyperlipidemia, diabetes, CKD); "
                    "polypharmacy/complex cases; special populations (e.g., pediatric, pregnant, frail elderly); "
                    "risky medication classes (e.g., anticoagulants, opioids, psychotropics); "
                    "medication transitions/adjustments in the past (e.g., side effect-driven changes, dose adjustments, prior discontinuations). "
                    "Include at least one patient where prior medical history, medication list, or allergies are undocumented or unclear."
                ),
                (
                    "Each patient narrative must present background information only — no visit context, no active concerns, no plan or recommendations."
                ),
                (
                    "Prior patients covered these scenarios: "
                    + "; ".join(self.seen_scenarios) + ". "
                    "Ensure none of these are repeated or too similar."
                ) if self.seen_scenarios else "This is the first batch — ensure diverse and unique scenarios.",
                (
                    "Output raw JSON only — no Markdown, code formatting, or commentary."
                )
            ]
        ))



        response = llm.request()
        #cleans any errors with json formatting (safety net)
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()
        batch_data = json.loads(cleaned)

        batch_profiles = []
        for name, narrative in batch_data.items():
            profile = PatientProfile(name, narrative)
            self.seen_scenarios.append(profile.summarize_scenario())
            batch_profiles.append(profile)

        return batch_profiles

class PatientProfilePipeline:
    def __init__(self, llm_key, output_path_str):
        self.generator = PatientProfileGenerator(llm_key)
        self.output_path = Path(output_path_str).expanduser()
        self.all_profiles = {}

    def _save(self):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open('w') as f:
            json.dump(self.all_profiles, f, indent=2)
        print(f"Saved {len(self.all_profiles)} medication management profiles to {self.output_path}")

    def run(self, batches=8, batch_size=5):
        for batch_num in range(1, batches + 1):
            print(f"Generating batch {batch_num}...")
            batch_profiles = self.generator.generate_batch(batch_num, batch_size)
            for profile in batch_profiles:
                self.all_profiles[profile.name] = profile.narrative

        self._save()

if __name__ == "__main__":
    llm_key = os.getenv('KeyTextLLM')
    if not llm_key:
        raise RuntimeError("KeyTextLLM environment variable is not set.")

    pipeline = PatientProfilePipeline(
        llm_key=llm_key,
        output_path_str="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management_v2/patient_profiles.json"
    )
    pipeline.run()
