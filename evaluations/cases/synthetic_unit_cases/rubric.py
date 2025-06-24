import os
import json
import argparse
from pathlib import Path
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog

class RubricGenerator:
    def __init__(self, llm_key: str):
        self.llm = LlmOpenai(MemoryLog.dev_null_instance(), llm_key, Constants.OPENAI_CHAT_TEXT, False)

    @staticmethod
    def load_json(path: Path):
        with path.open('r') as f:
            return json.load(f)

    def build_prompt(self, transcript, chart, canvas_context):
        self.llm.add_prompt(LlmTurn(
            role='system',
            text=[
                "You are a clinical informatics expert working with a senior physician to build innovative medical education software. "
                "You specialize in designing case-specific rubrics to evaluate the quality of medical scribe notes."
            ]
        ))

        self.llm.add_prompt(LlmTurn(
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

    def generate(self, transcript_path: Path, chart_path: Path, canvas_context_path: Path, output_path: Path):
        transcript = self.load_json(transcript_path)
        chart = self.load_json(chart_path)
        canvas_context = self.load_json(canvas_context_path)

        self.build_prompt(transcript, chart, canvas_context)

        print("Generating rubric...")
        response = self.llm.request()

        try:
            rubric = json.loads(response.response)
            with output_path.open('w') as f:
                json.dump(rubric, f, indent=2)
            print(f"Wrote rubric to {output_path}")
        except json.JSONDecodeError:
            print("Warning: LLM response is not valid JSON. Saving raw output instead.")
            with output_path.open('w') as f:
                f.write(response.response)
            print(f"Wrote raw response to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate a rubric JSON file from transcript, chart, and canvas context.")
    parser.add_argument("transcript_path", type=Path, help="Path to transcript.json")
    parser.add_argument("chart_path", type=Path, help="Path to limited_chart.json")
    parser.add_argument("canvas_context_path", type=Path, help="Path to canvas_context.json")
    parser.add_argument("output_path", type=Path, help="Path to save rubric.json")

    args = parser.parse_args()

    llm_key = os.environ['KeyTextLLM']
    generator = RubricGenerator(llm_key)
    generator.generate(args.transcript_path, args.chart_path, args.canvas_context_path, args.output_path)

if __name__ == "__main__":
    main()
