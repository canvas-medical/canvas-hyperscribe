import json
import random
from typing import Any, Dict, List, Tuple

from hyperscribe.structures.vendor_key import VendorKey
from evaluations.case_builders.synthetic_json_helper import generate_json
from evaluations.constants import Constants

class TranscriptGenerator:
    def __init__(self, vendor_key: VendorKey) -> None:
        self.vendor_key = vendor_key
        self.seen_openings: set[str] = set()

    def _random_bucket(self) -> str:
        return random.choice(list(Constants.TURN_BUCKETS.keys()))

    def _make_spec(self) -> Dict[str, Any]:
        bucket = self._random_bucket()
        lo, hi = Constants.TURN_BUCKETS[bucket]
        turn_total = random.randint(lo, hi)

        first = random.choice(["Clinician", "Patient"])
        other = "Patient" if first == "Clinician" else "Clinician"
        speaker_sequence = [first] + [
            random.choice([first, other]) for _ in range(turn_total - 1)
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

    def _build_prompt(self, profile_text: str, spec: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        system_prompt = [
            "You are simulating a real outpatient medication-management discussion.",
            "Return ONLY a raw JSON array of turns with 'speaker' and 'text'.",
            "Start mid-conversation, no greetings.",
            "End mid-topic, no farewells.",
            "We must follow the pre-defined speaker sequence and stay within ±10% of the C:P word-ratio target.",
            "Use plain language with occasional natural hesitations (e.g., 'uh', 'I mean')."
        ]
        if self.seen_openings:
            system_prompt.append(
                "Avoid starting with any of these previous first lines: " +
                ", ".join(sorted(self.seen_openings))
            )

        user_prompt = [
            f"Patient profile: {profile_text}",
            "--- TRANSCRIPT SPEC ---",
            json.dumps({
                "turn_total": spec["turn_total"],
                "speaker_sequence": spec["speaker_sequence"],
                "target_C_to_P_word_ratio": spec["ratio"]
            }),
            "Moods: " + ", ".join(m.value for m in spec["mood"]),
            "External pressure: " + spec["pressure"].value,
            f"Clinician persona: {spec['clinician_style'].value}",
            f"Patient persona: {spec['patient_style'].value}",
            "Instructions:",
            "1. Follow the speaker sequence exactly (same order and length).",
            "2. Strive for the requested word-ratio ±10%.",
            "3. Embed the mood, pressure, and personas naturally.",
            "4. Focus on medication details: dose changes, side-effects, adherence, etc.",
            "5. No concluding pleasantries.",
            "Return ONLY valid JSON — start with [ and end with ] — no other text."
        ]

        return system_prompt, user_prompt


    def generate_transcript_for_profile(
        self, profile_text: str
    ) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        spec = self._make_spec()
        spec["mood"] = [Constants.MOOD_MAP[m] for m in spec["mood"]]
        spec["pressure"] = Constants.PRESSURE_MAP[spec["pressure"]]
        spec["clinician_style"] = Constants.CLINICIAN_STYLE_MAP[spec["clinician_style"]]
        spec["patient_style"] = Constants.PATIENT_STYLE_MAP[spec["patient_style"]]
        spec["bucket"] = Constants.TURN_BUCKETS_MAP[spec["bucket"]]
        system_prompt, user_prompt = self._build_prompt(profile_text, spec)

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": spec["turn_total"],
            "maxItems": spec["turn_total"],
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["speaker", "text"],
                "additionalProperties": False
            }
        }

        transcript: List[Dict[str, str]] = generate_json(
            vendor_key=self.vendor_key,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
            retries=3
        )

        first_line = transcript[0].get("text", "").strip().lower()
        self.seen_openings.add(first_line)

        return transcript, spec
