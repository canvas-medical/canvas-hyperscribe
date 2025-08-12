import json, re, argparse, hashlib
from pathlib import Path
from typing import Any, cast

from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.libraries.memory_log import MemoryLog
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson
from evaluations.structures.patient_profile import PatientProfile


class SyntheticProfileGenerator:
    def __init__(self, vendor_key: VendorKey) -> None:
        self.vendor_key = vendor_key
        self.seen_scenarios: list[str] = []

    @classmethod
    def _extract_initial_fragment(cls, narrative: str) -> str:
        return narrative.split(".")[0][:100]

    @classmethod
    def load_json(cls, path: Path) -> list[PatientProfile]:
        with path.open("r") as f:
            profiles_dict = cast(dict[str, str], json.load(f))
        return [PatientProfile(name=name, profile=profile) for name, profile in profiles_dict.items()]

    def update_patient_names(self, profiles: list[PatientProfile]) -> list[PatientProfile]:
        """Update patient names with descriptive phrases based on their profiles using GPT-4o"""

        vendor_key = VendorKey(vendor=self.vendor_key.vendor, api_key=self.vendor_key.api_key)

        result: list[PatientProfile] = []

        for profile in profiles:
            # Generate descriptive name using GPT-4o
            system_prompt = [
                "You are an expert at creating concise, descriptive patient identifiers.",
                "Generate 1-3 short descriptive phrases (separated by dashes) "
                "that capture the key aspects of this patient's medical profile.",
                "Focus on the most relevant medical conditions, social factors, or medication themes.",
                "Use lowercase words separated by dashes"
                " (e.g., 'diabetes-hypertension', 'social-alcohol-questioning', "
                "'recent-travel-brazil').",
                "Return your answer as JSON inside a fenced ```json ... ``` block.",
                "The response must be a single string value containing the descriptive phrase(s).",
            ]

            user_prompt = [
                f"Patient profile: {profile.profile}",
                "",
                "Generate 1-3 descriptive phrases (max) separated by dashes"
                " that best describe this patient's key characteristics:",
            ]

            llm = LlmOpenai(
                MemoryLog.dev_null_instance(), vendor_key.api_key, Constants.OPENAI_CHAT_TEXT, with_audit=False
            )
            llm.set_system_prompt(system_prompt)
            llm.set_user_prompt(user_prompt)

            schema = {"type": "string"}
            response = llm.chat([schema])

            if response.has_error:
                raise Exception(response.error)

            descriptive_name = response.content[0] if response.content else "patient"
            random_hash = hashlib.md5(f"{profile.profile}{descriptive_name}".encode()).hexdigest()[:8]

            # append hash to name
            final_name = f"{descriptive_name}-{random_hash}"
            updated_profile = PatientProfile(name=final_name, profile=profile.profile)
            result.append(updated_profile)

        return result

    @classmethod
    def _save_combined(cls, profiles: list[PatientProfile], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        profiles_dict = {profile.name: profile.profile for profile in profiles}
        with output_path.open("w") as f:
            json.dump(profiles_dict, f, indent=2)
        print(f"Saved {len(profiles)} profiles to {output_path}")

    @classmethod
    def _save_individuals(cls, profiles: list[PatientProfile], output_path: Path) -> None:
        base_dir = output_path.parent
        for patient_profile in profiles:
            dir_name = re.sub(r"\s+", "_", patient_profile.name.strip())
            dir_path = base_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            file_path = dir_path / "profile.json"
            with file_path.open("w") as f:
                json.dump({patient_profile.name: patient_profile.profile}, f, indent=2)
            print(f"Saved profile for {patient_profile.name} to {file_path}")

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

    def generate_batch(self, batch_num: int, count: int) -> list[PatientProfile]:
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

        initial_profiles = cast(
            list[PatientProfile],
            HelperSyntheticJson.generate_json(
                vendor_key=self.vendor_key,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
                returned_class=PatientProfile,
            ),
        )

        # Track seen scenarios
        for profile in initial_profiles:
            self.seen_scenarios.append(self._extract_initial_fragment(profile.profile))

        result = self.update_patient_names(initial_profiles)

        return result

    def run(self, batches: int, batch_size: int, output_path: Path) -> None:
        all_profiles: list[PatientProfile] = []
        for i in range(1, batches + 1):
            print(f"Generating batch {i}…")
            batch_profiles = self.generate_batch(i, batch_size)
            all_profiles.extend(batch_profiles)
        self._save_combined(all_profiles, output_path)
        self._save_individuals(all_profiles, output_path)

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
