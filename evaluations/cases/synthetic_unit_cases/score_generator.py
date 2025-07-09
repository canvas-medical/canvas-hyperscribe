import json, os, re, sys, argparse
from pathlib import Path
from typing import Any
from hyperscribe.llms.llm_openai_o3 import LlmOpenaiO3
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.settings import Settings
from hyperscribe.libraries.memory_log import MemoryLog
from evaluations.constants import Constants
from evaluations.structures.rubric_criterion import RubricCriterion
from evaluations.structures.graded_criterion import GradedCriterion


class NoteGrader:
    def __init__(self, vendor_key: VendorKey, rubric: list[RubricCriterion], note: dict[str, Any], output_path: Path):
        self.vendor_key = vendor_key
        self.rubric = rubric
        self.note = note
        self.output_path = output_path

    @staticmethod
    def load_json(path: Path) -> Any:
        with path.open() as f:
            return json.load(f)

    def _build_llm(self) -> LlmOpenaiO3:
        llm = LlmOpenaiO3(MemoryLog.dev_null_instance(), self.vendor_key.api_key, with_audit=False)

        llm.set_system_prompt([
            "You are a clinical documentation grading assistant. "
            "You help evaluate medical scribe notes using structured rubrics."
        ])

        llm.set_user_prompt([
            (
                "Given the rubric and the hyperscribe output below, return a JSON "
                "array where each item corresponds to one rubric criterion in "
                "the same order. Keys per item:\n"
                "- 'rationale': short explanation\n"
                "- 'satisfaction': float 0-100"
            ),
            (
                "Output ONLY raw JSON (start with [, end with ]). "
                "No markdown or extra commentary."
            ),
            "--- BEGIN RUBRIC JSON ---",
            json.dumps(self.rubric),
            "--- END RUBRIC JSON ---",
            "--- BEGIN HYPERSCRIBE OUTPUT JSON ---",
            json.dumps(self.note),
            "--- END HYPERSCRIBE OUTPUT JSON ---"
        ])

        return llm

    def run(self) -> None:
        llm = self._build_llm()
        print("Grading …")
        raw = llm.request().response
        cleaned = re.sub(r"```(?:json)?\n?|\n?```", "", raw).strip()

        try:
            llm_results = [GradedCriterion(**r) for r in json.loads(cleaned)]
        except json.JSONDecodeError:
            print("LLM produced invalid JSON — saving raw text for inspection.")
            self.output_path.write_text(cleaned)
            sys.exit(1)

        final = []
        for criteria, result in zip(self.rubric, llm_results):
            if criteria.sense == Constants.POSITIVE_VALUE:
                score = round(criteria.weight * (result.satisfaction / 100), 2)
            else:
                score = -round(criteria.weight * (1 - (result.satisfaction / 100)), 2)

            final.append({
                "rationale": result.rationale,
                "satisfaction": result.satisfaction,
                "score": score
            })

        self.output_path.write_text(json.dumps(final, indent=2))
        print("Saved grading result in", self.output_path)


def main():
    parser = argparse.ArgumentParser(description="Grade a note against a rubric.")
    parser.add_argument("--rubric", type=Path, help="Path to rubric.json")
    parser.add_argument("--note", type=Path, help="Path to note.json")
    parser.add_argument("--output", type=Path, help="Where to save grading JSON")
    args = parser.parse_args()

    settings = Settings.from_dictionary(os.environ)
    vendor_key = settings.llm_text
    grader = NoteGrader(
        vendor_key=vendor_key,
        rubric=[RubricCriterion(**c) for c in NoteGrader.load_json(args.rubric)],
        note=NoteGrader.load_json(args.note),
        output_path=args.output)
    grader.run()


if __name__ == "__main__":
    main()
