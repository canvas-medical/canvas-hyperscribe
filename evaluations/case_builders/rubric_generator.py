import os, json, argparse
from pathlib import Path
from typing import Any, Dict, List

from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.settings    import Settings
from evaluations.case_builders.synthetic_json_helper import generate_json

class RubricGenerator:
    def __init__(self, vendor_key: VendorKey) -> None:
        self.vendor_key = vendor_key

    @staticmethod
    def load_json(path: Path) -> Any:
        with path.open("r") as f:
            return json.load(f)

    def schema_rubric(self) -> Dict[str, Any]:
        """
        JSON Schema for an array of rubric criteria objects:
        - criterion: string
        - weight: integer 0–100
        - sense: "positive" or "negative"
        """
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "weight":    {"type": "integer", "minimum": 0, "maximum": 100},
                    "sense":     {"type": "string", "enum": ["positive", "negative"]}
                },
                "required": ["criterion", "weight", "sense"],
                "additionalProperties": False
            }
        }

    def generate(self, transcript_path: Path, chart_path: Path, canvas_context_path: Path, output_path: Path) -> None:
        transcript = self.load_json(transcript_path)
        chart = self.load_json(chart_path)
        canvas_context = self.load_json(canvas_context_path)

        system_prompt: List[str] = [
            "You are a clinical informatics expert working with a senior physician "
            "to build innovative medical education software. You specialize in designing "
            "case-specific rubrics to evaluate how faithfully a medical scribe note "
            "reflects the conversation and chart."
        ]

        user_prompt: List[str] = [
            "Your task is to design a grading rubric for evaluating the fidelity of a medical scribe note. "
            "Fidelity is defined as the degree to which the note reflects exactly what was said or implied "
            "in the transcript, using relevant context from the chart. Do not judge clinical decisions — "
            "only documentation fidelity.",
            "",
            "You must follow this three-step reasoning but only output the final JSON array:",
            "1. Identify key events/statements in transcript/chart.",
            "2. Pick which items an ideal scribe should capture.",
            "3. Write the rubric as a JSON array of criteria objects.",
            "",
            "Each criterion object must have keys:",
            "- criterion    (clear, verifiable fidelity-focused text)",
            "- weight       (integer 0–100)",
            "- sense        (\"positive\" or \"negative\")",
            "",
            "Each criterion text must start with “Reward for” or “Penalize for”.",
            "Include at least one on overall completeness and one on chart-copy fidelity.",
            "Do NOT include markdown, commentary, or intermediate steps—only the JSON array.",
            "",
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


        rubric_list = generate_json(
            vendor_key=self.vendor_key,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=self.schema_rubric(),
            retries=3)

        with output_path.open("w") as f:
            json.dump(rubric_list, f, indent=2)
        print(f"Wrote rubric to {output_path}")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a fidelity-focused rubric for a medical scribe note.")
    parser.add_argument("transcript_path", type=Path, help="Path to transcript.json")
    parser.add_argument("chart_path", type=Path, help="Path to limited_chart.json")
    parser.add_argument("canvas_context_path", type=Path, help="Path to canvas_context.json")
    parser.add_argument("output_path", type=Path, help="Where to save rubric.json")
    args = parser.parse_args()

    settings = Settings.from_dictionary(dict(os.environ))
    vendor_key = settings.llm_text

    gen = RubricGenerator(vendor_key)
    gen.generate(
        transcript_path=args.transcript_path,
        chart_path=args.chart_path,
        canvas_context_path=args.canvas_context_path,
        output_path=args.output_path)

if __name__ == "__main__":
    main()