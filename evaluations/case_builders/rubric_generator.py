from __future__ import annotations
import json, argparse
from pathlib import Path
from typing import Any, cast

from datetime import datetime, UTC


from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson
from evaluations.constants import Constants
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.records.rubric import Rubric as RubricRecord
from evaluations.structures.enums.rubric_validation import RubricValidation
from evaluations.structures.rubric_criterion import RubricCriterion
from evaluations.datastores.postgres.rubric import Rubric as RubricDatastore
from evaluations.datastores.postgres.case import Case as CaseDatastore
from hyperscribe.structures.model_spec import ModelSpec


class RubricGenerator:
    @staticmethod
    def load_json(path: Path) -> Any:
        with path.open("r") as f:
            return json.load(f)

    @classmethod
    def schema_rubric(cls) -> dict[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {
                        "type": "string",
                        "description": "dimension of note being evaluated",
                    },
                    "weight": {
                        "type": "integer",
                        "description": "how much criterion is worth",
                        "minimum": 0,
                        "maximum": 100,
                    },
                },
                "required": ["criterion", "weight"],
                "additionalProperties": False,
            },
        }

    def build_prompts(self, transcript: dict, chart: dict, canvas_context: dict) -> tuple[list[str], list[str]]:
        schema = self.schema_rubric()

        system_prompt = [
            "You are a clinical informatics expert working with a senior physician "
            "to design case-specific rubrics that assess how faithfully a medical "
            "scribe note reflects the transcript and chart.",
            "Return your answer as JSON inside a fenced ```json ... ``` block.",
        ]

        user_prompt = [
            "Task: design a grading rubric for *documentation fidelity*.",
            "Definition of fidelity: how accurately the note captures what was said "
            "or implied in the transcript, using relevant context from the chart. "
            "Do not judge clinical decisions—only documentation fidelity.",
            "Follow three steps internally, but output **only** the final rubric:",
            " 1. Identify key events/statements in transcript & chart.",
            " 2. Decide what an ideal scribe must capture.",
            " 3. Produce the rubric as a JSON array of objects.",
            "Each object keys:",
            ' - criterion (string) — must start with "Reward for"',
            " - weight (int 0-100)",
            "Generate 4, 5, or 6 criteria. No exceptions.",
            "Include at least one criterion on overall completeness based on the transcript"
            "and one criterion related to not repeating information already documented in the chart.",
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
            "--- END CANVAS CONTEXT JSON ---",
        ]

        return system_prompt, user_prompt

    def generate(self, transcript: dict, chart: dict, canvas_context: dict) -> list[RubricCriterion]:
        system_prompt, user_prompt = self.build_prompts(transcript, chart, canvas_context)
        return cast(
            list[RubricCriterion],
            HelperSyntheticJson.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=self.schema_rubric(),
                returned_class=RubricCriterion,
            ),
        )

    @classmethod
    def generate_and_save2file(
        cls,
        transcript_path: Path,
        chart_path: Path,
        canvas_context_path: Path,
        output_path: Path,
    ) -> None:
        transcript = cls.load_json(transcript_path)
        chart = cls.load_json(chart_path)
        context = cls.load_json(canvas_context_path)

        rubric_list = cls().generate(transcript, chart, context)
        output_path.write_text(json.dumps([criterion.to_json() for criterion in rubric_list], indent=2))
        print(f"Saved rubric to file at: {output_path}")

    @classmethod
    def generate_and_save2database(cls, case_name: str, canvas_context_path: Path) -> RubricRecord:
        settings = HelperEvaluation.settings_reasoning_allowed()
        credentials = HelperEvaluation.postgres_credentials()

        datastore = CaseDatastore(credentials)

        case_id = datastore.get_id(case_name)
        transcript = datastore.get_transcript(case_id)
        chart = datastore.get_limited_chart(case_id)
        canvas_context = cls.load_json(canvas_context_path)

        rubric_list = cls().generate(transcript, chart, canvas_context)

        rubric_record = RubricRecord(
            id=0,
            case_id=case_id,
            parent_rubric_id=None,
            validation_timestamp=datetime.now(UTC),
            validation=RubricValidation.NOT_EVALUATED,
            author=Constants.RUBRIC_AUTHOR_LLM,
            rubric=[criterion.to_json() for criterion in rubric_list],
            case_provenance_classification="",
            comments="",
            text_llm_vendor=settings.llm_text.vendor,
            text_llm_name=settings.llm_text_model(ModelSpec.LISTED),
            temperature=settings.llm_text_temperature(),
        )
        print("Rubric record generated. Insert starting now.")
        return RubricDatastore(credentials).insert(rubric_record)

    @staticmethod
    def main() -> None:
        parser = argparse.ArgumentParser(description="Generate a fidelity rubric for documentation.")
        parser.add_argument("--canvas_context_path", type=Path, required=True)

        # File mode
        parser.add_argument("--transcript_path", type=Path)
        parser.add_argument("--chart_path", type=Path)
        parser.add_argument("--output_path", type=Path)
        # DB mode
        parser.add_argument("--case_name", type=str)

        args = parser.parse_args()

        file_mode = all([args.transcript_path, args.chart_path, args.canvas_context_path, args.output_path])
        db_mode = args.case_name is not None and args.canvas_context_path is not None

        if not (file_mode or db_mode):
            parser.error("Must provide either all file inputs or (--case_name and --canvas_context_path).")
        if file_mode and db_mode:
            parser.error("Cannot mix file-based and DB-based generation modes.")

        if file_mode:
            RubricGenerator.generate_and_save2file(
                args.transcript_path,
                args.chart_path,
                args.canvas_context_path,
                args.output_path,
            )
        else:
            result = RubricGenerator.generate_and_save2database(
                args.case_name,
                args.canvas_context_path,
            )
            print(f"Saved rubric to database with ID: {result.id}")


if __name__ == "__main__":
    RubricGenerator.main()
