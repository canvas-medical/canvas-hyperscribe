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
            role="system",
            text=[
                "You are a clinical informatics expert generating synthetic patient profiles for testing medication management AI systems. You understand the structure and variation in real EHR notes and how medication histories reflect complex clinical decision-making."
            ]
        ))

        llm.add_prompt(LlmTurn(
            role="user",
            text=[
                (
                    f"Create a JSON object with {count} key-value pairs labeled 'Patient {1 + (batch_num - 1) * count}' through 'Patient {batch_num * count}'. "
                    "Each value should be a free-text, realistic background narrative (3–7 sentences) summarizing the patient's longitudinal medication history."
                ),
                (
                    "The narrative **should resemble a subjective section or HPI summary** from a clinician’s perspective — not a templated demographic blurb. "
                    "Write each one differently, varying structure, voice, and order of information (e.g., lead with medication list, or with allergies, or with family history)."
                ),
                (
                    "Include details such as: current and prior medications (with reason for changes or side effects), relevant comorbidities, family history (if relevant), allergies, and any known social factors or documentation gaps that affect medication decisions."
                ),
                (
                    "Demographic context (age, gender, life role) should be lightly woven in — e.g., 'a retired mechanic in his 70s', 'a young woman recently diagnosed with diabetes', or implied through phrasing. Avoid template-like openings, but include enough detail to anchor the narrative."
                ),
                (
                    "Cover a **diverse set of realistic scenarios**, including: straightforward new prescriptions with no prior history; simple dose adjustments or clean medication changes (e.g., lisinopril to losartan); chronic single-medication use; and also complex edge cases involving risky medications, polypharmacy, or social barriers."
                ),
                (
                    "Avoid visit summaries, symptom descriptions, or care plans. These are background medication narratives, not SOAP notes or assessments."
                ),
                (
                    f"Previous profiles included scenarios like: {', '.join(self.seen_scenarios)}. Avoid repeating similar patients or medication stories. Use new combinations, conditions, or social factors that introduce variation without always increasing complexity."
                ) if self.seen_scenarios else "This is the first batch — ensure maximal diversity in profile structure, condition type, and medication reasoning.",
                (
                    "Output raw JSON only — no Markdown, no explanation, no formatting."
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

    def _save_combined(self):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open('w') as f:
            json.dump(self.all_profiles, f, indent=2)
        print(f"Saved {len(self.all_profiles)} medication management profiles to {self.output_path}")

    def _save_individuals(self):
        base_dir = self.output_path.parent
        for name, narrative in self.all_profiles.items():
            # Sanitize name for directory (e.g., "Patient 1" -> "Patient_1")
            dir_name = re.sub(r'\s+', '_', name.strip())
            dir_path = base_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

            file_path = dir_path / "profile.json"
            with file_path.open('w') as f:
                json.dump({name: narrative}, f, indent=2)
            print(f"Saved profile for {name} to {file_path}")

    def run(self, batches=8, batch_size=5):
        for batch_num in range(1, batches + 1):
            print(f"Generating batch {batch_num}...")
            batch_profiles = self.generator.generate_batch(batch_num, batch_size)
            for profile in batch_profiles:
                self.all_profiles[profile.name] = profile.narrative

        self._save_combined()
        self._save_individuals()


if __name__ == "__main__":
    llm_key = os.getenv('KeyTextLLM')
    if not llm_key:
        raise RuntimeError("KeyTextLLM environment variable is not set.")

    pipeline = PatientProfilePipeline(
        llm_key=llm_key,
        output_path_str="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management_collated/patient_profiles.json"
    )
    pipeline.run()
