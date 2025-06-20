import os
import json
import argparse

from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog

def load_chart_samples(chart_samples_dir):
    samples = []
    for fname in os.listdir(chart_samples_dir):
        if fname.endswith(".json"):
            fpath = os.path.join(chart_samples_dir, fname)
            with open(fpath, 'r') as f:
                samples.append(json.load(f))
    return samples

def generate_charts_for_case(case_path, chart_samples):
    transcript_path = os.path.join(case_path, "transcript.json")
    if not os.path.exists(transcript_path):
        print(f"Transcript missing in {case_path}, skipping...")
        return

    with open(transcript_path, 'r') as f:
        transcript = json.load(f)

    llm = LlmOpenai(
        MemoryLog.dev_null_instance(),
        os.environ['KeyTextLLM'],
        Constants.OPENAI_CHAT_TEXT,
        False
    )

    llm.add_prompt(LlmTurn(
        role='system',
        text=[
            "You are a clinical informatics generator creating synthetic patient chart summaries following Canvas Medical's command module structure."
        ]
    ))

    llm.add_prompt(LlmTurn(
        role='user',
        text=[
            (
                "Generate 5 different synthetic patient chart summaries that would plausibly match the given transcript. "
                "Each chart should represent a distinct patient profile for this medication management scenario, varying by medical history, medications, allergies, and relevant conditions. "
                "Ensure that the charts follow the structure and style of the provided examples, including the use of Canvas Medical command modules. "
                "Output as a JSON array of 5 chart objects, no Markdown, no code block markers, no commentary."
            ),
            "--- TRANSCRIPT ---",
            json.dumps(transcript),
            "--- EXAMPLE CHART SAMPLES ---"
        ] + [
            json.dumps(sample) for sample in chart_samples
        ]
    ))

    print(f"Generating charts for {os.path.basename(case_path)}...")
    response = llm.request()

    try:
        charts = json.loads(response.response)
    except json.JSONDecodeError:
        print(f"Invalid JSON for {os.path.basename(case_path)}. Saving raw output.")
        raw_path = os.path.join(case_path, "raw_charts_output.txt")
        with open(raw_path, 'w') as f:
            f.write(response.response)
        return

    charts_dir = os.path.join(case_path, "charts")
    os.makedirs(charts_dir, exist_ok=True)

    for i, chart in enumerate(charts, start=1):
        chart_path = os.path.join(charts_dir, f"chart{i}.json")
        with open(chart_path, 'w') as f:
            json.dump(chart, f, indent=2)
        print(f"Saved: {chart_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case_path",
        default=os.path.expanduser("~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management/case0"),
        help="Path to the case0 directory"
    )
    parser.add_argument(
        "--chart_samples_dir",
        default=os.path.expanduser("~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/chart_samples"),
        help="Path to directory containing chart sample JSON files"
    )

    args = parser.parse_args()

    chart_samples = load_chart_samples(args.chart_samples_dir)
    if not chart_samples:
        print("No chart samples found — please add sample JSON files to chart_samples directory.")
        return

    generate_charts_for_case(args.case_path, chart_samples)

if __name__ == "__main__":
    main()
