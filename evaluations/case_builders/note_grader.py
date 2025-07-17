from __future__ import annotations
import json, argparse
from pathlib import Path
from typing import Any, Dict, List, Tuple
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson
from evaluations.constants import Constants
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.rubric_criterion import RubricCriterion
from evaluations.structures.graded_criterion import GradedCriterion


class NoteGrader:
    def __init__(self, vendor_key: VendorKey, rubric: List[RubricCriterion], 
                 note: Dict[str, Any], output_path: Path) -> None:
        self.vendor_key = vendor_key
        self.rubric = rubric
        self.note = note
        self.output_path= output_path

    @staticmethod
    def load_json(path: Path) -> Any:
        with path.open() as f:
            return json.load(f)

    def schema_scores(self) -> Dict[str, Any]:
        """
        JSON Schema for the grader output: an array exactly len(rubric) long,
        each with 'rationale': str and 'satisfaction': integer 0–100.
        """
        count = len(self.rubric)
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": count,
            "maxItems": count,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "rationale":   {"type": "string"},
                    "satisfaction":{"type": "integer", "minimum": 0, "maximum": 100}
                },
                "required": ["rationale", "satisfaction"],
                "additionalProperties": False
            }
        }

    def build_prompts(self) -> Tuple[list[str], list[str]]:
        """Returns system‑prompt and user‑prompt as single strings, joined with new lines."""

        system_prompt = ["You are a clinical‑documentation grading assistant.",
            "You evaluate medical‑scribe notes using structured rubrics.",
            "The JSON response MUST satisfy the following JSON‑Schema:",
            json.dumps(self.schema_scores(), indent=2)]

        user_prompt = [
            "Given the rubric and the Hyperscribe output below, return **only** a "
            "JSON array where each element corresponds to the rubric criteria in "
            "order.",
            "",
            "Each element keys:",
            "  • rationale    : str  – short explanation",
            "  • satisfaction : int – 0 to 100",
            "",
            "Wrap the JSON in a fenced ```json ``` block to avoid extra tokens.",
            "",
            "---- BEGIN RUBRIC JSON ----",
            json.dumps([c._asdict() for c in self.rubric], indent=2),
            "---- END RUBRIC JSON ----",
            "---- BEGIN HYPERSCRIBE OUTPUT JSON ----",
            json.dumps(self.note, indent=2),
            "---- END HYPERSCRIBE OUTPUT JSON ----",]

        return system_prompt, user_prompt

    def run(self) -> None:
        sys_prompt, user_prompt = self.build_prompts()
        schema = self.schema_scores()

        print("Grading …")

        parsed = HelperSyntheticJson.generate_json(
            vendor_key = self.vendor_key,
            system_prompt = sys_prompt,
            user_prompt = user_prompt,
            schema = schema)

        llm_results = [GradedCriterion(**r) for r in parsed]

        final = []
        for criteria, result in zip(self.rubric, llm_results):
            if criteria.sense == Constants.POSITIVE_VALUE:
                score = round(criteria.weight * (result.satisfaction / 100), 2)
            else:
                score = -round(criteria.weight * (1 - (result.satisfaction / 100)), 2)

            final.append({
                "rationale":   result.rationale,
                "satisfaction":result.satisfaction,
                "score":       score
            })

        self.output_path.write_text(json.dumps(final, indent=2))
        print("Saved grading result in", self.output_path)

    @staticmethod
    def main() -> None:
        parser = argparse.ArgumentParser(description="Grade a note against a rubric.")
        parser.add_argument("--rubric", type=Path, required=True, help="Path to rubric.json")
        parser.add_argument("--note",   type=Path, required=True, help="Path to note.json")
        parser.add_argument("--output", type=Path, required=True, help="Where to save grading JSON")
        args = parser.parse_args()

        settings = HelperEvaluation.settings()
        vendor_key = settings.llm_text

        rubric = [RubricCriterion(**c) for c in NoteGrader.load_json(args.rubric)]
        note = NoteGrader.load_json(args.note)

        NoteGrader(vendor_key, rubric, note, output_path=args.output).run()

if __name__ == "__main__":
    NoteGrader.main()
