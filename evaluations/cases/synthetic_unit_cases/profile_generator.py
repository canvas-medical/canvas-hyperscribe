import re
import json
from pathlib import Path
import os
import argparse
from hyperscribe.llms.llm_openai_o3 import LlmOpenaiO3
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.settings import Settings
from hyperscribe.libraries.memory_log import MemoryLog
from typing import Any

class PatientProfileGenerator:
    def __init__(self, vendor_key: VendorKey, output_path_str: str) -> None:
        self.vendor_key = vendor_key
        self.output_path = Path(output_path_str).expanduser()
        self.seen_scenarios: list[str] = []
        self.all_profiles: dict[str, str] = {}

    def _create_llm(self) -> LlmOpenaiO3:
        return LlmOpenaiO3(
            MemoryLog.dev_null_instance(),
            self.vendor_key.api_key,
            with_audit=False
        )

    def _summarize_scenario(self, narrative: str) -> str:
        return narrative.split(".")[0][:100]

    def _save_combined(self) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open('w') as f:
            json.dump(self.all_profiles, f, indent=2)
        print(f"Saved {len(self.all_profiles)} medication management profiles to {self.output_path}")

    def _save_individuals(self) -> None:
        base_dir = self.output_path.parent
        for name, narrative in self.all_profiles.items():
            dir_name = re.sub(r'\s+', '_', name.strip())
            dir_path = base_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

            file_path = dir_path / "profile.json"
            with file_path.open('w') as f:
                json.dump({name: narrative}, f, indent=2)
            print(f"Saved profile for {name} to {file_path}")

    def generate_batch(self, batch_num: int, count: int) -> dict[str, str]:
        llm = self._create_llm()
        llm.set_system_prompt([
                "You are a clinical informatics expert generating synthetic patient profiles for testing medication management AI systems."
                " You understand the structure and variation in real EHR notes and how medication histories reflect complex clinical decision-making."
            ])
        llm.set_user_prompt([f"Create a JSON object with {count} key-value pairs labeled "
                f"\"Patient {1 + (batch_num-1)*count}\" through \"Patient {batch_num*count}\". "
                "Each value must be a 3-to-5-sentence medication-history narrative "
                "written for a broad audience (≈ 40-60 plain-English words).",

                "Include **at least two** LOW-complexity patients (single renewal, first-time Rx, or simple dose tweak). "
                "Other patients may be moderate or high complexity, guided by the diversity checklist below.",

                "For the whole batch vary **at least two** items per patient, avoiding repeats:",
                "- Age bands: <18, 18-30, 30-50, 50-70, >70.",
                "- Social context: homelessness, language barrier, uninsured, rural isolation, etc.",
                "- Novel drug classes: GLP-1 agonists, oral TKIs, depot antipsychotics, inhaled steroids, biologics, antivirals, contraception, chemo, herbals.",
                "- Edge-case themes: pregnancy, QT risk, REMS, dialysis, polypharmacy/deprescribing, travel medicine, etc.",

                f"Already-seen motifs → {', '.join(self.seen_scenarios) if self.seen_scenarios else 'None yet'}. "
                "**Avoid** re-using templates like ACE-inhibitor-to-ARB cough, long-term warfarin INR drift, or COPD tiotropium boilerplate.",

                "Write in clear prose with minimal jargon. If a medical abbreviation is unavoidable, spell it out the first time "
                "(e.g., “twice-daily (BID)”). Prefer full words: “by mouth” over “PO”, “under the skin” over “SC”. "
                "Vary openings: lead with social detail, medication list, or family history.",

                "Each narrative MUST include:",
                "• Current medicines in plain words, with some of the cases not having complete details.",
                "• A scenario involving medication management, whether it be straight forward new prescrptions with no prior history, simple dose adjustments"
                "or clean medication changes, chronic single-medication use, and also complex edge case involving risky medications, polypharmacy, or social barriers."
                "• Any key allergy, condition, or social barrier.",

                "Do NOT write SOAP notes, vital signs, or assessments.",
                "Return **raw JSON only** – no markdown, headings, or commentary."
            ])

        response = llm.request()
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()
        batch_data = json.loads(cleaned)

        for name, content in batch_data.items():
            if isinstance(content, dict) and "narrative" in content:
                narrative = content["narrative"]
            elif isinstance(content, str):
                narrative = content
            else:
                raise ValueError(f"Unexpected profile format for {name}: {content}")

            self.seen_scenarios.append(self._summarize_scenario(narrative))
            self.all_profiles[name] = narrative


        return batch_data

    def run(self, batches: int, batch_size: int) -> None:
        for batch_num in range(1, batches + 1):
            print(f"Generating batch {batch_num}...")
            self.generate_batch(batch_num, batch_size)
        self._save_combined()
        self._save_individuals()


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic patient-profile JSON batches.")
    parser.add_argument("--batches", type=int, required=True, help="Number of batches to produce")
    parser.add_argument("--batch-size", type=int, required=True, help="Profiles per batch")
    parser.add_argument("--output", type=str, required=True, help="Path of combined JSON output")
    args = parser.parse_args()

    settings = Settings.from_dictionary(os.environ)
    vendor_key = settings.llm_text

    generator = PatientProfileGenerator(
        vendor_key=vendor_key,
        output_path_str=args.output
    )
    generator.run(batches=args.batches, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
