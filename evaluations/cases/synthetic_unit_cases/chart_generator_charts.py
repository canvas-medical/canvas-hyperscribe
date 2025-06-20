import os
import json
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog

# Embedded sample chart structure
SAMPLE_CHART = {
  "stagedCommands": {
    "reasonForVisit": [
      {
        "uuid": "sample-uuid-1",
        "label": "Medication Management Visit",
        "code": "MMV-001"
      }
    ]
  },
  "demographicStr": "the patient is a male, born on 1970-01-01 (age 54)",
  "currentConditions": [
    {
      "uuid": "sample-cond-1",
      "label": "Essential hypertension",
      "code": "I10"
    }
  ],
  "currentMedications": [
    {
      "uuid": "sample-med-1",
      "label": "Lisinopril 10 mg tablet",
      "code": "197361"
    }
  ],
  "currentAllergies": [
    {
      "uuid": "sample-allergy-1",
      "label": "Penicillin",
      "code": "70618"
    }
  ],
  "surgeryHistory": [],
  "familyHistory": []
}

def generate_charts_for_profiles(llm, profiles, charts_dir):
    os.makedirs(charts_dir, exist_ok=True)
    for idx, profile in enumerate(profiles, 1):
        llm.add_prompt(LlmTurn(
            role='system',
            text=[
                "You are a clinical informatics assistant tasked with generating chart JSONs in Canvas Medical command style."
            ]
        ))
        llm.add_prompt(LlmTurn(
            role='user',
            text=[
                (
                    "Given this patient profile and chart sample, generate a full chart JSON file in Canvas Medical command module structure. "
                    "Be realistic and consistent with the profile. Output raw JSON object only — no Markdown, no commentary."
                ),
                "--- PATIENT PROFILE ---",
                json.dumps(profile),
                "--- CHART SAMPLE ---",
                json.dumps(SAMPLE_CHART)
            ]
        ))
        response = llm.request()
        chart = json.loads(response.response)
        chart_path = os.path.join(charts_dir, f"chart{idx}.json")
        with open(chart_path, 'w') as f:
            json.dump(chart, f, indent=2)
        print(f"Saved {chart_path}")

def main():
    #fix later, make this into a parameter entered in by user.
    base_dir = os.path.expanduser("~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management/case0")
    profiles_path = os.path.join(base_dir, "patient_profiles.json")
    charts_dir = os.path.join(base_dir, "charts_v2")

    with open(profiles_path, 'r') as f:
        profiles = json.load(f)

    llm = LlmOpenai(
        MemoryLog.dev_null_instance(),
        os.environ['KeyTextLLM'],
        Constants.OPENAI_CHAT_TEXT,
        False
    )

    generate_charts_for_profiles(llm, profiles, charts_dir)

if __name__ == "__main__":
    main()
