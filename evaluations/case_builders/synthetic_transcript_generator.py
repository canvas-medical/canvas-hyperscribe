from __future__ import annotations
import json, re, argparse, random
from pathlib import Path
from typing import Any, Tuple, cast

from hyperscribe.structures.vendor_key import VendorKey
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson
from evaluations.constants import Constants

class SyntheticTranscriptGenerator:
    def __init__(self, vendor_key: VendorKey, input_path: Path, output_path: Path) -> None:
        self.vendor_key  = vendor_key
        self.input_path  = input_path
        self.output_path = output_path
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.profiles = self._load_profiles()
        self.seen_openings: set[str] = set()

    def _load_profiles(self) -> dict[str, str]:
        with self.input_path.open() as f:
            return cast(dict[str, str], json.load(f))

    @staticmethod
    def _random_bucket() -> str:
        return random.choice(list(Constants.TURN_BUCKETS.keys()))

    def _make_spec(self) -> dict[str, Any]:
        bucket = self._random_bucket()
        low, high = Constants.TURN_BUCKETS[bucket]
        turn_total = random.randint(low, high)

        first  = random.choice(["Clinician", "Patient"])
        other  = "Patient" if first == "Clinician" else "Clinician"
        seq    = [first] + [random.choice([first, other]) for _ in range(turn_total - 1)]

        return {
            "turn_total": turn_total,
            "speaker_sequence": seq,
            "ratio": round(random.uniform(0.5, 2.0), 2),
            "mood": random.sample(Constants.MOOD_POOL, k=2),
            "pressure": random.choice(Constants.PRESSURE_POOL),
            "clinician_style": random.choice(Constants.CLINICIAN_PERSONAS),
            "patient_style": random.choice(Constants.PATIENT_PERSONAS),
            "bucket": bucket,
        }
    
    def schema_transcript(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Build a JSON Schema that enforces JSON transcript structure."""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": spec["turn_total"],
            "maxItems": spec["turn_total"],
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string",
                                "description": "Who is talking for this turn, either 'Clinician' or 'Patient'."},
                    "text":    {"type": "string",
                                "description": "Words spoken during the turn."},
                },
                "required": ["speaker", "text"],
                "additionalProperties": False,
            },
        }
        return schema

    def _build_prompt(self, profile_text: str, spec: dict[str, Any],
        schema: dict[str, Any],) -> Tuple[list[str], list[str]]:
        system_lines = [
            "You are simulating a real outpatient medication-management discussion.",
            "Return your answer as JSON inside a fenced ```json ... ``` block.",
            "Start mid-conversation, no greetings. End mid-topic, no farewells.",
            "Follow the speaker sequence *exactly* and aim for the target C:P word ratio ±10%.",
            "Use plain language with occasional natural hesitations (e.g., “uh”, “I mean”).",
        ]
        if self.seen_openings:
            system_lines.append(
                f"Avoid starting with any of these previous first lines: {', '.join(sorted(self.seen_openings))}")

        user_lines = [
            f"Patient profile: {profile_text}",
            "--- TRANSCRIPT SPEC ---",
            json.dumps(
                {
                    "turn_total": spec["turn_total"],
                    "speaker_sequence": spec["speaker_sequence"],
                    "target_C_to_P_word_ratio": spec["ratio"],
                }
            ),
            "",
            f"Moods: {', '.join(spec['mood'])}",
            f"External pressure: {spec['pressure']}",
            f"Clinician persona: {spec['clinician_style']}",
            f"Patient persona: {spec['patient_style']}",
            "",
            "Instructions:",
            "1. Follow the speaker sequence exactly (same order and length).",
            "2. Hit the requested word ratio ±10%.",
            "3. Embed the mood, pressure, and personas naturally.",
            "4. Focus on medication details—dose changes, side‑effects, adherence, etc.",
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

    def generate_transcript_for_profile(self, profile_text: str
        ) -> Tuple[list[dict[str, str]], dict[str, Any]]:
        spec = self._make_spec()
        schema = self.schema_transcript(spec)

        system_lines, user_lines = self._build_prompt(profile_text, spec, schema)

        transcript = HelperSyntheticJson.generate_json(
            vendor_key=self.vendor_key,
            system_prompt=system_lines,
            user_prompt=user_lines,
            schema=schema)

        first_line = transcript[0].get("text", "").strip().lower()
        self.seen_openings.add(first_line)

        return transcript, spec

    def run(self, start_index: int, limit: int) -> None:
        items = list(self.profiles.items())
        slice_ = items[start_index - 1 : start_index - 1 + limit]

        for patient_name, profile_text in slice_:
            safe_name   = re.sub(r"\W+", "_", patient_name)
            patient_dir = self.output_path / safe_name
            patient_dir.mkdir(parents=True, exist_ok=True)

            print(f"Generating transcript for {patient_name}…")
            transcript, spec = self.generate_transcript_for_profile(profile_text)

            (patient_dir / "transcript.json").write_text(json.dumps(transcript, indent=2))
            (patient_dir / "spec.json").write_text(json.dumps(spec, indent=2))
            print(f"Saved => {patient_dir/'transcript.json'}, {patient_dir/'spec.json'}")
    
    @staticmethod
    def main() -> None:
        parser = argparse.ArgumentParser(
            description="Generate synthetic transcripts from patient profiles.")
        parser.add_argument("--input",  type=Path, required=True, help="Path to profiles.json")
        parser.add_argument("--output", type=Path, required=True, help="Directory for outputs")
        parser.add_argument("--start",  type=int, required=True, help="1‑based start index")
        parser.add_argument("--limit",  type=int, required=True, help="Number of profiles")
        args = parser.parse_args()

        settings   = HelperEvaluation.settings()
        vendor_key = settings.llm_text

        generator = SyntheticTranscriptGenerator(
            vendor_key=vendor_key, input_path=args.input, output_path=args.output)
        generator.run(start_index=args.start, limit=args.limit)


if __name__ == "__main__":
    SyntheticTranscriptGenerator.main()
