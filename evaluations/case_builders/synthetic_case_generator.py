"""
evaluations/case_builders/synthetic_case_generator.py
-----------------------------------------------------

Run a full synthetic-case pipeline:

    python -m evaluations.case_builders.synthetic_case_generator \
        --category med_management \
        --batches 8 \
        --batch-size 5 \
        --example-chart evaluations/case_builders/context_representative_limited_chart.json \
        --output ./offline_cases

• If Postgres credentials (via env vars) are complete, records are upserted.
• Otherwise, Case & SyntheticCase NamedTuples are dumped as JSON files
  under --output (one folder per patient).
"""

import json, os, argparse, hashlib, re
from pathlib import Path
from typing import List, Tuple, Any, Dict
from enum import Enum
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.line import Line
from hyperscribe.structures.vendor_key import VendorKey

from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.constants import Constants
from hyperscribe.libraries.constants import Constants as HSConstants

from evaluations.structures.records.case import Case as CaseRecord
from evaluations.structures.records.synthetic_case import SyntheticCase as SyntheticRecord
from evaluations.datastores.postgres.case import Case
from evaluations.datastores.postgres.synthetic_case import SyntheticCase

from evaluations.case_builders.synthetic_profile_generator import PatientProfileGenerator
from evaluations.case_builders.synthetic_chart_generator import ChartGenerator
from evaluations.case_builders.synthetic_transcript_generator import TranscriptGenerator

def _load_json(path: Path):
    with path.open() as f:
        return json.load(f)

def _dump_json(path: Path, obj):
    def convert(val):
        if isinstance(val, Enum):
            return val.value
        elif isinstance(val, list):
            return [convert(v) for v in val]
        elif isinstance(val, dict):
            return {k: convert(v) for k, v in val.items()}
        return val

    cleaned = {k: convert(v) for k, v in obj.items()} 
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cleaned, indent=2))

def build_case_name(
    spec: Dict[str, Any],
    limited_chart: Dict[str, Any],
    category: str,
    ) -> str:
        """
        Name format:
        turnbucket_pressure_gender_age_category_hash
        e.g.  short_refill_limit_female_age_22_med_management_d4e7a
        """
        bucket = spec["bucket"].value if hasattr(spec["bucket"], "value") else str(spec["bucket"])
        pressure = spec["pressure"].value if hasattr(spec["pressure"], "value") else str(spec["pressure"])
        
        demo = limited_chart.get("demographicStr", "").lower()
        gender = "unspecified"
        if "woman" in demo or "female" in demo:
            gender = "female"
        elif "man" in demo or "male" in demo:
            gender = "male"
        
        age_match = re.search(r"\(age\s+(\d+)\)", demo)
        age_part = f"age_{age_match.group(1)}" if age_match else "age_unk"
        raw = f"{bucket}{pressure}{gender}{age_part}{category}"
        short_hash = hashlib.sha256(raw.encode()).hexdigest()[:6]
        return f"{bucket}_{pressure}_{gender}_{age_part}_{category}_{short_hash}"

class SyntheticCaseOrchestrator:
    def __init__(
        self,
        vendor_key: VendorKey,
        example_chart_path: Path,
        credentials: PostgresCredentials,
        output: Path,
        category: str,
    ):
        self.vendor_key = vendor_key
        self.example_chart = _load_json(example_chart_path)
        self.credentials = PostgresCredentials.from_dictionary(dict(os.environ))
        self.output = output
        self.category = category

        self.profile_gen = PatientProfileGenerator(vendor_key)
        self.chart_gen = ChartGenerator(vendor_key, self.example_chart)
        self.transcript_gen = TranscriptGenerator(vendor_key)

        self.case_dao = Case(credentials)
        self.synthetic_dao = SyntheticCase(credentials)

    def run(self, batches: int, batch_size: int) -> None:
        print(self.credentials.is_ready())
        print(self.credentials)
        profiles: List[Tuple[str, str]] = self.profile_gen.generate_profiles(batches, batch_size)

        for patient_name, profile_text in profiles:
            chart = self.chart_gen.generate_chart_for_profile(profile_text)
            transcript, spec = self.transcript_gen.generate_transcript_for_profile(profile_text)
            if isinstance(transcript, list):
                transcript = {"Cycle 1": transcript}
            for key in transcript:
                transcript[key] = [Line.load_from_json(line) if isinstance(line, dict) else line for line in transcript[key]]
            name = build_case_name(spec, chart, self.category)
            print(name)

            case_record = CaseRecord(
                name=name,
                transcript=transcript,
                limited_chart=chart,
                profile=profile_text,
                validation_status="GENERATION",
                batch_identifier=self.category,
                tags={},)

            synthetic_record = SyntheticRecord(
                case_id=0,  # updated if inserted into Postgres
                category=self.category,
                turn_total=spec["turn_total"],
                speaker_sequence=spec["speaker_sequence"],
                clinician_to_patient_turn_ratio=spec["ratio"],
                mood=spec["mood"],
                pressure=spec["pressure"],
                clinician_style=spec["clinician_style"],
                patient_style=spec["patient_style"],
                turn_buckets=spec["bucket"],
                duration=spec.get("duration", 0.0),
                text_llm_vendor=HSConstants.VENDOR_OPENAI,
                text_llm_name=HSConstants.OPENAI_CHAT_TEXT_O3,
            )
            
            if self.credentials.is_ready(): 
                saved_case = self.case_dao.upsert(case_record)
                synthetic_record_with_id = synthetic_record._replace(case_id=saved_case.id)
                self.synthetic_dao.upsert(synthetic_record_with_id)
                print(f"Upserted to Postgres successfully: {name}")
            else:
                folder = self.output / patient_name.replace(" ", "_")
                _dump_json(folder / "case_record.json", case_record._asdict())
                _dump_json(folder / "synthetic_case_record.json", synthetic_record._asdict())
                print(f"[•] saved locally: {patient_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic cases with profile, chart, and transcript")
    parser.add_argument("--category", required=True, help="e.g. med_management")
    parser.add_argument("--batches", type=int, required=True)
    parser.add_argument("--batch-size", type=int, required=True)
    parser.add_argument("--example-chart", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("./offline_cases"))
    args = parser.parse_args()

    settings = Settings.from_dictionary(dict(os.environ))
    vendor_key = settings.llm_text
    credentials = PostgresCredentials.from_dictionary(dict(os.environ))

    orchestrator = SyntheticCaseOrchestrator(
        vendor_key=vendor_key,
        credentials=credentials,
        example_chart_path=args.example_chart,
        output=args.output,
        category=args.category,
    )

    orchestrator.run(batches=args.batches, batch_size=args.batch_size)
