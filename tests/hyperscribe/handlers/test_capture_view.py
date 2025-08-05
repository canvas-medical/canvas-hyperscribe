import json
import re
from datetime import datetime
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import patch, call

from canvas_generated.messages.effects_pb2 import Effect
from canvas_sdk.effects.simple_api import Response, HTMLResponse
from canvas_sdk.handlers.simple_api import SimpleAPI, Credentials
from canvas_sdk.v1.data import Task
from canvas_sdk.v1.data.staff import Staff

from hyperscribe.handlers.capture_view import CaptureView
from hyperscribe.libraries.audio_client import AudioClient
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper

# Disable automatic route resolution
CaptureView._ROUTES = {}


def helper_instance():
    # Minimal fake event with method context
    event = SimpleNamespace(context={"method": "GET"})
    secrets = {
        Constants.SECRET_API_SIGNING_KEY: "signingKey",
        Constants.SECRET_AUDIO_HOST: "https://audio",
        Constants.SECRET_AUDIO_HOST_PRE_SHARED_KEY: "shared",
        Constants.SECRET_AUDIO_INTERVAL: 5,
        Constants.COPILOTS_TEAM_FHIR_GROUP_ID: "team123",
        Constants.FUMAGE_BEARER_TOKEN: "bearerToken",
    }
    environment = {Constants.CUSTOMER_IDENTIFIER: "customerIdentifier"}
    view = CaptureView(event, secrets, environment)
    view._path_pattern = re.compile(r".*")
    return view


def test_class():
    assert issubclass(CaptureView, SimpleAPI)


def test_constants():
    # PREFIX exists (even if None)
    assert hasattr(CaptureView, "PREFIX")


@patch.object(Authenticator, "check")
def test_authenticate(check):
    view = helper_instance()
    view.request = SimpleNamespace(query_params={"ts": "123", "sig": "abc"})
    creds = Credentials(view.request)

    # False case
    check.return_value = False
    assert view.authenticate(creds) is False
    check.assert_called_once_with("signingKey", Constants.API_SIGNED_EXPIRATION_SECONDS, {"ts": "123", "sig": "abc"})
    check.reset_mock()

    # True case
    check.return_value = True
    assert view.authenticate(creds) is True
    check.assert_called_once()


@patch("hyperscribe.handlers.capture_view.Helper")
@patch("hyperscribe.handlers.capture_view.render_to_string")
@patch("hyperscribe.handlers.capture_view.Authenticator")
def test_capture_get(authenticator, render_to_string, helper):
    def reset_mocks():
        authenticator.reset_mock()
        render_to_string.reset_mock()
        helper.reset_mock()

    render_to_string.side_effect = ["<html/>"]
    authenticator.presigned_url.side_effect = ["Url1"]
    authenticator.presigned_url_no_params.side_effect = ["Url2", "Url3", "Url4", "Url5"]
    helper.is_copilot_session_paused.side_effect = [True]

    tested = helper_instance()
    tested.request = SimpleNamespace(path_params={"patient_id": "p", "note_id": "n"}, query_params={}, headers={})

    result = tested.capture_get()
    expected = [HTMLResponse(content="<html/>", status_code=HTTPStatus(200))]
    assert result == expected

    calls = [
        call.presigned_url("signingKey", "/plugin-io/api/hyperscribe/progress", {"note_id": "n"}),
        call.presigned_url_no_params("signingKey", "/plugin-io/api/hyperscribe/capture/new-session/p/n"),
        call.presigned_url_no_params("signingKey", "/plugin-io/api/hyperscribe/capture/idle/p/n/pause"),
        call.presigned_url_no_params("signingKey", "/plugin-io/api/hyperscribe/capture/idle/p/n/resume"),
        call.presigned_url_no_params("signingKey", "/plugin-io/api/hyperscribe/audio/p/n"),
    ]
    assert authenticator.mock_calls == calls
    calls = [
        call(
            "templates/hyperscribe.html",
            {
                "patientUuid": "p",
                "noteUuid": "n",
                "interval": 5,
                "endFlag": "EOF",
                "progressURL": "Url1",
                "newSessionURL": "Url2",
                "pauseSessionURL": "Url3",
                "resumeSessionURL": "Url4",
                "saveAudioURL": "Url5",
                "isPaused": True,
            },
        ),
    ]
    assert render_to_string.mock_calls == calls
    calls = [call.is_copilot_session_paused("p", "n")]
    assert helper.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.handlers.capture_view.AudioClient")
