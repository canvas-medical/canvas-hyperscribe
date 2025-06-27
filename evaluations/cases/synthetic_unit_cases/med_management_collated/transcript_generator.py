from pathlib import Path
import json
import re
import os
import random
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
        self.seen_openings = set()

    def _load_profiles(self):
        with self.input_profiles_path.open('r') as f:
            return json.load(f)

    def _create_llm(self, seen_openings_prompt):
        llm = LlmOpenai(
            MemoryLog.dev_null_instance(),
            self.llm_key,
            Constants.OPENAI_CHAT_TEXT,
            False
        )

        system_prompt = [
            "You are simulating realistic outpatient clinical conversations between a clinician and a patient, based on a synthetic patient profile.",
            "Your output must be a raw JSON array of turn objects, each with a 'speaker' (either 'Clinician' or 'Patient') and a 'text'.",
            "The transcript is not the full visit — it should be a **snippet** from the middle of an ongoing conversation.",
            "The snippet must start **midway through a conversation**, not with a greeting or with the start of a discussion. It may resume a topic, clarify something mentioned earlier, or reflect a shift in focus.",
            "Do not introduce new major topics in the first line of the snippet.",
            "Avoid ending with concluding remarks like 'Thanks for coming in,' 'We’ll follow up,' or 'Take care.' The conversation should end as if it is about to continue.",
            "You will be told who starts the snippet — the first turn must come from that speaker.",
            "Choose a random conversation **duration** from: [15, 20, 25, 30, 35, 40, 45, 50, 55, 60] seconds. Then, choose a **turn count** at uniform random between 2 and the ceiling of (duration / 10).",
            "The conversation should focus on detailed medication management topics such as: starting/stopping a medication, dose adjustments, managing side effects, adherence concerns, family influence, or prior experiences with medications.",
            "You must **randomly assign** each transcript an affective context. Choose one or more relevant affective states and pressures (internal or external):",
            "Affective states: patient is frustrated, patient is tearful, clinician is concerned, clinician is rushed, patient is embarrassed, patient is defensive.",
            "External pressures: time pressure on the visit, formulary change, side effect report just came in, patient is traveling soon, refill limit reached, insurance denied prior authorization.",
            "Also choose random personality archetypes for both the clinician and the patient:",
            "Clinician personalities: warm and chatty; brief and efficient; cautious and inquisitive; overexplainer.",
            "Patient personalities: anxious and talkative; confused and forgetful; assertive and informed; agreeable but vague.",
            "Ensure natural variation in sentence structure and tone. Include occasional hesitations, clarifications, or corrections — the kinds of imperfect phrasing common in real clinical conversations.",
            "Do not include any metadata, Markdown, or explanation — only a valid JSON array of turns with 'speaker' and 'text' keys."
        ]

        if self.seen_openings:
            seen_lines = ', '.join(f'"{line}"' for line in sorted(self.seen_openings))
            system_prompt.append(
                f"Previous conversation openings include: {seen_lines}. Strictly avoid beginning with any of the following lines."
            )

        llm.add_prompt(LlmTurn(role='system', text=system_prompt))
        return llm

    def generate_transcript_for_profile(self, profile_text):
        first_speaker = random.choice(["Clinician", "Patient"])
        llm = self._create_llm(self.seen_openings)

        llm.add_prompt(LlmTurn(
            role='user',
            text=[
                f"Patient profile: {profile_text}",
                f"The snippet must start with the {first_speaker}.",
                "Generate a realistic JSON transcript snippet (not a full conversation) that follows the instructions above.",
                "Start in the **middle of a conversation**, not with a greeting or the beginning of a visit. The conversation should already be in progress.",
                "Do not summarize previous content; instead, resume mid-topic, clarify something, or continue an ongoing medication-related exchange.",
                "End the snippet as if the conversation is ongoing — do not include final remarks or closing phrases.",
                "Focus on specific medication management details. Include natural-sounding language and occasional imperfect phrasing, like hesitations or course corrections."
            ]
        ))

        response = llm.request()
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()
        transcript = json.loads(cleaned)

        if transcript and isinstance(transcript, list) and "text" in transcript[0]:
            opening_line = transcript[0]["text"].strip()
            self.seen_openings.add(opening_line)

        return transcript

    def run(self):
        for patient_name, profile_text in self.profiles.items():
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
        input_profiles_path="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management_collated/patient_profiles.json",
        output_root_path="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management_collated"
    )
    generator.run()
