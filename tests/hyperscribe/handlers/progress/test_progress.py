import json
from datetime import datetime, timezone, UTC
from unittest.mock import patch, call

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.handlers.application import Application

from hyperscribe.handlers.progress.progress import Progress


def test_class():
    tested = Progress
    assert issubclass(tested, Application)


@patch("hyperscribe.handlers.progress.progress.datetime", wraps=datetime)
@patch("hyperscribe.handlers.progress.progress.render_to_string")
def test_open(render_to_string, mock_datetime):
    def reset_mocks():
        render_to_string.reset_mock()
        mock_datetime.reset_mock()

    dates = [
        datetime(2025, 4, 30, 15, 46, 17, tzinfo=timezone.utc),
    ]
    secrets = {
        "AwsKey": "theKey",
        "AwsSecret": "theSecret",
        "AwsRegion": "theRegion",
        "AwsBucket": "theBucket",
    }
    # patient id provided
    event = Event(EventRequest(context=json.dumps({"patient": {"id": "thePatientUuid"}})))
    environment = {"CUSTOMER_IDENTIFIER": "theTestEnv"}
    tested = Progress(event, secrets, environment)

    render_to_string.side_effect = ["theContent"]
    mock_datetime.now.side_effect = dates

    result = tested.on_open()
    expected = Effect(
        type="LAUNCH_MODAL",
        payload=json.dumps({"data": {"url": None, "content": "theContent", "target": "right_chart_pane"}}),
    )
    assert result == expected

    calls = [call(
        'handlers/progress/progress.html',
        {
            'aws_s3_path': 'https://hyperscribe.s3.theRegion.amazonaws.com/theTestEnv/progresses/thePatientUuid.log',
            'message_after_date': '2025-04-30T15:46:17+00:00',
            'message_end_flag': 'EOF',
        },
    )]
    assert render_to_string.mock_calls == calls
    calls = [call.now(UTC)]
    assert mock_datetime.mock_calls == calls
    reset_mocks()
    # patient id not provided
    event = Event(EventRequest(context=json.dumps({"patient": {}})))
    environment = {"CUSTOMER_IDENTIFIER": "theTestEnv"}
    tested = Progress(event, secrets, environment)

    render_to_string.side_effect = ["theContent"]
    mock_datetime.now.side_effect = dates

    result = tested.on_open()
    expected = Effect(
        type="LAUNCH_MODAL",
        payload=json.dumps({"data": {"url": None, "content": "invalid context", "target": "right_chart_pane"}}),
    )
    assert result == expected

    assert render_to_string.mock_calls == []
    assert mock_datetime.mock_calls == []
    reset_mocks()
