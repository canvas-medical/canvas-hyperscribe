import json
import re
from datetime import datetime, timezone, UTC
from http import HTTPStatus
from unittest.mock import patch, call

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.effects.simple_api import JSONResponse
from canvas_sdk.events import Event
from canvas_sdk.events.base import TargetType
from canvas_sdk.handlers.simple_api import SimpleAPIRoute, Credentials
from canvas_sdk.v1.data import Patient

from hyperscribe.handlers.progress import Progress
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.progress_message import ProgressMessage
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import is_constant


def helper_instance() -> Progress:
    event = Event(
        EventRequest(
            context=json.dumps(
                {
                    "note_id": "noteId",
                    "method": "GET",
                    "path": "/progress",
                    "query_string": "note_id=noteId",
                    "body": "",
                    "headers": {"Host": "theHost"},
                },
            ),
        ),
    )
    event.target = TargetType(id="targetId", type=Patient)
    secrets = {"APISigningKey": "theApiSigningKey"}
    environment = {}
    instance = Progress(event, secrets, environment)
    instance._path_pattern = re.compile(
        r".*",
    )  # TODO this is a hack, find the right way to create the Archiver instance
    return instance


def test_class():
    tested = Progress
    assert issubclass(tested, SimpleAPIRoute)


def test_constants():
    tested = Progress
    constants = {
        "PATH": "/progress",
        "RESPONDS_TO": ["SIMPLE_API_AUTHENTICATE", "SIMPLE_API_REQUEST"],  # <--- SimpleAPIBase class
    }
    assert is_constant(tested, constants)


@patch.object(Authenticator, "check")
def test_authenticate(check):
    def reset_mocks():
        check.reset_mock()

    tested = helper_instance()
    tested.request.query_params = {"key": "value"}
    for test in [True, False]:
        check.side_effect = [test]
        result = tested.authenticate(Credentials(tested.request))
        assert result is test
        calls = [call("theApiSigningKey", 3600, {"key": "value"})]
        assert check.mock_calls == calls
        reset_mocks()


@patch("hyperscribe.handlers.progress.datetime", wraps=datetime)
@patch("hyperscribe.handlers.progress.get_cache")
def test_get(get_cache, mock_datetime):
    def reset_mocks():
        get_cache.reset_mock()
        mock_datetime.reset_mock()

    a_date = datetime(2025, 5, 15, 21, 6, 21, tzinfo=timezone.utc)

    tested = helper_instance()

    # no progress
    mock_datetime.now.side_effect = [a_date]
    get_cache.return_value.get.side_effect = [None]

    result = tested.get()
    expected = [JSONResponse(content={"time": "2025-05-15T21:06:21+00:00", "messages": []})]
    assert result == expected

    calls = [call.now(UTC)]
    assert mock_datetime.mock_calls == calls
    calls = [
        call(),
        call().get("progress-noteId"),
    ]
    assert get_cache.mock_calls == calls
    reset_mocks()

    # some progress
    messages = [
        {"message": "EOF", "time": "2025-04-30T18:19:11.123456+00:00"},
        {"message": "the first", "time": "2025-04-30T18:19:07.123456+00:00"},
    ]
    get_cache.return_value.get.side_effect = [messages]
    mock_datetime.now.side_effect = [a_date]

    result = tested.get()
    expected = [JSONResponse(content={"time": "2025-05-15T21:06:21+00:00", "messages": messages})]
    assert result == expected

    calls = [call.now(UTC)]
    assert mock_datetime.mock_calls == calls
    calls = [
        call(),
        call().get("progress-noteId"),
    ]
    assert get_cache.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.handlers.progress.get_cache")
def test_post(get_cache):
    def reset_mocks():
        get_cache.reset_mock()

    tested = helper_instance()

    tests = [
        (
            "noteId",
            '[{"key": "value1"}]',
            None,
            [
                call(),
                call().get("progress-noteId"),
                call(),
                call().set("progress-noteId", [{"key": "value1"}]),
            ],
        ),
        ("", '[{"key": "value1"}]', [], []),
        (
            "noteId",
            '[{"key": "value1"},{"key": "value4"}]',
            [{"key": "value3"}, {"key": "value2"}],
            [
                call(),
                call().get("progress-noteId"),
                call(),
                call().set(
                    "progress-noteId", [{"key": "value3"}, {"key": "value2"}, {"key": "value1"}, {"key": "value4"}]
                ),
            ],
        ),
    ]
    for note_id, body, side_effect_get, exp_calls in tests:
        get_cache.return_value.get.side_effect = [side_effect_get]
        tested.request.query_params = {"note_id": note_id}
        tested.request.body = body
        result = tested.post()
        expected = [
            Effect(
                type="SIMPLE_API_WEBSOCKET_BROADCAST",
                payload=json.dumps(
                    {
                        "data": {"channel": "progresses", "message": {"events": json.loads(body)}},
                    }
                ),
            ),
            JSONResponse(content={"status": "ok"}, status_code=HTTPStatus.ACCEPTED),
        ]
        assert result == expected
        assert get_cache.mock_calls == exp_calls
        reset_mocks()


def test_key_cache():
    tested = helper_instance()
    tests = [
        ("noteId", "progress-noteId"),
        ("", ""),
    ]
    for note_id, key in tests:
        tested.request.query_params = {"note_id": note_id}
        result = tested.key_cache()
        assert result == key


@patch("hyperscribe.handlers.progress.datetime", wraps=datetime)
@patch("hyperscribe.handlers.progress.Authenticator")
@patch("hyperscribe.handlers.progress.requests_post")
def test_send_to_user(requests_post, authenticator, mock_datetime):
    def reset_mocks():
        requests_post.reset_mock()
        authenticator.reset_mock()
        mock_datetime.reset_mock()

    a_date = datetime(2025, 5, 15, 11, 17, 31, tzinfo=timezone.utc)

    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )

    tested = Progress

    # set to send messages to the user
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
        audit_llm=False,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        send_progress=True,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
    )
    authenticator.presigned_url.side_effect = ["thePresignedUrl"]
    mock_datetime.now.side_effect = [a_date]

    tested.send_to_user(
        identification,
        settings,
        [
            ProgressMessage(message="theMessage1", section="theSection1"),
            ProgressMessage(message="theMessage2", section="theSection2"),
        ],
    )

    calls = [
        call.presigned_url(
            "theApiSigningKey",
            "https://canvasInstance.canvasmedical.com/plugin-io/api/hyperscribe/progress",
            {"note_id": "noteUuid"},
        ),
    ]
    assert authenticator.mock_calls == calls
    calls = [
        call(
            "thePresignedUrl",
            headers={"Content-Type": "application/json"},
            json=[
                {"time": "2025-05-15T11:17:31+00:00", "message": "theMessage1", "section": "theSection1"},
                {"time": "2025-05-15T11:17:31+00:00", "message": "theMessage2", "section": "theSection2"},
            ],
            verify=True,
            timeout=None,
        ),
    ]
    assert requests_post.mock_calls == calls
    calls = [call.now(UTC)]
    assert mock_datetime.mock_calls == calls
    reset_mocks()

    # set to not send messages to the user
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
        audit_llm=False,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
    )
    authenticator.presigned_url.side_effect = []
    mock_datetime.now.side_effect = []

    tested.send_to_user(
        identification,
        settings,
        [
            ProgressMessage(message="theMessage", section="theSection"),
        ],
    )

    assert authenticator.mock_calls == []
    assert requests_post.mock_calls == []
    assert mock_datetime.mock_calls == []
    reset_mocks()
