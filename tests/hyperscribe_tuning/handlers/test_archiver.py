import json
from http import HTTPStatus
from io import BytesIO
from time import time
from typing import NamedTuple
from unittest.mock import patch, call, MagicMock

from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.effects.simple_api import HTMLResponse, JSONResponse
from canvas_sdk.events import Event
from canvas_sdk.events.base import TargetType
from canvas_sdk.handlers.simple_api import SimpleAPIRoute, Credentials
from canvas_sdk.v1.data import Patient
from requests import Response

from hyperscribe_tuning.handlers.archiver import Archiver
from tests.helper import is_constant


def helper_instance() -> Archiver:
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
        "APISigningKey": "theApiSigningKey",
        "AwsKey": "theKey",
        "AwsSecret": "theSecret",
        "AwsRegion": "theRegion",
        "AwsBucket": "theBucket",
    }
    return Archiver(event, secrets)


def test_class():
    tested = Archiver
    assert issubclass(tested, SimpleAPIRoute)


def test_constants():
    tested = Archiver
    constants = {
        "PATH": "/archive",
        "RESPONDS_TO": ['SIMPLE_API_AUTHENTICATE', 'SIMPLE_API_REQUEST'],  # <--- SimpleAPIBase class
    }
    assert is_constant(tested, constants)


@patch("hyperscribe_tuning.handlers.archiver.time", wraps=time)
def test_authenticate(mock_time):
    def reset_mocks():
        mock_time.reset_mock()

    tested = helper_instance()

    # all good
    tested.request.query_params = {
        "ts": "1741964291",
        "sig": "ceb81ba49d3a2f950b0327a9af6a6fe7677994b8467ba076f9953a9171b9728a",
    }  # <-- it should be this dictionary
    mock_time.side_effect = [1741964291.775192]
    result = tested.authenticate(Credentials(tested.request))
    assert result is True
    calls = [call()]
    assert mock_time.mock_calls == calls
    reset_mocks()

    # incorrect sig
    tested.request.query_params = {
        "ts": "1741964291",
        "sig": "ceb81ba49d3a2f950b0327a9af6a6fe7677994b8467ba076f9953a9171b9728x",
    }
    mock_time.side_effect = [1741964291.775192]
    result = tested.authenticate(Credentials(tested.request))
    assert result is False
    calls = [call()]
    assert mock_time.mock_calls == calls
    reset_mocks()

    # too old ts
    tested.request.query_params = {
        "ts": "1741964291",
        "sig": "ceb81ba49d3a2f950b0327a9af6a6fe7677994b8467ba076f9953a9171b9728a",
    }
    mock_time.side_effect = [1741964291.775192 + 3601]
    result = tested.authenticate(Credentials(tested.request))
    assert result is False
    calls = [call()]
    assert mock_time.mock_calls == calls
    reset_mocks()

    # missing sig
    tested.request.query_params = {
        "ts": "1741964291",
    }
    mock_time.side_effect = [1741964291.775192]
    result = tested.authenticate(Credentials(tested.request))
    assert result is False
    assert mock_time.mock_calls == []
    reset_mocks()

    # missing ts
    tested.request.query_params = {
        "sig": "ceb81ba49d3a2f950b0327a9af6a6fe7677994b8467ba076f9953a9171b9728a",
    }
    mock_time.side_effect = [1741964291.775192]
    result = tested.authenticate(Credentials(tested.request))
    assert result is False
    assert mock_time.mock_calls == []
    reset_mocks()


@patch("hyperscribe_tuning.handlers.archiver.render_to_string")
def test_get(render_to_string):
    def reset_mocks():
        render_to_string.reset_mock()

    tests = [
        ("", "15"),
        ("14", "15"),
        ("33", "33"),
        ("67", "67"),
    ]
    for audio_interval, exp_interval in tests:
        tested = helper_instance()
        tested.secrets["AudioIntervalSeconds"] = audio_interval

        render_to_string.side_effect = ["theBody"]

        tested.request.query_params = {
            "ts": "1741964291",
            "sig": "ceb81ba49d3a2f950b0327a9af6a6fe7677994b8467ba076f9953a9171b9728a",
            "patient_id": "thePatientId",
            "note_id": "theNoteId",
        }
        result = tested.get()
        expected = [
            HTMLResponse(
                content='theBody',
                headers={'Content-Type': 'text/html'},
            ),
        ]
        assert result == expected
        calls = [call(
            'templates/capture_tuning_case.html',
            {'interval': exp_interval, 'patient_id': 'thePatientId', 'note_id': 'theNoteId'},
        )]
        assert render_to_string.mock_calls == calls
        reset_mocks()


@patch("hyperscribe_tuning.handlers.archiver.time", wraps=time)
@patch("hyperscribe_tuning.handlers.archiver.AwsS3")
def test_post(aws_s3, mock_time):
    mock_form = MagicMock()

    def reset_mocks():
        aws_s3.reset_mock()
        mock_time.reset_mock()
        mock_form.reset_mock()

    class FormFile(NamedTuple):
        filename: str
        content: str
        content_type: str

    def form_data():
        return mock_form

    tested = helper_instance()

    # all good
    response = Response()
    response.status_code = 1234
    response.raw = BytesIO(b"theResponseText")
    response.encoding = "utf-8"

    aws_s3.return_value.upload_binary_to_s3.side_effect = [response]
    mock_time.side_effect = [1741964291.775192]
    mock_form.get.side_effect = [FormFile(
        filename="theFileName",
        content="theContent",
        content_type="theContentType",
    )]
    tested.request.form_data = form_data

    result = tested.post()
    expected = [
        JSONResponse({
            "s3status": 1234,
            "s3text": "theResponseText",
            "s3key": "theHost/theFileName",
        }),
    ]
    assert result == expected
    calls = [
        call('theKey', 'theSecret', 'theRegion', 'theBucket'),
        call().upload_binary_to_s3('theHost/theFileName', 'theContent', 'theContentType'),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call()]
    assert mock_time.mock_calls == calls
    calls = [call.get('audio')]
    assert mock_form.mock_calls == calls
    reset_mocks()

    # no audio
    aws_s3.return_value.upload_binary_to_s3.side_effect = []
    mock_time.side_effect = []
    mock_form.get.side_effect = [None]
    tested.request.form_data = form_data

    result = tested.post()
    expected = [
        JSONResponse(
            {"message": "Form data must include 'audio' part"},
            HTTPStatus.BAD_REQUEST,
        ),
    ]
    assert result == expected
    calls = [
        call('theKey', 'theSecret', 'theRegion', 'theBucket'),
    ]
    assert aws_s3.mock_calls == calls
    assert mock_time.mock_calls == []
    calls = [call.get('audio')]
    assert mock_form.mock_calls == calls
    reset_mocks()
