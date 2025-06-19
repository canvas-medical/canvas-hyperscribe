#inputs: rubric, hyperscribe_output to be graded
#output: two vectors: score and reasoning vectors. 
#USAGE from root canvas-hyperscribe directory: uv run python rubric_eval_sample/grader.py rubric_eval_sample/rubric.json rubric_eval_sample/hyperscribe_output.json rubric_eval_sample/graded_scores.json
#SAMPLE FATIGUE_CASE USAGE: #USAGE from root canvas-hyperscribe directory: uv run python rubric_eval_sample/grader.py rubric_eval_sample/fcs/rubric.json rubric_eval_sample/fcs/summary.json rubric_eval_sample/fcs/graded_scores.json

import sys
import os
import json
import argparse

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

    # System prompt
    llm.add_prompt(LlmTurn(
        role='system',
        text=[
            "You are a clinical documentation grading assistant. You help evaluate medical scribe notes against structured rubrics in medical education contexts."
        ]
    ))

    # Refined user prompt
    llm.add_prompt(LlmTurn(
    role='user',
    text=[
        (
            "Given the rubric and the hyperscribe output below, produce a strict JSON object containing two arrays: "
            "\"score_vector\" and \"reasoning_vector\"."
        ),
        (
            "\"score_vector\" must contain one numeric score for each rubric criterion, in order. "
            "Each score must be an integer >= 0 and <= the max score for that criterion from the rubric."
        ),
        (
            "\"reasoning_vector\" must contain one short, clear explanation for each score in the score vector, describing why the score was given for that criterion."
        ),
        (
            "Make sure the two arrays have the same length and order as the rubric."
        ),
        (
            "Output ONLY the pure JSON object without ANY markdown (such as ```json), "
            "without ANY wrapping characters, without ANY commentary — just the raw JSON text starting with { and ending with }."
        ),
        "--- RUBRIC JSON ---",
        json.dumps(rubric),
        "--- HYPERSCRIBE OUTPUT JSON ---",
        json.dumps(hyperscribe_output)
        ]
    ))

    print("Grading...")
    response = llm.request()

    try:
        result = json.loads(response.response)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Wrote grading result to {output_path}")
    except json.JSONDecodeError:
        print("Warning: LLM response is not valid JSON. Saving raw output instead.") #occurred once, edited prompt to include no markdown prompting (line 60).
        with open(output_path, 'w') as f:
            f.write(response.response)
        print(f"Wrote raw response to {output_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Grade hyperscribe output against a rubric.")
    parser.add_argument("rubric_path", help="Path to rubric.json")
    parser.add_argument("hyperscribe_output_path", help="Path to hyperscribe_output.json")
    parser.add_argument("output_path", help="Path to save grading result json")

    args = parser.parse_args()

    main(args.rubric_path, args.hyperscribe_output_path, args.output_path)
