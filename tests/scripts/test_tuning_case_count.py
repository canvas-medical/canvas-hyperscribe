"""Tests for the tuning_case_count.py script."""

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.tuning_case_count import TuningCaseCount


class MockS3Object:
    """Mock S3 object for testing."""

    def __init__(self, key: str):
        self.key = key


class TestTuningCaseCount:
    """Test suite for TuningCaseCount class."""

    def test_count_tuning_data_basic(self):
        """Test basic counting of patients, notes, and chunks."""
        mock_s3_client = MagicMock()

        mock_objects = [
            MockS3Object("hyperscribe-production/patient_123/note_abc/chunk_001.webm"),
            MockS3Object("hyperscribe-production/patient_123/note_abc/chunk_002.webm"),
            MockS3Object("hyperscribe-production/patient_123/note_abc/metadata.json"),
            MockS3Object("hyperscribe-production/patient_123/note_def/chunk_001.webm"),
            MockS3Object("hyperscribe-production/patient_456/note_xyz/chunk_001.webm"),
            MockS3Object("hyperscribe-production/patient_456/note_xyz/chunk_002.webm"),
            MockS3Object("hyperscribe-production/patient_456/note_xyz/chunk_003.webm"),
        ]
        mock_s3_client.list_s3_objects.return_value = mock_objects

        patients, notes = TuningCaseCount._count_tuning_data(mock_s3_client, "hyperscribe-production")

        # Should have 2 patients
        assert len(patients) == 2
        assert "patient_123" in patients
        assert "patient_456" in patients

        # Patient 123 should have 2 notes
        assert len(patients["patient_123"]) == 2
        assert "note_abc" in patients["patient_123"]
        assert "note_def" in patients["patient_123"]

        # Patient 456 should have 1 note
        assert len(patients["patient_456"]) == 1
        assert "note_xyz" in patients["patient_456"]

        # Should have 3 notes with correct chunk counts
        assert len(notes) == 3
        assert notes["note_abc"] == 2
        assert notes["note_def"] == 1
        assert notes["note_xyz"] == 3

        # Verify S3 call
        assert mock_s3_client.list_s3_objects.call_count == 1
        assert mock_s3_client.list_s3_objects.call_args == call("hyperscribe-production")

    def test_count_tuning_data_empty(self):
        """Test counting with no objects."""
        mock_s3_client = MagicMock()
        mock_s3_client.list_s3_objects.return_value = []

        patients, notes = TuningCaseCount._count_tuning_data(mock_s3_client, "hyperscribe-empty")

        assert len(patients) == 0
        assert len(notes) == 0
        assert mock_s3_client.list_s3_objects.call_count == 1

    def test_count_tuning_data_ignores_invalid_structure(self):
        """Test that invalid key structures are ignored."""
        mock_s3_client = MagicMock()

        mock_objects = [
            # Valid
            MockS3Object("hyperscribe-production/patient_123/note_abc/chunk_001.webm"),
            # Invalid - too few parts
            MockS3Object("hyperscribe-production/patient_123"),
            # Invalid - doesn't start with patient_
            MockS3Object("hyperscribe-production/other_123/note_abc/chunk_001.webm"),
            # Invalid - doesn't start with note_
            MockS3Object("hyperscribe-production/patient_123/other_abc/chunk_001.webm"),
            # Valid - non-webm file should still track patient/note
            MockS3Object("hyperscribe-production/patient_456/note_def/metadata.json"),
        ]
        mock_s3_client.list_s3_objects.return_value = mock_objects

        patients, notes = TuningCaseCount._count_tuning_data(mock_s3_client, "hyperscribe-production")

        # Should only have 2 valid patients
        assert len(patients) == 2
        assert "patient_123" in patients
        assert "patient_456" in patients

        # Should only count webm files
        assert notes["note_abc"] == 1
        assert notes.get("note_def", 0) == 0  # metadata.json doesn't count

    def test_count_tuning_data_multiple_patients_same_note(self):
        """Test that notes are tracked per patient correctly."""
        mock_s3_client = MagicMock()

        mock_objects = [
            MockS3Object("hyperscribe-production/patient_123/note_abc/chunk_001.webm"),
            # Same note_id, different patient
            MockS3Object("hyperscribe-production/patient_456/note_abc/chunk_001.webm"),
        ]
        mock_s3_client.list_s3_objects.return_value = mock_objects

        patients, notes = TuningCaseCount._count_tuning_data(mock_s3_client, "hyperscribe-production")

        # Both patients should have the same note
        assert len(patients) == 2
        assert "note_abc" in patients["patient_123"]
        assert "note_abc" in patients["patient_456"]

        # Note should have total chunks from both patients
        assert notes["note_abc"] == 2

    def test_calculate_summary(self):
        """Test summary statistics calculation."""
        patients = {
            "patient_123": {"note_abc", "note_def"},
            "patient_456": {"note_xyz"},
            "patient_789": {"note_aaa", "note_bbb", "note_ccc"},
        }

        notes = {
            "note_abc": 2,
            "note_def": 1,
            "note_xyz": 3,
            "note_aaa": 5,
            "note_bbb": 2,
            "note_ccc": 1,
        }

        patient_count, note_count, chunk_count = TuningCaseCount._calculate_summary(patients, notes)

        assert patient_count == 3
        assert note_count == 6  # 2 + 1 + 3
        assert chunk_count == 14  # 2 + 1 + 3 + 5 + 2 + 1

    def test_calculate_summary_empty(self):
        """Test summary calculation with empty data."""
        patient_count, note_count, chunk_count = TuningCaseCount._calculate_summary({}, {})

        assert patient_count == 0
        assert note_count == 0
        assert chunk_count == 0

    def test_discover_all_customers(self):
        """Test discovering all customer prefixes."""
        mock_s3_client = MagicMock()

        mock_objects = [
            MockS3Object("hyperscribe-production/patient_123/note_abc/file.webm"),
            MockS3Object("hyperscribe-staging/patient_456/note_def/file.webm"),
            MockS3Object("hyperscribe-production/patient_789/note_ghi/file.webm"),
            MockS3Object("hyperscribe-demo/patient_012/note_jkl/file.webm"),
            MockS3Object("other-bucket/file.txt"),  # Should be ignored
        ]
        mock_s3_client.list_s3_objects.return_value = mock_objects

        result = TuningCaseCount._discover_all_customers(mock_s3_client)

        assert result == ["hyperscribe-demo", "hyperscribe-production", "hyperscribe-staging"]
        assert mock_s3_client.list_s3_objects.call_count == 1
        assert mock_s3_client.list_s3_objects.call_args == call("")

    def test_discover_all_customers_empty(self):
        """Test discovering customers with no objects."""
        mock_s3_client = MagicMock()
        mock_s3_client.list_s3_objects.return_value = []

        result = TuningCaseCount._discover_all_customers(mock_s3_client)

        assert result == []
        assert mock_s3_client.list_s3_objects.call_count == 1

    def test_discover_all_customers_no_hyperscribe_prefixes(self):
        """Test discovering customers when no hyperscribe prefixes exist."""
        mock_s3_client = MagicMock()

        mock_objects = [
            MockS3Object("other-bucket/file.txt"),
            MockS3Object("another-bucket/file.json"),
        ]
        mock_s3_client.list_s3_objects.return_value = mock_objects

        result = TuningCaseCount._discover_all_customers(mock_s3_client)

        assert result == []

    @patch("sys.argv", ["tuning_case_count.py", "hyperscribe-production"])
    def test_parameters_with_prefix(self):
        """Test parameter parsing with prefix."""
        params = TuningCaseCount._parameters()

        assert params.prefix == "hyperscribe-production"
        assert params.all_customers is False

    @patch("sys.argv", ["tuning_case_count.py", "--all-customers"])
    def test_parameters_with_all_customers(self):
        """Test parameter parsing with --all-customers flag."""
        params = TuningCaseCount._parameters()

        assert params.prefix is None
        assert params.all_customers is True

    @patch("sys.argv", ["tuning_case_count.py"])
    def test_parameters_no_arguments(self):
        """Test parameter parsing with no arguments."""
        params = TuningCaseCount._parameters()

        assert params.prefix is None
        assert params.all_customers is False

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"SuperAwsKey": "test-key", "SuperAwsSecret": "test-secret"})
    @patch("scripts.tuning_case_count.AwsS3")
    def test_run_with_single_prefix(self, mock_aws_s3, mock_stderr, mock_stdout):
        """Test full run with a single prefix."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        # Mock S3 response
        mock_objects = [
            MockS3Object("hyperscribe-production/patient_123/note_abc/chunk_001.webm"),
            MockS3Object("hyperscribe-production/patient_123/note_abc/chunk_002.webm"),
            MockS3Object("hyperscribe-production/patient_456/note_def/chunk_001.webm"),
        ]
        mock_s3_client.list_s3_objects.return_value = mock_objects

        with patch("sys.argv", ["tuning_case_count.py", "hyperscribe-production"]):
            TuningCaseCount.run()

        # Verify output
        output = mock_stdout.getvalue()
        lines = output.strip().split("\n")

        assert lines[0] == "customer,patients,notes,chunks"
        assert lines[1] == "production,2,2,3"

        # Verify progress to stderr
        stderr = mock_stderr.getvalue()
        assert "Analyzing hyperscribe-production..." in stderr
        assert "Found 3 S3 objects" in stderr

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"SuperAwsKey": "test-key", "SuperAwsSecret": "test-secret"})
    @patch("scripts.tuning_case_count.AwsS3")
    def test_run_with_all_customers(self, mock_aws_s3, mock_stderr, mock_stdout):
        """Test full run with --all-customers flag."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        # Mock S3 responses
        mock_s3_client.list_s3_objects.side_effect = [
            # Discovery call
            [
                MockS3Object("hyperscribe-prod1/patient_123/note_abc/file.webm"),
                MockS3Object("hyperscribe-prod2/patient_456/note_def/file.webm"),
            ],
            # prod1 data
            [
                MockS3Object("hyperscribe-prod1/patient_123/note_abc/chunk_001.webm"),
                MockS3Object("hyperscribe-prod1/patient_123/note_abc/chunk_002.webm"),
                MockS3Object("hyperscribe-prod1/patient_123/note_def/chunk_001.webm"),
            ],
            # prod2 data
            [
                MockS3Object("hyperscribe-prod2/patient_456/note_xyz/chunk_001.webm"),
            ],
        ]

        with patch("sys.argv", ["tuning_case_count.py", "--all-customers"]):
            TuningCaseCount.run()

        # Verify output
        output = mock_stdout.getvalue()
        lines = output.strip().split("\n")

        assert lines[0] == "customer,patients,notes,chunks"
        # Should be sorted by notes descending
        assert lines[1] == "prod1,1,2,3"
        assert lines[2] == "prod2,1,1,1"

        # Verify progress messages
        stderr = mock_stderr.getvalue()
        assert "Discovering all customer prefixes..." in stderr
        assert "Found 2 customer prefixes" in stderr
        assert "Analyzing hyperscribe-prod1..." in stderr
        assert "Analyzing hyperscribe-prod2..." in stderr

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"SuperAwsKey": "test-key", "SuperAwsSecret": "test-secret"})
    @patch("scripts.tuning_case_count.AwsS3")
    def test_run_sorted_by_notes_descending(self, mock_aws_s3, mock_stderr, mock_stdout):
        """Test that output is sorted by notes in descending order."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        # Mock S3 responses
        # The customers are processed alphabetically: large, medium, small
        mock_s3_client.list_s3_objects.side_effect = [
            # Discovery call
            [
                MockS3Object("hyperscribe-small/file.webm"),
                MockS3Object("hyperscribe-large/file.webm"),
                MockS3Object("hyperscribe-medium/file.webm"),
            ],
            # large (3 notes) - processed first alphabetically
            [
                MockS3Object("hyperscribe-large/patient_1/note_a/chunk_1.webm"),
                MockS3Object("hyperscribe-large/patient_1/note_b/chunk_1.webm"),
                MockS3Object("hyperscribe-large/patient_1/note_c/chunk_1.webm"),
            ],
            # medium (2 notes) - processed second
            [
                MockS3Object("hyperscribe-medium/patient_1/note_a/chunk_1.webm"),
                MockS3Object("hyperscribe-medium/patient_1/note_b/chunk_1.webm"),
            ],
            # small (1 note) - processed third
            [
                MockS3Object("hyperscribe-small/patient_1/note_a/chunk_1.webm"),
            ],
        ]

        with patch("sys.argv", ["tuning_case_count.py", "--all-customers"]):
            TuningCaseCount.run()

        # Verify output is sorted by notes descending
        output = mock_stdout.getvalue()
        lines = output.strip().split("\n")

        assert lines[0] == "customer,patients,notes,chunks"
        assert lines[1] == "large,1,3,3"
        assert lines[2] == "medium,1,2,2"
        assert lines[3] == "small,1,1,1"

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"SuperAwsKey": "", "SuperAwsSecret": ""}, clear=False)
    def test_run_missing_credentials(self, mock_stderr, mock_stdout):
        """Test run exits when credentials are missing."""
        # Remove the keys entirely to trigger KeyError
        import os

        os.environ.pop("SuperAwsKey", None)
        os.environ.pop("SuperAwsSecret", None)

        with patch("sys.argv", ["tuning_case_count.py", "hyperscribe-production"]):
            with pytest.raises(SystemExit) as exc_info:
                TuningCaseCount.run()

            assert exc_info.value.code == 1

        # Verify error message
        stderr = mock_stderr.getvalue()
        assert "Error: Missing environment variable" in stderr
        assert "Required: SuperAwsKey, SuperAwsSecret" in stderr

    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"SuperAwsKey": "test-key", "SuperAwsSecret": "test-secret"})
    @patch("scripts.tuning_case_count.AwsS3")
    def test_run_s3_client_not_ready(self, mock_aws_s3, mock_stderr):
        """Test run exits when S3 client is not ready."""
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = False

        with patch("sys.argv", ["tuning_case_count.py", "hyperscribe-production"]):
            with pytest.raises(SystemExit) as exc_info:
                TuningCaseCount.run()

            assert exc_info.value.code == 1

        # Verify error message
        stderr = mock_stderr.getvalue()
        assert "Error: AWS S3 client not properly configured" in stderr

    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"SuperAwsKey": "test-key", "SuperAwsSecret": "test-secret"})
    @patch("scripts.tuning_case_count.AwsS3")
    def test_run_no_prefix_no_all_customers(self, mock_aws_s3, mock_stderr):
        """Test run exits when no prefix and no --all-customers flag."""
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        with patch("sys.argv", ["tuning_case_count.py"]):
            with pytest.raises(SystemExit) as exc_info:
                TuningCaseCount.run()

            assert exc_info.value.code == 1

        # Verify error message
        stderr = mock_stderr.getvalue()
        assert "You must specify a prefix or use --all-customers" in stderr

    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"SuperAwsKey": "test-key", "SuperAwsSecret": "test-secret"})
    @patch("scripts.tuning_case_count.AwsS3")
    def test_run_error_discovering_customers(self, mock_aws_s3, mock_stderr):
        """Test run exits when error occurs discovering customers."""
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True
        mock_s3_client.list_s3_objects.side_effect = Exception("S3 access denied")

        with patch("sys.argv", ["tuning_case_count.py", "--all-customers"]):
            with pytest.raises(SystemExit) as exc_info:
                TuningCaseCount.run()

            assert exc_info.value.code == 1

        # Verify error message
        stderr = mock_stderr.getvalue()
        assert "Error discovering customer prefixes: S3 access denied" in stderr

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"SuperAwsKey": "test-key", "SuperAwsSecret": "test-secret"})
    @patch("scripts.tuning_case_count.AwsS3")
    def test_run_error_processing_prefix(self, mock_aws_s3, mock_stderr, mock_stdout):
        """Test run continues when error occurs processing a specific prefix."""
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        # Mock S3 responses - customers are processed alphabetically (bad, good)
        # so the second call raises exception for "bad"
        mock_s3_client.list_s3_objects.side_effect = [
            # Discovery call
            [
                MockS3Object("hyperscribe-good/file.webm"),
                MockS3Object("hyperscribe-bad/file.webm"),
            ],
            # bad data - processed first alphabetically, raises exception
            Exception("Network error"),
            # good data - processed second
            [
                MockS3Object("hyperscribe-good/patient_1/note_a/chunk_1.webm"),
            ],
        ]

        with patch("sys.argv", ["tuning_case_count.py", "--all-customers"]):
            TuningCaseCount.run()

        # Verify output only includes successful prefix
        output = mock_stdout.getvalue()
        lines = output.strip().split("\n")

        assert lines[0] == "customer,patients,notes,chunks"
        assert lines[1] == "good,1,1,1"
        assert len(lines) == 2  # Only header and good result

        # Verify error was logged
        stderr = mock_stderr.getvalue()
        assert "Error processing hyperscribe-bad: Network error" in stderr

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"SuperAwsKey": "test-key", "SuperAwsSecret": "test-secret"})
    @patch("scripts.tuning_case_count.AwsS3")
    def test_run_customer_name_extraction(self, mock_aws_s3, mock_stderr, mock_stdout):
        """Test that customer names are correctly extracted from prefixes."""
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        mock_s3_client.list_s3_objects.return_value = [
            MockS3Object("hyperscribe-production/patient_1/note_a/chunk_1.webm"),
        ]

        with patch("sys.argv", ["tuning_case_count.py", "hyperscribe-production"]):
            TuningCaseCount.run()

        output = mock_stdout.getvalue()
        lines = output.strip().split("\n")

        # Should strip "hyperscribe-" prefix
        assert lines[1] == "production,1,1,1"

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.stderr", new_callable=StringIO)
    @patch.dict("os.environ", {"SuperAwsKey": "test-key", "SuperAwsSecret": "test-secret"})
    @patch("scripts.tuning_case_count.AwsS3")
    def test_run_non_hyperscribe_prefix(self, mock_aws_s3, mock_stderr, mock_stdout):
        """Test handling of prefixes that don't start with hyperscribe-."""
        mock_s3_client = MagicMock()
        mock_aws_s3.return_value = mock_s3_client
        mock_s3_client.is_ready.return_value = True

        mock_s3_client.list_s3_objects.return_value = [
            MockS3Object("custom-prefix/patient_1/note_a/chunk_1.webm"),
        ]

        with patch("sys.argv", ["tuning_case_count.py", "custom-prefix"]):
            TuningCaseCount.run()

        output = mock_stdout.getvalue()
        lines = output.strip().split("\n")

        # Should use prefix as-is if it doesn't start with hyperscribe-
        assert lines[1] == "custom-prefix,1,1,1"
