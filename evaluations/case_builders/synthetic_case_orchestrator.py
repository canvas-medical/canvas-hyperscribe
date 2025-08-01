from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Tuple

from hyperscribe.libraries.constants import Constants

from hyperscribe.structures.vendor_key import VendorKey
from evaluations.structures.enums.case_status import CaseStatus
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.patient_profile import PatientProfile

from evaluations.case_builders.synthetic_profile_generator import SyntheticProfileGenerator
from evaluations.case_builders.synthetic_chart_generator import SyntheticChartGenerator
from evaluations.case_builders.synthetic_transcript_generator import SyntheticTranscriptGenerator

from evaluations.structures.records.case import Case as CaseRecord
from evaluations.structures.records.synthetic_case import SyntheticCase as SyntheticCaseRecord

from evaluations.datastores.postgres.case import Case as CaseDatastore
from evaluations.datastores.postgres.synthetic_case import SyntheticCase as SyntheticCaseDatastore


class SyntheticCaseOrchestrator:
    def __init__(
        self,
        vendor_key: VendorKey,
        category: str,
    ):
        self.vendor_key = vendor_key
        self.category = category
        self.profile_generator = SyntheticProfileGenerator(vendor_key=vendor_key)

    def generate(
        self,
        number_of_batches: int,
        batch_size: int,
    ) -> list[Tuple[CaseRecord, SyntheticCaseRecord]]:
        """
        Generate synthetic cases in memory and return a list of tuples:
        (CaseRecord, SyntheticCaseRecord).
        """
        # 1) profiles + generator set-ups
        all_profiles: list[PatientProfile] = []
        for batch_index in range(1, number_of_batches + 1):
            print(f"[Profile] batch {batch_index}/{number_of_batches}")
            batch_profiles = self.profile_generator.generate_batch(batch_index, batch_size)
            all_profiles.extend(batch_profiles)

        chart_generator = SyntheticChartGenerator(
            vendor_key=self.vendor_key,
            profiles=all_profiles,
        )

        transcript_generator = SyntheticTranscriptGenerator(
            vendor_key=self.vendor_key,
            profiles=all_profiles,
        )

        results: list[Tuple[CaseRecord, SyntheticCaseRecord]] = []

        for profile_index, patient_profile in enumerate(all_profiles, start=1):
            print(f"\n Generating for '{patient_profile.name}' (#{profile_index})")

            limited_chart = chart_generator.generate_chart_for_profile(patient_profile)
            transcript_line_objects, specifications = transcript_generator.generate_transcript_for_profile(
                patient_profile
            )

            #
            transcript_cycles = HelperEvaluation.split_lines_into_cycles(transcript_line_objects)

            # case_record and synthetic_record setup with proper fields via profile_index
            # (indices updated at upsert based on name if going to db, otherwise local
            case_record = CaseRecord(
                id=profile_index,
                name=patient_profile.name,
                transcript=transcript_cycles,
                limited_chart=limited_chart.to_json(),
                profile=patient_profile.profile,
                validation_status=CaseStatus.GENERATION,
                batch_identifier="",
                tags={},
            )

            synthetic_record = SyntheticCaseRecord(
                case_id=profile_index,
                category=self.category,
                turn_total=specifications.turn_total,
                speaker_sequence=specifications.speaker_sequence,
                clinician_to_patient_turn_ratio=specifications.ratio,
                mood=specifications.mood,
                pressure=specifications.pressure,
                clinician_style=specifications.clinician_style,
                patient_style=specifications.patient_style,
                turn_buckets=specifications.bucket,
                duration=0.0,
                text_llm_vendor=self.vendor_key.vendor,
                text_llm_name=Constants.OPENAI_CHAT_TEXT_O3,
                id=profile_index,
            )

            results.append((case_record, synthetic_record))

        return results

    @classmethod
    def generate_and_save2database(
        cls,
        number_of_batches: int,
        batch_size: int,
        category: str,
    ) -> list[SyntheticCaseRecord]:
        credentials = HelperEvaluation.postgres_credentials()
        vendor_key = HelperEvaluation.settings().llm_text

        orchestrator = cls(vendor_key, category)
        record_pairs = orchestrator.generate(number_of_batches, batch_size)

        case_store = CaseDatastore(credentials)
        synthetic_case_store = SyntheticCaseDatastore(credentials)
        saved_records: list[SyntheticCaseRecord] = []

        for case_record, synthetic_record in record_pairs:
            upserted_case = case_store.upsert(case_record)
            # create a new SyntheticCaseRecord with the correct case_id
            record_to_upsert = synthetic_record._replace(case_id=upserted_case.id)
            # upsert the synthetic case
            upserted_synthetic = synthetic_case_store.upsert(record_to_upsert)
            saved_records.append(upserted_synthetic)

        return saved_records

    @classmethod
    def generate_and_save2file(
        cls,
        number_of_batches: int,
        batch_size: int,
        category: str,
        output_root: Path,
    ) -> None:
        vendor_key = HelperEvaluation.settings().llm_text
        orchestrator = cls(vendor_key, category)
        record_pairs = orchestrator.generate(number_of_batches, batch_size)

        for index, (case_record, synthetic_record) in enumerate(record_pairs, start=1):
            patient_dir = output_root / case_record.name.replace(" ", "_")
            patient_dir.mkdir(parents=True, exist_ok=True)

            case_path = patient_dir / f"case_{index}.json"
            synthetic_path = patient_dir / f"synthetic_case_{index}.json"

            # json conversions
            case_data = case_record.to_json()
            with case_path.open("w") as f:
                json.dump(case_data, f, indent=2)
            print(f"Wrote {case_path}")

            synthetic_data = synthetic_record.to_json()
            with synthetic_path.open("w") as f:
                json.dump(synthetic_data, f, indent=2)
            print(f"Wrote {synthetic_path}")

    @staticmethod
    def main() -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--batches", type=int, required=True)
        parser.add_argument("--batch-size", type=int, required=True)
        parser.add_argument("--category", type=str, required=True)
        parser.add_argument(
            "--mode",
            choices=["db", "file"],
            required=True,
            help="Choose 'db' to upsert into Postgres or 'file' to write JSON files",
        )
        parser.add_argument(
            "--output-root",
            type=Path,
            help="Required when --mode is 'file'",
        )
        args = parser.parse_args()

        if args.mode == "db":
            saved = SyntheticCaseOrchestrator.generate_and_save2database(
                args.batches,
                args.batch_size,
                args.category,
            )
            print(f"Inserted {len(saved)} synthetic_case records.")
        else:
            if not args.output_root:
                parser.error("--output-root is required in file mode")
            SyntheticCaseOrchestrator.generate_and_save2file(
                args.batches,
                args.batch_size,
                args.category,
                args.output_root,
            )
            print(f"Wrote files to {args.output_root}")


if __name__ == "__main__":
    SyntheticCaseOrchestrator.main()
