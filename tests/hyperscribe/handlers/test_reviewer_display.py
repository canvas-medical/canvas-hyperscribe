import json
import re
from datetime import timezone, datetime
from time import time
from unittest.mock import patch, call

from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.effects.simple_api import HTMLResponse
from canvas_sdk.events import Event
from canvas_sdk.events.base import TargetType
from canvas_sdk.handlers.simple_api import SimpleAPIRoute, Credentials
from canvas_sdk.v1.data import Patient

from hyperscribe.handlers.reviewer_display import ReviewerDisplay
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.aws_s3_object import AwsS3Object
from tests.helper import is_constant


def helper_instance() -> ReviewerDisplay:
    event = Event(EventRequest(context=json.dumps({
        "note_id": "noteId",
        "method": "GET",
        "path": "/capture-case",
        "query_string": "",
        "body": "",
        "headers": {"Host": "theHost"},
    })))
    event.target = TargetType(id="targetId", type=Patient)
    secrets = {
        "AwsKey": "theKey",
        "AwsSecret": "theSecret",
        "AwsRegion": "theRegion",
        "AwsBucket": "theBucket",
    }
    environment = {
        "CUSTOMER_IDENTIFIER": "theTestEnv",
    }
    instance = ReviewerDisplay(event, secrets, environment)
    instance._path_pattern = re.compile(r".*")  # TODO this is a hack, find the right way to create the Archiver instance
    return instance


def test_class():
    tested = ReviewerDisplay
    assert issubclass(tested, SimpleAPIRoute)


def test_constants():
    tested = ReviewerDisplay
    constants = {
        "PATH": "/reviewer",
        "RESPONDS_TO": ['SIMPLE_API_AUTHENTICATE', 'SIMPLE_API_REQUEST'],  # <--- SimpleAPIBase class
    }
    assert is_constant(tested, constants)


@patch("hyperscribe.handlers.reviewer_display.time", wraps=time)
def test_authenticate(mock_time):
    def reset_mocks():
        mock_time.reset_mock()

    tested = helper_instance()

    # all good
    tested.request.query_params = {
        "ts": "1746790419",
        "sig": "db6ba533682736ca1937979afa2b461c49f659f73cc565e64e00771c77e8d5be",
    }  # <-- it should be this dictionary
    mock_time.side_effect = [1746790419.775192]
    result = tested.authenticate(Credentials(tested.request))
    assert result is True
    calls = [call()]
    assert mock_time.mock_calls == calls
    reset_mocks()

    # incorrect sig
    tested.request.query_params = {
        "ts": "1746790419",
        "sig": "db6ba533682736ca1937979afa2b461c49f659f73cc565e64e00771c77e8d5bx",
    }
    mock_time.side_effect = [1746790419.775192]
    result = tested.authenticate(Credentials(tested.request))
    assert result is False
    calls = [call()]
    assert mock_time.mock_calls == calls
    reset_mocks()

    # too old ts
    tested.request.query_params = {
        "ts": "1746790419",
        "sig": "db6ba533682736ca1937979afa2b461c49f659f73cc565e64e00771c77e8d5be",
    }
    mock_time.side_effect = [1746790419.775192 + 1201]
    result = tested.authenticate(Credentials(tested.request))
    assert result is False
    calls = [call()]
    assert mock_time.mock_calls == calls
    reset_mocks()

    # missing sig
    tested.request.query_params = {
        "ts": "1746790419",
    }
    mock_time.side_effect = [1746790419.775192]
    result = tested.authenticate(Credentials(tested.request))
    assert result is False
    assert mock_time.mock_calls == []
    reset_mocks()

    # missing ts
    tested.request.query_params = {
        "sig": "db6ba533682736ca1937979afa2b461c49f659f73cc565e64e00771c77e8d5be",
    }
    mock_time.side_effect = [1746790419.775192]
    result = tested.authenticate(Credentials(tested.request))
    assert result is False
    assert mock_time.mock_calls == []
    reset_mocks()


@patch("hyperscribe.handlers.reviewer_display.render_to_string")
@patch('hyperscribe.handlers.reviewer_display.AwsS3')
def test_get(aws_s3, render_to_string):
    def reset_mocks():
        aws_s3.reset_mock()
        render_to_string.reset_mock()

    aws_s3_credentials = AwsS3Credentials(
        aws_key='theKey',
        aws_secret='theSecret',
        region='theRegion',
        bucket='theBucket',
    )
    a_date = datetime(2025, 5, 8, 7, 11, 45, tzinfo=timezone.utc)

    tested = helper_instance()
    tested.request.query_params = {
        "note_id": "theNoteId",
    }
    # s3 not ready
    aws_s3.return_value.is_ready.side_effect = [False]
    aws_s3.return_value.list_s3_objects.side_effect = []
    aws_s3.return_value.generate_presigned_url.side_effect = []
    render_to_string.side_effect = ["theRenderedString"]

    result = tested.get()
    expected = [
        HTMLResponse(
            content='theRenderedString',
            headers={'Content-Type': 'text/html'},
        ),
    ]
    assert result == expected

    calls = [
        call(aws_s3_credentials),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call("templates/reviewer.html", {"url_list": "[]"})]
    assert render_to_string.mock_calls == calls
    reset_mocks()

    # s3 is ready
    aws_s3.return_value.is_ready.side_effect = [True]
    aws_s3.return_value.list_s3_objects.side_effect = [
        [
            AwsS3Object(key="path01", last_modified=a_date, size=4785236),
            AwsS3Object(key="path02", last_modified=a_date, size=4785236),
            AwsS3Object(key="path03", last_modified=a_date, size=4785236),
        ],
    ]
    aws_s3.return_value.generate_presigned_url.side_effect = [
        "pre_assigned_01",
        "pre_assigned_02",
        "pre_assigned_03",
    ]
    render_to_string.side_effect = ["theRenderedString"]

    result = tested.get()
    expected = [
        HTMLResponse(
            content='theRenderedString',
            headers={'Content-Type': 'text/html'},
        ),
    ]
    assert result == expected

    calls = [
        call(aws_s3_credentials),
        call().is_ready(),
        call().list_s3_objects('theTestEnv/audits/theNoteId/'),
        call().generate_presigned_url('path01', 1200),
        call().generate_presigned_url('path02', 1200),
        call().generate_presigned_url('path03', 1200),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call(
        "templates/reviewer.html",
        {"url_list": '["pre_assigned_01", "pre_assigned_02", "pre_assigned_03"]'},
    )]
    assert render_to_string.mock_calls == calls
    reset_mocks()
