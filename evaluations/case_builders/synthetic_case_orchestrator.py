from __future__ import annotations
import argparse
import json
import tempfile
from pathlib import Path
from typing import Tuple, Any

from hyperscribe.libraries.constants import Constants
from evaluations.constants import Constants as EvalConstants

from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.line import Line
from evaluations.structures.enums.case_status import CaseStatus
from evaluations.helper_evaluation import HelperEvaluation

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
        example_chart_path: Path,
    ):
        self.vendor_key = vendor_key
        self.category = category
        self.example_chart = SyntheticChartGenerator.load_json(example_chart_path)
        # profile_generator output_path unused in generate, so set to a temp dir
        self.profile_generator = SyntheticProfileGenerator(
            vendor_key=vendor_key,
            output_path=Path(tempfile.mkdtemp()),
        )

    def generate(
        self,
        number_of_batches: int,
        batch_size: int,
    ) -> list[Tuple[CaseRecord, SyntheticCaseRecord]]:
        """
        Generate synthetic cases in memory and return a list of tuples:
        (CaseRecord, SyntheticCaseRecord).
        """
        # 1) Generate all profiles
        for batch_index in range(1, number_of_batches + 1):
            print(f"[Profile] batch {batch_index}/{number_of_batches}")
            self.profile_generator.generate_batch(batch_index, batch_size)
        all_profiles: dict[str, str] = self.profile_generator.all_profiles

        # 2) Create temporary directories for chart and transcript generation
        temp_directory = Path(tempfile.mkdtemp())
        chart_temp_directory = temp_directory / "charts_tmp"
        transcript_temp_dir = temp_directory / "transcripts_tmp"
        chart_temp_directory.mkdir(parents=True, exist_ok=True)
        transcript_temp_dir.mkdir(parents=True, exist_ok=True)

        # 3) Initialize generators
        chart_generator = SyntheticChartGenerator(
            vendor_key=self.vendor_key,
            profiles=all_profiles,
            output=chart_temp_directory,
            example_chart=self.example_chart,
        )
        # Write profiles.json for transcript generator
        profiles_file = temp_directory / "profiles.json"
        profiles_file.write_text(json.dumps(all_profiles, indent=2))

        transcript_generator = SyntheticTranscriptGenerator(
            vendor_key=self.vendor_key,
            input_path=profiles_file,
            output_path=transcript_temp_dir,
        )

        results: list[Tuple[CaseRecord, SyntheticCaseRecord]] = []

        # 4) Iterate each profile and build records
        for profile_index, (patient_name, profile_text) in enumerate(all_profiles.items(), start=1):
            print(f"\n→ Generating for '{patient_name}' (#{profile_index})")

            limited_chart_data = chart_generator.generate_chart_for_profile(profile_text)
            raw_transcript, specifications = transcript_generator.generate_transcript_for_profile(profile_text)
            normalized: list[dict] = []
            for turn_index, turn_item in enumerate(raw_transcript, start=1):
                parsed_object: Any = turn_item
                while isinstance(parsed_object, str):
                    parsed_object = json.loads(parsed_object)
                if not isinstance(parsed_object, dict):
                    raise TypeError(f"Turn #{turn_index} decoded to {type(parsed_object).__name__}, expected dict")
                normalized.append(parsed_object)

            # d) Convert dicts to Line objects
            line_objects: list[Line] = Line.load_from_json(normalized)

            # e) Group Line objects into cycles of up to 1000 chars, not splitting a turn
            transcript_cycles: dict[str, list[Line]] = {}
            cycle_num = 1
            current_cycle: list[Line] = []
            current_length = 0

            for line_object in line_objects:
                turn_json = line_object.to_json()
                length = len(json.dumps(turn_json))
                if current_cycle and (current_length + length > EvalConstants.MAX_CHARACTERS_PER_CYCLE):
                    key = f"cycle_{cycle_num:03d}"
                    transcript_cycles[key] = current_cycle
                    cycle_num += 1
                    current_cycle = []
                    current_length = 0
                current_cycle.append(line_object)
                current_length += length

            if current_cycle:
                key = f"cycle_{cycle_num:03d}"
                transcript_cycles[key] = current_cycle

            # f) Build CaseRecord (uses Line objects)
            case_record = CaseRecord(
                id=0,
                name=patient_name,
                transcript=transcript_cycles,
                limited_chart=limited_chart_data,
                profile=profile_text,
                validation_status=CaseStatus.GENERATION,
                batch_identifier="",
                tags={},
            )

            # g) Build SyntheticCaseRecord with new signature
            synthetic_record = SyntheticCaseRecord(
                case_id=profile_index,
                category=self.category,
                turn_total=specifications["turn_total"],
                speaker_sequence=specifications["speaker_sequence"],
                clinician_to_patient_turn_ratio=specifications["ratio"],
                mood=specifications["mood"],
                pressure=specifications["pressure"],
                clinician_style=specifications["clinician_style"],
                patient_style=specifications["patient_style"],
                turn_buckets=specifications["bucket"],
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
        example_chart_path: Path,
    ) -> list[SyntheticCaseRecord]:
        credentials = HelperEvaluation.postgres_credentials()
        vendor_key = HelperEvaluation.settings().llm_text

        orchestrator = cls(vendor_key, category, example_chart_path)
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
        example_chart_path: Path,
        output_root: Path,
    ) -> None:
        vendor_key = HelperEvaluation.settings().llm_text
        orchestrator = cls(vendor_key, category, example_chart_path)
        record_pairs = orchestrator.generate(number_of_batches, batch_size)

        for index, (case_record, synthetic_record) in enumerate(record_pairs, start=1):
            patient_dir = output_root / case_record.name.replace(" ", "_")
            patient_dir.mkdir(parents=True, exist_ok=True)

            case_path = patient_dir / f"case_{index}.json"
            synthetic_path = patient_dir / f"synthetic_case_{index}.json"

            # serialize CaseRecord to JSON
            case_data = case_record._asdict()
            case_data["validation_status"] = case_data["validation_status"].value
            case_data["transcript"] = {
                key: [line.to_json() for line in lines] for key, lines in case_record.transcript.items()
            }
            with case_path.open("w") as f:
                json.dump(case_data, f, indent=2)
            print(f"Wrote {case_path}")

            # serialize SyntheticCaseRecord to JSON
            synthetic_data = synthetic_record._asdict()
            synthetic_data["turn_buckets"] = synthetic_data["turn_buckets"].value
            with synthetic_path.open("w") as f:
                json.dump(synthetic_data, f, indent=2)
            print(f"Wrote {synthetic_path}")

    @staticmethod
    def main() -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--batches", type=int, required=True)
        parser.add_argument("--batch-size", type=int, required=True)
        parser.add_argument("--category", type=str, required=True)
        parser.add_argument("--example-chart", type=Path, required=True)
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
                args.example_chart,
            )
            print(f"Inserted {len(saved)} synthetic_case records.")
        else:
            if not args.output_root:
                parser.error("--output-root is required in file mode")
            SyntheticCaseOrchestrator.generate_and_save2file(
                args.batches,
                args.batch_size,
                args.category,
                args.example_chart,
                args.output_root,
            )
            print(f"Wrote files to {args.output_root}")


if __name__ == "__main__":
    SyntheticCaseOrchestrator.main()