@patch.object(Helper, "copilot_task")
def test_new_session_post(copilot_task, audio_client):
    def reset_mocks():
        copilot_task.reset_mock()
        audio_client.reset_mock()

    tests = [
        (
            Task(id="theTaskId", created=datetime(2025, 5, 8, 12, 34, 56, 123456)),
            [
                Effect(
                    type="CREATE_TASK_COMMENT",
                    payload=json.dumps(
                        {
                            "data": {
                                "task": {"id": "theTaskId"},
                                "body": json.dumps(
                                    {
                                        "chunk_index": 1,
                                        "note_id": "n",
                                        "patient_id": "p",
                                        "is_paused": False,
                                        "created": "2025-05-08T12:34:56.123456",
                                        "finished": None,
                                    }
                                ),
                            },
                        }
                    ),
                )
            ],
        ),
        (None, []),
    ]
    for task, expected in tests:
        audio_client.for_operation.return_value.get_user_token.side_effect = ["theUserToken"]
        audio_client.for_operation.return_value.create_session.side_effect = ["theSessionId"]
        copilot_task.side_effect = [task]
        audio_client.for_operation.return_value.add_session.side_effect = ["theFhirResponse"]

        tested = helper_instance()
        tested.request = SimpleNamespace(
            path_params={"patient_id": "p", "note_id": "n"},
            headers={"canvas-logged-in-user-id": "u"},
        )
        result = tested.new_session_post()
        assert result == expected

        calls = [call("p")]
        assert copilot_task.mock_calls == calls
        calls = [
            call.for_operation("https://audio", "customerIdentifier", "shared"),
            call.for_operation().get_user_token("u"),
            call.for_operation().create_session("theUserToken", {"note_id": "n", "patient_id": "p"}),
            call.for_operation().add_session("p", "n", "theSessionId", "u", "theUserToken"),
        ]
        assert audio_client.mock_calls == calls
        reset_mocks()


@patch.object(Helper, "copilot_task")
def test_idle_session_post(copilot_task):
    def reset_mocks():
        copilot_task.reset_mock()

    tested = helper_instance()

    tests = [
        ("pause", None, []),
        ("resume", None, []),
        (
            "pause",
            Task(id="theTaskId", created=datetime(2025, 5, 8, 12, 34, 56, 123456)),
            [
                Effect(
                    type="CREATE_TASK_COMMENT",
                    payload=json.dumps(
                        {
                            "data": {
                                "task": {"id": "theTaskId"},
                                "body": json.dumps(
                                    {
                                        "chunk_index": -1,
                                        "note_id": "n",
                                        "patient_id": "p",
                                        "is_paused": True,
                                        "created": "2025-05-08T12:34:56.123456",
                                        "finished": None,
                                    }
                                ),
                            },
                        }
                    ),
                )
            ],
        ),
        (
            "resume",
            Task(id="theTaskId", created=datetime(2025, 5, 8, 12, 34, 56, 123456)),
            [
                Effect(
                    type="CREATE_TASK_COMMENT",
                    payload=json.dumps(
                        {
                            "data": {
                                "task": {"id": "theTaskId"},
                                "body": json.dumps(
                                    {
                                        "chunk_index": -1,
                                        "note_id": "n",
                                        "patient_id": "p",
                                        "is_paused": False,
                                        "created": "2025-05-08T12:34:56.123456",
                                        "finished": None,
                                    }
                                ),
                            },
                        }
                    ),
                )
            ],
        ),
    ]
    for action, task, expected in tests:
        copilot_task.side_effect = [task]

        tested.request = SimpleNamespace(
            path_params={"patient_id": "p", "note_id": "n", "action": action},
            headers={"canvas-logged-in-user-id": "u"},
        )
        result = tested.idle_session_post()
        assert result == expected

        calls = [call("p")]
        assert copilot_task.mock_calls == calls
        reset_mocks()


