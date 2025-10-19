"""
Command line tool to count patients, notes, and chunks in S3 tuning data.

This tool analyzes the hyperscribe-tuning-case-data bucket structure to count:
- Number of unique patients
- Number of notes per patient
- Number of audio chunks (.webm files) per note

Required Environment Variables:
    SuperAwsKey: AWS access key ID for S3 authentication
    SuperAwsSecret: AWS secret access key for S3 authentication

Usage:
    python tuning_case_count.py <prefix>
    python tuning_case_count.py --all-customers

Examples:
    python tuning_case_count.py hyperscribe-production
    python tuning_case_count.py --all-customers
"""

from argparse import ArgumentParser, Namespace
from os import environ
from pathlib import Path
import sys
from typing import Dict, Set

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials


class TuningCaseCount:
    """Utility for counting tuning case data in S3."""

    @classmethod
    def _count_tuning_data(cls, s3_client: AwsS3, prefix: str) -> tuple[Dict[str, Set[str]], Dict[str, int]]:
        """
        Count patients, notes, and chunks under the given S3 prefix.

        Args:
            s3_client: Configured AWS S3 client
            prefix: S3 prefix to analyze

        Returns:
            Tuple of (patients_dict, notes_dict) where:
            - patients_dict maps patient_id to set of note_ids
            - notes_dict maps note_id to chunk count
        """
        patients: Dict[str, Set[str]] = {}  # patient_id -> set of note_ids
        notes: Dict[str, int] = {}  # note_id -> chunk count

        objects = s3_client.list_s3_objects(prefix)
        print(f"Found {len(objects)} S3 objects under prefix: {prefix}", file=sys.stderr)

        for item in objects:
            key_parts = item.key.split("/")
            if len(key_parts) < 3:
                continue

            # Only process patient_*/note_* structure
            if not (key_parts[1].startswith("patient_") and key_parts[2].startswith("note_")):
                continue

            patient_id = key_parts[1]
            note_id = key_parts[2]

            # Initialize note if not seen
            if note_id not in notes:
                notes[note_id] = 0

            # Count .webm chunks
            if key_parts[-1].endswith(".webm"):
                notes[note_id] += 1

            # Track patient -> notes relationship
            if patient_id not in patients:
                patients[patient_id] = set()
            patients[patient_id].add(note_id)

        return patients, notes

    @classmethod
    def _calculate_summary(cls, patients: Dict[str, Set[str]], notes: Dict[str, int]) -> tuple[int, int, int]:
        """
        Calculate summary statistics.

        Args:
            patients: Dictionary mapping patient IDs to sets of note IDs
            notes: Dictionary mapping note IDs to chunk counts

        Returns:
            Tuple of (patient_count, note_count, chunk_count)
        """
        patient_count = len(patients)
        note_count = sum(len(note_set) for note_set in patients.values())
        chunk_count = sum(notes.values())
        return patient_count, note_count, chunk_count

    @classmethod
    def _discover_all_customers(cls, s3_client: AwsS3) -> list[str]:
        """
        Discover all customer prefixes in the tuning bucket.

        Returns:
            Sorted list of customer prefixes (e.g., ['hyperscribe-production', 'hyperscribe-staging'])
        """
        all_objects = s3_client.list_s3_objects("")

        # Extract unique prefixes that start with "hyperscribe-"
        prefixes = set()
        for obj in all_objects:
            key_parts = obj.key.split("/")
            if len(key_parts) >= 1 and key_parts[0].startswith("hyperscribe-"):
                prefixes.add(key_parts[0])

        return sorted(list(prefixes))

    @classmethod
    def _parameters(cls) -> Namespace:
        """Parse command-line arguments."""
        parser = ArgumentParser(description="Count patients, notes, and chunks in S3 tuning data")
        parser.add_argument(
            "prefix",
            type=str,
            nargs="?",
            help="S3 prefix to analyze (e.g., 'hyperscribe-production'). Optional if --all-customers is used.",
        )
        parser.add_argument(
            "--all-customers", action="store_true", help="Analyze all customer prefixes found in the bucket"
        )
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        """Main entry point for the script."""
        parameters = cls._parameters()

        # Get credentials
        try:
            credentials = AwsS3Credentials(
                aws_key=environ["SuperAwsKey"],
                aws_secret=environ["SuperAwsSecret"],
                region="us-west-2",
                bucket="hyperscribe-tuning-case-data",
            )
        except KeyError as e:
            print(f"Error: Missing environment variable {e}", file=sys.stderr)
            print("Required: SuperAwsKey, SuperAwsSecret", file=sys.stderr)
            sys.exit(1)

        s3_client = AwsS3(credentials)

        if not s3_client.is_ready():
            print("Error: AWS S3 client not properly configured.", file=sys.stderr)
            sys.exit(1)

        # Determine which prefixes to analyze
        if parameters.all_customers:
            print("Discovering all customer prefixes...", file=sys.stderr)
            try:
                prefixes = cls._discover_all_customers(s3_client)
                print(f"Found {len(prefixes)} customer prefixes: {', '.join(prefixes)}\n", file=sys.stderr)
            except Exception as e:
                print(f"Error discovering customer prefixes: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            if not parameters.prefix:
                print("Error: You must specify a prefix or use --all-customers", file=sys.stderr)
                sys.exit(1)
            prefixes = [parameters.prefix]

        # Build data structure: list of (customer, patients, notes, chunks)
        results = []

        # Process each prefix
        for prefix in prefixes:
            print(f"Analyzing {prefix}...", file=sys.stderr)

            try:
                patients, notes = cls._count_tuning_data(s3_client, prefix)
                patient_count, note_count, chunk_count = cls._calculate_summary(patients, notes)

                # Extract customer name from prefix (remove 'hyperscribe-' prefix)
                customer = prefix.replace("hyperscribe-", "") if prefix.startswith("hyperscribe-") else prefix

                results.append((customer, patient_count, note_count, chunk_count))
            except Exception as e:
                print(f"  Error processing {prefix}: {e}", file=sys.stderr)
                continue

        # Sort by notes descending
        results.sort(key=lambda x: x[2], reverse=True)

        # Print CSV header
        print("customer,patients,notes,chunks")

        # Print data rows
        for customer, patient_count, note_count, chunk_count in results:
            print(f"{customer},{patient_count},{note_count},{chunk_count}")


if __name__ == "__main__":
    TuningCaseCount.run()
