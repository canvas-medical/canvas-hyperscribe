import json, os, re, sys, argparse
from pathlib import Path
from typing import Any
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.settings import Settings
from hyperscribe.libraries.memory_log import MemoryLog

class NoteGrader:
    def __init__(self,
                 vendor_key: VendorKey,
                 rubric_path: str | Path,
                 note_path: str | Path,
                 output_path: str | Path):
        self.vendor_key = vendor_key
        self.rubric_path = Path(rubric_path).expanduser()
        self.note_path = Path(note_path).expanduser()
        self.output_path = Path(output_path).expanduser()
        self.rubric = _load_json(self.rubric_path)
        self.note   = _load_json(self.note_path)

    @classmethod
    def _load_json(p: Path) -> Any:
        with Path(p).expanduser().open() as f:
            return json.load(f)
        
    def _build_llm(self) -> LlmOpenai:
        llm = LlmOpenai(
            MemoryLog.dev_null_instance(),
            self.vendor_key.api_key,
            with_audit=False
        )

        llm.add_prompt(LlmTurn(role="system", text=[
            "You are a clinical documentation grading assistant. "
            "You help evaluate medical scribe notes using structured rubrics."
        ]))

        llm.add_prompt(LlmTurn(role="user", text=[
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
        ]))
        return llm
    
    def run(self) -> None:
        llm = self._build_llm()
        print("Grading …")
        raw = llm.request().response
        cleaned = re.sub(r"```(?:json)?\n?|\n?```", "", raw).strip()

        try:
            llm_results = json.loads(cleaned)
        except json.JSONDecodeError:
            print("LLM produced invalid JSON — saving raw text for inspection.")
            self.output_path.write_text(cleaned)
            sys.exit(1)

        final = []
        for criteria, result in zip(self.rubric, llm_results):
            sat = float(result["satisfaction"])
            weight = criteria["weight"]

            # positive sense = positive score; negative sense = penalty.
            if criteria["sense"] == "positive":
                score = round(weight * (sat / 100), 2)
            else:
                score = -round(weight * (1 - (sat / 100)), 2)

            final.append({
                "rationale": result["rationale"],
                "satisfaction": sat,
                "score": score
            })

        self.output_path.write_text(json.dumps(final, indent=2))
        print("Saved grading result in", self.output_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grade a note against a rubric.")
    parser.add_argument("rubric_path", help="Path to rubric.json")
    parser.add_argument("hyperscribe_output_path", help="Path to note.json")
    parser.add_argument("output_path", help="Where to save grading JSON")
    args = parser.parse_args()

    settings = Settings.from_dictionary(os.environ)
    vendor_key = settings.llm_text
    grader = NoteGrader(
        vendor_key,
        rubric_path=args.rubric_path,
        note_path=args.hyperscribe_output_path,
        output_path=args.output_path)
    grader.run()
