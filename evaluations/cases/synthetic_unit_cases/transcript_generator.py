from pathlib import Path
import json
import re
import os
import random
import argparse
from typing import List, Tuple, Any
from json import JSONDecodeError

from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.llm_turn import LlmTurn
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog

class Constants:
    TURN_BUCKETS = {
        "short": (2, 4),      
        "medium": (6, 8),
        "long": (10, 14)
    }

    MOOD_POOL = [
        "patient is frustrated", "patient is tearful", "patient is embarrassed",
        "patient is defensive", "clinician is concerned", "clinician is rushed",
        "clinician is warm", "clinician is brief"
    ]

    PRESSURE_POOL = [
        "time pressure on the visit", "insurance denied prior authorization",
        "formulary change", "refill limit reached", "patient traveling soon",
        "side‑effect report just came in"
    ]

    CLINICIAN_PERSONAS = [
        "warm and chatty", "brief and efficient", "cautious and inquisitive",
        "over‑explainer"
    ]

    PATIENT_PERSONAS = [
        "anxious and talkative", "confused and forgetful",
        "assertive and informed", "agreeable but vague"
    ]

    FORBIDDEN_CLOSINGS = {
        "okay thanks", "thanks for coming", "take care", "bye for now",
        "we'll follow up", "see you next time"
    }

def _safe_json_load(txt: str) -> Tuple[Any, str | None]:
    """Return (data, err_msg).  data is None if still invalid."""
    def attempt(s: str):
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

    stripped = re.sub(r",(?=[\\s]*[\\]}])", "", txt)
    data, err = attempt(stripped)
    if data:
        return data, None

    data, err = attempt(stripped.rstrip("'\"` \n"))
    return data, err

class TranscriptGenerator:
    """Generate mid‑conversation transcript snippets with controlled variation."""

    def __init__(self, llm_key: str, input_profiles_path: str, output_root_path: str):
        self.llm_key = llm_key
        self.input_profiles_path = Path(input_profiles_path).expanduser()
        self.output_root = Path(output_root_path).expanduser()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.profiles = self._load_profiles()
        self.seen_openings: set[str] = set()

    def _load_profiles(self):
        with self.input_profiles_path.open() as f:
            return json.load(f)

    def _create_llm(self):
        return LlmOpenai(MemoryLog.dev_null_instance(), self.llm_key,
                         Constants.OPENAI_CHAT_TEXT, False)

    def _random_bucket(self):
        return random.choice(list(Constants.TURN_BUCKETS.keys()))

    def _make_spec(self):
        bucket = self._random_bucket()
        lo, hi = Constants.TURN_BUCKETS[bucket]
        turn_total = random.randint(lo, hi)

        first = random.choice(["Clinician", "Patient"])
        other = "Patient" if first == "Clinician" else "Clinician"
        speaker_sequence: List[str] = [first]
        for _ in range(turn_total - 1):
            speaker_sequence.append(random.choice([first, other]))

        #randomized ratio between 1:2 to 2:1. 
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
            "bucket": bucket
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
            LlmTurn(role="user",  text=user_lines)
        ]

    def generate_transcript_for_profile(self, profile_text: str) -> Tuple[list, dict]:
        spec = self._make_spec()
        llm = self._create_llm()
        for turn in self._build_prompt(profile_text, spec):
            llm.add_prompt(turn)

        raw = llm.request().response
        cleaned = re.sub(r"```(?:json)?\n?|\\n?```", "", raw).strip()

        transcript, err = _safe_json_load(cleaned)
        if transcript is None:
            # fallback placeholder + raw text file
            print("Transcript generation formatting error, look at spec audit.")
            transcript = [{"speaker": "SYSTEM", "text": "RAW_LLM_OUTPUT_NOT_JSON"}]
            transcript.append({"speaker": "LLM_RAW", "text": cleaned[:5000]})
            spec["json_error"] = err  # record parse error

        if transcript and isinstance(transcript, list) and "text" in transcript[0]:
            self.seen_openings.add(transcript[0]["text"].strip().lower())

        return transcript, spec, cleaned

    def run(self, start_index: int = 1, limit: int | None = None):
        items = list(self.profiles.items())
        #slicing based on start_index and limit flags in cases of partial run fails.
        items = items[start_index - 1:] 
        if limit:
            items = items[:limit]

        for patient_name, profile_text in items:
            safe_name = re.sub(r"\W+", "_", patient_name)
            patient_dir = self.output_root / safe_name
            patient_dir.mkdir(parents=True, exist_ok=True)

            print(f"Generating transcript for {patient_name}")
            transcript, spec, raw_txt = self.generate_transcript_for_profile(profile_text)

            # save transcript + spec
            (patient_dir / "transcript.json").write_text(json.dumps(transcript, indent=2))
            (patient_dir / "spec.json").write_text(json.dumps(spec, indent=2))

            #keeping raw file just in case for debugging. 
            (patient_dir / "raw_transcript.txt").write_text(raw_txt)

            print("Saved => transcript.json, spec.json, raw_transcript.txt")


if __name__ == "__main__":
    llm_key = os.getenv("KeyTextLLM")
    if not llm_key:
        raise RuntimeError("KeyTextLLM env var not set")

    generator = TranscriptGenerator(
        llm_key=llm_key,
        input_profiles_path="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management/patient_profiles.json",
        output_root_path="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management"
    )
    # pass --limit N via CLI if desired
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start", type=int, default=1,   help="start at patient N (1-based)")
    args = parser.parse_args()
    generator.run(start_index=args.start, limit=args.limit)
