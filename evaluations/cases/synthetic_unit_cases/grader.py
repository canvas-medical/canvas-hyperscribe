import sys
import os
import json
import argparse
import re

from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog


def load_json_file(path):
    with open(path, 'r') as f:
        return json.load(f)


def main(rubric_path, hyperscribe_output_path, output_path):
    # Load input files
    rubric = load_json_file(rubric_path)
    hyperscribe_output = load_json_file(hyperscribe_output_path)

    # Initialize LLM
    llm = LlmOpenai(
        MemoryLog.dev_null_instance(),
        os.environ['KeyTextLLM'],
        Constants.OPENAI_CHAT_TEXT,
        False
    )

    llm.add_prompt(LlmTurn(
        role='system',
        text=[
            "You are a clinical documentation grading assistant. You help evaluate medical scribe notes using structured rubrics."
        ]
    ))

    llm.add_prompt(LlmTurn(
        role='user',
        text=[
            (
                "Given the rubric and the hyperscribe output below, return a JSON array where each item corresponds to one rubric criterion, "
                "in the same order as the rubric. Each item must be a dictionary with the following keys:\n"
                "- 'rationale': a short, specific explanation of how well the criterion was satisfied or not.\n"
                "- 'satisfaction': a numeric value between 0 and 100 (can be any float such as 20, 55, or 85, not just 0, 50, 100), indicating how well the criterion was satisfied.\n"
                "- 'score': the result of multiplying the satisfaction percentage (as a fraction, e.g., 83%) by the criterion's weight."
            ),
            (
                "For example, if the criterion is mostly met but missing some details, you might assign a satisfaction of 83.7, not just 50 or 100. "
                "Use your best judgment, but justify every score precisely. Avoid rounding unless clearly appropriate."
            ),
            (
                "Maintain the original order and structure of the rubric—output must be a list of the same length and order as the rubric input."
            ),
            (
                "Output ONLY the raw JSON array, starting with [ and ending with ]. No markdown, no extra text, no explanation."
            ),
            "--- BEGIN RUBRIC JSON ---",
            json.dumps(rubric),
            "--- END RUBRIC JSON",
            "--- BEGIN HYPERSCRIBE OUTPUT JSON ---",
            json.dumps(hyperscribe_output),
            "--- END HYPERSCRIBE OUTPUT JSON ---",
        ]
    ))


    print("Grading...")
    response = llm.request()
    cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()

    try:
        result = json.loads(cleaned)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Wrote grading result to {output_path}")
    except json.JSONDecodeError:
        print("Warning: LLM response is not valid JSON. Saving raw output instead.")
        with open(output_path, 'w') as f:
            f.write(cleaned)
        print(f"Wrote raw response to {output_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Grade hyperscribe output against a rubric.")
    parser.add_argument("rubric_path", help="Path to rubric.json")
    parser.add_argument("hyperscribe_output_path", help="Path to hyperscribe_output.json")
    parser.add_argument("output_path", help="Path to save grading result json")

    args = parser.parse_args()

    main(args.rubric_path, args.hyperscribe_output_path, args.output_path)
