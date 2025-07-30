import json, re, argparse
from pathlib import Path
from typing import Any, cast

from hyperscribe.structures.vendor_key import VendorKey
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson


class SyntheticProfileGenerator:
    def __init__(self, vendor_key: VendorKey) -> None:
        self.vendor_key = vendor_key
        self.seen_scenarios: list[str] = []
        self.all_profiles: dict[str, str] = {}

    @classmethod
    def _extract_initial_fragment(cls, narrative: str) -> str:
        return narrative.split(".")[0][:100]

    def _save_combined(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w") as f:
            json.dump(self.all_profiles, f, indent=2)
        print(f"Saved {len(self.all_profiles)} profiles to {output_path}")

    def _save_individuals(self, output_path: Path) -> None:
        base_dir = output_path.parent
        for name, narrative in self.all_profiles.items():
            dir_name = re.sub(r"\s+", "_", name.strip())
            dir_path = base_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            file_path = dir_path / "profile.json"
            with file_path.open("w") as f:
                json.dump({name: narrative}, f, indent=2)
            print(f"Saved profile for {name} to {file_path}")

    @classmethod
    def schema_batch(cls, count_patients: int) -> dict[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "minProperties": count_patients,
            "maxProperties": count_patients,
            "patternProperties": {r"^Patient\s\d+$": {"type": "string", "description": "patient profile"}},
            "additionalProperties": False,
        }

    def generate_batch(self, batch_num: int, count: int) -> dict[str, str]:
        schema = self.schema_batch(count)

        system_prompt: list[str] = [
            "You are a clinical‑informatics expert generating synthetic patient "
            "profiles for testing medication‑management AI systems.",
            "Return your answer as JSON inside a fenced ```json ... ``` block.",
            "The response **must** conform to the following JSON Schema:",
            "```json",
            json.dumps(schema, indent=2),
            "```",
        ]

        user_prompt = [
            f"Create a JSON object with {count} key-value pairs labeled "
            f'"Patient {1 + (batch_num - 1) * count}" through "Patient {batch_num * count}". '
            "Each value must be a 3-to-5-sentence medication-history narrative "
            "written for a broad audience (≈ 40-60 plain-English words).",
            "",
            "Include **at least two** LOW-complexity patients "
            "(single renewal, first-time Rx, or simple dose tweak). Other patients may be moderate "
            "or high complexity, guided by the diversity checklist below:",
            "- Age bands: <18, 18-30, 30-50, 50-70, >70.",
            "- Social context: homelessness, language barrier, uninsured, rural isolation, etc.",
            "- Novel drug classes: GLP-1 agonists, oral TKIs, depot antipsychotics, inhaled steroids, biologics, "
            "antivirals, contraception, chemo, herbals.",
            "- Edge-case themes: pregnancy, QT risk, REMS, dialysis, polypharmacy/deprescribing, travel medicine, etc.",
            "",
            f"Already-seen motifs → {', '.join(self.seen_scenarios) if self.seen_scenarios else 'None yet'}. "
            "**Avoid** re-using templates like ACE-inhibitor-to-ARB cough, long-term warfarin INR drift, "
            "or COPD tiotropium boilerplate.",
            "",
            "Write in clear prose with minimal jargon. If a medical abbreviation is unavoidable, "
            "spell it out the first time (e.g., “twice-daily (BID)”). Prefer full words: “by mouth” "
            "over “PO”, “under the skin” over “SC”. Vary openings: lead with social detail, "
            "medication list, or family history.",
            "",
            "Each narrative MUST include:",
            "• Current medicines in plain words, with some cases not having complete details.",
            "• A scenario involving medication management—straightforward new prescriptions, simple dose "
            "adjustments, or complex edge cases involving risky medications, polypharmacy, or social barriers.",
            "• Any key allergy, condition, or social barrier.",
            "",
            "Do NOT write SOAP notes, vital signs, or assessments.",
            "",
            "Wrap the JSON in a fenced ```json block and output nothing else.",
        ]

        batch = cast(
            dict[str, str],
            HelperSyntheticJson.generate_json(
                vendor_key=self.vendor_key,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
            ),
        )

        for name, content in batch.items():
            self.seen_scenarios.append(self._extract_initial_fragment(content))
            self.all_profiles[name] = content

        return batch

    def run(self, batches: int, batch_size: int, output_path: Path) -> None:
        for i in range(1, batches + 1):
            print(f"Generating batch {i}…")
            self.generate_batch(i, batch_size)
        self._save_combined(output_path)
        self._save_individuals(output_path)

    @staticmethod
    def main() -> None:
        parser = argparse.ArgumentParser(description="Generate synthetic patient-profile JSON batches.")
        parser.add_argument("--batches", type=int, required=True, help="Number of batches")
        parser.add_argument("--batch-size", type=int, required=True, help="Profiles per batch")
        parser.add_argument("--output", type=Path, required=True, help="Combined JSON output path")
        args = parser.parse_args()

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        settings = HelperEvaluation.settings()
        vendor_key = settings.llm_text

        SyntheticProfileGenerator(vendor_key).run(
            batches=args.batches, batch_size=args.batch_size, output_path=args.output
        )


if __name__ == "__main__":
    SyntheticProfileGenerator.main()
