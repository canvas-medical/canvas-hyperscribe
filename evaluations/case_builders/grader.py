import json, os, argparse
from pathlib import Path
from typing import Any, Dict, List, Tuple

from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.settings    import Settings
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson
from evaluations.constants import Constants
from evaluations.structures.rubric_criterion import RubricCriterion
from evaluations.structures.graded_criterion import GradedCriterion


class NoteGrader:
    def __init__(
        self,
        vendor_key: VendorKey,
        rubric: List[RubricCriterion],
        note: Dict[str, Any],
        output_path: Path
    ) -> None:
        self.vendor_key = vendor_key
        self.rubric     = rubric
        self.note       = note
        self.output_path= output_path

    @staticmethod
    def load_json(path: Path) -> Any:
        with path.open() as f:
            return json.load(f)

    def schema_scores(self) -> Dict[str, Any]:
        """
        JSON Schema for the grader output: an array exactly len(rubric) long,
        each with 'rationale': str and 'satisfaction': number 0–100.
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
                    "rationale":   {"type": "string"},
                    "satisfaction":{"type": "number", "minimum": 0, "maximum": 100}
                },
                "required": ["rationale", "satisfaction"],
                "additionalProperties": False
            }
        }

    def build_prompts(self) -> Tuple[List[str], List[str]]:
        system_prompt = [
            "You are a clinical documentation grading assistant.",
            "You help evaluate medical scribe notes using structured rubrics."
        ]

        user_prompt = [
            "Given the rubric and the hyperscribe output below, return a JSON array "
            "where each item corresponds to one rubric criterion in the same order. "
            "Keys per item:\n"
            "- 'rationale': short explanation\n"
            "- 'satisfaction': float 0-100",
            "Output ONLY raw JSON (start with [, end with ]). No markdown or commentary.",
            "--- BEGIN RUBRIC JSON ---",
            json.dumps([c._asdict() for c in self.rubric]),
            "--- END RUBRIC JSON ---",
            "--- BEGIN HYPERSCRIBE OUTPUT JSON ---",
            json.dumps(self.note),
            "--- END HYPERSCRIBE OUTPUT JSON ---"
        ]

        return system_prompt, user_prompt

    def run(self) -> None:
        sys_prompt, user_prompt = self.build_prompts()
        schema = self.schema_scores()

        print("Grading …")

        parsed = HelperSyntheticJson.generate_json(
            vendor_key   = self.vendor_key,
            system_prompt= sys_prompt,
            user_prompt  = user_prompt,
            schema       = schema,
            retries      = 3
        )

        llm_results = [GradedCriterion(**r) for r in parsed]

        final = []
        for crit, res in zip(self.rubric, llm_results):
            if crit.sense == Constants.POSITIVE_VALUE:
                score = round(crit.weight * (res.satisfaction / 100), 2)
            else:
                score = -round(crit.weight * (1 - (res.satisfaction / 100)), 2)

            final.append({
                "rationale":   res.rationale,
                "satisfaction":res.satisfaction,
                "score":       score
            })

        self.output_path.write_text(json.dumps(final, indent=2))
        print("Saved grading result in", self.output_path)


    def main() -> None:
        parser = argparse.ArgumentParser(description="Grade a note against a rubric.")
        parser.add_argument("--rubric", type=Path, required=True, help="Path to rubric.json")
        parser.add_argument("--note",   type=Path, required=True, help="Path to note.json")
        parser.add_argument("--output", type=Path, required=True, help="Where to save grading JSON")
        args = parser.parse_args()

        settings   = Settings.from_dictionary(dict(os.environ))
        vendor_key = settings.llm_text

        rubric = [RubricCriterion(**c) for c in NoteGrader.load_json(args.rubric)]
        note   = NoteGrader.load_json(args.note)

        grader = NoteGrader(
            vendor_key=vendor_key,
            rubric=rubric,
            note=note,
            output_path=args.output
        )
        grader.run()


if __name__ == "__main__":
    NoteGrader.main()
