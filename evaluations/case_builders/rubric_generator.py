import json, argparse
from pathlib import Path
from typing import Any, Dict

from hyperscribe.structures.vendor_key import VendorKey
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson
from evaluations.constants import Constants

class RubricGenerator:
    def __init__(self, vendor_key: VendorKey) -> None:
        self.vendor_key = vendor_key

    @staticmethod
    def load_json(path: Path) -> Any:
        with path.open("r") as f:
            return json.load(f)

    @classmethod
    def schema_rubric(cls) -> Dict[str, Any]:
        """
        JSON Schema for an array of rubric criteria objects:
        - criterion: string
        - weight: integer 0-100
        - sense: "positive" or "negative"
        """
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string",
                                  "description": "dimension of note being evaluated"},
                    "weight":    {"type": "integer", 
                                  "description": "how much criterion is worth", 
                                  "minimum": 0, "maximum": 100},
                    "sense":     {"type": "string", 
                                  "description": "positive or negative direction",
                                  "enum": [Constants.POSITIVE_VALUE, Constants.NEGATIVE_VALUE]}
                },
                "required": ["criterion", "weight", "sense"],
                "additionalProperties": False
            }
        }

    def generate(self, transcript_path: Path, chart_path: Path,
        canvas_context_path: Path, output_path: Path,) -> None:
        transcript = self.load_json(transcript_path)
        chart = self.load_json(chart_path)
        canvas_context = self.load_json(canvas_context_path)
        schema = self.schema_rubric()

        system_prompt: list[str] = [
            "You are a clinical informatics expert working with a senior physician "
            "to design case-specific rubrics that assess how faithfully a medical "
            "scribe note reflects the transcript and chart.",
            "Return your answer as JSON inside a fenced ```json ... ``` block."]

        user_prompt: list[str] = [
            "Task: design a grading rubric for *documentation fidelity*.",
            "Definition of fidelity: how accurately the note captures what was said "
            "or implied in the transcript, using relevant context from the chart. "
            "Do not judge clinical decisions—only documentation fidelity.",
            "Follow three steps internally, but output **only** the final rubric:",
            " 1. Identify key events/statements in transcript & chart.",
            " 2. Decide what an ideal scribe must capture.",
            " 3. Produce the rubric as a JSON array of objects.",
            "Each object keys:",
            " - criterion (string) — must start with with \"Reward for\" or \"Penalize for\"",
            " - weight    (int 0-100)",
            " - sense     (\"positive\" | \"negative\")",
            "Include at least one criterion on overall completeness and one on chart-copy fidelity.",
            "Your JSON **must** conform to the following JSON Schema:",
            "```json",
            json.dumps(schema, indent=2),
            "```",
            "Wrap the JSON array in a fenced ```json block and output nothing else.",
            "--- BEGIN TRANSCRIPT JSON ---",
            json.dumps(transcript),
            "--- END TRANSCRIPT JSON ---",
            "--- BEGIN CHART JSON ---",
            json.dumps(chart),
            "--- END CHART JSON ---",
            "--- BEGIN CANVAS CONTEXT JSON ---",
            json.dumps(canvas_context),
            "--- END CANVAS CONTEXT JSON ---",]

        rubric_list = HelperSyntheticJson.generate_json(
            vendor_key=self.vendor_key,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema)

        output_path.write_text(json.dumps(rubric_list, indent=2))
        print(f"Wrote rubric to {output_path}")

    @staticmethod
    def main() -> None:
        parser = argparse.ArgumentParser(
            description="Generate a fidelity-focused rubric for a medical scribe note.")
        parser.add_argument("--transcript_path", type=Path, help="Path to transcript.json")
        parser.add_argument("--chart_path", type=Path, help="Path to limited_chart.json")
        parser.add_argument("--canvas_context_path", type=Path, help="Path to canvas_context.json")
        parser.add_argument("--output_path", type=Path, help="Where to save rubric.json")
        args = parser.parse_args()

        settings = HelperEvaluation.settings()
        vendor_key = settings.llm_text

        RubricGenerator(vendor_key).generate(
            transcript_path=args.transcript_path,
            chart_path=args.chart_path,
            canvas_context_path=args.canvas_context_path,
            output_path=args.output_path)

if __name__ == "__main__":
    RubricGenerator.main()