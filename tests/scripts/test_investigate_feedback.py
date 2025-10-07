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
        feedback_id="7792e7c9", instance_name="test_instance", note_id="note123", feedback_text="User reported an issue"
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
        Namespace(feedback_id="existing123", instance_name="prod", note_id="note789", feedback_text="Already processed")
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


@patch("scripts.investigate_feedback.AwsS3")
@patch("scripts.investigate_feedback.HelperEvaluation")
@patch.object(InvestigateFeedback, "_parameters")
@patch("builtins.open", create=True)
@patch("scripts.investigate_feedback.Path")
def test_run_with_transcripts(mock_path, mock_open, parameters, helper, aws_s3, capsys):
    def reset_mocks():
        parameters.reset_mock()
        aws_s3.reset_mock()
        helper.reset_mock()
        mock_open.reset_mock()
        mock_path.reset_mock()

    tested = InvestigateFeedback

    parameters.side_effect = [
        Namespace(feedback_id="7792e7c9", instance_name="prod", note_id="note123", feedback_text="Audio issue")
    ]
    helper.aws_s3_credentials.side_effect = ["theCredentials"]

    # Mock S3 client
    mock_s3_client = MagicMock()
    mock_s3_client.is_ready.return_value = True
    mock_s3_client.bucket = "test-bucket"
    mock_s3_client.region = "us-west-2"

    # Mock transcript objects
    mock_transcript_objects = [
        MockClass(key="hyperscribe-prod/transcripts/note123/transcript_0.json"),
    ]
    mock_s3_client.list_s3_objects.return_value = mock_transcript_objects

    # Mock transcript content
    mock_response = MockClass(
        status_code=HTTPStatus.OK.value,
        content=json.dumps([{"speaker": "user", "text": "Test message"}]).encode("utf-8"),
    )
    mock_s3_client.access_s3_object.return_value = mock_response

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
    assert "Successfully saved transcript to:" in captured.out

    calls = [call()]
    assert parameters.mock_calls == calls

    calls = [call.aws_s3_credentials()]
    assert helper.mock_calls == calls

    calls = [
        call("theCredentials"),
        call().is_ready(),
        call().list_s3_objects("hyperscribe-prod/transcripts/note123"),
        call().access_s3_object("hyperscribe-prod/transcripts/note123/transcript_0.json"),
    ]
    assert aws_s3.mock_calls == calls

    reset_mocks()
