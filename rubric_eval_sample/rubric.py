# input: chart, transcript, canvas-specific context (descriptions of the implemented-commands class)
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
        "You are a clinical informatics expert working with a senior physician to build innovative medical education software. "
        "You specialize in designing case-specific rubrics to evaluate the quality of medical scribe notes."
        ]
    ))

    llm.add_prompt(LlmTurn(
        role='user',
        text=[
            (
                "Your task is to create a detailed, case-specific scoring rubric that will evaluate a medical scribe's notes. "
                "The rubric is for a single case involving synthetic (fake) medical conversations, synthetic medical record data, "
                "and a Canvas Medical EMR command module structure."
            ),
            (
                "Each rubric criterion must directly reference specific facts, concepts, or decisions found in the provided transcript and chart. "
                "**Do not write generic documentation criteria. Every criterion must name or describe the actual elements from this specific case, such as the exact medication change, diagnosis, symptom, or decision.**"
            ),
            (
                "The chart represents pre-existing medical record information and **must not be repeated or copied into the scribe's note**. "
                "Chart data must serve *only* as background to inform documentation decisions — for example, identifying allergies to guide prescribing decisions or recognizing pre-existing conditions that shape the plan of care. "
                "**Any inclusion of redundant or copied chart information must result in negative points.**"
            ),
            (
                "**Be explicit about what the scribe note must capture for this case, including the specific conditions, medications, allergies, symptoms, and plan decisions.** "
                "The rubric should specify these required elements exactly as they appear in the case."
            ),
            (
                "Assign relative weights thoughtfully. Core clinical elements should carry more weight. "
                "Negative points should be used for criteria where the *presence* of a problem (e.g., inclusion of misleading information, redundant chart data, copying of chart content) should be penalized. "
                "Frame all criteria as clear positive or neutral statements. Let the max_score value indicate whether it is a reward (positive points) or penalty (negative points)."
            ),
            (
                "There is no fixed total maximum score — assign point values as appropriate based on the importance of each criterion."
            ),
            (
                "Your output must be a JSON array of tuples: "
                "[[\"criterion description\", max_score], [\"criterion description\", max_score], ...]. "
                "Each criterion description must be 1-2 brief, clear sentences that state what is being evaluated. "
                "The max_score must be a numeric integer — do not use strings like '5 points'."
            ),
            (
                "The rubric should follow best practices similar to OpenAI HealthBench — it must be tailored to the specific case and context, "
                "and must explicitly reference actual case facts in each criterion."
            ),
            (
                "**Be extremely strict about preventing redundancy or unnecessary repetition. Notes should focus only on new, relevant, case-specific information and appropriate decisions informed by, but not duplicating, the chart.**"
            ),
            (
                "DO NOT include any Markdown, code block formatting, explanations, or extraneous text — only output the pure JSON array that can be loaded with json.loads()."
            ),
            (
                "Your output must begin with the [ character and end with the ] character. "
                "Do not include any Markdown syntax, code block markers, or language tags such as ```json. "
                "Output the raw JSON array only, nothing else."
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


