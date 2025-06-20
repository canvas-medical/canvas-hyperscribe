import os
import json
import argparse

from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog

def generate_transcripts(base_dir, n_cases, seed_transcript):
    med_dir = os.path.join(base_dir, "med_management")
    os.makedirs(med_dir, exist_ok=True)

    llm = LlmOpenai(MemoryLog.dev_null_instance(), os.environ['KeyTextLLM'], Constants.OPENAI_CHAT_TEXT, False)

    llm.add_prompt(LlmTurn(
        role='system',
        text=[
            "You are a skilled clinical language generator specializing in synthetic patient-doctor conversations for medical training."
        ]
    ))

    llm.add_prompt(LlmTurn(
        role='user',
        text=[
            (
                f"Generate {n_cases} synthetic patient-doctor transcripts related to medication management. "
                "Each transcript should simulate a realistic interaction focused on medication reconciliation, adjusting medications, managing side effects, or related tasks. "
                "Use the provided transcript as a stylistic and structural reference. Do not copy it, but try to generate these transcripts as a comprehensive suite testing conversations about medication management between doctors and patients."
            ),
            "--- EXAMPLE TRANSCRIPT ---",
            json.dumps(seed_transcript),
            (
                "Each generated transcript must be a JSON array of turn objects with 'speaker' and 'text'. "
                "Speakers must be 'Doctor' or 'Patient'. "
                "Do not include any Markdown, code blocks, or commentary. Output only the JSON array of arrays."
            )
        ]
    ))

    print(f"Generating {n_cases} synthetic transcripts...")
    response = llm.request()

    try:
        transcripts = json.loads(response.response)
    except json.JSONDecodeError:
        print("Invalid JSON from LLM. Saving raw output.")
        raw_path = os.path.join(med_dir, "raw_transcripts_output.txt")
        with open(raw_path, 'w') as f:
            f.write(response.response)
        print(f"Raw output saved to {raw_path}")
        return

    for idx, transcript in enumerate(transcripts, start=1):
        case_dir = os.path.join(med_dir, f"case{idx}")
        os.makedirs(case_dir, exist_ok=True)
        transcript_path = os.path.join(case_dir, "transcript.json")
        with open(transcript_path, 'w') as f:
            json.dump(transcript, f, indent=2)
        print(f"Saved: {transcript_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_dir", default=os.path.expanduser("~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases"), help="Base synthetic_unit_cases directory")
    parser.add_argument("--n_cases", type=int, default=10, help="Number of synthetic transcripts to generate")
    args = parser.parse_args()

    init_transcript = [
        {
            "speaker": "Doctor",
            "text": "I think we should stop the statin for now because of your muscle aches."
        },
        {
            "speaker": "Patient",
            "text": "Okay, I was wondering about that."
        },
        {
            "speaker": "Doctor",
            "text": "I'm going to prescribe a PCSK9 inhibitor instead and we'll see if that works better."
        }
    ]

    generate_transcripts(args.base_dir, args.n_cases, init_transcript)