@patch("hyperscribe.handlers.capture_view.datetime", wraps=datetime)
@patch("hyperscribe.handlers.capture_view.time")
@patch("hyperscribe.handlers.capture_view.log")
@patch("hyperscribe.handlers.capture_view.requests")
@patch.object(Staff, "objects")
def test_fhir_task_upsert(staff_db, requests, log, time_mock, datetime_mock):
    def reset_mocks():
        staff_db.reset_mock()
        requests.reset_mock()
        log.reset_mock()
        time_mock.reset_mock()
        datetime_mock.reset_mock()

    staff_db.get.side_effect = [Staff(id=123)]
    requests.post.side_effect = [Response(content=b"ok", status_code=HTTPStatus(202))]
    time_mock.side_effect = [123456.87, 123478.91]
    datetime_mock.now.side_effect = [datetime(2025, 8, 3, 23, 55, 8, 955044)]

    tested = helper_instance()
    tested.request = SimpleNamespace(
        path_params={"patient_id": "p", "note_id": "n"},
        headers={"canvas-logged-in-user-id": "u"},
    )
    result = tested.fhir_task_upsert("thePatientId", "theText")
    expected = [Response(content=b"ok", status_code=HTTPStatus(202))]
    assert result == expected

    calls = [call.get(dbid=1)]
    assert staff_db.mock_calls == calls
    calls = [
        call.post(
            "https://fumage-customerIdentifier.canvasmedical.com/Task",
            json={
                "resourceType": "Task",
                "extension": [
                    {
                        "url": "http://schemas.canvasmedical.com/fhir/extensions/task-group",
                        "valueReference": {"reference": "Group/team123"},
                    },
                ],
                "status": "requested",
                "intent": "unknown",
                "description": "Encounter Copilot",
                "for": {"reference": "Patient/thePatientId"},
                "authoredOn": "2025-08-03T23:55:08.955044+00:00",
                "requester": {"reference": "Practitioner/123"},
                "owner": {"reference": "Practitioner/123"},
                "note": [
                    {
                        "authorReference": {"reference": "Practitioner/123"},
                        "time": "2025-08-03T23:55:08.955044+00:00",
                        "text": "theText",
                    },
                ],
                "input": [
                    {
                        "type": {"text": "label"},
                        "valueString": "Encounter Copilot",
                    },
                ],
            },
            headers={"Authorization": "Bearer bearerToken"},
        )
    ]
    assert requests.mock_calls == calls
    calls = [call.info("FHIR Task Create duration: 22.04 seconds")]
    assert log.mock_calls == calls
    calls = [call(), call()]
    assert time_mock.mock_calls == calls
    calls = [call.now()]
    assert datetime_mock.mock_calls == calls
    reset_mocks()


@patch.object(AudioClient, "save_audio_chunk")
def test_audio_chunk_post(save_chunk):
    view = helper_instance()
    # missing file part
    view.request = SimpleNamespace(path_params={"patient_id": "p", "note_id": "n"}, form_data=lambda: {})
    result = view.audio_chunk_post()
    assert isinstance(result, list)
    resp = result[0]
    assert isinstance(resp, Response) and resp.status_code == 400

    # non-file part
    class Part:
        name = "audio"
        filename = "f"
        content = b""
        content_type = "audio/test"

        def is_file(self):
            return False

    view.request = SimpleNamespace(path_params={"patient_id": "p", "note_id": "n"}, form_data=lambda: {"audio": Part()})
    result = view.audio_chunk_post()
    assert isinstance(result, list)
    resp = result[0]
    assert isinstance(resp, Response) and resp.status_code == 422

    # save error (returns list)
    save_chunk.return_value = SimpleNamespace(status_code=500, content=b"err")

    class PartOK(Part):
        def is_file(self):
            return True

    view.request = SimpleNamespace(
        path_params={"patient_id": "p", "note_id": "n"}, form_data=lambda: {"audio": PartOK()}
    )
    result = view.audio_chunk_post()
    assert isinstance(result, list)
    resp = result[0]
    assert resp.status_code == 500 and resp.content == b"err"

    # save success
    save_chunk.return_value = SimpleNamespace(status_code=201, content=b"")
    result = view.audio_chunk_post()
    resp = result[0]
    assert resp.status_code == 201 and resp.content == b"Audio chunk saved OK"
