import os
import re
import json
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog

def generate_med_management_profiles_batch(llm, batch_num, count=5, seen_scenarios=None):
    if seen_scenarios is None:
        seen_scenarios = []

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
                "Each value should be a realistic narrative (4-6 sentences) describing a distinct patient profile. Make sure these are written in the past tense to describe the patient history."
            ),
            (
                "Ensure this batch spans diverse medication management scenarios, including: "
                "common chronic conditions (e.g., hypertension, hyperlipidemia, diabetes, CKD); "
                "polypharmacy/complex cases; special populations (e.g., pediatric, pregnant, frail elderly); "
                "risky medication classes (e.g., anticoagulants, opioids, psychotropics); "
                "medication transitions/adjustments (e.g., side effect-driven changes, dose adjustments, new initiations); "
                "various care contexts (e.g. new patient intake, post-discharge management, assisted living scenarios, rural pharmacy limitations). "
                "Include at least one patient in this batch where the prior medical history, medication list, or allergies are undocumented or unknown, requiring the care team to investigate and clarify these details."
            ),
            (
                "Each patient narrative must describe relevant details supporting medication management decisions, including key workflows. "
                "Do not repeat or closely mimic previous patient scenarios — create unique combinations of conditions, medications, demographics, or contexts not already described."
            ),
            (
                "Prior patients covered these scenarios: "
                + "; ".join(seen_scenarios) + ". "
                "Ensure none of these are repeated or too similar."
            ) if seen_scenarios else "This is the first batch — ensure diverse and unique scenarios.",
            (
                "Output raw JSON only — no Markdown, code formatting, or commentary."
            )
        ]
    ))

    response = llm.request()
    cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()
    batch_profiles = json.loads(cleaned)
    return batch_profiles

def main():
    output_path = os.path.expanduser(
        "~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management_v2/patient_profiles_v2.json"
    )
    all_profiles = {}
    seen_scenarios = []

    for batch_num in range(1, 9):  # 8 batches × 5 = 40 profiles
        print(f"Generating batch {batch_num}...")
        llm = LlmOpenai(
            MemoryLog.dev_null_instance(),
            os.environ['KeyTextLLM'],
            Constants.OPENAI_CHAT_TEXT,
            False
        )
        batch_profiles = generate_med_management_profiles_batch(llm, batch_num, seen_scenarios=seen_scenarios)
        for profile in batch_profiles.values():
            summary = profile.split(".")[0][:100]
            seen_scenarios.append(summary)
        all_profiles.update(batch_profiles)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(all_profiles, f, indent=2)

    print(f"Saved 40 medication management profiles to {output_path}")

if __name__ == "__main__":
    main()
