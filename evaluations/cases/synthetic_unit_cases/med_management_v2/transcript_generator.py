import json
import re
from pathlib import Path
import os
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog


class TranscriptGenerator:
    def __init__(self, llm_key, input_profiles_path, output_root_path):
        self.llm_key = llm_key
        self.input_profiles_path = Path(input_profiles_path).expanduser()
        self.output_root = Path(output_root_path).expanduser()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.profiles = self._load_profiles()

    def _load_profiles(self):
        with self.input_profiles_path.open('r') as f:
            return json.load(f)

    def _create_llm(self):
        return LlmOpenai(
            MemoryLog.dev_null_instance(),
            self.llm_key,
            Constants.OPENAI_CHAT_TEXT,
            False
        )

    def generate_transcript_for_profile(self, profile_text):
        llm = self._create_llm()

        llm.add_prompt(LlmTurn(
            role='system',
            text=[
                "You are simulating realistic outpatient clinical conversations between a doctor and a patient based on a provided patient profile.",
                "Your output must be a raw JSON array of turn objects, where each object has a 'speaker' (either 'Doctor' or 'Patient') and 'text'.",
                "The conversation should focus on specific medication management topics relevant to the profile, such as: starting or stopping a medication, adjusting dose, managing side effects, discussing adherence challenges, or reviewing prior medication history.",
                "Avoid generic or non-specific conclusions like 'we'll keep monitoring' unless it naturally fits a detailed discussion.",
                "The dialogue should reflect realistic outpatient dynamics, with a balance of doctor questioning, patient responses, and mutual decision making about medications."
            ]
        ))

        llm.add_prompt(LlmTurn(
            role='user',
            text=[
                f"Patient profile: {profile_text}",
                "Generate a realistic transcript lasting about 20 to 30 seconds of spoken dialogue. The transcript should contain at least 6 turns between doctor and patient.",
                "Only include JSON — no markdown, code fences, or commentary."
            ]
        ))

        response = llm.request()
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()
        return json.loads(cleaned)

    def run(self):
        for patient_name, profile_text in self.profiles.items():
            #Generate a new directory per profile and place the transcript there. 
            safe_name = re.sub(r'\W+', '_', patient_name)
            patient_dir = self.output_root / safe_name
            patient_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"Generating transcript for {patient_name} → {patient_dir}")
            transcript = self.generate_transcript_for_profile(profile_text)

            transcript_path = patient_dir / "transcript.json"
            with transcript_path.open('w') as f:
                json.dump(transcript, f, indent=2)
            print(f"Saved transcript to {transcript_path}")


if __name__ == "__main__":
    llm_key = os.getenv('KeyTextLLM')
    if not llm_key:
        raise RuntimeError("KeyTextLLM environment variable is not set.")

    generator = TranscriptGenerator(
        llm_key=llm_key,
        input_profiles_path="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management_v2/patient_profiles.json",
        output_root_path="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management_v2"
    )
    generator.run()
