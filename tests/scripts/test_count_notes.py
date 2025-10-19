"""Tests for the count_notes.py script."""

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.count_notes import S3NoteCounts


class MockS3Object:
    """Mock S3 object for testing."""

    def __init__(self, key: str):
        self.key = key


class TestS3NoteCounts:
    """Test suite for S3NoteCounts class."""

    def test_construct_logs_s3_prefix(self):
        """Test S3 prefix construction for log files."""
        result = S3NoteCounts._construct_logs_s3_prefix("production", "2025-10-15")
        assert result == "hyperscribe-production/finals/2025-10-15/"

    def test_count_notes_for_prefix(self):
        """Test counting notes from S3 objects."""
        mock_s3_client = MagicMock()

        # Create mock S3 objects with different note IDs
        mock_objects = [
            MockS3Object("hyperscribe-prod/finals/2025-10-15/abc123def456789012345678901234567-note1/log.txt"),
            MockS3Object("hyperscribe-prod/finals/2025-10-15/abc123def456789012345678901234567-note1/log2.txt"),
            MockS3Object("hyperscribe-prod/finals/2025-10-15/def456abc789012345678901234567890-note2/log.txt"),
            MockS3Object("hyperscribe-prod/finals/2025-10-15/ghi789abc012345678901234567890123-note3/log.txt"),
        ]
        mock_s3_client.list_s3_objects.return_value = mock_objects

        result = S3NoteCounts._count_notes_for_prefix(mock_s3_client, "hyperscribe-prod/finals/2025-10-15/")

        assert result == 3
        assert mock_s3_client.list_s3_objects.call_count == 1
        assert mock_s3_client.list_s3_objects.call_args == call("hyperscribe-prod/finals/2025-10-15/")

    def test_count_notes_for_prefix_empty(self):
        """Test counting notes with no objects."""
        mock_s3_client = MagicMock()
        mock_s3_client.list_s3_objects.return_value = []

        result = S3NoteCounts._count_notes_for_prefix(mock_s3_client, "hyperscribe-prod/finals/2025-10-15/")

        assert result == 0
        assert mock_s3_client.list_s3_objects.call_count == 1

    def test_count_notes_for_prefix_with_hyphens_in_note_id(self):
        """Test counting notes where note IDs contain hyphens."""
        mock_s3_client = MagicMock()

        mock_objects = [
            MockS3Object(
                "hyperscribe-prod/finals/2025-10-15/abc123def456789012345678901234567-note-with-hyphens/log.txt"
            ),
            MockS3Object(
                "hyperscribe-prod/finals/2025-10-15/abc123def456789012345678901234567-note-with-hyphens/log2.txt"
            ),
            MockS3Object(
                "hyperscribe-prod/finals/2025-10-15/def456abc789012345678901234567890-another-note-id/log.txt"
            ),
        ]
        mock_s3_client.list_s3_objects.return_value = mock_objects

        result = S3NoteCounts._count_notes_for_prefix(mock_s3_client, "hyperscribe-prod/finals/2025-10-15/")

        assert result == 2
        assert mock_s3_client.list_s3_objects.call_count == 1

    def test_count_notes_for_prefix_with_edge_cases(self):
        """Test counting notes with various edge case object keys."""
        mock_s3_client = MagicMock()

        mock_objects = [
            # Valid note
            MockS3Object("hyperscribe-prod/finals/2025-10-15/abc123def456789012345678901234567-note1/log.txt"),
            # Key with fewer than 4 parts - should be ignored
            MockS3Object("hyperscribe-prod/finals/2025-10-15"),
            # Patient note without hyphen - should be ignored (len(parts) < 2 after split)
            MockS3Object("hyperscribe-prod/finals/2025-10-15/nohyphenhere/log.txt"),
            # Patient note with exactly one hyphen at end - should be ignored  (len(parts) == 2 but empty note_id)
            MockS3Object("hyperscribe-prod/finals/2025-10-15/abc123def456789012345678901234567-/log.txt"),
            # Another valid note
            MockS3Object("hyperscribe-prod/finals/2025-10-15/def456abc789012345678901234567890-note2/log.txt"),
        ]
        mock_s3_client.list_s3_objects.return_value = mock_objects

        result = S3NoteCounts._count_notes_for_prefix(mock_s3_client, "hyperscribe-prod/finals/2025-10-15/")

        # Should only count the 2 valid notes
        assert result == 2
        assert mock_s3_client.list_s3_objects.call_count == 1

    def test_discover_all_customers(self):
        """Test discovering all customer instances from S3."""
        mock_s3_client = MagicMock()

        mock_objects = [
            MockS3Object("hyperscribe-production/finals/2025-10-15/file.txt"),
            MockS3Object("hyperscribe-staging/finals/2025-10-14/file.txt"),
            MockS3Object("hyperscribe-production/finals/2025-10-16/file.txt"),
            MockS3Object("hyperscribe-demo/audits/file.txt"),
            MockS3Object("other-bucket/file.txt"),  # Should be ignored
        ]
        mock_s3_client.list_s3_objects.return_value = mock_objects

        result = S3NoteCounts._discover_all_customers(mock_s3_client)

        assert result == ["demo", "production", "staging"]
        assert mock_s3_client.list_s3_objects.call_count == 1
        assert mock_s3_client.list_s3_objects.call_args == call("")

    def test_discover_all_customers_empty(self):
        """Test discovering customers with no objects."""
        mock_s3_client = MagicMock()
        mock_s3_client.list_s3_objects.return_value = []

        result = S3NoteCounts._discover_all_customers(mock_s3_client)

        assert result == []
        assert mock_s3_client.list_s3_objects.call_count == 1

    def test_discover_all_customers_with_edge_cases(self):
        """Test discovering customers with various edge case object keys."""
        mock_s3_client = MagicMock()

        mock_objects = [
            # Valid customer
            MockS3Object("hyperscribe-production/finals/2025-10-15/file.txt"),
            # Doesn't start with hyperscribe- - should be ignored
            MockS3Object("other-bucket/file.txt"),
            # Empty customer name after replacing prefix - should be ignored
            MockS3Object("hyperscribe-/file.txt"),
            # Another valid customer
            MockS3Object("hyperscribe-staging/audits/file.txt"),
        ]
        mock_s3_client.list_s3_objects.return_value = mock_objects

        result = S3NoteCounts._discover_all_customers(mock_s3_client)

        # Should only include production and staging
        assert result == ["production", "staging"]
        assert mock_s3_client.list_s3_objects.call_count == 1

    def test_discover_all_dates(self):
        """Test discovering all dates for a given instance."""
        mock_s3_client = MagicMock()

        mock_objects = [
            MockS3Object("hyperscribe-production/finals/2025-10-15/abc123-note1/log.txt"),
            MockS3Object("hyperscribe-production/finals/2025-10-14/def456-note2/log.txt"),
            MockS3Object("hyperscribe-production/finals/2025-10-15/ghi789-note3/log.txt"),
            MockS3Object("hyperscribe-production/finals/2025-10-16/jkl012-note4/log.txt"),
            MockS3Object("hyperscribe-production/finals/invalid-date/file.txt"),  # Should be ignored
        ]
        mock_s3_client.list_s3_objects.return_value = mock_objects

        result = S3NoteCounts._discover_all_dates(mock_s3_client, "production")

        assert result == ["2025-10-14", "2025-10-15", "2025-10-16"]
        assert mock_s3_client.list_s3_objects.call_count == 1
        assert mock_s3_client.list_s3_objects.call_args == call("hyperscribe-production/finals/")

    def test_discover_all_dates_empty(self):
        """Test discovering dates with no objects."""
        mock_s3_client = MagicMock()
        mock_s3_client.list_s3_objects.return_value = []

        result = S3NoteCounts._discover_all_dates(mock_s3_client, "production")

        assert result == []
        assert mock_s3_client.list_s3_objects.call_count == 1

    def test_discover_all_dates_with_invalid_dates(self):
        """Test discovering dates with invalid date formats."""
        mock_s3_client = MagicMock()

        mock_objects = [
            # Valid date
            MockS3Object("hyperscribe-production/finals/2025-10-15/abc123-note1/log.txt"),
            # Key with fewer than 3 parts - should be ignored
            MockS3Object("hyperscribe-production/finals"),
            # Invalid date format (too short) - should be ignored
            MockS3Object("hyperscribe-production/finals/2025-10/file.txt"),
            # Invalid date format (no hyphens in right places) - should be ignored
            MockS3Object("hyperscribe-production/finals/20251015xx/file.txt"),
            # Another valid date
            MockS3Object("hyperscribe-production/finals/2025-10-16/def456-note2/log.txt"),
        ]
        mock_s3_client.list_s3_objects.return_value = mock_objects

        result = S3NoteCounts._discover_all_dates(mock_s3_client, "production")

        # Should only include the 2 valid dates
        assert result == ["2025-10-15", "2025-10-16"]
        assert mock_s3_client.list_s3_objects.call_count == 1

    def test_generate_date_range_all_dates(self):
        """Test date range generation with all_dates flag."""
        result = S3NoteCounts._generate_date_range(None, None, None, True)
        assert result is None

    def test_generate_date_range_single_date(self):
        """Test date range generation with a single date."""
        result = S3NoteCounts._generate_date_range(None, None, "2025-10-15", False)
        assert result == ["2025-10-15"]

    def test_generate_date_range_start_and_end(self):
        """Test date range generation with start and end dates."""
        result = S3NoteCounts._generate_date_range("2025-10-15", "2025-10-17", None, False)
        assert result == ["2025-10-15", "2025-10-16", "2025-10-17"]

    def test_generate_date_range_start_only(self):
        """Test date range generation with only start date."""
        with patch("scripts.count_notes.datetime") as mock_datetime:
            mock_datetime.strptime.side_effect = lambda d, f: __import__("datetime").datetime.strptime(d, f)
            mock_datetime.now.return_value = __import__("datetime").datetime(2025, 10, 17)

            result = S3NoteCounts._generate_date_range("2025-10-15", None, None, False)

            assert result == ["2025-10-15", "2025-10-16", "2025-10-17"]

    def test_generate_date_range_end_only(self):
        """Test date range generation with only end date."""
        with patch("scripts.count_notes.datetime") as mock_datetime:
            mock_datetime.strptime.side_effect = lambda d, f: __import__("datetime").datetime.strptime(d, f)
            mock_datetime.now.return_value = __import__("datetime").datetime(2025, 10, 15)

            result = S3NoteCounts._generate_date_range(None, "2025-10-17", None, False)

            assert result == ["2025-10-15", "2025-10-16", "2025-10-17"]

    def test_generate_date_range_default_today(self):
        """Test date range generation defaults to today."""
        with patch("scripts.count_notes.datetime") as mock_datetime:
            mock_datetime.now.return_value = __import__("datetime").datetime(2025, 10, 15)

            result = S3NoteCounts._generate_date_range(None, None, None, False)

            assert result == ["2025-10-15"]
            assert mock_datetime.now.call_count == 1  # Called once in the method

    def test_fill_date_range(self):
        """Test filling in missing dates in a range."""
        result = S3NoteCounts._fill_date_range("2025-10-15", "2025-10-18")
        assert result == ["2025-10-15", "2025-10-16", "2025-10-17", "2025-10-18"]

    def test_fill_date_range_single_day(self):
        """Test filling date range for a single day."""
        result = S3NoteCounts._fill_date_range("2025-10-15", "2025-10-15")
        assert result == ["2025-10-15"]

    @patch("sys.argv", ["count_notes.py", "production", "staging"])
    def test_parameters_basic(self):
        """Test parameter parsing with basic arguments."""
        params = S3NoteCounts._parameters()

        assert params.hosts == ["production", "staging"]
        assert params.date is None
        assert params.start_date is None
        assert params.end_date is None
        assert params.all_dates is False
        assert params.all_customers is False

    @patch("sys.argv", ["count_notes.py", "production", "--date", "2025-10-15"])
    def test_parameters_with_date(self):
        """Test parameter parsing with date argument."""
        params = S3NoteCounts._parameters()

        assert params.hosts == ["production"]
        assert params.date == "2025-10-15"
        assert params.start_date is None
        assert params.end_date is None

    @patch("sys.argv", ["count_notes.py", "prod1", "prod2", "--start-date", "2025-10-15", "--end-date", "2025-10-17"])
    def test_parameters_with_date_range(self):
        """Test parameter parsing with date range."""
        params = S3NoteCounts._parameters()

        assert params.hosts == ["prod1", "prod2"]
        assert params.start_date == "2025-10-15"
        assert params.end_date == "2025-10-17"

    @patch("sys.argv", ["count_notes.py", "production", "--all-dates"])
    def test_parameters_with_all_dates(self):
        """Test parameter parsing with all-dates flag."""
        params = S3NoteCounts._parameters()

        assert params.hosts == ["production"]
        assert params.all_dates is True

    @patch("sys.argv", ["count_notes.py", "--all-customers"])
    def test_parameters_with_all_customers(self):
        """Test parameter parsing with all-customers flag."""
        params = S3NoteCounts._parameters()

        assert params.hosts == []
        assert params.all_customers is True

    @patch("sys.argv", ["count_notes.py", "--all-customers", "--all-dates"])
    def test_parameters_with_all_flags(self):
        """Test parameter parsing with both all flags."""
        params = S3NoteCounts._parameters()

        assert params.hosts == []
        assert params.all_customers is True
        assert params.all_dates is True

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch("scripts.count_notes.HelperEvaluation.aws_s3_credentials")
    @patch("scripts.count_notes.AwsS3")
    def test_run_with_specific_hosts_and_dates(self, mock_aws_s3, mock_credentials, mock_stderr, mock_stdout):
        """Test full run with specific hosts and dates."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        # Mock S3 responses
        mock_s3_client.list_s3_objects.side_effect = [
            # production, 2025-10-15
            [MockS3Object("hyperscribe-production/finals/2025-10-15/abc123def456789012345678901234567-note1/log.txt")],
            # staging, 2025-10-15
            [
                MockS3Object("hyperscribe-staging/finals/2025-10-15/def456abc789012345678901234567890-note2/log.txt"),
                MockS3Object("hyperscribe-staging/finals/2025-10-15/ghi789abc012345678901234567890123-note3/log.txt"),
            ],
        ]

        with patch("sys.argv", ["count_notes.py", "production", "staging", "--date", "2025-10-15"]):
            S3NoteCounts.run()

        # Verify output
        output = mock_stdout.getvalue()
        lines = output.strip().split("\n")

        assert lines[0] == "date,production,staging"
        assert lines[1] == "2025-10-15,1,2"

        # Verify mock calls
        assert mock_s3_client.list_s3_objects.call_count == 2
        assert mock_s3_client.list_s3_objects.call_args_list == [
            call("hyperscribe-production/finals/2025-10-15/"),
            call("hyperscribe-staging/finals/2025-10-15/"),
        ]

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch("scripts.count_notes.HelperEvaluation.aws_s3_credentials")
    @patch("scripts.count_notes.AwsS3")
    def test_run_with_date_range_and_filling(self, mock_aws_s3, mock_credentials, mock_stderr, mock_stdout):
        """Test run with date range that requires filling missing dates."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        # Mock S3 responses - only data for 2025-10-15, nothing for 2025-10-16, 2025-10-17
        mock_s3_client.list_s3_objects.side_effect = [
            # production, 2025-10-15
            [MockS3Object("hyperscribe-production/finals/2025-10-15/abc123def456789012345678901234567-note1/log.txt")],
            # production, 2025-10-16
            [],
            # production, 2025-10-17
            [MockS3Object("hyperscribe-production/finals/2025-10-17/def456abc789012345678901234567890-note2/log.txt")],
        ]

        with patch(
            "sys.argv", ["count_notes.py", "production", "--start-date", "2025-10-15", "--end-date", "2025-10-17"]
        ):
            S3NoteCounts.run()

        # Verify output includes all dates with zeros for missing data
        output = mock_stdout.getvalue()
        lines = output.strip().split("\n")

        assert lines[0] == "date,production"
        assert lines[1] == "2025-10-15,1"
        assert lines[2] == "2025-10-16,0"
        assert lines[3] == "2025-10-17,1"

        # Verify all dates were queried
        assert mock_s3_client.list_s3_objects.call_count == 3

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch("scripts.count_notes.HelperEvaluation.aws_s3_credentials")
    @patch("scripts.count_notes.AwsS3")
    def test_run_with_all_customers(self, mock_aws_s3, mock_credentials, mock_stderr, mock_stdout):
        """Test run with --all-customers flag."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        # Mock S3 responses
        mock_s3_client.list_s3_objects.side_effect = [
            # Discover customers
            [
                MockS3Object("hyperscribe-prod1/finals/2025-10-15/file.txt"),
                MockS3Object("hyperscribe-prod2/finals/2025-10-15/file.txt"),
            ],
            # prod1, 2025-10-15
            [MockS3Object("hyperscribe-prod1/finals/2025-10-15/abc123def456789012345678901234567-note1/log.txt")],
            # prod2, 2025-10-15
            [MockS3Object("hyperscribe-prod2/finals/2025-10-15/def456abc789012345678901234567890-note2/log.txt")],
        ]

        with patch("sys.argv", ["count_notes.py", "--all-customers", "--date", "2025-10-15"]):
            S3NoteCounts.run()

        # Verify output
        output = mock_stdout.getvalue()
        lines = output.strip().split("\n")

        assert lines[0] == "date,prod1,prod2"
        assert lines[1] == "2025-10-15,1,1"

        # Verify mock calls
        assert mock_s3_client.list_s3_objects.call_count == 3
        assert mock_s3_client.list_s3_objects.call_args_list[0] == call("")  # Discover customers

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch("scripts.count_notes.HelperEvaluation.aws_s3_credentials")
    @patch("scripts.count_notes.AwsS3")
    def test_run_with_all_dates(self, mock_aws_s3, mock_credentials, mock_stderr, mock_stdout):
        """Test run with --all-dates flag."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        # Mock S3 responses
        mock_s3_client.list_s3_objects.side_effect = [
            # Discover dates for production
            [
                MockS3Object(
                    "hyperscribe-production/finals/2025-10-15/abc123def456789012345678901234567-note1/log.txt"
                ),
                MockS3Object(
                    "hyperscribe-production/finals/2025-10-16/def456abc789012345678901234567890-note2/log.txt"
                ),
            ],
            # production, 2025-10-15
            [MockS3Object("hyperscribe-production/finals/2025-10-15/abc123def456789012345678901234567-note1/log.txt")],
            # production, 2025-10-16
            [
                MockS3Object(
                    "hyperscribe-production/finals/2025-10-16/def456abc789012345678901234567890-note2/log.txt"
                ),
                MockS3Object(
                    "hyperscribe-production/finals/2025-10-16/ghi789abc012345678901234567890123-note3/log.txt"
                ),
            ],
        ]

        with patch("sys.argv", ["count_notes.py", "production", "--all-dates"]):
            S3NoteCounts.run()

        # Verify output
        output = mock_stdout.getvalue()
        lines = output.strip().split("\n")

        assert lines[0] == "date,production"
        assert lines[1] == "2025-10-15,1"
        assert lines[2] == "2025-10-16,2"

        # Verify mock calls
        assert mock_s3_client.list_s3_objects.call_count == 3

    @patch("sys.stderr", new_callable=StringIO)
    @patch("scripts.count_notes.HelperEvaluation.aws_s3_credentials")
    @patch("scripts.count_notes.AwsS3")
    def test_run_with_no_credentials(self, mock_aws_s3, mock_credentials, mock_stderr):
        """Test run exits when S3 credentials are not configured."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = False

        with patch("sys.argv", ["count_notes.py", "production"]):
            with pytest.raises(SystemExit) as exc_info:
                S3NoteCounts.run()

            assert exc_info.value.code == 1

        # Verify error message
        stderr = mock_stderr.getvalue()
        assert "Error: AWS S3 credentials not properly configured" in stderr
        assert "AwsKey" in stderr
        assert "AwsSecret" in stderr
        assert "AwsRegion" in stderr
        assert "AwsBucketLogs" in stderr

    @patch("sys.stderr", new_callable=StringIO)
    @patch("scripts.count_notes.HelperEvaluation.aws_s3_credentials")
    @patch("scripts.count_notes.AwsS3")
    def test_run_with_no_hosts_and_no_all_customers(self, mock_aws_s3, mock_credentials, mock_stderr):
        """Test run exits when no hosts specified and --all-customers not used."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        with patch("sys.argv", ["count_notes.py"]):
            with pytest.raises(SystemExit) as exc_info:
                S3NoteCounts.run()

            assert exc_info.value.code == 1

        # Verify error message
        stderr = mock_stderr.getvalue()
        assert "You must specify host names or use --all-customers" in stderr

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch("scripts.count_notes.HelperEvaluation.aws_s3_credentials")
    @patch("scripts.count_notes.AwsS3")
    def test_run_with_error_querying_date(self, mock_aws_s3, mock_credentials, mock_stderr, mock_stdout):
        """Test run handles errors when querying specific dates."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        # Mock S3 responses - first call succeeds, second raises exception
        mock_s3_client.list_s3_objects.side_effect = [
            [MockS3Object("hyperscribe-production/finals/2025-10-15/abc123def456789012345678901234567-note1/log.txt")],
            Exception("Network error"),
        ]

        with patch(
            "sys.argv",
            ["count_notes.py", "production", "--start-date", "2025-10-15", "--end-date", "2025-10-16"],
        ):
            S3NoteCounts.run()

        # Verify output includes the successful query and 0 for the errored one
        output = mock_stdout.getvalue()
        lines = output.strip().split("\n")

        assert lines[0] == "date,production"
        assert lines[1] == "2025-10-15,1"
        assert lines[2] == "2025-10-16,0"

        # Verify error was logged to stderr
        stderr = mock_stderr.getvalue()
        assert "Error querying 2025-10-16: Network error" in stderr

    @patch("sys.stderr", new_callable=StringIO)
    @patch("scripts.count_notes.HelperEvaluation.aws_s3_credentials")
    @patch("scripts.count_notes.AwsS3")
    def test_run_with_error_discovering_customers(self, mock_aws_s3, mock_credentials, mock_stderr):
        """Test run exits when error occurs discovering customers."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        # Mock S3 to raise exception when discovering customers
        mock_s3_client.list_s3_objects.side_effect = Exception("S3 access denied")

        with patch("sys.argv", ["count_notes.py", "--all-customers", "--date", "2025-10-15"]):
            with pytest.raises(SystemExit) as exc_info:
                S3NoteCounts.run()

            assert exc_info.value.code == 1

        # Verify error message
        stderr = mock_stderr.getvalue()
        assert "Error discovering customers: S3 access denied" in stderr

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch("scripts.count_notes.HelperEvaluation.aws_s3_credentials")
    @patch("scripts.count_notes.AwsS3")
    def test_run_with_error_discovering_dates(self, mock_aws_s3, mock_credentials, mock_stderr, mock_stdout):
        """Test run continues when error occurs discovering dates for a host."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        # Mock S3 to raise exception when discovering dates
        mock_s3_client.list_s3_objects.side_effect = Exception("S3 access denied")

        with patch("sys.argv", ["count_notes.py", "production", "--all-dates"]):
            S3NoteCounts.run()

        # Verify error was logged to stderr
        stderr = mock_stderr.getvalue()
        assert "Error discovering dates: S3 access denied" in stderr
        assert "No data found" in stderr

        # No CSV output since no data was found
        output = mock_stdout.getvalue()
        assert output.strip() == ""

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch("scripts.count_notes.HelperEvaluation.aws_s3_credentials")
    @patch("scripts.count_notes.AwsS3")
    def test_run_with_no_data_found_explicit_date(self, mock_aws_s3, mock_credentials, mock_stderr, mock_stdout):
        """Test run outputs zeros when explicit date has no data."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        # Mock S3 to return empty results
        mock_s3_client.list_s3_objects.return_value = []

        with patch("sys.argv", ["count_notes.py", "production", "--date", "2025-10-15"]):
            S3NoteCounts.run()

        # When dates are explicitly specified, even with no notes, we output CSV with zeros
        output = mock_stdout.getvalue()
        lines = output.strip().split("\n")
        assert lines[0] == "date,production"
        assert lines[1] == "2025-10-15,0"
