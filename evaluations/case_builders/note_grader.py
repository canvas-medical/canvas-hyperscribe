from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Tuple, cast

from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson
from evaluations.constants import Constants
from evaluations.datastores.postgres.generated_note import GeneratedNote as GeneratedNoteDatastore
from evaluations.datastores.postgres.rubric import Rubric as RubricDatastore
from evaluations.datastores.postgres.score import Score as ScoreDatastore
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.graded_criterion import GradedCriterion
from evaluations.structures.records.score import Score as ScoreRecord
from evaluations.structures.rubric_criterion import RubricCriterion
from hyperscribe.libraries.constants import Constants as HyperscribeConstants
from hyperscribe.structures.vendor_key import VendorKey


class NoteGrader:
    def __init__(
        self,
        vendor_key: VendorKey,
        rubric: list[RubricCriterion],
        note: dict[str, Any],
    ) -> None:
        self.vendor_key = vendor_key
        self.rubric = rubric
        self.note = note

    @staticmethod
    def load_json(path: Path) -> Any:
        with path.open() as f:
            return json.load(f)

    def schema_scores(self) -> dict[str, Any]:
        """
        JSON Schema for the grader output: an array exactly len(rubric) long,
        each with 'rationale': str and 'satisfaction': integer 0-100.
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
                    "id": {
                        "type": "integer",
                        "description": "index to match criteria",
                    },
                    "rationale": {
                        "type": "string",
                        "description": "reasoning for satisfaction score",
                    },
                    "satisfaction": {
                        "type": "integer",
                        "description": "note grade",
                        "minimum": 0,
                        "maximum": 100,
                    },
                },
                "required": [
                    "id",
                    "rationale",
                    "satisfaction",
                ],
                "additionalProperties": False,
            },
        }

    def build_prompts(self) -> Tuple[list[str], list[str]]:
        """Returns system-prompt and user-prompt as single strings, joined with new lines."""

        system_prompt = [
            "You are a clinical-documentation grading assistant.",
            "You evaluate medical-scribe notes using structured rubrics.",
            "The JSON response MUST satisfy the following JSON-Schema:",
            json.dumps(self.schema_scores(), indent=2),
        ]

        user_prompt = [
            "Given the rubric and the Hyperscribe output below, return **only** a "
            "JSON array where each element corresponds to the rubric criteria in "
            "order.",
            "",
            "Each element keys:",
            " - id: int to index based on the criteria",
            " - rationale : str - short explanation",
            " - satisfaction : int - 0 to 100",
            "",
            "Wrap the JSON in a fenced ```json ``` block to avoid extra tokens.",
            "",
            "---- BEGIN RUBRIC JSON ----",
            json.dumps([c._asdict() for c in self.rubric], indent=2),
            "---- END RUBRIC JSON ----",
            "---- BEGIN HYPERSCRIBE OUTPUT JSON ----",
            json.dumps(self.note, indent=2),
            "---- END HYPERSCRIBE OUTPUT JSON ----",
        ]

        return system_prompt, user_prompt

    def run(self) -> list[GradedCriterion]:
        system_prompt, user_prompt = self.build_prompts()
        schema = self.schema_scores()

        print("Grading …")

        graded_criteria = cast(
            list[GradedCriterion],
            HelperSyntheticJson.generate_json(
                vendor_key=self.vendor_key,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
                returned_class=list[GradedCriterion],
            ),
        )

        result = []
        for graded_criterion, rubric_criterion in zip(graded_criteria, self.rubric):
            if rubric_criterion.sense == Constants.POSITIVE_VALUE:
                score = round(rubric_criterion.weight * (graded_criterion.satisfaction / 100), 2)
            else:
                score = -round(rubric_criterion.weight * (1 - (graded_criterion.satisfaction / 100)), 2)

            result.append(
                GradedCriterion(
                    id=graded_criterion.id,
                    rationale=graded_criterion.rationale,
                    satisfaction=graded_criterion.satisfaction,
                    score=score,
                )
            )

        return result

    @classmethod
    def grade_and_save2database(cls, rubric_id: int, generated_note_id: int) -> ScoreRecord:
        credentials = HelperEvaluation.postgres_credentials()
        vendor_key = HelperEvaluation.settings().llm_text

        rubric = [RubricCriterion(**c) for c in RubricDatastore(credentials).get_rubric(rubric_id)]
        note_data = GeneratedNoteDatastore(credentials).get_note_json(generated_note_id)

        scoring_result: list[GradedCriterion] = cls(vendor_key, rubric, note_data).run()

        overall_score = sum(item.score for item in scoring_result)

        score_record = ScoreRecord(
            rubric_id=rubric_id,
            generated_note_id=generated_note_id,
            scoring_result=scoring_result,
            overall_score=overall_score,
            comments="",
            text_llm_vendor=vendor_key.vendor,
            text_llm_name=HyperscribeConstants.OPENAI_CHAT_TEXT_O3,
            temperature=Constants.O3_TEMPERATURE,
        )
        return ScoreDatastore(credentials).insert(score_record)

    @classmethod
    def grade_and_save2file(cls, rubric_path: Path, note_path: Path, output_path: Path) -> None:
        """Grade a note using rubric from files and save result to output file."""
        vendor_key = HelperEvaluation.settings().llm_text

        rubric = [RubricCriterion(**c) for c in cls.load_json(rubric_path)]
        note = cls.load_json(note_path)

        grader = cls(vendor_key, rubric, note)
        result = grader.run()

        output_path.write_text(json.dumps([item._asdict() for item in result], indent=2))
        print("Saved grading result in", output_path)

    @staticmethod
    def main() -> None:
        parser = argparse.ArgumentParser(description="Grade a note against a rubric.")

        # File-based parameters
        parser.add_argument("--rubric", type=Path, help="Path to rubric.json")
        parser.add_argument("--note", type=Path, help="Path to note.json")
        parser.add_argument("--output", type=Path, help="Where to save grading JSON")

        # Database-based parameters
        parser.add_argument("--rubric_id", type=int, help="Rubric ID from database")
        parser.add_argument("--generated_note_id", type=int, help="Generated note ID from database")

        args = parser.parse_args()

        # Validate parameter combinations
        file_params = [args.rubric, args.note, args.output]
        db_params = [args.rubric_id, args.generated_note_id]

        file_mode = all(param is not None for param in file_params)
        db_mode = all(param is not None for param in db_params)

        if not (file_mode or db_mode):
            parser.error("Must provide either (--rubric, --note, --output) or (--rubric_id, --generated_note_id)")

        if file_mode and db_mode:
            parser.error("Cannot provide both file-based and database-based parameters")

        if file_mode:
            NoteGrader.grade_and_save2file(args.rubric, args.note, args.output)
        else:  # db_mode
            result = NoteGrader.grade_and_save2database(args.rubric_id, args.generated_note_id)
            print(f"Saved grading result to database with score ID: {result.id}")


if __name__ == "__main__":
    NoteGrader.main()
