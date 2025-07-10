import json, os, re, argparse, random
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast

from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.settings    import Settings
from evaluations.case_builders.synthetic_json_helper import generate_json
from evaluations.constants import Constants

class TranscriptGenerator:
    def __init__(self, vendor_key: VendorKey, input_path: str, output_root: str) -> None:
        self.vendor_key  = vendor_key
        self.input_path  = Path(input_path).expanduser()
        self.output_root = Path(output_root).expanduser()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.profiles    = self._load_profiles()
        self.seen_openings: set[str] = set()

    def _load_profiles(self) -> Dict[str,str]:
        with self.input_path.open() as f:
            return cast(Dict[str, str], json.load(f))

    def _random_bucket(self) -> str:
        return random.choice(list(Constants.TURN_BUCKETS.keys()))

    def _make_spec(self) -> Dict[str,Any]:
        bucket = self._random_bucket()
        lo, hi = Constants.TURN_BUCKETS[bucket]
        turn_total = random.randint(lo, hi)

        first = random.choice(["Clinician","Patient"])
        other = "Patient" if first=="Clinician" else "Clinician"
        speaker_sequence = [first] + [
            random.choice([first, other]) 
            for _ in range(turn_total - 1)
        ]

        return {
            "turn_total": turn_total,
            "speaker_sequence": speaker_sequence,
            "ratio": round(random.uniform(0.5, 2.0), 2),
            "mood": random.sample(Constants.MOOD_POOL, k=2),
            "pressure": random.choice(Constants.PRESSURE_POOL),
            "clinician_style": random.choice(Constants.CLINICIAN_PERSONAS),
            "patient_style": random.choice(Constants.PATIENT_PERSONAS),
            "bucket": bucket
        }

    def _build_prompt(self, profile_text: str, spec: Dict[str,Any]) -> Tuple[List[str], List[str]]:
        # system lines
        sys_lines = [
            "You are simulating a real outpatient medication-management discussion.",
            "Return ONLY a raw JSON array of turns with 'speaker' and 'text'.",
            "Start mid-conversation, no greetings.",
            "End mid-topic, no farewells.",
            "We must follow the pre-defined speaker sequence and stay within ±10% of the C:P word-ratio target.",
            "Use plain language with occasional natural hesitations (e.g., 'uh', 'I mean')."
        ]
        if self.seen_openings:
            sys_lines.append(
                "Avoid starting with any of these previous first lines: "
                + ", ".join(sorted(self.seen_openings))
            )

        user_lines = [
            f"Patient profile: {profile_text}",
            "--- TRANSCRIPT SPEC ---",
            json.dumps({
                "turn_total": spec["turn_total"],
                "speaker_sequence": spec["speaker_sequence"],
                "target_C_to_P_word_ratio": spec["ratio"]
            }),
            "Moods: " + ", ".join(spec["mood"]),
            "External pressure: " + spec["pressure"],
            f"Clinician persona: {spec['clinician_style']}",
            f"Patient persona: {spec['patient_style']}",
            "Instructions:",
            "1. Follow the speaker sequence exactly (same order and length).",
            "2. Strive for the requested word-ratio ±10%.",
            "3. Embed the mood, pressure, and personas naturally.",
            "4. Focus on medication details: dose changes, side-effects, adherence, etc.",
            "5. No concluding pleasantries.",
            "Return ONLY valid JSON — start with [ and end with ] — no other text."
        ]

        return sys_lines, user_lines

    def generate_transcript_for_profile(self, profile_text: str) -> Tuple[List[Dict[str,str]], Dict[str,Any]]:
        # 1) build spec & prompts
        spec = self._make_spec()
        sys_lines, user_lines = self._build_prompt(profile_text, spec)

        # 2) JSON schema for an array of exactly turn_total items
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": spec["turn_total"],
            "maxItems": spec["turn_total"],
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string"},
                    "text":    {"type": "string"}
                },
                "required": ["speaker", "text"],
                "additionalProperties": False
            }
        }

        transcript = generate_json(
            vendor_key=self.vendor_key,
            system_prompt=sys_lines,
            user_prompt=user_lines,
            schema=schema,
            retries=3
        )

        first = transcript[0].get("text", "").strip().lower()
        self.seen_openings.add(first)

        return transcript, spec

    def run(self, start_index: int, limit: int) -> None:
        items = list(self.profiles.items())
        slice_ = items[start_index-1 : start_index-1 + limit]

        for patient_name, profile_text in slice_:
            safe_name = re.sub(r"\W+", "_", patient_name)
            patient_dir = self.output_root / safe_name
            patient_dir.mkdir(parents=True, exist_ok=True)

            print(f"Generating transcript for {patient_name}…")
            transcript, spec = self.generate_transcript_for_profile(profile_text)

            (patient_dir / "transcript.json").write_text(
                json.dumps(transcript, indent=2))
            (patient_dir / "spec.json").write_text(
                json.dumps(spec, indent=2))
            print(f"Saved => {patient_dir/'transcript.json'}, {patient_dir/'spec.json'}")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic transcripts from patient profiles."
    )
    parser.add_argument("--input",  type=Path, required=True, help="Path to profiles JSON")
    parser.add_argument("--output", type=Path, required=True, help="Directory for outputs")
    parser.add_argument("--start",  type=int, required=True, help="1-based start index")
    parser.add_argument("--limit",  type=int, required=True, help="Number of profiles")
    args = parser.parse_args()

    settings = Settings.from_dictionary(dict(os.environ))
    vendor_key = settings.llm_text

    gen = TranscriptGenerator(
        vendor_key=vendor_key,
        input_path=args.input,
        output_root=args.output)
    gen.run(start_index=args.start, limit=args.limit)

if __name__ == "__main__":
    main()
