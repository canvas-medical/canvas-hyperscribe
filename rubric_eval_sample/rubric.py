#input: chart, transcript, canvas-specific context (descriptions of the implemented-commands class)
#api call for model with specific prompt to ask for an effective rubric.
#output: rubric.json in cases/case_name/directory – for now, keeping it in rubric_eval_sample. 
#USAGE from root canvas-hyperscribe directory: uv run python rubric_eval_sample/rubric.py rubric_eval_sample/test.json rubric_eval_sample/chart.json rubric_eval_sample/canvas_context.json rubric_eval_sample/rubric.json 

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

def main(transcript_path, chart_path, canvas_context_path, output_path):
    transcript = load_json_file(transcript_path)
    chart = load_json_file(chart_path)
    canvas_context = load_json_file(canvas_context_path)

    #LLM init from normalize_external_transcript.py.
    llm = LlmOpenai(MemoryLog.dev_null_instance(), os.environ['KeyTextLLM'], Constants.OPENAI_CHAT_TEXT, False)

    #Copied from previous example.
    llm.add_prompt(LlmTurn(
        role='system',
        text=[
            'You are a clinical informatics expert helping a veteran physician build a new type of medical education software.'
        ]
    ))

    #Initial draft authored by AS, asked GPT to improve prompt for its own API for both system and user add_prompt calls.
    llm.add_prompt(LlmTurn(
        role='user',
        text=[
            (
                "You are a clinical informatics expert helping a veteran physician build a new type of medical education software. "
                "Your task is to create a scoring rubric that can be used to evaluate a medical scribe's notes based on a provided transcript "
                "of synthetic (fake) medical conversations, synthetic medical record information, and Canvas Medical's EMR command module structure. "
            ),
            (
                "The rubric should help assess whether a scribe's note correctly reflects key medical information and documentation standards. "
                "Use the available commands in the Canvas context to inform your criteria. Each criterion should represent an essential element "
                "that should appear in a good scribe note for this case."
            ),
            (
                "Your output must be a JSON array of tuples: "
                "[[\"criterion 1 description\", max_score], [\"criterion 2 description\", max_score], ...]. "
                "Each criterion description must be 1-2 brief, concise, and clear sentences. The max_score should be a positive integer representing the full points."
                "if the criterion is fully met. Example: [[\"Includes a ReasonForVisit command with appropriate details\", 5], [\"Documents medication changes using AdjustPrescription\", 3]]"
            ),
            (
                "DO NOT include any Markdown, explanations, or extraneous text — only the pure JSON array that can be loaded with json.loads()."
            ),
            "Below is the data to inform your rubric design:",
            "--- TRANSCRIPT JSON ---",
            json.dumps(transcript),
            "--- CHART JSON ---",
            json.dumps(chart),
            "--- CANVAS CONTEXT JSON ---",
            json.dumps(canvas_context)
        ]
    ))

    print("Generating rubric...")
    response = llm.request()

    try:
        rubric = json.loads(response.response)
        with open(output_path, 'w') as f:
            json.dump(rubric, f, indent=2)
        print(f"Wrote rubric to {output_path}")
    except json.JSONDecodeError:
        print("Warning: LLM response is not valid JSON. Saving raw output instead.") 
        with open(output_path, 'w') as f:
            f.write(response.response)
        print(f"Wrote raw response to {output_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate a rubric JSON file from transcript, chart, and canvas context.")
    parser.add_argument("transcript_path", help="Path to transcript.json")
    parser.add_argument("chart_path", help="Path to chart.json")
    parser.add_argument("canvas_context_path", help="Path to canvas_context.json")
    parser.add_argument("output_path", help="Path to save rubric.json")

    args = parser.parse_args()

    main(args.transcript_path, args.chart_path, args.canvas_context_path, args.output_path)


