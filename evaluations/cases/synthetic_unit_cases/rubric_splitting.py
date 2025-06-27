import os
import re
import json
import argparse
from pathlib import Path
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog


class RubricSplitGenerator:
    def __init__(self, llm_key: str):
        self.llm = LlmOpenai(MemoryLog.dev_null_instance(), llm_key, Constants.OPENAI_CHAT_TEXT, False)
        self.llm_key = llm_key

    @staticmethod
    def load_json(path: Path):
        with path.open('r') as f:
            return json.load(f)

    def build_prompt(self, transcript, chart, canvas_context):
        self.llm.clear_prompts()
        self.llm.add_prompt(LlmTurn(
            role='system',
            text=[
                "You are a clinical informatics expert working with a senior physician to build innovative medical education software. "
                "You specialize in designing case-specific rubrics to evaluate the quality and safety of medical scribe documentation."
            ]
        ))

        self.llm.add_prompt(LlmTurn(
            role='user',
            text=[
                "Your task is to generate a grading rubric for evaluating documentation from a partial segment of a specific patient encounter, using the provided transcript and medical background.",

                "You must then classify the generated rubric into two distinct categories:",
                "1. `fidelity_criteria`: Criteria that assess how faithfully the documentation reflects the content and implications of the transcript and chart. These must only test for presence, omission, or distortion of what was explicitly or implicitly stated or known — without invoking clinical judgment or external guidelines.",
                "2. `appropriateness_criteria`: Criteria that rely on medical knowledge, clinical judgment, or safety/risk analysis, such as evidence-based decision making, patient safety, or appropriate-risk choices. These criteria assess whether decisions or omissions were reasonable, safe, or compliant with standards of care.",

                "You must first read the transcript and chart carefully to understand the medical context.",
                "Then, use your expertise to generate the smallest comprehensive set of evaluation criteria that are mutually exclusive, collectively exhaustive, specific to the case, and formatted precisely.",

                "Each criterion must test for the presence or absence of a quality, safety, or fidelity-related feature in the documentation. Each must be expressed as:",
                "{\"criterion\": <verifiable testable condition>, \"weight\": <0–100>, \"sense\": \"positive\"|\"negative\"}",

                "Each must start with 'Reward for' or 'Penalize for'.",
                "- Use 'Reward for' and sense 'positive' for presence of correct, safe, or complete documentation.",
                "- Use 'Penalize for' and sense 'negative' for omissions, incorrectness, unsafe choices, or documentation failures.",

                "Do not write general criteria. Be precise and grounded in the case-specific facts and decisions. Avoid repetition or overlap between criteria.",
                "You must include at least one patient safety-related criterion, and one evidence-based decision-making criterion in the `appropriateness_criteria` category.",
                "You must include at least one criterion related to completeness of the note in the `fidelity_criteria` category.",

                "**IMPORTANT**: Classify each criterion strictly. Fidelity criteria must not include judgment about what *should* have been done — only what *was said* and whether it was accurately documented. Appropriateness criteria must not be based only on whether something was said — they must assess the quality or correctness of clinical decisions.",

                "Output your results as a JSON object with this format:",
                "{ \"fidelity_criteria\": [...], \"appropriateness_criteria\": [...] }",

                "Do NOT include any markdown, code blocks, commentary, or extra text. Your output must start with `{` and end with `}` and contain only valid JSON parsable by json.loads().",

                "Below is the data to inform your rubric design:",
                "--- BEGIN TRANSCRIPT JSON ---",
                json.dumps(transcript),
                "--- END TRANSCRIPT JSON ---",
                "--- BEGIN CHART JSON ---",
                json.dumps(chart),
                "--- END CHART JSON ---",
                "--- BEGIN CANVAS CONTEXT JSON ---",
                json.dumps(canvas_context),
                "--- END CANVAS CONTEXT JSON ---"
            ]
        ))

    def generate(self, transcript_path: Path, chart_path: Path, canvas_context_path: Path, output_path: Path):
        transcript = self.load_json(transcript_path)
        chart = self.load_json(chart_path)
        canvas_context = self.load_json(canvas_context_path)

        self.build_prompt(transcript, chart, canvas_context)

        print("Generating split rubrics...")
        response = self.llm.request()
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()

        try:
            rubric = json.loads(cleaned)
            with output_path.open('w') as f:
                json.dump(rubric, f, indent=2)
            print(f"Wrote rubric to {output_path}")
        except json.JSONDecodeError:
            print("Warning: response not valid JSON. Saving raw.")
            with output_path.open('w') as f:
                f.write(cleaned)
            print(f"Wrote raw response to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate a split rubric (fidelity and appropriateness).")
    parser.add_argument("transcript_path", type=Path)
    parser.add_argument("chart_path", type=Path)
    parser.add_argument("canvas_context_path", type=Path)
    parser.add_argument("output_path", type=Path)

    args = parser.parse_args()

    llm_key = os.environ['KeyTextLLM']
    generator = RubricSplitGenerator(llm_key)
    generator.generate(args.transcript_path, args.chart_path, args.canvas_context_path, args.output_path)


if __name__ == "__main__":
    main()
