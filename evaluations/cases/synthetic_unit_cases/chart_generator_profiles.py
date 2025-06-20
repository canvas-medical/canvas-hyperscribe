import os
import json
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog

def generate_patient_profiles(llm, transcript, output_path):
    llm.add_prompt(LlmTurn(
        role='system',
        text=[
            "You are a clinical informatics assistant tasked with designing plausible synthetic patient profiles for medical education."
        ]
    ))
    llm.add_prompt(LlmTurn(
        role='user',
        text=[
            (
                "Generate a JSON array of 5 distinct patient profiles that would be realistic given the following transcript of a medical conversation. "
                "Each profile should be a plausible variation of a patient where this transcript could apply. "
                "Each profile must include: age, sex, conditions (list), medications (list), allergies (list), and recent care context (brief sentence). "
                "This list of characteristics for the profile is not comprehensive — include any relevant information that would ensure that the patient profile being created is different from the others. "
                "Output raw JSON array only — no Markdown, no commentary."
            ),
            "--- TRANSCRIPT JSON ---",
            json.dumps(transcript)
        ]
    ))
    response = llm.request()

    #fixes markdown variation creeping in occasionally.
    raw_response = response.response.strip()
    if raw_response.startswith("```"):
        raw_response = raw_response.split("```")[1].strip()
    if raw_response.startswith("json"):
        raw_response = raw_response[len("json"):].strip()

    profiles = json.loads(raw_response)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(profiles, f, indent=2)
    print(f"Saved patient profiles to {output_path}")

    return profiles

def main():
    #fix later, make this into a parameter entered in by user.
    base_dir = os.path.expanduser("~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management/case0")
    transcript_path = os.path.join(base_dir, "transcript.json")
    profiles_path = os.path.join(base_dir, "patient_profiles.json")

    with open(transcript_path, 'r') as f:
        transcript = json.load(f)

    llm = LlmOpenai(
        MemoryLog.dev_null_instance(),
        os.environ['KeyTextLLM'],
        Constants.OPENAI_CHAT_TEXT,
        False
    )

    generate_patient_profiles(llm, transcript, profiles_path)

if __name__ == "__main__":
    main()
