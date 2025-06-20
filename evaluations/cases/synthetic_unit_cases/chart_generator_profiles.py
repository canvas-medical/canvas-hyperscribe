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
            "Generate 5 distinct short patient profile summaries that could realistically correspond to the following medical conversation transcript. "
            "Each summary should be a plausible patient scenario for this case. Do not include details from the transcript to inform the profile–it should be a background for the patient for which the transcript could be a conversation."
            "Vary the detail and completeness across profiles to reflect real-world documentation — for example, some profiles may include more medication details, others may emphasize conditions or context. "
            "Format the output as a JSON object where each key is 'Patient N' (where N is 1-5) and each value is a string summary of that patient's profile. "
            "Example: {\"Patient 1\": \"Profile 1 summary...\", \"Patient 2\": \"Profile 2 summary...\", ...}. "
            "Do not include Markdown, code block formatting, or commentary. Output raw JSON only."
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
    profiles_path = os.path.join(base_dir, "patient_profiles_v2.json")

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
