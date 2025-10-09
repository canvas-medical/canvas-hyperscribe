import json
from argparse import Namespace
from http import HTTPStatus
from unittest.mock import patch, call, MagicMock

from _pytest.capture import CaptureResult

from scripts.investigate_feedback import InvestigateFeedback
from tests.helper import MockClass


@patch("scripts.investigate_feedback.ArgumentParser")
def test__parameters(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    expected = Namespace(
        feedback_id="7792e7c9",
        instance_name="test_instance",
        note_id="note123",
        feedback_text="User reported an issue",
        debug=False,
        force=False,
    )
    argument_parser.return_value.parse_args.side_effect = [expected]

    tested = InvestigateFeedback
    result = tested._parameters()
    assert result == expected

    calls = [
        call(description="Retrieve and search log objects from S3 for user feedback analysis"),
        call().add_argument("feedback_id", type=str, help="Unique identifier for the feedback (e.g., '7792e7c9')"),
        call().add_argument("instance_name", type=str, help="Name of the instance to investigate"),
        call().add_argument("note_id", type=str, help="ID of the note associated with the feedback"),
        call().add_argument("feedback_text", type=str, help="Text of the user feedback to search for"),
        call().add_argument(
            "--debug", action="store_true", help="Debug mode: limit to 1 object each, print debug info"
        ),
        call().add_argument("--force", action="store_true", help="Force overwrite of existing files without prompting"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("scripts.investigate_feedback.AwsS3")
@patch("scripts.investigate_feedback.HelperEvaluation")
@patch.object(InvestigateFeedback, "_parameters")
@patch("builtins.open", create=True)
@patch("scripts.investigate_feedback.Path")
def test_run(mock_path, mock_open, parameters, helper, aws_s3, capsys):
    def reset_mocks():
        parameters.reset_mock()
        aws_s3.reset_mock()
        helper.reset_mock()
        mock_open.reset_mock()
        mock_path.reset_mock()

    tested = InvestigateFeedback

    # Test case with valid S3 credentials but no transcripts
    parameters.side_effect = [
        Namespace(
            feedback_id="abc123",
            instance_name="prod_instance",
            note_id="note456",
            feedback_text="Audio not working properly",
            debug=False,
            force=False,
        )
    ]
    helper.aws_s3_credentials.side_effect = ["theCredentials"]

    # Mock S3 client
    mock_s3_client = MagicMock()
    mock_s3_client.is_ready.return_value = True
    mock_s3_client.bucket = "test-bucket-logs"
    mock_s3_client.region = "us-east-1"
    mock_s3_client.list_s3_objects.return_value = []  # No transcripts found
    aws_s3.return_value = mock_s3_client

    # Mock Path
    mock_dir = MagicMock()
    mock_file = MagicMock()
    mock_path.return_value = mock_dir
    mock_dir.__truediv__.return_value = mock_file
    mock_file.exists.return_value = False  # File doesn't exist yet
    mock_file.__str__.return_value = "/tmp/PHI-hyperscribe-feedback/abc123/full_transcript.json"

    tested.run()

    captured = capsys.readouterr()

    # Verify output contains expected information
    assert "Feedback ID: abc123" in captured.out
    assert "Instance: prod_instance" in captured.out
    assert "Note ID: note456" in captured.out
    assert "Feedback: Audio not working properly" in captured.out
    assert "S3 Bucket: test-bucket-logs" in captured.out
    assert "S3 Region: us-east-1" in captured.out
    assert "Retrieving transcripts from: hyperscribe-prod_instance/transcripts/note456" in captured.out
    assert "Found 0 transcript objects" in captured.out
    assert "Total turns: 0" in captured.out
    assert "Successfully saved transcript to:" in captured.out

    calls = [call()]
    assert parameters.mock_calls == calls

    calls = [call.aws_s3_credentials()]
    assert helper.mock_calls == calls

    calls = [
        call("theCredentials"),
        call().is_ready(),
        call().list_s3_objects("hyperscribe-prod_instance/transcripts/note456"),
    ]
    assert aws_s3.mock_calls == calls

    reset_mocks()


@patch("scripts.investigate_feedback.AwsS3")
@patch("scripts.investigate_feedback.HelperEvaluation")
@patch.object(InvestigateFeedback, "_parameters")
@patch("scripts.investigate_feedback.sys.exit")
def test_run_invalid_credentials(mock_exit, parameters, helper, aws_s3, capsys):
    def reset_mocks():
        parameters.reset_mock()
        aws_s3.reset_mock()
        helper.reset_mock()
        mock_exit.reset_mock()

    tested = InvestigateFeedback

    # Test case with invalid S3 credentials
    parameters.side_effect = [
        Namespace(
            feedback_id="abc123",
            instance_name="prod_instance",
            note_id="note456",
            feedback_text="Audio not working properly",
            debug=False,
            force=False,
        )
    ]
    helper.aws_s3_credentials.side_effect = ["invalidCredentials"]

    # Mock S3 client with invalid credentials
    mock_s3_client = MagicMock()
    mock_s3_client.is_ready.return_value = False
    aws_s3.return_value = mock_s3_client

    # Make sys.exit raise SystemExit to stop execution
    mock_exit.side_effect = SystemExit(1)

    try:
        tested.run()
    except SystemExit:
        pass

    expected_err = (
        "Error: AWS S3 credentials not properly configured.\n"
        "Please ensure the required environment variables are set.\n"
    )
    exp_out = CaptureResult("", err=expected_err)
    assert capsys.readouterr() == exp_out

    calls = [call(1)]
    assert mock_exit.mock_calls == calls

    calls = [call.aws_s3_credentials()]
    assert helper.mock_calls == calls

    calls = [
        call("invalidCredentials"),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls

    reset_mocks()


@patch("scripts.investigate_feedback.AwsS3")
@patch("scripts.investigate_feedback.HelperEvaluation")
@patch.object(InvestigateFeedback, "_parameters")
@patch("scripts.investigate_feedback.Path")
def test_run_file_already_exists(mock_path, parameters, helper, aws_s3, capsys):
    def reset_mocks():
        parameters.reset_mock()
        aws_s3.reset_mock()
        helper.reset_mock()
        mock_path.reset_mock()

    tested = InvestigateFeedback

    parameters.side_effect = [
        Namespace(
            feedback_id="existing123",
            instance_name="prod",
            note_id="note789",
            feedback_text="Already processed",
            debug=False,
            force=False,
        )
    ]

    # Mock Path to indicate file exists
    mock_dir = MagicMock()
    mock_file = MagicMock()
    mock_path.return_value = mock_dir
    mock_dir.__truediv__.return_value = mock_file
    mock_file.exists.return_value = True
    mock_file.__str__.return_value = "/tmp/PHI-hyperscribe-feedback/existing123/full_transcript.json"

    tested.run()

    captured = capsys.readouterr()

    # Verify early exit message
    assert "Transcript already exists at:" in captured.out
    assert "/tmp/PHI-hyperscribe-feedback/existing123/full_transcript.json" in captured.out
    assert "Skipping S3 retrieval." in captured.out

    # Verify S3 client was never created
    assert helper.aws_s3_credentials.call_count == 0
    assert aws_s3.call_count == 0

    calls = [call()]
    assert parameters.mock_calls == calls

    reset_mocks()


def test__construct_s3_prefix():
    tested = InvestigateFeedback

    result = tested._construct_s3_prefix("prod", "note123")
    assert result == "hyperscribe-prod/transcripts/note123"

    result = tested._construct_s3_prefix("staging", "abc456xyz")
    assert result == "hyperscribe-staging/transcripts/abc456xyz"


def test__construct_logs_s3_prefix():
    tested = InvestigateFeedback

    result = tested._construct_logs_s3_prefix("prod", "2025-10-08")
    assert result == "hyperscribe-prod/finals/2025-10-08/"

    result = tested._construct_logs_s3_prefix("staging", "2025-01-15")
    assert result == "hyperscribe-staging/finals/2025-01-15/"


def test__extract_iso_date():
    from datetime import datetime, UTC

    tested = InvestigateFeedback

    # Test with valid transcript objects
    mock_objects = [
        MockClass(last_modified=datetime(2025, 10, 8, 14, 30, 0, tzinfo=UTC)),
        MockClass(last_modified=datetime(2025, 10, 8, 15, 30, 0, tzinfo=UTC)),
    ]
    result = tested._extract_iso_date(mock_objects)
    assert result == "2025-10-08"

    # Test with empty list
    result = tested._extract_iso_date([])
    assert result is None


def test__retrieve_transcript_objects():
    tested = InvestigateFeedback

    mock_s3_client = MagicMock()
    mock_objects = [
        MockClass(key="transcript1"),
        MockClass(key="transcript2"),
    ]
    mock_s3_client.list_s3_objects.return_value = mock_objects

    result = tested._retrieve_transcript_objects(mock_s3_client, "test-prefix")

    assert result == mock_objects
    assert mock_s3_client.list_s3_objects.call_args == call("test-prefix")


def test__retrieve_log_objects():
    tested = InvestigateFeedback

    mock_s3_client = MagicMock()

    # Mock various log objects, some matching note_id, some not
    mock_objects = [
        MockClass(key="hyperscribe-prod/finals/2025-10-08/abcd1234567890abcd1234567890abcd-note123/log1.json"),
        MockClass(key="hyperscribe-prod/finals/2025-10-08/1111222233334444555566667777888-note456/log2.json"),
        MockClass(key="hyperscribe-prod/finals/2025-10-08/ffffeeeeddddccccbbbbaaaa99998888-note123/log3.json"),
        MockClass(key="hyperscribe-prod/finals/2025-10-08/other-file.json"),
    ]
    mock_s3_client.list_s3_objects.return_value = mock_objects

    result = tested._retrieve_log_objects(mock_s3_client, "hyperscribe-prod/finals/2025-10-08/", "note123")

    # Should only return objects with -note123/ in the key
    assert len(result) == 2
    assert result[0].key == "hyperscribe-prod/finals/2025-10-08/abcd1234567890abcd1234567890abcd-note123/log1.json"
    assert result[1].key == "hyperscribe-prod/finals/2025-10-08/ffffeeeeddddccccbbbbaaaa99998888-note123/log3.json"


def test__parse_and_concatenate_transcripts(capsys):
    tested = InvestigateFeedback

    mock_s3_client = MagicMock()

    transcript_objects = [
        MockClass(key="hyperscribe-prod/transcripts/note123/transcript_01.log"),
        MockClass(key="hyperscribe-prod/transcripts/note123/transcript_02.log"),
        MockClass(key="hyperscribe-prod/transcripts/note123/transcript_03.log"),
        MockClass(key="hyperscribe-prod/transcripts/note123/transcript_04.log"),
    ]

    # Mock responses with different status codes and content
    mock_responses = [
        MockClass(
            status_code=HTTPStatus.OK.value,
            content=json.dumps(
                [{"speaker": "user", "text": "Hello"}, {"speaker": "assistant", "text": "Hi there"}]
            ).encode("utf-8"),
        ),
        MockClass(status_code=HTTPStatus.NOT_FOUND.value, content=b""),
        MockClass(
            status_code=HTTPStatus.OK.value,
            content=json.dumps(
                [
                    {"speaker": "user", "text": "How are you?"},
                ]
            ).encode("utf-8"),
        ),
        MockClass(status_code=HTTPStatus.OK.value, content=b"Invalid JSON {this is not valid"),
    ]

    mock_s3_client.access_s3_object.side_effect = mock_responses

    result = tested._parse_and_concatenate_transcripts(mock_s3_client, transcript_objects)

    # Should have 3 turns: 2 from first transcript, 0 from second (failed), 1 from third, 0 from fourth (parse error)
    assert len(result) == 3
    assert result[0] == {
        "speaker": "user",
        "text": "Hello",
        "object_key": "hyperscribe-prod/transcripts/note123/transcript_01.log",
    }
    assert result[1] == {
        "speaker": "assistant",
        "text": "Hi there",
        "object_key": "hyperscribe-prod/transcripts/note123/transcript_01.log",
    }
    assert result[2] == {
        "speaker": "user",
        "text": "How are you?",
        "object_key": "hyperscribe-prod/transcripts/note123/transcript_03.log",
    }

    # Verify warnings were printed for failed retrieval and parse error
    captured = capsys.readouterr()
    assert "Warning: Failed to retrieve hyperscribe-prod/transcripts/note123/transcript_02.log" in captured.err
    assert "Warning: Failed to parse hyperscribe-prod/transcripts/note123/transcript_04.log" in captured.err


def test__parse_and_concatenate_logs(capsys):
    tested = InvestigateFeedback

    mock_s3_client = MagicMock()

    log_objects = [
        MockClass(key="hyperscribe-prod/finals/2025-10-08/abc123/log1.txt"),
        MockClass(key="hyperscribe-prod/finals/2025-10-08/abc123/log2.txt"),
        MockClass(key="hyperscribe-prod/finals/2025-10-08/abc123/log3.txt"),
    ]

    # Mock responses with text content
    mock_responses = [
        MockClass(
            status_code=HTTPStatus.OK.value,
            content=b"Log line 1\nLog line 2\n\nLog line 3",
        ),
        MockClass(
            status_code=HTTPStatus.OK.value,
            content=b"Another log line\n",
        ),
        MockClass(status_code=HTTPStatus.NOT_FOUND.value, content=b""),
    ]

    mock_s3_client.access_s3_object.side_effect = mock_responses

    result = tested._parse_and_concatenate_logs(mock_s3_client, log_objects, debug=False)

    # Should have 4 log entries: 3 from first file (empty lines excluded), 1 from second file, 0 from third (failed)
    assert len(result) == 4
    assert result[0] == "Log line 1"
    assert result[1] == "Log line 2"
    assert result[2] == "Log line 3"
    assert result[3] == "Another log line"

    # Verify warnings were printed for failed retrieval
    captured = capsys.readouterr()
    assert "Warning: Failed to retrieve hyperscribe-prod/finals/2025-10-08/abc123/log3.txt" in captured.err


def test__parse_and_concatenate_logs_with_non_dict_items(capsys):
    tested = InvestigateFeedback

    mock_s3_client = MagicMock()

    log_objects = [
        MockClass(key="hyperscribe-prod/finals/2025-10-08/abc123/log1.txt"),
        MockClass(key="hyperscribe-prod/finals/2025-10-08/abc123/log2.txt"),
    ]

    # Mock responses: text files with various content including empty lines
    mock_responses = [
        MockClass(
            status_code=HTTPStatus.OK.value,
            content=b"Line 1\n\n\nLine 2\n   \nLine 3",
        ),
        MockClass(
            status_code=HTTPStatus.OK.value,
            content=b"\n\nOnly whitespace\n\n",
        ),
    ]

    mock_s3_client.access_s3_object.side_effect = mock_responses

    result = tested._parse_and_concatenate_logs(mock_s3_client, log_objects, debug=False)

    # Should only have 4 log entries (empty and whitespace-only lines are filtered out)
    assert len(result) == 4
    assert result[0] == "Line 1"
    assert result[1] == "Line 2"
    assert result[2] == "Line 3"
    assert result[3] == "Only whitespace"


@patch("scripts.investigate_feedback.AwsS3")
@patch("scripts.investigate_feedback.HelperEvaluation")
@patch.object(InvestigateFeedback, "_parameters")
@patch("builtins.open", create=True)
@patch("scripts.investigate_feedback.Path")
def test_run_with_transcripts(mock_path, mock_open, parameters, helper, aws_s3, capsys):
    from datetime import datetime, UTC

    def reset_mocks():
        parameters.reset_mock()
        aws_s3.reset_mock()
        helper.reset_mock()
        mock_open.reset_mock()
        mock_path.reset_mock()

    tested = InvestigateFeedback

    parameters.side_effect = [
        Namespace(
            feedback_id="7792e7c9",
            instance_name="prod",
            note_id="note123",
            feedback_text="Audio issue",
            debug=False,
            force=False,
        )
    ]
    helper.aws_s3_credentials.side_effect = ["theCredentials"]

    # Mock S3 client
    mock_s3_client = MagicMock()
    mock_s3_client.is_ready.return_value = True
    mock_s3_client.bucket = "test-bucket"
    mock_s3_client.region = "us-west-2"

    # Mock transcript objects with last_modified dates
    mock_transcript_objects = [
        MockClass(
            key="hyperscribe-prod/transcripts/note123/transcript_0.json",
            last_modified=datetime(2025, 10, 8, 14, 30, 0, tzinfo=UTC),
        ),
    ]

    # Mock log objects
    mock_log_objects = [
        MockClass(key="hyperscribe-prod/finals/2025-10-08/abc123-note123/log1.txt"),
    ]

    # Set up list_s3_objects to return different results for transcripts and logs
    mock_s3_client.list_s3_objects.side_effect = [mock_transcript_objects, mock_log_objects]

    # Mock transcript and log content
    transcript_response = MockClass(
        status_code=HTTPStatus.OK.value,
        content=json.dumps([{"speaker": "user", "text": "Test message"}]).encode("utf-8"),
    )
    log_response = MockClass(status_code=HTTPStatus.OK.value, content=b"Log line 1\n")
    mock_s3_client.access_s3_object.side_effect = [transcript_response, log_response]

    aws_s3.return_value = mock_s3_client

    # Mock Path
    mock_dir = MagicMock()
    mock_file = MagicMock()
    mock_path.return_value = mock_dir
    mock_dir.__truediv__.return_value = mock_file
    mock_file.exists.return_value = False  # File doesn't exist yet
    mock_file.__str__.return_value = "/tmp/PHI-hyperscribe-feedback/7792e7c9/full_transcript.json"

    tested.run()

    captured = capsys.readouterr()

    # Verify output contains expected information
    assert "Feedback ID: 7792e7c9" in captured.out
    assert "Instance: prod" in captured.out
    assert "Note ID: note123" in captured.out
    assert "Feedback: Audio issue" in captured.out
    assert "S3 Bucket: test-bucket" in captured.out
    assert "S3 Region: us-west-2" in captured.out
    assert "Retrieving transcripts from: hyperscribe-prod/transcripts/note123" in captured.out
    assert "Found 1 transcript objects" in captured.out
    assert "Total turns: 1" in captured.out
    assert "Retrieving logs from: hyperscribe-prod/finals/2025-10-08/" in captured.out
    assert "Found 1 log objects" in captured.out
    assert "Total log lines: 1" in captured.out
    assert "Successfully saved transcript to:" in captured.out
    assert "Successfully saved logs to:" in captured.out

    calls = [call()]
    assert parameters.mock_calls == calls

    calls = [call.aws_s3_credentials()]
    assert helper.mock_calls == calls

    calls = [
        call("theCredentials"),
        call().is_ready(),
        call().list_s3_objects("hyperscribe-prod/transcripts/note123"),
        call().access_s3_object("hyperscribe-prod/transcripts/note123/transcript_0.json"),
        call().list_s3_objects("hyperscribe-prod/finals/2025-10-08/"),
        call().access_s3_object("hyperscribe-prod/finals/2025-10-08/abc123-note123/log1.txt"),
    ]
    assert aws_s3.mock_calls == calls

    reset_mocks()


def test__parse_and_concatenate_transcripts_debug(capsys):
    tested = InvestigateFeedback

    mock_s3_client = MagicMock()

    transcript_objects = [
        MockClass(key="hyperscribe-prod/transcripts/note123/transcript_01.log"),
    ]

    mock_responses = [
        MockClass(
            status_code=HTTPStatus.OK.value,
            content=json.dumps([{"speaker": "provider", "text": "Hello"}]).encode("utf-8"),
        ),
    ]

    mock_s3_client.access_s3_object.side_effect = mock_responses

    result = tested._parse_and_concatenate_transcripts(mock_s3_client, transcript_objects, debug=True)

    assert len(result) == 1
    assert result[0] == {
        "speaker": "provider",
        "text": "Hello",
        "object_key": "hyperscribe-prod/transcripts/note123/transcript_01.log",
    }

    # Verify debug output was printed
    captured = capsys.readouterr()
    assert "DEBUG TRANSCRIPT:" in captured.out
    assert "Object Key: hyperscribe-prod/transcripts/note123/transcript_01.log" in captured.out
    assert "Status Code: 200" in captured.out
    assert "Content Preview (first 50 chars):" in captured.out


def test__parse_and_concatenate_logs_debug(capsys):
    tested = InvestigateFeedback

    mock_s3_client = MagicMock()

    log_objects = [
        MockClass(key="hyperscribe-prod/finals/2025-10-08/abc123/log1.txt"),
    ]

    mock_responses = [
        MockClass(
            status_code=HTTPStatus.OK.value,
            content=b"Debug log line\n",
        ),
    ]

    mock_s3_client.access_s3_object.side_effect = mock_responses

    result = tested._parse_and_concatenate_logs(mock_s3_client, log_objects, debug=True)

    assert len(result) == 1
    assert result[0] == "Debug log line"

    # Verify debug output was printed
    captured = capsys.readouterr()
    assert "DEBUG LOG:" in captured.out
    assert "Object Key: hyperscribe-prod/finals/2025-10-08/abc123/log1.txt" in captured.out
    assert "Status Code: 200" in captured.out
    assert "Content Preview (first 50 chars):" in captured.out


def test__parse_and_concatenate_logs_decode_error(capsys):
    tested = InvestigateFeedback

    mock_s3_client = MagicMock()

    log_objects = [
        MockClass(key="hyperscribe-prod/finals/2025-10-08/abc123/log1.txt"),
        MockClass(key="hyperscribe-prod/finals/2025-10-08/abc123/log2.txt"),
    ]

    mock_responses = [
        MockClass(
            status_code=HTTPStatus.OK.value,
            content=b"\xff\xfe",  # Invalid UTF-8
        ),
        MockClass(
            status_code=HTTPStatus.OK.value,
            content=b"Valid log line\n",
        ),
    ]

    mock_s3_client.access_s3_object.side_effect = mock_responses

    result = tested._parse_and_concatenate_logs(mock_s3_client, log_objects, debug=False)

    # Should only have 1 log entry from the second file
    assert len(result) == 1
    assert result[0] == "Valid log line"

    # Verify warning was printed for decode error
    captured = capsys.readouterr()
    assert "Warning: Failed to decode hyperscribe-prod/finals/2025-10-08/abc123/log1.txt" in captured.err


@patch("builtins.open", create=True)
@patch("builtins.input")
@patch("scripts.investigate_feedback.Path")
@patch("scripts.investigate_feedback.AwsS3")
@patch("scripts.investigate_feedback.HelperEvaluation")
@patch.object(InvestigateFeedback, "_parameters")
def test_run_debug_overwrite_yes(parameters, helper, aws_s3, mock_path, mock_input, mock_open, capsys):
    tested = InvestigateFeedback

    parameters.side_effect = [
        Namespace(
            feedback_id="debug123",
            instance_name="prod",
            note_id="note456",
            feedback_text="Debug test",
            debug=True,
            force=False,
        )
    ]

    # Mock Path to indicate file exists
    mock_dir = MagicMock()
    mock_file = MagicMock()
    mock_path.return_value = mock_dir
    mock_dir.__truediv__.return_value = mock_file
    mock_file.exists.return_value = True
    mock_file.__str__.return_value = "/tmp/PHI-hyperscribe-feedback/debug123/full_transcript.json"

    # Mock user input to continue with overwrite
    mock_input.return_value = "Y"

    helper.aws_s3_credentials.side_effect = ["theCredentials"]

    # Mock S3 client
    mock_s3_client = MagicMock()
    mock_s3_client.is_ready.return_value = True
    mock_s3_client.bucket = "test-bucket"
    mock_s3_client.region = "us-west-2"
    mock_s3_client.list_s3_objects.return_value = []
    aws_s3.return_value = mock_s3_client

    tested.run()

    captured = capsys.readouterr()
    assert "Proceeding with overwrite..." in captured.out


@patch("builtins.input")
@patch("scripts.investigate_feedback.Path")
@patch("scripts.investigate_feedback.AwsS3")
@patch("scripts.investigate_feedback.HelperEvaluation")
@patch.object(InvestigateFeedback, "_parameters")
def test_run_debug_overwrite_no(parameters, helper, aws_s3, mock_path, mock_input, capsys):
    tested = InvestigateFeedback

    parameters.side_effect = [
        Namespace(
            feedback_id="debug123",
            instance_name="prod",
            note_id="note456",
            feedback_text="Debug test",
            debug=True,
            force=False,
        )
    ]

    # Mock Path to indicate file exists
    mock_dir = MagicMock()
    mock_file = MagicMock()
    mock_path.return_value = mock_dir
    mock_dir.__truediv__.return_value = mock_file
    mock_file.exists.return_value = True
    mock_file.__str__.return_value = "/tmp/PHI-hyperscribe-feedback/debug123/full_transcript.json"

    # Mock user input to abort
    mock_input.return_value = "n"

    tested.run()

    captured = capsys.readouterr()
    assert "Aborting." in captured.out


@patch("scripts.investigate_feedback.AwsS3")
@patch("scripts.investigate_feedback.HelperEvaluation")
@patch.object(InvestigateFeedback, "_parameters")
@patch("builtins.open", create=True)
@patch("scripts.investigate_feedback.Path")
def test_run_debug_limit_objects(mock_path, mock_open, parameters, helper, aws_s3, capsys):
    from datetime import datetime, UTC

    tested = InvestigateFeedback

    parameters.side_effect = [
        Namespace(
            feedback_id="debug456",
            instance_name="prod",
            note_id="note789",
            feedback_text="Debug limit test",
            debug=True,
            force=False,
        )
    ]
    helper.aws_s3_credentials.side_effect = ["theCredentials"]

    # Mock S3 client
    mock_s3_client = MagicMock()
    mock_s3_client.is_ready.return_value = True
    mock_s3_client.bucket = "test-bucket"
    mock_s3_client.region = "us-west-2"

    # Mock multiple transcript objects
    mock_transcript_objects = [
        MockClass(
            key="hyperscribe-prod/transcripts/note789/transcript_0.json",
            last_modified=datetime(2025, 10, 8, 14, 30, 0, tzinfo=UTC),
        ),
        MockClass(
            key="hyperscribe-prod/transcripts/note789/transcript_1.json",
            last_modified=datetime(2025, 10, 8, 14, 31, 0, tzinfo=UTC),
        ),
        MockClass(
            key="hyperscribe-prod/transcripts/note789/transcript_2.json",
            last_modified=datetime(2025, 10, 8, 14, 32, 0, tzinfo=UTC),
        ),
    ]

    # Mock multiple log objects
    mock_log_objects = [
        MockClass(key="hyperscribe-prod/finals/2025-10-08/abc123-note789/log1.txt"),
        MockClass(key="hyperscribe-prod/finals/2025-10-08/abc123-note789/log2.txt"),
        MockClass(key="hyperscribe-prod/finals/2025-10-08/abc123-note789/log3.txt"),
    ]

    # Set up list_s3_objects to return different results for transcripts and logs
    mock_s3_client.list_s3_objects.side_effect = [mock_transcript_objects, mock_log_objects]

    # Mock transcript and log content
    transcript_response = MockClass(
        status_code=HTTPStatus.OK.value,
        content=json.dumps([{"speaker": "user", "text": "Test message"}]).encode("utf-8"),
    )
    log_response = MockClass(status_code=HTTPStatus.OK.value, content=b"Log line 1\n")
    mock_s3_client.access_s3_object.side_effect = [transcript_response, log_response]

    aws_s3.return_value = mock_s3_client

    # Mock Path
    mock_dir = MagicMock()
    mock_file = MagicMock()
    mock_path.return_value = mock_dir
    mock_dir.__truediv__.return_value = mock_file
    mock_file.exists.return_value = False
    mock_file.__str__.return_value = "/tmp/PHI-hyperscribe-feedback/debug456/full_transcript.json"

    tested.run()

    captured = capsys.readouterr()

    # Verify debug mode messages are shown
    assert "DEBUG: Limiting to first transcript object only" in captured.out
    assert "DEBUG: Limiting to first log object only" in captured.out

    # Verify only 1 transcript and 1 log object were processed (limited from 3 each)
    assert "Found 1 transcript objects" in captured.out
    assert "Found 1 log objects" in captured.out


@patch("builtins.open", create=True)
@patch("scripts.investigate_feedback.Path")
@patch("scripts.investigate_feedback.AwsS3")
@patch("scripts.investigate_feedback.HelperEvaluation")
@patch.object(InvestigateFeedback, "_parameters")
def test_run_force_overwrite(parameters, helper, aws_s3, mock_path, mock_open, capsys):
    tested = InvestigateFeedback

    parameters.side_effect = [
        Namespace(
            feedback_id="force123",
            instance_name="prod",
            note_id="note789",
            feedback_text="Force test",
            debug=False,
            force=True,
        )
    ]

    # Mock Path to indicate file exists
    mock_dir = MagicMock()
    mock_file = MagicMock()
    mock_path.return_value = mock_dir
    mock_dir.__truediv__.return_value = mock_file
    mock_file.exists.return_value = True
    mock_file.__str__.return_value = "/tmp/PHI-hyperscribe-feedback/force123/full_transcript.json"

    helper.aws_s3_credentials.side_effect = ["theCredentials"]

    # Mock S3 client
    mock_s3_client = MagicMock()
    mock_s3_client.is_ready.return_value = True
    mock_s3_client.bucket = "test-bucket"
    mock_s3_client.region = "us-west-2"
    mock_s3_client.list_s3_objects.return_value = []
    aws_s3.return_value = mock_s3_client

    tested.run()

    captured = capsys.readouterr()
    assert "Force mode: overwriting existing files..." in captured.out
    # Should not see any prompt or abort messages
    assert "proceed? [Y/n]" not in captured.out
    assert "Aborting." not in captured.out
    assert "Skipping S3 retrieval." not in captured.out
