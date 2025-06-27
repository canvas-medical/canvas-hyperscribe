import re
import json
from pathlib import Path
import os
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog


class PatientProfile:
    def __init__(self, name, narrative):
        self.name = name
        self.narrative = narrative

    def summarize_scenario(self):
        #Returns first sentence to ensure profile diversity with downstream seen_scenarios variable.
        return self.narrative.split(".")[0][:100]


class PatientProfileGenerator:
    def __init__(self, llm_key):
        self.llm_key = llm_key
        self.seen_scenarios = []

    def _create_llm(self):
        return LlmOpenai(
            MemoryLog.dev_null_instance(),
            self.llm_key,
            Constants.OPENAI_CHAT_TEXT,
            False
        )

    def generate_batch(self, batch_num, count=5):
        llm = self._create_llm()

        llm.add_prompt(LlmTurn(
            role="system",
            text=[
                "You are a clinical informatics expert generating synthetic patient profiles for testing medication management AI systems. You understand the structure and variation in real EHR notes and how medication histories reflect complex clinical decision-making."
            ]
        ))

        llm.add_prompt(LlmTurn(
            role="user",
            text=[
                f"Create a JSON object with {count} key-value pairs labeled "
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
            ]
        ))

        response = llm.request()
        #cleans any errors with json formatting (safety net)
        cleaned = re.sub(r'```(?:json)?\n?|\n?```', '', response.response).strip()
        batch_data = json.loads(cleaned)

        batch_profiles = []
        for name, narrative in batch_data.items():
            profile = PatientProfile(name, narrative)
            self.seen_scenarios.append(profile.summarize_scenario())
            batch_profiles.append(profile)

        return batch_profiles

class PatientProfilePipeline:
    def __init__(self, llm_key, output_path_str):
        self.generator = PatientProfileGenerator(llm_key)
        self.output_path = Path(output_path_str).expanduser()
        self.all_profiles = {}

    def _save_combined(self):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open('w') as f:
            json.dump(self.all_profiles, f, indent=2)
        print(f"Saved {len(self.all_profiles)} medication management profiles to {self.output_path}")

    def _save_individuals(self):
        base_dir = self.output_path.parent
        for name, narrative in self.all_profiles.items():
            # Sanitize name for directory (e.g., "Patient 1" -> "Patient_1")
            dir_name = re.sub(r'\s+', '_', name.strip())
            dir_path = base_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

            file_path = dir_path / "profile.json"
            with file_path.open('w') as f:
                json.dump({name: narrative}, f, indent=2)
            print(f"Saved profile for {name} to {file_path}")

    def run(self, batches=8, batch_size=5):
        for batch_num in range(1, batches + 1):
            print(f"Generating batch {batch_num}...")
            batch_profiles = self.generator.generate_batch(batch_num, batch_size)
            for profile in batch_profiles:
                self.all_profiles[profile.name] = profile.narrative

        self._save_combined()
        self._save_individuals()


if __name__ == "__main__":
    llm_key = os.getenv('KeyTextLLM')
    if not llm_key:
        raise RuntimeError("KeyTextLLM environment variable is not set.")

    pipeline = PatientProfilePipeline(
        llm_key=llm_key,
        output_path_str="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management_tpc_o3/patient_profiles.json"
    )
    pipeline.run()
