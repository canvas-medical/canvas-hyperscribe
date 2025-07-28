#!/usr/bin/env python3
"""
Script to load synthetic cases from Patient directories into the database.
Creates records in both the 'case' and 'synthetic_case' tables.
"""

import json
import glob
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from evaluations.datastores.postgres.case import Case as CaseDatastore
from evaluations.datastores.postgres.synthetic_case import SyntheticCase as SyntheticCaseDatastore
from evaluations.structures.records.case import Case as CaseRecord
from evaluations.structures.records.synthetic_case import SyntheticCase as SyntheticCaseRecord
from evaluations.structures.enums.case_status import CaseStatus
from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood
from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure
from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle
from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.constants import Constants
from hyperscribe.structures.line import Line


class SyntheticCaseLoader:
    @classmethod
    def load_json_file(cls, file_path: Path) -> Any:
        """Load and return JSON data from a file."""
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def process_patient_directory(
        cls,
        patient_dir: str,
        case_ds: CaseDatastore,
        synthetic_case_ds: SyntheticCaseDatastore,
        batch_identifier: str,
    ) -> bool:
        """Process a single Patient directory and create database records."""
        patient_name = Path(patient_dir).name
        print(f"Processing {patient_name}...")

        # Check for required files
        required_files = ["transcript.json", "limited_chart.json", "profile.json", "spec.json"]
        for required_file in required_files:
            file_path = Path(patient_dir) / required_file
            if not file_path.exists():
                print(f"  ERROR: Missing {required_file} in {patient_name}")
                return False

        try:
            # Load JSON files
            transcript_data = cls.load_json_file(Path(patient_dir) / "transcript.json")
            limited_chart_data = cls.load_json_file(Path(patient_dir) / "limited_chart.json")
            profile_data = cls.load_json_file(Path(patient_dir) / "profile.json")
            spec_data = cls.load_json_file(Path(patient_dir) / "spec.json")

            # Extract profile text from JSON object
            assert isinstance(profile_data, dict), "profile_data should be a dict"
            profile_text = next(iter(profile_data.values()))  # Get the first (and only) value

            # Create case record
            assert isinstance(transcript_data, list), "transcript_data should be a list"
            assert isinstance(limited_chart_data, dict), "limited_chart_data should be a dict"
            case_record = CaseRecord(
                name=patient_name,
                transcript={f"{Constants.CASE_CYCLE_SUFFIX}_001": Line.load_from_json(transcript_data)},
                limited_chart=limited_chart_data,
                profile=profile_text,
                validation_status=CaseStatus.GENERATION,
                batch_identifier=batch_identifier,
                tags={},
            )

            # Insert case record
            created_case = case_ds.upsert(case_record)
            print(f"  Created case record with ID: {created_case.id}")

            # Convert mood values to enum list
            assert isinstance(spec_data, dict), "spec_data should be a dict"
            mood_enums = []
            for mood_value in spec_data["mood"]:
                mood_enums.append(SyntheticCaseMood(mood_value))

            # Create synthetic case record
            synthetic_case_record = SyntheticCaseRecord(
                case_id=created_case.id,
                category="test",
                turn_total=spec_data["turn_total"],
                speaker_sequence=spec_data["speaker_sequence"],
                clinician_to_patient_turn_ratio=spec_data["ratio"],
                mood=mood_enums,
                pressure=SyntheticCasePressure(spec_data["pressure"]),
                clinician_style=SyntheticCaseClinicianStyle(spec_data["clinician_style"]),
                patient_style=SyntheticCasePatientStyle(spec_data["patient_style"]),
                turn_buckets=SyntheticCaseTurnBuckets(spec_data["bucket"]),
                duration=0.0,  # Not specified in spec.json
                text_llm_vendor="OpenAI",
                text_llm_name="o3",
            )

            # Insert synthetic case record
            created_synthetic_case = synthetic_case_ds.upsert(synthetic_case_record)
            print(f"  Created synthetic case record with ID: {created_synthetic_case.id}")
            return True

        except Exception as e:
            print(f"  ERROR processing {patient_name}: {str(e)}")
            return False

    @classmethod
    def run(cls) -> None:
        """Main execution method."""
        # Get database credentials from environment
        credentials = HelperEvaluation.postgres_credentials()

        if not credentials.is_ready():
            print("ERROR: Database credentials not properly configured.")
            return

        # Initialize datastores
        case_ds = CaseDatastore(credentials)
        synthetic_case_ds = SyntheticCaseDatastore(credentials)

        # Generate batch identifier from current datetime
        batch_identifier = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M")

        # Find all Patient directories
        pattern = "evaluations/cases/synthetic_unit_cases/med_management/Patient_*"
        patient_dirs = glob.glob(pattern)

        if not patient_dirs:
            print(f"No Patient directories found matching pattern: {pattern}")
            return

        print(f"Found {len(patient_dirs)} Patient directories to process")
        print(f"Using batch identifier: {batch_identifier}")

        # Process each directory
        success_count = 0
        for patient_dir in sorted(patient_dirs):
            if Path(patient_dir).is_dir():
                if cls.process_patient_directory(patient_dir, case_ds, synthetic_case_ds, batch_identifier):
                    success_count += 1

        print(f"Successfully processed {success_count}/{len(patient_dirs)} directories")


if __name__ == "__main__":
    SyntheticCaseLoader.run()
