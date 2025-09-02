import re
from datetime import timezone, datetime
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import patch, call

from canvas_generated.messages.effects_pb2 import Effect
from canvas_sdk.effects.simple_api import Response, HTMLResponse
from canvas_sdk.handlers.simple_api import SimpleAPI, Credentials
from canvas_sdk.handlers.simple_api.api import StringFormPart
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.note import Note

from hyperscribe.handlers.capture_view import CaptureView
from hyperscribe.libraries.audio_client import AudioClient
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.progress_message import ProgressMessage
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey

# Disable automatic route resolution
CaptureView._ROUTES = {}


def helper_instance():
    # Minimal fake event with method context
    event = SimpleNamespace(context={"method": "GET"})
    secrets = {
        "APISigningKey": "signingKey",
        "AudioHost": "https://audio",
        "AudioHostSharedSecret": "shared",
        "AudioIntervalSeconds": 5,
        "KeyTextLLM": "theKeyTextLLM",
        "VendorTextLLM": "theVendorTextLLM",
        "KeyAudioLLM": "theKeyAudioLLM",
        "VendorAudioLLM": "theVendorAudioLLM",
        "StructuredReasonForVisit": "yes",
        "AuditLLMDecisions": "yes",
        "AwsKey": "theKey",
        "AwsSecret": "theSecret",
        "AwsRegion": "theRegion",
        "AwsBucketLogs": "theBucketLogs",
        "CycleTranscriptOverlap": "37",
        "MaxWorkers": 5,
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


@patch("hyperscribe.handlers.capture_view.requests_post")
@patch("hyperscribe.handlers.capture_view.Helper")
@patch("hyperscribe.handlers.capture_view.Authenticator")
def test_trigger_render(authenticator, helper, requests_post):
    def reset_mocks():
        authenticator.reset_mock()
        helper.reset_mock()
        requests_post.reset_mock()

    authenticator.presigned_url.side_effect = ["theUrl"]
    helper.canvas_host.side_effect = ["theHost"]
    requests_post.side_effect = ["theResponse"]

    tested = helper_instance()
    result = tested.trigger_render("thePatientId", "theNoteId")
    expected = "theResponse"
    assert result == expected

    calls = [
        call.presigned_url(
            "signingKey",
            "theHost/plugin-io/api/hyperscribe/render/thePatientId/theNoteId",
            {},
        )
    ]
    assert authenticator.mock_calls == calls
    calls = [call.canvas_host("customerIdentifier")]
    assert helper.mock_calls == calls
    calls = [call("theUrl", headers={"Content-Type": "application/json"}, verify=True, timeout=None)]
    assert requests_post.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.handlers.capture_view.Helper")
@patch("hyperscribe.handlers.capture_view.StopAndGo")
@patch("hyperscribe.handlers.capture_view.render_to_string")
@patch("hyperscribe.handlers.capture_view.Authenticator")
def test_capture_get(authenticator, render_to_string, stop_and_go, helper):
    def reset_mocks():
        authenticator.reset_mock()
        render_to_string.reset_mock()
        stop_and_go.reset_mock()
        helper.reset_mock()

    render_to_string.side_effect = ["<html/>"]
    helper.canvas_ws_host.side_effect = ["theWsHost"]
    authenticator.presigned_url.side_effect = ["Url1"]
    authenticator.presigned_url_no_params.side_effect = ["Url2", "Url3", "Url4", "Url5", "Url6", "Url7", "Url8"]
    stop_and_go.get.return_value.is_ended.side_effect = [False]
    stop_and_go.get.return_value.is_paused.side_effect = [False, False]
    stop_and_go.get.return_value.cycle.side_effect = [7]

    tested = helper_instance()
    tested.request = SimpleNamespace(
        path_params={"patient_id": "p", "note_id": "n", "note_reference": "4571"},
        query_params={},
        headers={},
    )

    result = tested.capture_get()
    expected = [HTMLResponse(content="<html/>", status_code=HTTPStatus(200))]
    assert result == expected

    calls = [
        call.presigned_url("signingKey", "/plugin-io/api/hyperscribe/progress", {"note_id": "n"}),
        call.presigned_url_no_params("signingKey", "/plugin-io/api/hyperscribe/capture/new-session/p/n"),
        call.presigned_url_no_params("signingKey", "/plugin-io/api/hyperscribe/capture/idle/p/n/pause"),
        call.presigned_url_no_params("signingKey", "/plugin-io/api/hyperscribe/capture/idle/p/n/resume"),
        call.presigned_url_no_params("signingKey", "/plugin-io/api/hyperscribe/capture/idle/p/n/end"),
        call.presigned_url_no_params("signingKey", "/plugin-io/api/hyperscribe/feedback/p/n"),
        call.presigned_url_no_params("signingKey", "/plugin-io/api/hyperscribe/audio/p/n"),
    ]
    assert authenticator.mock_calls == calls
    calls = [
        call(
            "templates/hyperscribe.html",
            {
                "patientUuid": "p",
                "noteUuid": "n",
                "noteReference": "4571",
                "interval": 5,
                "endFlag": "EOF",
                "wsProgressURL": "theWsHost/plugin-io/ws/hyperscribe/progresses/",
                "progressURL": "Url1",
                "newSessionURL": "Url2",
                "pauseSessionURL": "Url3",
                "resumeSessionURL": "Url4",
                "endSessionURL": "Url5",
                "feedbackURL": "Url6",
                "saveAudioURL": "Url7",
                "isEnded": False,
                "isPaused": False,
                "chunkId": 6,
            },
        ),
    ]
    assert render_to_string.mock_calls == calls
    calls = [
        call.get("n"),
        call.get().is_ended(),
        call.get().is_paused(),
        call.get().cycle(),
        call.get().is_paused(),
    ]
    assert stop_and_go.mock_calls == calls
    calls = [call.canvas_ws_host("customerIdentifier")]
    assert helper.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.handlers.capture_view.AudioClient")
def test_new_session_post(audio_client):
    def reset_mocks():
        audio_client.reset_mock()

    audio_client.for_operation.return_value.get_user_token.side_effect = ["theUserToken"]
    audio_client.for_operation.return_value.create_session.side_effect = ["theSessionId"]
    audio_client.for_operation.return_value.add_session.side_effect = ["theFhirResponse"]

    tested = helper_instance()
    tested.request = SimpleNamespace(
        path_params={"patient_id": "p", "note_id": "n"},
        headers={"canvas-logged-in-user-id": "u"},
    )
    result = tested.new_session_post()
    assert result == []

    calls = [
        call.for_operation("https://audio", "customerIdentifier", "shared"),
        call.for_operation().get_user_token("u"),
        call.for_operation().create_session("theUserToken", {"note_id": "n", "patient_id": "p"}),
        call.for_operation().add_session("p", "n", "theSessionId", "u", "theUserToken"),
    ]
    assert audio_client.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.handlers.capture_view.StopAndGo")
def test_idle_session_post(stop_and_go):
    def reset_mocks():
        stop_and_go.reset_mock()

    tested = helper_instance()

    tests = [
        (
            "end",
            False,
            False,
            [
                call.get("n"),
                call.get().is_ended(),
                call.get().set_ended(True),
                call.get().set_ended().save(),
            ],
        ),
        (
            "end",
            True,
            False,
            [
                call.get("n"),
                call.get().is_ended(),
                call.get().is_paused(),
                call.get().is_paused(),
            ],
        ),
        (
            "pause",
            False,
            True,
            [
                call.get("n"),
                call.get().is_ended(),
                call.get().is_paused(),
                call.get().is_paused(),
            ],
        ),
        (
            "pause",
            False,
            False,
            [
                call.get("n"),
                call.get().is_ended(),
                call.get().is_paused(),
                call.get().is_paused(),
                call.get().set_paused(True),
                call.get().set_paused().save(),
            ],
        ),
        (
            "resume",
            False,
            True,
            [
                call.get("n"),
                call.get().is_ended(),
                call.get().is_paused(),
                call.get().set_paused(False),
                call.get().set_paused().save(),
            ],
        ),
        (
            "resume",
            False,
            False,
            [
                call.get("n"),
                call.get().is_ended(),
                call.get().is_paused(),
                call.get().is_paused(),
            ],
        ),
    ]
    for action, is_ended, is_paused, exp_calls in tests:
        stop_and_go.get.return_value.is_ended.side_effect = [is_ended]
        stop_and_go.get.return_value.is_paused.side_effect = [is_paused, is_paused]

        tested.request = SimpleNamespace(
            path_params={"patient_id": "p", "note_id": "n", "action": action},
            headers={"canvas-logged-in-user-id": "u"},
        )
        result = tested.idle_session_post()
        assert result == []

        assert stop_and_go.mock_calls == exp_calls
        reset_mocks()


@patch("hyperscribe.handlers.capture_view.StopAndGo")
@patch("hyperscribe.handlers.capture_view.AudioClient")
@patch("hyperscribe.handlers.capture_view.Helper")
@patch("hyperscribe.handlers.capture_view.executor")
def test_audio_chunk_post(executor, helper, audio_client, stop_and_go):
    def reset_mocks():
        executor.reset_mock()
        helper.reset_mock()
        audio_client.reset_mock()
        stop_and_go.reset_mock()

    tested = helper_instance()
    # missing file part
    tested.request = SimpleNamespace(path_params={"patient_id": "p", "note_id": "n"}, form_data=lambda: {})
    result = tested.audio_chunk_post()
    assert isinstance(result, list)
    resp = result[0]
    assert isinstance(resp, Response) and resp.status_code == 400

    assert executor.mock_calls == []
    assert helper.mock_calls == []
    assert audio_client.mock_calls == []
    assert stop_and_go.mock_calls == []
    reset_mocks()

    # non-file part
    class Part:
        name = "audio"
        filename = "chunk_123_other"
        content = b""
        content_type = "audio/test"

        def is_file(self):
            return False

    tested.request = SimpleNamespace(
        path_params={"patient_id": "p", "note_id": "n"}, form_data=lambda: {"audio": Part()}
    )
    result = tested.audio_chunk_post()
    assert isinstance(result, list)
    resp = result[0]
    assert isinstance(resp, Response) and resp.status_code == 422

    assert executor.mock_calls == []
    assert helper.mock_calls == []
    assert audio_client.mock_calls == []
    assert stop_and_go.mock_calls == []
    reset_mocks()

    # save error (returns list)
    audio_client.for_operation.return_value.save_audio_chunk.side_effect = [
        SimpleNamespace(status_code=500, content=b"err")
    ]

    class PartOK(Part):
        def is_file(self):
            return True

    part = PartOK()
    tested.request = SimpleNamespace(path_params={"patient_id": "p", "note_id": "n"}, form_data=lambda: {"audio": part})
    result = tested.audio_chunk_post()
    assert isinstance(result, list)
    resp = result[0]
    assert resp.status_code == 500 and resp.content == b"err"

    assert executor.mock_calls == []
    assert helper.mock_calls == []
    calls = [
        call.for_operation("https://audio", "customerIdentifier", "shared"),
        call.for_operation().save_audio_chunk("p", "n", part),
    ]
    assert audio_client.mock_calls == calls
    assert stop_and_go.mock_calls == []
    reset_mocks()

    # save success
    # -- valid name
    audio_client.for_operation.return_value.save_audio_chunk.side_effect = [
        SimpleNamespace(status_code=201, content=b"")
    ]
    result = tested.audio_chunk_post()
    resp = result[0]
    assert resp.status_code == 201 and resp.content == b"Audio chunk saved OK"

    calls = [call.submit(helper.with_cleanup.return_value, "p", "n")]
    assert executor.mock_calls == calls
    calls = [call.with_cleanup(tested.trigger_render)]
    assert helper.mock_calls == calls
    calls = [
        call.for_operation("https://audio", "customerIdentifier", "shared"),  # -- valid name
        call.for_operation().save_audio_chunk("p", "n", part),
    ]
    assert audio_client.mock_calls == calls
    calls = [
        call.get("n"),
        call.get().add_waiting_cycle(123),
        call.get().add_waiting_cycle().save(),
    ]
    assert stop_and_go.mock_calls == calls
    reset_mocks()
    # -- invalid name
    audio_client.for_operation.return_value.save_audio_chunk.side_effect = [
        SimpleNamespace(status_code=201, content=b"")
    ]
    part.filename = "chunk_other.test"
    result = tested.audio_chunk_post()
    resp = result[0]
    assert resp.status_code == 201 and resp.content == b"Audio chunk saved OK"

    assert executor.mock_calls == []
    assert helper.mock_calls == []
    calls = [
        call.for_operation("https://audio", "customerIdentifier", "shared"),  # -- valid name
        call.for_operation().save_audio_chunk("p", "n", part),
    ]
    assert audio_client.mock_calls == calls
    assert stop_and_go.mock_calls == []
    reset_mocks()


@patch("hyperscribe.handlers.capture_view.Helper")
@patch("hyperscribe.handlers.capture_view.executor")
@patch("hyperscribe.handlers.capture_view.StopAndGo")
def test_render_effect_post(stop_and_go, executor, helper):
    def reset_mocks():
        stop_and_go.reset_mock()
        executor.reset_mock()
        helper.reset_mock()

    tested = helper_instance()

    effects = [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
    date_0 = datetime(2025, 8, 7, 18, 11, 21, 123456, tzinfo=timezone.utc)

    tests = [
        (
            effects,
            True,
            True,
            7,
            True,
            effects,
            [
                call.get("noteId"),
                call.get().paused_effects(),
                call.get().reset_paused_effect(),
                call.get().reset_paused_effect().set_delay(),
                call.get().reset_paused_effect().set_delay().save(),
            ],
            [call.submit(helper.with_cleanup.return_value, "patientId", "noteId")],
            [call.with_cleanup(tested.trigger_render)],
        ),
        (
            [],
            True,
            True,
            7,
            True,
            [],
            [
                call.get("noteId"),
                call.get().paused_effects(),
                call.get().is_running(),
            ],
            [],
            [],
        ),
        (
            [],
            False,
            True,
            7,
            True,
            [],
            [
                call.get("noteId"),
                call.get().paused_effects(),
                call.get().is_running(),
                call.get().consume_delay(),
                call.get().consume_next_waiting_cycles(True),
                call.get().cycle(),
            ],
            [call.submit(helper.with_cleanup.return_value, "patientId", "noteId", 7)],
            [call.with_cleanup(tested.run_commander)],
        ),
        (
            [],
            False,
            False,
            7,
            True,
            [],
            [
                call.get("noteId"),
                call.get().paused_effects(),
                call.get().is_running(),
                call.get().consume_delay(),
                call.get().consume_next_waiting_cycles(True),
                call.get().is_ended(),
                call.get().created(),
                call.get().cycle(),
            ],
            [call.submit(helper.with_cleanup.return_value, "patientId", "noteId", date_0, 7)],
            [call.with_cleanup(tested.run_reviewer)],
        ),
        (
            [],
            False,
            False,
            7,
            False,
            [],
            [
                call.get("noteId"),
                call.get().paused_effects(),
                call.get().is_running(),
                call.get().consume_delay(),
                call.get().consume_next_waiting_cycles(True),
                call.get().is_ended(),
            ],
            [],
            [],
        ),
    ]

    for idx, test in enumerate(tests):
        (
            paused_effects,
            is_running,
            consume,
            cycle,
            is_ended,
            expected,
            exp_calls,
            exp_executor,
            exp_helper,
        ) = test

        stop_and_go.get.return_value.paused_effects.side_effect = [paused_effects]
        stop_and_go.get.return_value.is_running.side_effect = [is_running]
        stop_and_go.get.return_value.consume_next_waiting_cycles.side_effect = [consume]
        stop_and_go.get.return_value.cycle.side_effect = [cycle]
        stop_and_go.get.return_value.is_ended.side_effect = [is_ended]
        stop_and_go.get.return_value.created.side_effect = [date_0]

        tested.request = SimpleNamespace(
            path_params={"patient_id": "patientId", "note_id": "noteId"},
            headers={"canvas-logged-in-user-id": "u"},
        )

        result = tested.render_effect_post()
        assert result == expected

        assert stop_and_go.mock_calls == exp_calls, f"---> {idx}"
        assert executor.mock_calls == exp_executor, f"---> {idx}"
        assert helper.mock_calls == exp_helper, f"---> {idx}"
        reset_mocks()


@patch("hyperscribe.handlers.capture_view.datetime", wraps=datetime)
@patch("hyperscribe.handlers.capture_view.AwsS3")
def test_feedback_post(aws_s3, mock_datetime):
    def reset_mocks():
        aws_s3.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 8, 29, 10, 14, 57, 123456, tzinfo=timezone.utc)

    tested = helper_instance()

    # missing feedback
    aws_s3.return_value.is_ready.side_effect = []
    mock_datetime.now.side_effect = []
    tested.request = SimpleNamespace(
        path_params={"patient_id": "p", "note_id": "n"},
        form_data=lambda: {},
    )
    result = tested.feedback_post()
    expected = [Response(content=b"Feedback cannot be empty", status_code=400)]
    assert result == expected

    assert aws_s3.mock_calls == []
    assert mock_datetime.mock_calls == []
    reset_mocks()

    # empty feedback
    aws_s3.return_value.is_ready.side_effect = []
    mock_datetime.now.side_effect = []
    tested.request = SimpleNamespace(
        path_params={"patient_id": "p", "note_id": "n"},
        form_data=lambda: {"feedback": StringFormPart(name="feedback", value="")},
    )
    result = tested.feedback_post()
    expected = [Response(content=b"Feedback cannot be empty", status_code=400)]
    assert result == expected

    assert aws_s3.mock_calls == []
    assert mock_datetime.mock_calls == []
    reset_mocks()

    # AWS credentials not provided
    aws_s3.return_value.is_ready.side_effect = [False]
    mock_datetime.now.side_effect = []
    tested.request = SimpleNamespace(
        path_params={"patient_id": "p", "note_id": "n"},
        form_data=lambda: {"feedback": StringFormPart(name="feedback", value="theFeedback")},
    )
    result = tested.feedback_post()
    expected = [Response(content=b"Storage is not made available", status_code=500)]
    assert result == expected

    calls = [
        call(
            AwsS3Credentials(
                aws_key="theKey",
                aws_secret="theSecret",
                region="theRegion",
                bucket="theBucketLogs",
            )
        ),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    assert mock_datetime.mock_calls == []
    reset_mocks()

    # all good
    aws_s3.return_value.is_ready.side_effect = [True]
    mock_datetime.now.side_effect = [date_0]

    tested.request = SimpleNamespace(
        path_params={"patient_id": "p", "note_id": "n"},
        form_data=lambda: {"feedback": StringFormPart(name="feedback", value="theFeedback")},
    )
    result = tested.feedback_post()
    expected = [Response(content=b"Feedback saved OK", status_code=201)]
    assert result == expected

    calls = [
        call(
            AwsS3Credentials(
                aws_key="theKey",
                aws_secret="theSecret",
                region="theRegion",
                bucket="theBucketLogs",
            )
        ),
        call().is_ready(),
        call().upload_text_to_s3("hyperscribe-customerIdentifier/feedback/n/20250829-101457", "theFeedback"),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls
    reset_mocks()


@patch.object(Command, "objects")
@patch.object(Note, "objects")
@patch("hyperscribe.handlers.capture_view.Progress")
@patch("hyperscribe.handlers.capture_view.LlmDecisionsReviewer")
@patch("hyperscribe.handlers.capture_view.ImplementedCommands")
@patch("hyperscribe.handlers.capture_view.log")
def test_run_reviewer(log, implemented_commands, llm_decision_reviewer, progress, note_db, command_db):
    def reset_mocks():
        log.reset_mock()
        implemented_commands.reset_mock()
        llm_decision_reviewer.reset_mock()
        progress.reset_mock()
        note_db.reset_mock()
        command_db.reset_mock()

    date_0 = datetime(2025, 8, 7, 18, 11, 21, 123456, tzinfo=timezone.utc)
    identification = IdentificationParameters(
        patient_uuid="patientId",
        note_uuid="noteId",
        provider_uuid="theProviderId",
        canvas_instance="customerIdentifier",
    )
    settings = Settings(
        api_signing_key="signingKey",
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        structured_rfv=True,
        audit_llm=False,
        max_workers=5,
        is_tuning=False,
        send_progress=True,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
    )
    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucketLogs")

    note_db.get.return_value.provider.id = "theProviderId"

    tested = helper_instance()
    # no LLM audit
    tested.secrets["AuditLLMDecisions"] = "n"
    tested.run_reviewer("patientId", "noteId", date_0, 7)

    assert log.mock_calls == []
    assert implemented_commands.mock_calls == []
    assert llm_decision_reviewer.mock_calls == []
    calls = [
        call.send_to_user(identification, settings, [ProgressMessage(message="finished", section="events:7")]),
        call.send_to_user(identification, settings, [ProgressMessage(message="EOF", section="events:7")]),
    ]
    assert progress.mock_calls == calls
    calls = [call.get(id="noteId")]
    assert note_db.mock_calls == calls
    assert command_db.mock_calls == []
    reset_mocks()

    # with LLM audit
    tested.secrets["AuditLLMDecisions"] = "y"
    settings = settings._replace(audit_llm=True)

    implemented_commands.schema_key2instruction.side_effect = [
        {
            "canvasCommandX": "theInstructionX",
            "canvasCommandY": "theInstructionY",
            "canvasCommandZ": "theInstructionZ",
            "Questionnaire": "Questionnaire",
        },
    ]
    command_db.filter.return_value.order_by.side_effect = [
        [
            Command(schema_key="canvasCommandX", id="uuid1"),
            Command(schema_key="canvasCommandY", id="uuid2"),
            Command(schema_key="canvasCommandY", id="uuid3"),
            Command(schema_key="Questionnaire", id="uuid4"),
        ],
    ]

    tested.run_reviewer("patientId", "noteId", date_0, 7)

    calls = [
        call.info("  => final audit started...noteId / 7 cycles"),
        call.info("  => final audit done (noteId / 7 cycles)"),
    ]
    assert log.mock_calls == calls
    calls = [call.schema_key2instruction()]
    assert implemented_commands.mock_calls == calls

    calls = [
        call.review(
            identification,
            settings,
            credentials,
            {
                "theInstructionX_00": "uuid1",
                "theInstructionY_01": "uuid2",
                "theInstructionY_02": "uuid3",
                "Questionnaire_03": "uuid4",
            },
            date_0,
            7,
        ),
    ]
    assert llm_decision_reviewer.mock_calls == calls
    calls = [
        call.send_to_user(identification, settings, [ProgressMessage(message="finished", section="events:7")]),
        call.send_to_user(identification, settings, [ProgressMessage(message="EOF", section="events:7")]),
    ]
    assert progress.mock_calls == calls
    calls = [call.get(id="noteId")]
    assert note_db.mock_calls == calls
    calls = [
        call.filter(patient__id="patientId", note__id="noteId", state="staged"),
        call.filter().order_by("dbid"),
    ]
    assert command_db.mock_calls == calls
    reset_mocks()


@patch.object(Note, "objects")
@patch("hyperscribe.handlers.capture_view.LlmTurnsStore")
@patch("hyperscribe.handlers.capture_view.Commander")
@patch("hyperscribe.handlers.capture_view.Progress")
@patch("hyperscribe.handlers.capture_view.MemoryLog")
@patch("hyperscribe.handlers.capture_view.StopAndGo")
@patch("hyperscribe.handlers.capture_view.log")
@patch.object(CaptureView, "trigger_render")
def test_run_commander(
    trigger_render,
    log,
    stop_and_go,
    memory_log,
    progress,
    commander,
    llm_turns_store,
    note_db,
    monkeypatch,
):
    monkeypatch.setattr("hyperscribe.handlers.capture_view.version", "theVersion")

    def reset_mocks():
        trigger_render.reset_mock()
        log.reset_mock()
        stop_and_go.reset_mock()
        memory_log.reset_mock()
        progress.reset_mock()
        commander.reset_mock()
        llm_turns_store.reset_mock()
        note_db.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="patientId",
        note_uuid="noteId",
        provider_uuid="theProviderId",
        canvas_instance="customerIdentifier",
    )
    settings = Settings(
        api_signing_key="signingKey",
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        structured_rfv=True,
        audit_llm=True,
        is_tuning=False,
        max_workers=5,
        send_progress=True,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
    )
    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucketLogs")
    effects = [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
    ]
    audio_client = AudioClient(
        base_url="https://audio",
        registration_key=None,
        instance="customerIdentifier",
        instance_key="shared",
    )

    tested = helper_instance()
    # all good
    progress_msg = [ProgressMessage(section="events:4", message="waiting for the next cycle 8...")]
    tests = [
        (False, False, [], "=> go to next iteration (8)", progress_msg),
        (True, False, [], None, None),
        (True, False, ["effect"], "=> go to next iteration (8)", progress_msg),
        (False, True, [], "=> go to next iteration (8)", progress_msg),
        (True, True, [], None, None),
    ]
    for is_ended, is_paused, waiting_cycles, exp_log_msg, exp_progress_msg in tests:
        note_db.get.return_value.provider.id = "theProviderId"
        commander.compute_audio.side_effect = [(False, effects)]
        stop_and_go.get.return_value.is_ended.side_effect = [is_ended]
        stop_and_go.get.return_value.is_paused.side_effect = [is_paused]
        stop_and_go.get.return_value.waiting_cycles.side_effect = [waiting_cycles]

        tested.run_commander("patientId", "noteId", 7)

        calls = [call("patientId", "noteId")]
        assert trigger_render.mock_calls == calls
        calls = []
        if exp_log_msg:
            calls = [call.info(exp_log_msg)]
        assert log.mock_calls == calls
        calls = [
            call.get("noteId"),
            call.get().set_cycle(7),
            call.get().set_cycle().set_running(True),
            call.get().set_cycle().set_running().save(),
            call.get("noteId"),
            call.get().add_paused_effects(effects),
            call.get().add_paused_effects().save(),
            call.get().waiting_cycles(),
        ]
        if not waiting_cycles:
            calls.append(call.get().is_ended())

        calls.extend(
            [
                call.get("noteId"),
                call.get().set_running(False),
                call.get().set_running().save(),
            ]
        )

        assert stop_and_go.mock_calls == calls
        calls = [
            call.instance(identification, "main", credentials),
            call.instance().output("SDK: theVersion - Text: theVendorTextLLM - Audio: theVendorAudioLLM - Workers: 5"),
            call.end_session("noteId"),
        ]
        assert memory_log.mock_calls == calls
        calls = []
        if not is_ended or waiting_cycles:
            calls = [call.send_to_user(identification, settings, exp_progress_msg)]
        assert progress.mock_calls == calls
        calls = [call.compute_audio(identification, settings, credentials, audio_client, 7)]
        assert commander.mock_calls == calls
        calls = [call.end_session("noteId")]
        assert llm_turns_store.mock_calls == calls
        calls = [call.get(id="noteId")]
        assert note_db.mock_calls == calls
        reset_mocks()

    # error in Commander.compute_audio
    note_db.get.return_value.provider.id = "theProviderId"
    commander.compute_audio.side_effect = [Exception("Test error")]

    tested.run_commander("patientId", "noteId", 7)

    calls = [call("patientId", "noteId")]
    assert trigger_render.mock_calls == calls
    calls = [
        call.info("************************"),
        call.info("Error while running commander: Test error"),
        call.info("************************"),
    ]
    assert log.mock_calls == calls
    calls = [
        call.get("noteId"),
        call.get().set_cycle(7),
        call.get().set_cycle().set_running(True),
        call.get().set_cycle().set_running().save(),
        call.get("noteId"),
        call.get().set_running(False),
        call.get().set_running().save(),
    ]
    assert stop_and_go.mock_calls == calls
    calls = [
        call.instance(identification, "main", credentials),
        call.instance().output("SDK: theVersion - Text: theVendorTextLLM - Audio: theVendorAudioLLM - Workers: 5"),
    ]
    assert memory_log.mock_calls == calls
    assert progress.mock_calls == []
    calls = [call.compute_audio(identification, settings, credentials, audio_client, 7)]
    assert commander.mock_calls == calls
    assert llm_turns_store.mock_calls == []
    calls = [call.get(id="noteId")]
    assert note_db.mock_calls == calls
    reset_mocks()
