"""
Command line tool to retrieve and search log objects from S3 for user feedback analysis.

This tool investigates end-user feedback by retrieving logged sessions from S3,
concatenating them, and searching for relevant information.

Required Environment Variables:
    Either provide individual credentials:
        AwsKey: AWS access key ID for S3 authentication
        AwsSecret: AWS secret access key for S3 authentication
        AwsRegion: AWS region where the S3 bucket is located (e.g., 'us-east-1')
        AwsBucketLogs: S3 bucket name containing the log files

    Or provide a combined JSON credential:
        S3CredentialsLogs: JSON string containing all credentials in format:
            {"key": "...", "secret": "...", "region": "...", "bucket": "..."}

Usage:
    python investigate_feedback.py <feedback_id> <instance_name> <note_id> <feedback_text>
"""

import json
import sys
from argparse import ArgumentParser, Namespace
from http import HTTPStatus
from pathlib import Path

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.aws_s3 import AwsS3


class InvestigateFeedback:
    @classmethod
    def _construct_s3_prefix(cls, instance_name: str, note_id: str) -> str:
        """Construct S3 prefix for transcript files."""
        return f"hyperscribe-{instance_name}/transcripts/{note_id}"

    @classmethod
    def _retrieve_transcript_objects(cls, s3_client: AwsS3, prefix: str) -> list:
        """Retrieve all transcript objects from S3 under the given prefix."""
        return s3_client.list_s3_objects(prefix)

    @classmethod
    def _parse_and_concatenate_transcripts(cls, s3_client: AwsS3, transcript_objects: list) -> list[dict]:
        """
        Parse transcript JSON objects and concatenate into a single list of turns.

        Each turn dictionary will contain:
        - speaker: The speaker identifier
        - text: The text of the turn
        - object_key: The S3 object key of the transcript file
        """
        concatenated_turns = []

        for transcript_obj in transcript_objects:
            response = s3_client.access_s3_object(transcript_obj.key)

            if response.status_code != HTTPStatus.OK.value:
                print(f"Warning: Failed to retrieve {transcript_obj.key}", file=sys.stderr)
                continue

            try:
                turns = json.loads(response.content.decode("utf-8"))

                # Add object_key to each turn
                for turn in turns:
                    turn["object_key"] = transcript_obj.key
                    concatenated_turns.append(turn)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"Warning: Failed to parse {transcript_obj.key}: {e}", file=sys.stderr)
                continue

        return concatenated_turns

    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Retrieve and search log objects from S3 for user feedback analysis")
        parser.add_argument("feedback_id", type=str, help="Unique identifier for the feedback (e.g., '7792e7c9')")
        parser.add_argument("instance_name", type=str, help="Name of the instance to investigate")
        parser.add_argument("note_id", type=str, help="ID of the note associated with the feedback")
        parser.add_argument("feedback_text", type=str, help="Text of the user feedback to search for")
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls._parameters()

        # Check if transcript already exists on disk
        output_dir = Path(f"/tmp/PHI-hyperscribe-feedback/{parameters.feedback_id}")
        output_file = output_dir / "full_transcript.json"

        if output_file.exists():
            print(f"Transcript already exists at: {output_file}")
            print("Skipping S3 retrieval.")
            return

        s3_credentials = HelperEvaluation.aws_s3_credentials()
        s3_client = AwsS3(s3_credentials)

        if not s3_client.is_ready():
            print("Error: AWS S3 credentials not properly configured.", file=sys.stderr)
            print("Please ensure the required environment variables are set.", file=sys.stderr)
            sys.exit(1)

        print(f"Feedback ID: {parameters.feedback_id}")
        print(f"Instance: {parameters.instance_name}")
        print(f"Note ID: {parameters.note_id}")
        print(f"Feedback: {parameters.feedback_text}")
        print(f"S3 Bucket: {s3_client.bucket}")
        print(f"S3 Region: {s3_client.region}")
        print()

        # Construct S3 prefix and retrieve transcript objects
        prefix = cls._construct_s3_prefix(parameters.instance_name, parameters.note_id)
        print(f"Retrieving transcripts from: {prefix}")

        transcript_objects = cls._retrieve_transcript_objects(s3_client, prefix)
        print(f"Found {len(transcript_objects)} transcript objects")
        print()

        # Parse and concatenate all transcripts
        concatenated_turns = cls._parse_and_concatenate_transcripts(s3_client, transcript_objects)
        print(f"Total turns: {len(concatenated_turns)}")
        print()

        # Save to file
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            json.dump(concatenated_turns, f, indent=2)

        print(f"Successfully saved transcript to: {output_file}")


if __name__ == "__main__":
    InvestigateFeedback.run()
