from __future__ import annotations
import json, re, argparse, random
from pathlib import Path
from typing import Any, Tuple, cast

from hyperscribe.structures.vendor_key import VendorKey
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson
from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle
from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle
from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood
from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets
from evaluations.constants import Constants


class SyntheticTranscriptGenerator:
    def __init__(self, vendor_key: VendorKey, input_path: Path, output_path: Path) -> None:
        self.vendor_key = vendor_key
        self.input_path = input_path
        self.output_path = output_path
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.profiles = self._load_profiles()
        self.seen_openings: set[str] = set()

    def _load_profiles(self) -> dict[str, str]:
        with self.input_path.open() as f:
            return cast(dict[str, str], json.load(f))

    @staticmethod
    def _random_bucket() -> SyntheticCaseTurnBuckets:
        return random.choice(list(SyntheticCaseTurnBuckets))

    def _make_specifications(self) -> dict[str, Any]:
        bucket = self._random_bucket()
        low, high = Constants.TURN_BUCKETS[bucket]
        turn_total = random.randint(low, high)

        sequence = [random.choice(["Clinician", "Patient"]) for _ in range(turn_total)]

        return {
            Constants.TURN_TOTAL: turn_total,
            Constants.SPEAKER_SEQUENCE: sequence,
            Constants.RATIO: round(random.uniform(0.5, 2.0), 2),
            Constants.MOOD_KEY: random.sample([mood.value for mood in SyntheticCaseMood], k=2),
            Constants.PRESSURE_KEY: random.choice([pressure.value for pressure in SyntheticCasePressure]),
            Constants.CLINICIAN_STYLE_KEY: random.choice(
                [clinician_style.value for clinician_style in SyntheticCaseClinicianStyle]
            ),
            Constants.PATIENT_STYLE_KEY: random.choice(
                [patient_style.value for patient_style in SyntheticCasePatientStyle]
            ),
            Constants.BUCKET: bucket.value,
        }

    @classmethod
    def schema_transcript(cls, turn_total: int) -> dict[str, Any]:
        """Build a JSON Schema that enforces JSON transcript structure."""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": turn_total,
            "maxItems": turn_total,
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {
                        "type": "string",
                        "description": "Who is talking for this turn, either 'Clinician' or 'Patient'.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Words spoken during the turn.",
                    },
                },
                "required": ["speaker", "text"],
                "additionalProperties": False,
            },
        }

    def _build_prompt(
        self,
        profile_text: str,
        specifications: dict[str, Any],
        schema: dict[str, Any],
    ) -> Tuple[list[str], list[str]]:
        system_lines = [
            "You are simulating a real outpatient medication-management discussion.",
            "Return your answer as JSON inside a fenced ```json ... ``` block.",
            "Start mid-conversation, no greetings. End mid-topic, no farewells.",
            "Follow the speaker sequence *exactly* and aim for the target C:P word ratio ±10%.",
            "Use plain language with occasional natural hesitations (e.g., “uh”, “I mean”).",
        ]
        if self.seen_openings:
            system_lines.append(
                f"Avoid starting with any of these previous first lines: {', '.join(sorted(self.seen_openings))}"
            )

        user_lines = [
            f"Patient profile: {profile_text}",
            "--- TRANSCRIPT SPEC ---",
            json.dumps(
                {
                    Constants.TURN_TOTAL: specifications[Constants.TURN_TOTAL],
                    Constants.SPEAKER_SEQUENCE: specifications[Constants.SPEAKER_SEQUENCE],
                    Constants.TARGET_C_TO_P_WORD_RATIO: specifications[Constants.RATIO],
                }
            ),
            "",
            f"Moods: {', '.join(specifications[Constants.MOOD_KEY])}",
            f"External pressure: {specifications[Constants.PRESSURE_KEY]}",
            f"Clinician persona: {specifications[Constants.CLINICIAN_STYLE_KEY]}",
            f"Patient persona: {specifications[Constants.PATIENT_STYLE_KEY]}",
            "",
            "Instructions:",
            "1. Follow the speaker sequence exactly (same order and length).",
            "2. Hit the requested word ratio ±10%.",
            "3. Embed the mood, pressure, and personas naturally.",
            "4. Focus on medication details—dose changes, side-effects, adherence, etc.",
            "5. No concluding pleasantries.",
            "",
            "Your JSON **must** conform to the following JSON Schema:",
            "```json",
            json.dumps(schema, indent=2),
            "```",
            "",
            "Wrap the JSON array in a fenced ```json block and output nothing else.",
        ]

        return system_lines, user_lines

    def generate_transcript_for_profile(self, profile_text: str) -> Tuple[list[dict[str, str]], dict[str, Any]]:
        specifications = self._make_specifications()
        schema = self.schema_transcript(specifications["turn_total"])

        system_lines, user_lines = self._build_prompt(profile_text, specifications, schema)

        transcript = HelperSyntheticJson.generate_json(
            vendor_key=self.vendor_key,
            system_prompt=system_lines,
            user_prompt=user_lines,
            schema=schema,
        )

        first_line = transcript[0].get("text", "").strip().lower()
        self.seen_openings.add(first_line)

        return transcript, specifications

    def run(self, start_index: int, limit: int) -> None:
        items = list(self.profiles.items())
        slice_ = items[start_index - 1 : start_index - 1 + limit]

        for patient_name, profile_text in slice_:
            safe_name = re.sub(r"\W+", "_", patient_name)
            patient_dir = self.output_path / safe_name
            patient_dir.mkdir(parents=True, exist_ok=True)

            print(f"Generating transcript for {patient_name}…")
            transcript, specifications = self.generate_transcript_for_profile(profile_text)

            (patient_dir / "transcript.json").write_text(json.dumps(transcript, indent=2))
            (patient_dir / "specifications.json").write_text(json.dumps(specifications, indent=2))
            print(f"Saved => {patient_dir / 'transcript.json'}, {patient_dir / 'specifications.json'}")

    @staticmethod
    def main() -> None:
        parser = argparse.ArgumentParser(description="Generate synthetic transcripts from patient profiles.")
        parser.add_argument("--input", type=Path, required=True, help="Path to profiles.json")
        parser.add_argument("--output", type=Path, required=True, help="Directory for outputs")
        parser.add_argument("--start", type=int, required=True, help="1‑based start index")
        parser.add_argument("--limit", type=int, required=True, help="Number of profiles")
        args = parser.parse_args()

        settings = HelperEvaluation.settings()
        vendor_key = settings.llm_text

        generator = SyntheticTranscriptGenerator(vendor_key=vendor_key, input_path=args.input, output_path=args.output)
        generator.run(start_index=args.start, limit=args.limit)


if __name__ == "__main__":
    SyntheticTranscriptGenerator.main()
