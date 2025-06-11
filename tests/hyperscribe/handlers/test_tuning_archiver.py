import json
import re
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
from canvas_sdk.v1.data import Patient, Command
from requests import Response

from hyperscribe.handlers.commander import Commander
from hyperscribe.handlers.tuning_archiver import TuningArchiver, ArchiverHelper
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from tests.helper import is_constant


def helper_instance() -> TuningArchiver:
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
        "AwsBucketTuning": "theBucketTuning",
    }
    instance = TuningArchiver(event, secrets)
    instance._path_pattern = re.compile(r".*")  # TODO this is a hack, find the right way to create the Archiver instance
    return instance


def test_class():
    tested = TuningArchiver
    assert issubclass(tested, SimpleAPIRoute)


def test_constants():
    tested = TuningArchiver
    constants = {
        "PATH": "/archive",
        "RESPONDS_TO": ['SIMPLE_API_AUTHENTICATE', 'SIMPLE_API_REQUEST'],  # <--- SimpleAPIBase class
    }
    assert is_constant(tested, constants)


@patch("hyperscribe.handlers.tuning_archiver.time", wraps=time)
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


@patch("hyperscribe.handlers.tuning_archiver.render_to_string")
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


@patch.object(ArchiverHelper, "store_audio")
@patch.object(ArchiverHelper, "store_chart")
@patch("hyperscribe.handlers.tuning_archiver.AwsS3")
def test_post(aws_s3, post_chart, post_audio):
    def reset_mocks():
        aws_s3.reset_mock()
        post_chart.reset_mock()
        post_audio.reset_mock()

    tested = helper_instance()

    # save chart
    response = Response()
    response.status_code = 1234
    response.raw = BytesIO(b"theResponseText")
    response.encoding = "utf-8"

    aws_s3.side_effect = ["awsS3Instance"]
    post_chart.side_effect = ["thePostChart"]
    post_audio.side_effect = []
    tested.request.query_params = {
        "archive_limited_chart": True,
    }

    result = tested.post()
    expected = ["thePostChart"]
    assert result == expected
    calls = [
        call(AwsS3Credentials(aws_key='theKey', aws_secret='theSecret', region='theRegion', bucket='theBucketTuning')),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call("awsS3Instance", "theHost", tested.request)]
    assert post_chart.mock_calls == calls
    assert post_audio.mock_calls == []
    reset_mocks()

    # save audio
    response = Response()
    response.status_code = 1234
    response.raw = BytesIO(b"theResponseText")
    response.encoding = "utf-8"

    aws_s3.side_effect = ["awsS3Instance"]
    post_chart.side_effect = []
    post_audio.side_effect = ["thePostAudio"]
    tested.request.query_params = {
        "archive_limited_chart": False,
    }

    result = tested.post()
    expected = ["thePostAudio"]
    assert result == expected
    calls = [
        call(AwsS3Credentials(aws_key='theKey', aws_secret='theSecret', region='theRegion', bucket='theBucketTuning')),
    ]
    assert aws_s3.mock_calls == calls
    assert post_chart.mock_calls == []
    calls = [call("awsS3Instance", "theHost", tested.request)]
    assert post_audio.mock_calls == calls
    reset_mocks()


@patch.object(Command, "objects")
@patch.object(Commander, 'existing_commands_to_coded_items')
@patch("hyperscribe.handlers.tuning_archiver.LimitedCache")
@patch("hyperscribe.handlers.tuning_archiver.AwsS3")
def test_store_chart(aws_s3, limited_cache, existing_commands_to_coded_items, command_db):
    mock_request = MagicMock()

    def reset_mocks():
        aws_s3.reset_mock()
        limited_cache.reset_mock()
        existing_commands_to_coded_items.reset_mock()
        command_db.reset_mock()
        mock_request.reset_mock()

    tested = ArchiverHelper

    response = Response()
    response.status_code = 1234
    response.raw = BytesIO(b"theResponseText")
    response.encoding = "utf-8"

    aws_s3.upload_text_to_s3.side_effect = [response]
    existing_commands_to_coded_items.side_effect = ["existingCommandsToCodedItems"]
    limited_cache.return_value.to_json.side_effect = [{"key": "theLimitedCache"}]
    command_db.filter.return_value.order_by.side_effect = ["QuerySetCommands"]
    mock_request.query_params = {
        "patient_id": "thePatientId",
        "note_id": "theNoteId",
    }

    result = tested.store_chart(aws_s3, "theHost", mock_request)
    expected = JSONResponse({
        "s3status": 1234,
        "s3text": "theResponseText",
        "s3key": "hyperscribe-theHost/patient_thePatientId/note_theNoteId/limited_chart.json",
    })
    assert result == expected

    calls = [
        call.upload_text_to_s3(
            'hyperscribe-theHost/patient_thePatientId/note_theNoteId/limited_chart.json',
            '{"key": "theLimitedCache"}',
        ),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call('QuerySetCommands', AccessPolicy(policy=False, items=[]), False)]
    assert existing_commands_to_coded_items.mock_calls == calls
    calls = [
        call.filter(patient__id='thePatientId', note__id='theNoteId', state='staged'),
        call.filter().order_by('dbid'),
    ]
    assert command_db.mock_calls == calls
    calls = [
        call("thePatientId", "existingCommandsToCodedItems"),
        call().to_json(True),
    ]
    assert limited_cache.mock_calls == calls
    assert mock_request.mock_calls == []
    reset_mocks()


@patch("hyperscribe.handlers.tuning_archiver.time", wraps=time)
@patch("hyperscribe.handlers.tuning_archiver.AwsS3")
def test_store_audio(aws_s3, mock_time):
    mock_request = MagicMock()

    def reset_mocks():
        aws_s3.reset_mock()
        mock_time.reset_mock()
        mock_request.reset_mock()

    class FormFile(NamedTuple):
        filename: str
        content: str
        content_type: str

    tested = ArchiverHelper

    # all good
    response = Response()
    response.status_code = 1234
    response.raw = BytesIO(b"theResponseText")
    response.encoding = "utf-8"

    aws_s3.upload_binary_to_s3.side_effect = [response]
    mock_time.side_effect = [1741964291.775192]
    mock_request.form_data.return_value.get.side_effect = [FormFile(
        filename="theFileName",
        content="theContent",
        content_type="theContentType",
    )]

    result = tested.store_audio(aws_s3, "theHost", mock_request)
    expected = JSONResponse({
        "s3status": 1234,
        "s3text": "theResponseText",
        "s3key": "hyperscribe-theHost/theFileName",
    })
    assert result == expected

    calls = [
        call.upload_binary_to_s3('hyperscribe-theHost/theFileName', 'theContent', 'theContentType'),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call()]
    assert mock_time.mock_calls == calls
    calls = [
        call.form_data(),
        call.form_data().get('audio'),
    ]
    assert mock_request.mock_calls == calls
    reset_mocks()

    # no audio
    aws_s3.return_value.upload_binary_to_s3.side_effect = []
    mock_time.side_effect = []
    mock_request.form_data.return_value.get.side_effect = [None]

    result = tested.store_audio(aws_s3, "theHost", mock_request)
    expected = JSONResponse(
        {"message": "Form data must include 'audio' part"},
        HTTPStatus.BAD_REQUEST,
    )
    assert result == expected

    assert aws_s3.mock_calls == []
    assert mock_time.mock_calls == []
    calls = [
        call.form_data(),
        call.form_data().get('audio'),
    ]
    assert mock_request.mock_calls == calls
    reset_mocks()
