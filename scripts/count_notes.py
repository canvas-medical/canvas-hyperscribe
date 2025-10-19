"""
Command line tool to query S3 and produce a CSV table of note counts by date and customer.

This tool queries the hyperscribe-logs bucket to count notes under customer prefixes
without retrieving the actual objects. It outputs a wide-format CSV table with:
- One row per date (with missing dates filled in)
- One column per customer (customer name as column header)
- Values are note counts, or 0 if no notes on that date

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
    python count_notes.py [<host1> <host2> ...] [--date YYYY-MM-DD] [--start-date YYYY-MM-DD]
                          [--end-date YYYY-MM-DD] [--all-dates] [--all-customers]
"""

import sys
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path to allow imports from evaluations and hyperscribe
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.aws_s3 import AwsS3


class S3NoteCounts:
    @classmethod
    def _construct_logs_s3_prefix(cls, instance_name: str, iso_date: str) -> str:
        """Construct S3 prefix for log files on a specific date."""
        return f"hyperscribe-{instance_name}/finals/{iso_date}/"

    @classmethod
    def _count_notes_for_prefix(cls, s3_client: AwsS3, prefix: str) -> int:
        """
        Count the number of unique notes under a given S3 prefix.

        Notes are identified by the pattern: {patient_key}-{note_id}/
        where patient_key is 32 hex chars. We count unique note_ids.
        """
        all_objects = s3_client.list_s3_objects(prefix)

        # Extract unique note IDs from object keys
        note_ids = set()
        for obj in all_objects:
            # Object keys look like: hyperscribe-{instance}/finals/{date}/{patient_key}-{note_id}/...
            # We need to extract the {note_id} portion
            key_parts = obj.key.split("/")
            if len(key_parts) >= 4:
                # The fourth part should be {patient_key}-{note_id}
                patient_note = key_parts[3]
                if "-" in patient_note:
                    # Extract note_id (everything after the first hyphen)
                    # Pattern: {32-char-hex}-{note_id}
                    # Since we checked '-' is in patient_note, split will always give at least 2 parts
                    parts = patient_note.split("-", 1)  # Split on first hyphen only
                    note_id = parts[1]
                    if note_id:  # Only add if not empty
                        note_ids.add(note_id)

        return len(note_ids)

    @classmethod
    def _discover_all_customers(cls, s3_client: AwsS3) -> list[str]:
        """
        Discover all available customer instances by listing the bucket root.

        Returns a sorted list of customer names (without the hyperscribe- prefix).
        """
        # List all objects in the bucket to find hyperscribe-* prefixes
        all_objects = s3_client.list_s3_objects("")

        # Extract unique customer names
        customers = set()
        for obj in all_objects:
            # Object keys look like: hyperscribe-{customer}/...
            key_parts = obj.key.split("/")
            if len(key_parts) >= 1 and key_parts[0].startswith("hyperscribe-"):
                customer = key_parts[0].replace("hyperscribe-", "")
                if customer:
                    customers.add(customer)

        return sorted(list(customers))

    @classmethod
    def _discover_all_dates(cls, s3_client: AwsS3, instance_name: str) -> list[str]:
        """
        Discover all available dates for a given instance by listing the finals/ directory.

        Returns a sorted list of ISO date strings.
        """
        prefix = f"hyperscribe-{instance_name}/finals/"
        all_objects = s3_client.list_s3_objects(prefix)

        # Extract unique dates from object keys
        dates = set()
        for obj in all_objects:
            # Object keys look like: hyperscribe-{instance}/finals/{date}/{patient_key}-{note_id}/...
            # We need to extract the {date} portion
            key_parts = obj.key.split("/")
            if len(key_parts) >= 3:
                # The third part should be the date
                date_str = key_parts[2]
                # Validate it looks like a date (YYYY-MM-DD format)
                if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
                    dates.add(date_str)

        return sorted(list(dates))

    @classmethod
    def _generate_date_range(
        cls,
        start_date: str | None,
        end_date: str | None,
        single_date: str | None,
        all_dates: bool,
    ) -> list[str] | None:
        """
        Generate a list of ISO date strings based on the provided date parameters.

        If all_dates is True, returns None to signal that dates should be discovered per host.
        If single_date is provided, returns a list with just that date.
        If start_date and/or end_date are provided, generates a range.
        If neither are provided, returns today's date.
        """
        if all_dates:
            return None

        if single_date:
            return [single_date]

        if start_date or end_date:
            # Parse dates or use defaults
            if start_date:
                start = datetime.strptime(start_date, "%Y-%m-%d")
            else:
                start = datetime.now()

            if end_date:
                end = datetime.strptime(end_date, "%Y-%m-%d")
            else:
                end = datetime.now()

            # Generate range
            dates = []
            current = start
            while current <= end:
                dates.append(current.strftime("%Y-%m-%d"))
                current += timedelta(days=1)

            return dates

        # Default to today
        return [datetime.now().strftime("%Y-%m-%d")]

    @classmethod
    def _fill_date_range(cls, min_date: str, max_date: str) -> list[str]:
        """
        Generate a complete list of dates from min_date to max_date inclusive.
        """
        start = datetime.strptime(min_date, "%Y-%m-%d")
        end = datetime.strptime(max_date, "%Y-%m-%d")

        dates = []
        current = start
        while current <= end:
            dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        return dates

    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Query S3 and produce a CSV table of note counts by date and customer")
        parser.add_argument(
            "hosts",
            type=str,
            nargs="*",
            help="Host names (instance names) to query (optional if --all-customers is used)",
        )
        parser.add_argument("--date", type=str, help="Specific date to query in YYYY-MM-DD format (default: today)")
        parser.add_argument("--start-date", type=str, help="Start date for date range query in YYYY-MM-DD format")
        parser.add_argument("--end-date", type=str, help="End date for date range query in YYYY-MM-DD format")
        parser.add_argument("--all-dates", action="store_true", help="Query all available dates in S3 (no date limit)")
        parser.add_argument("--all-customers", action="store_true", help="Query all customer instances found in S3")
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls._parameters()

        # Get S3 credentials
        s3_credentials = HelperEvaluation.aws_s3_credentials()
        s3_client = AwsS3(s3_credentials)

        if not s3_client.is_ready():
            print("Error: AWS S3 credentials not properly configured.", file=sys.stderr)
            print("", file=sys.stderr)
            print("Please set the required environment variables:", file=sys.stderr)
            print("  AwsKey - AWS access key ID", file=sys.stderr)
            print("  AwsSecret - AWS secret access key", file=sys.stderr)
            print("  AwsRegion - AWS region (e.g., 'us-east-1')", file=sys.stderr)
            print("  AwsBucketLogs - S3 bucket name containing log files", file=sys.stderr)
            print("", file=sys.stderr)
            print("Or provide a combined JSON credential:", file=sys.stderr)
            print("  S3CredentialsLogs - JSON string with format:", file=sys.stderr)
            print('    {"key": "...", "secret": "...", "region": "...", "bucket": "..."}', file=sys.stderr)
            sys.exit(1)

        # Determine which hosts to query
        if parameters.all_customers:
            print("Discovering all customers...", file=sys.stderr)
            try:
                hosts = cls._discover_all_customers(s3_client)
                print(f"Found {len(hosts)} customers: {', '.join(hosts)}", file=sys.stderr)
            except Exception as e:
                print(f"Error discovering customers: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            if not parameters.hosts:
                print("Error: You must specify host names or use --all-customers", file=sys.stderr)
                sys.exit(1)
            hosts = parameters.hosts

        # Generate date range or signal to discover dates per host
        dates = cls._generate_date_range(
            parameters.start_date, parameters.end_date, parameters.date, parameters.all_dates
        )

        # Build data structure: {date: {host: count}}
        data: defaultdict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
        all_dates_set: set[str] = set()

        # Query each host
        for host in hosts:
            print(f"Querying {host}...", file=sys.stderr)

            # If --all is specified, discover all dates for this host
            if dates is None:
                try:
                    host_dates = cls._discover_all_dates(s3_client, host)
                    print(f"  Discovered {len(host_dates)} dates", file=sys.stderr)
                except Exception as e:
                    print(f"  Error discovering dates: {e}", file=sys.stderr)
                    continue
            else:
                host_dates = dates

            # Track all dates we've seen
            all_dates_set.update(host_dates)

            # Query each date for this host
            for date in host_dates:
                prefix = cls._construct_logs_s3_prefix(host, date)

                try:
                    note_count = cls._count_notes_for_prefix(s3_client, prefix)
                    data[date][host] = note_count
                except Exception as e:
                    print(f"  Error querying {date}: {e}", file=sys.stderr)
                    data[date][host] = 0

        if not all_dates_set:
            print("No data found.", file=sys.stderr)
            return

        # Fill in missing dates in the range
        min_date = min(all_dates_set)
        max_date = max(all_dates_set)
        complete_dates = cls._fill_date_range(min_date, max_date)

        print(f"\nGenerating CSV for date range {min_date} to {max_date}...", file=sys.stderr)

        # Sort hosts for consistent column order
        hosts = sorted(hosts)

        # Print CSV header
        header = ["date"] + hosts
        print(",".join(header))

        # Print data rows
        for date in complete_dates:
            row = [date]
            for host in hosts:
                count = data[date].get(host, 0)
                row.append(str(count))
            print(",".join(row))


if __name__ == "__main__":
    S3NoteCounts.run()
