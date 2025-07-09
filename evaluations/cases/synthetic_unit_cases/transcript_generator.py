from pathlib import Path
import json
import re
import os
import random
import argparse
from typing import List, Tuple, Any, cast
from json import JSONDecodeError

from hyperscribe.llms.llm_openai_o3 import LlmOpenaiO3
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.settings import Settings
from hyperscribe.libraries.memory_log import MemoryLog
from evaluations.constants import Constants

class TranscriptGenerator:
    def __init__(self, vendor_key: VendorKey, input_profiles_path: str, output_root_path: str) -> None:
        self.vendor_key = vendor_key
        self.input_profiles_path = Path(input_profiles_path).expanduser()
        self.output_root = Path(output_root_path).expanduser()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.profiles = self._load_profiles()
        self.seen_openings: set[str] = set()

    def _load_profiles(self) -> dict[str, str]:
        with self.input_profiles_path.open() as f:
            return cast(dict[str, str], json.load(f))

    def _create_llm(self) -> LlmOpenaiO3:
        return LlmOpenaiO3(
            MemoryLog.dev_null_instance(),
            self.vendor_key.api_key,
            with_audit=False
        )

    def _safe_json_load(self, txt: str) -> Tuple[Any | None, str | None]:
        def attempt(s: str) -> Tuple[Any | None, str | None]:
            try:
                return json.loads(s), None
            except JSONDecodeError as e:
                return None, str(e)

        data, err = attempt(txt)
        if data:
            return data, None

        m = re.search(r"[\\[{]", txt)
        if m:
            data, err = attempt(txt[m.start():])
            if data:
                return data, None

        stripped = re.sub(r",\s+(?=[}\]])", "", txt)
        data, err = attempt(stripped)
        if data:
            return data, None

        return attempt(stripped.rstrip("'\"` \n"))

    def _random_bucket(self) -> str:
        return random.choice(list(Constants.TURN_BUCKETS.keys()))

    def _make_spec(self) -> dict[str, Any]:
        bucket = self._random_bucket()
        lo, hi = Constants.TURN_BUCKETS[bucket]
        turn_total = random.randint(lo, hi)

        first = random.choice(["Clinician", "Patient"])
        other = "Patient" if first == "Clinician" else "Clinician"
        speaker_sequence = [first] + [random.choice([first, other]) for _ in range(turn_total - 1)]
        ratio = round(random.uniform(0.5, 2.0), 2)
        mood = random.sample(Constants.MOOD_POOL, k=2)
        pressure = random.choice(Constants.PRESSURE_POOL)
        clinician_style = random.choice(Constants.CLINICIAN_PERSONAS)
        patient_style = random.choice(Constants.PATIENT_PERSONAS)

        return {
            "turn_total": turn_total,
            "speaker_sequence": speaker_sequence,
            "ratio": ratio,
            "mood": mood,
            "pressure": pressure,
            "clinician_style": clinician_style,
            "patient_style": patient_style,
            "bucket": bucket,
        }

    def _build_prompt(self, profile_text: str, spec: dict) -> List[LlmTurn]:
        system_lines = [
            "You are simulating a real outpatient medication-management discussion.",
            "Return ONLY a raw JSON array of turns with 'speaker' and 'text'.",
            "Start mid-conversation, no greetings.",
            "End mid-topic, no farewells.",
            "We must follow the pre-defined speaker sequence and stay within ±10% of the C:P word-ratio target.",
            "Use plain language with occasional natural hesitations (e.g., 'uh', 'I mean')."
        ]
        if self.seen_openings:
            system_lines.append(
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
        return [
            LlmTurn(role="system", text=system_lines),
            LlmTurn(role="user", text=user_lines)
        ]

    def generate_transcript_for_profile(self, profile_text: str) -> Tuple[list[Any], dict[str, Any], str]:
        spec = self._make_spec()
        llm = self._create_llm()
        for turn in self._build_prompt(profile_text, spec):
            llm.add_prompt(turn)

        raw = llm.request().response
        cleaned = re.sub(r"```(?:json)?\n?|\\n?```", "", raw).strip()

        transcript, err = self._safe_json_load(cleaned)
        if transcript is None:
            print("Transcript generation formatting error, look at spec audit.")
            transcript = [{"speaker": "SYSTEM", "text": "RAW_LLM_OUTPUT_NOT_JSON"}]
            transcript.append({"speaker": "LLM_RAW", "text": cleaned[:Constants.RAW_TEXT_CUTOFF]})
            spec["json_error"] = err

        if transcript and isinstance(transcript, list) and "text" in transcript[0]:
            self.seen_openings.add(transcript[0]["text"].strip().lower())

        return transcript, spec, cleaned

    def run(self, start_index: int, limit: int) -> None:
        items = list(self.profiles.items())
        items = items[start_index - 1:start_index - 1 + limit]

        for patient_name, profile_text in items:
            safe_name = re.sub(r"\W+", "_", patient_name)
            patient_dir = self.output_root / safe_name
            patient_dir.mkdir(parents=True, exist_ok=True)

            print(f"Generating transcript for {patient_name}")
            transcript, spec, raw_txt = self.generate_transcript_for_profile(profile_text)

            (patient_dir / "transcript.json").write_text(json.dumps(transcript, indent=2))
            (patient_dir / "spec.json").write_text(json.dumps(spec, indent=2))
            (patient_dir / "raw_transcript.txt").write_text(raw_txt)

            print("Saved => transcript.json, spec.json, raw_transcript.txt")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--limit", type=int, required=True)
    args = parser.parse_args()

    settings = Settings.from_dictionary(os.environ)
    vendor_key = settings.llm_text

    generator = TranscriptGenerator(
        vendor_key=vendor_key,
        input_profiles_path=args.profiles,
        output_root_path=args.output
    )
    generator.run(start_index=args.start, limit=args.limit)
