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
    def _construct_logs_s3_prefix(cls, instance_name: str, iso_date: str) -> str:
        """Construct S3 prefix for log files."""
        return f"hyperscribe-{instance_name}/finals/{iso_date}/"

    @classmethod
    def _extract_iso_date(cls, transcript_objects: list) -> str | None:
        """Extract ISO date from the first transcript object's last modified date."""
        if not transcript_objects:
            return None
        return transcript_objects[0].last_modified.strftime("%Y-%m-%d")

    @classmethod
    def _retrieve_transcript_objects(cls, s3_client: AwsS3, prefix: str) -> list:
        """Retrieve all transcript objects from S3 under the given prefix."""
        return s3_client.list_s3_objects(prefix)

    @classmethod
    def _retrieve_log_objects(cls, s3_client: AwsS3, prefix: str, note_id: str) -> list:
        """
        Retrieve log objects from S3 under the given prefix, filtered by note_id.

        Filters objects that match the pattern: {32-char-hex}-{note_id}/
        """
        all_objects = s3_client.list_s3_objects(prefix)
        # Filter for objects that contain the note_id in the expected pattern
        # Pattern: {patient_key}-{note_id}/ where patient_key is 32 hex chars
        filtered_objects = []
        for obj in all_objects:
            # Check if the key contains a path segment ending with -{note_id}/
            if f"-{note_id}/" in obj.key:
                filtered_objects.append(obj)
        return filtered_objects

    @classmethod
    def _parse_and_concatenate_transcripts(cls, s3_client: AwsS3, transcript_objects: list, debug: bool = False) -> list[dict]:
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

            if debug:
                content_preview = response.content[:50].decode("utf-8", errors="replace") if response.content else ""
                print(f"DEBUG TRANSCRIPT:")
                print(f"  Object Key: {transcript_obj.key}")
                print(f"  Status Code: {response.status_code}")
                print(f"  Content Preview (first 50 chars): {content_preview}")
                print()

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
    def _parse_and_concatenate_logs(cls, s3_client: AwsS3, log_objects: list, debug: bool = False) -> list[str]:
        """
        Parse log objects (text files) and concatenate into a single list of log lines.

        Each log line is a string from the text files.
        """
        concatenated_logs = []

        for log_obj in log_objects:
            response = s3_client.access_s3_object(log_obj.key)

            if debug:
                content_preview = response.content[:50].decode("utf-8", errors="replace") if response.content else ""
                print(f"DEBUG LOG:")
                print(f"  Object Key: {log_obj.key}")
                print(f"  Status Code: {response.status_code}")
                print(f"  Content Preview (first 50 chars): {content_preview}")
                print()

            if response.status_code != HTTPStatus.OK.value:
                print(f"Warning: Failed to retrieve {log_obj.key}", file=sys.stderr)
                continue

            try:
                # Parse as text, split into lines
                log_text = response.content.decode("utf-8")
                log_lines = log_text.splitlines()

                # Add each non-empty line to the concatenated list
                for line in log_lines:
                    if line.strip():  # Only add non-empty lines
                        concatenated_logs.append(line)

            except UnicodeDecodeError as e:
                print(f"Warning: Failed to decode {log_obj.key}: {e}", file=sys.stderr)
                continue

        return concatenated_logs

    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Retrieve and search log objects from S3 for user feedback analysis")
        parser.add_argument("feedback_id", type=str, help="Unique identifier for the feedback (e.g., '7792e7c9')")
        parser.add_argument("instance_name", type=str, help="Name of the instance to investigate")
        parser.add_argument("note_id", type=str, help="ID of the note associated with the feedback")
        parser.add_argument("feedback_text", type=str, help="Text of the user feedback to search for")
        parser.add_argument("--debug", action="store_true", help="Debug mode: limit to 1 object each, print debug info")
        parser.add_argument("--force", action="store_true", help="Force overwrite of existing files without prompting")
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls._parameters()

        # Check if transcript already exists on disk
        output_dir = Path(f"/tmp/PHI-hyperscribe-feedback/{parameters.feedback_id}")
        output_file = output_dir / "full_transcript.json"

        if output_file.exists():
            if parameters.force:
                print("Force mode: overwriting existing files...")
            elif parameters.debug:
                response = input("This is a debug run and will overwrite the contents, proceed? [Y/n] ")
                if response.lower() not in ["y", ""]:
                    print("Aborting.")
                    return
                print("Proceeding with overwrite...")
            else:
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

        # Limit to 1 object in debug mode
        if parameters.debug and transcript_objects:
            print(f"DEBUG: Limiting to first transcript object only")
            transcript_objects = transcript_objects[:1]

        print(f"Found {len(transcript_objects)} transcript objects")
        print()

        # Parse and concatenate all transcripts
        concatenated_turns = cls._parse_and_concatenate_transcripts(s3_client, transcript_objects, parameters.debug)
        print(f"Total turns: {len(concatenated_turns)}")
        print()

        # Extract ISO date from first transcript for log retrieval
        iso_date = cls._extract_iso_date(transcript_objects)

        # Retrieve and parse logs if we have a date
        concatenated_logs = []
        if iso_date:
            logs_prefix = cls._construct_logs_s3_prefix(parameters.instance_name, iso_date)
            print(f"Retrieving logs from: {logs_prefix}")

            log_objects = cls._retrieve_log_objects(s3_client, logs_prefix, parameters.note_id)

            # Limit to 1 object in debug mode
            if parameters.debug and log_objects:
                print(f"DEBUG: Limiting to first log object only")
                log_objects = log_objects[:1]

            print(f"Found {len(log_objects)} log objects")
            print()

            concatenated_logs = cls._parse_and_concatenate_logs(s3_client, log_objects, parameters.debug)
            print(f"Total log lines: {len(concatenated_logs)}")
            print()
        else:
            print("No transcript objects found, skipping log retrieval")
            print()

        # Save to files
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            json.dump(concatenated_turns, f, indent=2)

        print(f"Successfully saved transcript to: {output_file}")

        # Save logs as text file (one line per log entry)
        logs_file = output_dir / "full_logs.txt"
        with open(logs_file, "w") as f:
            f.write("\n".join(concatenated_logs))

        print(f"Successfully saved logs to: {logs_file}")


if __name__ == "__main__":
    InvestigateFeedback.run()
