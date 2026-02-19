import re
from datetime import timezone, datetime
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import patch, call, MagicMock

import pytest
from canvas_generated.messages.effects_pb2 import Effect
from canvas_sdk.effects.simple_api import Response, HTMLResponse, JSONResponse
from canvas_sdk.handlers.simple_api import SimpleAPI, Credentials
from canvas_sdk.handlers.simple_api.api import StringFormPart
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.note import Note

from hyperscribe.handlers.capture_view import CaptureView
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.custom_prompt import CustomPrompt
from hyperscribe.structures.customization import Customization
from hyperscribe.structures.default_tab import DefaultTab
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.notion_feedback_record import NotionFeedbackRecord
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
        "NotionAPIKey": "theNotionAPIKey",
        "NotionFeedbackDatabaseId": "theNotionFeedbackDatabaseId",
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

    authenticator.presigned_url_no_params.side_effect = ["theUrl"]
    helper.canvas_host.side_effect = ["theHost"]
    requests_post.side_effect = ["theResponse"]

    tested = helper_instance()
    result = tested.trigger_render("thePatientId", "theNoteId", "theUserId")
    expected = "theResponse"
    assert result == expected

    calls = [
        call.presigned_url_no_params(
            "signingKey",
            "theHost/plugin-io/api/hyperscribe/capture/render/thePatientId/theNoteId/theUserId",
        )
    ]
    assert authenticator.mock_calls == calls
    calls = [call.canvas_host("customerIdentifier")]
    assert helper.mock_calls == calls
    calls = [call("theUrl", headers={"Content-Type": "application/json"}, verify=True, timeout=None)]
    assert requests_post.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.handlers.capture_view.ProgressDisplay")
def test_session_progress_log(progress):
    def reset_mocks():
        progress.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="thePatientId",
        note_uuid="theNoteId",
        provider_uuid="",
        canvas_instance="customerIdentifier",
    )
    settings = Settings(
        api_signing_key="signingKey",
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        structured_rfv=True,
        audit_llm=True,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        max_workers=5,
        hierarchical_detection_threshold=5,
        send_progress=True,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    tested = helper_instance()
    tested.session_progress_log("thePatientId", "theNoteId", "theProgress")
    calls = [
        call.send_to_user(
            identification,
            settings,
            [ProgressMessage(message="theProgress", section="events:7")],
        )
    ]
    assert progress.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.handlers.capture_view.Customization")
@patch("hyperscribe.handlers.capture_view.Helper")
@patch("hyperscribe.handlers.capture_view.StopAndGo")
@patch("hyperscribe.handlers.capture_view.render_to_string")
@patch("hyperscribe.handlers.capture_view.Authenticator")
def test_capture_get(authenticator, render_to_string, stop_and_go, helper, customization):
    mock_stop_and_go = MagicMock()

    def reset_mocks():
        authenticator.reset_mock()
        render_to_string.reset_mock()
        stop_and_go.reset_mock()
        helper.reset_mock()
        customization.reset_mock()
        mock_stop_and_go.reset_mock()

    render_to_string.side_effect = ["<html/>"]
    helper.canvas_ws_host.side_effect = ["theWsHost"]
    customization.customizations.side_effect = [Customization(ui_default_tab=DefaultTab.ACTIVITY, custom_prompts=[])]
    authenticator.presigned_url.side_effect = ["Url1"]
    authenticator.presigned_url_no_params.side_effect = ["Url2", "Url3", "Url4", "Url5", "Url6", "Url7", "Url8", "Url9"]
    mock_stop_and_go.is_ended.side_effect = [False]
    mock_stop_and_go.is_paused.side_effect = [False, False]
    mock_stop_and_go.cycle.side_effect = [7]
    stop_and_go.get.side_effect = [mock_stop_and_go]

    tested = helper_instance()
    tested.request = SimpleNamespace(
        path_params={"patient_id": "the-00-patient", "note_id": "the-00-note", "note_reference": "4571"},
        query_params={},
        headers={"canvas-logged-in-user-id": "the-00-user"},
    )

    result = tested.capture_get()
    expected = [HTMLResponse(content="<html/>", status_code=HTTPStatus(200))]
    assert result == expected

    calls = [
        call.presigned_url("signingKey", "/plugin-io/api/hyperscribe/progress", {"note_id": "the-00-note"}),
        call.presigned_url_no_params(
            "signingKey",
            "/plugin-io/api/hyperscribe/capture/new-session/the-00-patient/the-00-note",
        ),
        call.presigned_url_no_params(
            "signingKey",
            "/plugin-io/api/hyperscribe/capture/idle/the-00-patient/the-00-note/pause",
        ),
        call.presigned_url_no_params(
            "signingKey",
            "/plugin-io/api/hyperscribe/capture/idle/the-00-patient/the-00-note/resume",
        ),
        call.presigned_url_no_params(
            "signingKey",
            "/plugin-io/api/hyperscribe/capture/idle/the-00-patient/the-00-note/end",
        ),
        call.presigned_url_no_params(
            "signingKey",
            "/plugin-io/api/hyperscribe/feedback/the-00-patient/the-00-note",
        ),
        call.presigned_url_no_params(
            "signingKey",
            "/plugin-io/api/hyperscribe/audio/the-00-patient/the-00-note",
        ),
        call.presigned_url_no_params(
            "signingKey",
            "/plugin-io/api/hyperscribe/transcript/the-00-patient/the-00-note",
        ),
        call.presigned_url_no_params(
            "signingKey",
            "/plugin-io/api/hyperscribe/draft/the-00-patient/the-00-note",
        ),
    ]
    assert authenticator.mock_calls == calls
    calls = [
        call(
            "templates/hyperscribe.html",
            {
                "patientUuid": "the-00-patient",
                "noteUuid": "the-00-note",
                "noteReference": "4571",
                "userUuid": "the-00-user",
                "interval": 5,
                "endFlag": "EOF",
                "wsProgressURL": "theWsHost/plugin-io/ws/hyperscribe/progress_the00note/",
                "progressURL": "Url1",
                "newSessionURL": "Url2",
                "pauseSessionURL": "Url3",
                "resumeSessionURL": "Url4",
                "endSessionURL": "Url5",
                "feedbackURL": "Url6",
                "saveAudioURL": "Url7",
                "saveTranscriptURL": "Url8",
                "draftTranscriptURL": "Url9",
                "isEnded": False,
                "isPaused": False,
                "chunkId": 6,
                "uiDefaultTab": "activity",
            },
        ),
    ]
    assert render_to_string.mock_calls == calls
    calls = [call.get("the-00-note")]
    assert stop_and_go.mock_calls == calls
    calls = [
        call.is_ended(),
        call.is_paused(),
        call.cycle(),
        call.is_paused(),
    ]
    assert mock_stop_and_go.mock_calls == calls
    calls = [call.canvas_ws_host("customerIdentifier")]
    assert helper.mock_calls == calls
    calls = [
        call.customizations(
            AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucketLogs"),
            "customerIdentifier",
            "the-00-user",
        )
    ]
    assert customization.mock_calls == calls
    reset_mocks()


@patch.object(CaptureView, "session_progress_log")
def test_new_session_post(session_progress_log):
    def reset_mocks():
        session_progress_log.reset_mock()

    tested = helper_instance()
    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        headers={"canvas-logged-in-user-id": "theUserId"},
    )

    result = tested.new_session_post()
    assert result == []

    calls = [call("thePatientId", "theNoteId", "started")]
    assert session_progress_log.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.handlers.capture_view.StopAndGo")
@patch.object(CaptureView, "session_progress_log")
def test_idle_session_post(session_progress_log, stop_and_go):
    def reset_mocks():
        session_progress_log.reset_mock()
        stop_and_go.reset_mock()

    tested = helper_instance()

    tests = [
        (
            "end",
            False,
            False,
            [call("thePatientId", "theNoteId", "stopped")],
            [
                call.get("theNoteId"),
                call.get().is_ended(),
                call.get().set_ended(True),
                call.get().set_ended().save(),
            ],
        ),
        (
            "end",
            True,
            False,
            [],
            [
                call.get("theNoteId"),
                call.get().is_ended(),
                call.get().is_paused(),
                call.get().is_paused(),
            ],
        ),
        (
            "pause",
            False,
            True,
            [],
            [
                call.get("theNoteId"),
                call.get().is_ended(),
                call.get().is_paused(),
                call.get().is_paused(),
            ],
        ),
        (
            "pause",
            False,
            False,
            [call("thePatientId", "theNoteId", "paused")],
            [
                call.get("theNoteId"),
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
            [call("thePatientId", "theNoteId", "resumed")],
            [
                call.get("theNoteId"),
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
            [],
            [
                call.get("theNoteId"),
                call.get().is_ended(),
                call.get().is_paused(),
                call.get().is_paused(),
            ],
        ),
    ]
    for action, is_ended, is_paused, exp_progress_calls, exp_stop_and_go_calls in tests:
        stop_and_go.get.return_value.is_ended.side_effect = [is_ended]
        stop_and_go.get.return_value.is_paused.side_effect = [is_paused, is_paused]

        tested.request = SimpleNamespace(
            path_params={"patient_id": "thePatientId", "note_id": "theNoteId", "action": action},
            headers={"canvas-logged-in-user-id": "theUserId"},
        )
        result = tested.idle_session_post()
        assert result == []

        assert session_progress_log.mock_calls == exp_progress_calls
        assert stop_and_go.mock_calls == exp_stop_and_go_calls
        reset_mocks()


@patch("hyperscribe.handlers.capture_view.log")
@patch("hyperscribe.handlers.capture_view.WebmPrefix")
@patch.object(CaptureView, "_add_cycle")
def test_audio_chunk_post(add_cycle, webm_prefix, log):
    def reset_mocks():
        add_cycle.reset_mock()
        webm_prefix.reset_mock()
        log.reset_mock()

    tested = helper_instance()
    # missing file part
    add_cycle.side_effect = []
    webm_prefix.side_effect = []
    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {},
    )
    result = tested.audio_chunk_post()
    expected = [Response(b"No audio file part in the request", HTTPStatus(400))]
    assert result == expected

    assert add_cycle.mock_calls == []
    assert webm_prefix.mock_calls == []
    assert log.mock_calls == []
    reset_mocks()

    # non-file part
    add_cycle.side_effect = []
    webm_prefix.side_effect = []
    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {"audio": SimpleNamespace(is_file=lambda: False)},
    )
    result = tested.audio_chunk_post()
    expected = [Response(b"The audio form part is not a file", HTTPStatus(422))]
    assert result == expected

    assert add_cycle.mock_calls == []
    assert webm_prefix.mock_calls == []
    assert log.mock_calls == []
    reset_mocks()

    # valid form
    # -- first chunk
    add_cycle.side_effect = [[Response(b"Good", HTTPStatus(200))]]
    webm_prefix.side_effect = []
    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {
            "audio": SimpleNamespace(
                is_file=lambda: True,
                name="audio",
                filename="chunk_000_other",
                content=b"theAudio",
                content_type="audio/test",
            )
        },
    )
    result = tested.audio_chunk_post()
    expected = [Response(b"Good", HTTPStatus(200))]
    assert result == expected

    calls = [call(b"theAudio", "audio/test")]
    assert add_cycle.mock_calls == calls
    assert webm_prefix.mock_calls == []
    calls = [
        call.info("audio_form_part.name: audio"),
        call.info("audio_form_part.filename: chunk_000_other"),
        call.info("len(audio_form_part.content): 8"),
        call.info("audio_form_part.content_type: audio/test"),
    ]
    assert log.mock_calls == calls
    reset_mocks()
    # -- later chunk
    add_cycle.side_effect = [[Response(b"Good", HTTPStatus(200))]]
    webm_prefix.add_prefix.side_effect = [b"thePrefixedAudio"]
    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {
            "audio": SimpleNamespace(
                is_file=lambda: True,
                name="audio",
                filename="chunk_123_other",
                content=b"theAudio",
                content_type="audio/test",
            )
        },
    )
    result = tested.audio_chunk_post()
    expected = [Response(b"Good", HTTPStatus(200))]
    assert result == expected

    calls = [call(b"thePrefixedAudio", "audio/test")]
    assert add_cycle.mock_calls == calls
    calls = [call.add_prefix(b"theAudio")]
    assert webm_prefix.mock_calls == calls
    calls = [
        call.info("audio_form_part.name: audio"),
        call.info("audio_form_part.filename: chunk_123_other"),
        call.info("len(audio_form_part.content): 8"),
        call.info("audio_form_part.content_type: audio/test"),
    ]
    assert log.mock_calls == calls
    reset_mocks()


@patch.object(CaptureView, "_add_cycle")
def test_transcript_chunk_post(add_cycle):
    def reset_mocks():
        add_cycle.reset_mock()

    tested = helper_instance()
    add_cycle.side_effect = [[Response(b"Good", HTTPStatus(200))]]
    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {"transcript": SimpleNamespace(value="theTranscript")},
    )
    result = tested.transcript_chunk_post()
    expected = [Response(b"Good", HTTPStatus(200))]
    assert result == expected

    calls = [call(b"theTranscript", "text/plain")]
    assert add_cycle.mock_calls == calls
    reset_mocks()


def test__draft_key():
    tested = helper_instance()
    tested.request = SimpleNamespace(path_params={"patient_id": "patientId", "note_id": "noteId"})
    result = tested._draft_key()
    expected = "draft_patientId_noteId"
    assert result == expected


@patch("hyperscribe.handlers.capture_view.get_cache")
def test_draft_chunk_post(get_cache):
    def reset_mocks():
        get_cache.reset_mock()

    tested = helper_instance()
    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {"transcript": SimpleNamespace(value="theTranscript")},
    )
    result = tested.draft_chunk_post()
    expected = [Response(status_code=HTTPStatus(201))]
    assert result == expected

    calls = [
        call(),
        call().set("draft_thePatientId_theNoteId", "theTranscript"),
    ]
    assert get_cache.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.handlers.capture_view.get_cache")
def test_draft_chunk_get(get_cache):
    def reset_mocks():
        get_cache.reset_mock()

    get_cache.return_value.get.side_effect = ["theTranscript"]
    tested = helper_instance()
    tested.request = SimpleNamespace(path_params={"patient_id": "thePatientId", "note_id": "theNoteId"})
    result = tested.draft_chunk_get()
    expected = [
        JSONResponse(
            content={"draft": "theTranscript"},
            status_code=HTTPStatus(200),
        )
    ]
    assert result == expected

    calls = [
        call(),
        call().get("draft_thePatientId_theNoteId"),
    ]
    assert get_cache.mock_calls == calls
    reset_mocks()


@patch.object(Note, "objects")
@patch("hyperscribe.handlers.capture_view.log")
@patch("hyperscribe.handlers.capture_view.AwsS3")
@patch("hyperscribe.handlers.capture_view.StopAndGo")
@patch("hyperscribe.handlers.capture_view.CycleData")
@patch("hyperscribe.handlers.capture_view.Helper")
@patch("hyperscribe.handlers.capture_view.executor")
def test__add_cycle(executor, helper, cycle_data, stop_and_go, aws_s3, log, note_db):
    stop_and_go_not_running = MagicMock(is_running=lambda: False, waiting_cycles=lambda: [21])
    stop_and_go_is_running = MagicMock(is_running=lambda: True, waiting_cycles=lambda: [27, 28])

    def reset_mocks():
        executor.reset_mock()
        helper.reset_mock()
        cycle_data.reset_mock()
        stop_and_go.reset_mock()
        aws_s3.reset_mock()
        log.reset_mock()
        note_db.reset_mock()
        stop_and_go_not_running.reset_mock()
        stop_and_go_is_running.reset_mock()

    aws_s3_credentials = AwsS3Credentials(
        aws_key="theKey",
        aws_secret="theSecret",
        region="theRegion",
        bucket="theBucketLogs",
    )
    identification = IdentificationParameters(
        patient_uuid="thePatientId",
        note_uuid="theNoteId",
        provider_uuid="theProviderId",
        canvas_instance="customerIdentifier",
    )

    tested = helper_instance()
    # failed AWS S3 upload
    # -- valid response from AWS S3
    cycle_data.s3_key_path.side_effect = ["theS3Path"]
    stop_and_go.get.side_effect = [stop_and_go_not_running]
    aws_s3.return_value.upload_binary_to_s3.side_effect = [SimpleNamespace(content=b"theProblem", status_code=501)]
    note_db.get.side_effect = [SimpleNamespace(provider=SimpleNamespace(id="theProviderId"))]

    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {},
    )
    result = tested._add_cycle(b"theContent", "content/type")
    expected = [Response(b"theProblem", HTTPStatus(501))]
    assert result == expected

    assert executor.mock_calls == []
    assert helper.mock_calls == []
    calls = [call.s3_key_path(identification, 21)]
    assert cycle_data.mock_calls == calls
    calls = [call.get("theNoteId")]
    assert stop_and_go.mock_calls == calls
    calls = [
        call(aws_s3_credentials),
        call().upload_binary_to_s3("theS3Path", b"theContent", "content/type"),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call.info("Failed to save chunk 21 with status 501: b'theProblem'")]
    assert log.mock_calls == calls
    calls = [call.get(id="theNoteId")]
    assert note_db.mock_calls == calls
    calls = [
        call.add_waiting_cycle(),
        call.add_waiting_cycle().save(),
    ]
    assert stop_and_go_not_running.mock_calls == calls
    assert stop_and_go_is_running.mock_calls == []
    reset_mocks()
    # -- invalid response from AWS S3
    cycle_data.s3_key_path.side_effect = ["theS3Path"]
    stop_and_go.get.side_effect = [stop_and_go_not_running]
    aws_s3.return_value.upload_binary_to_s3.side_effect = [SimpleNamespace(content=None, status_code=None)]
    note_db.get.side_effect = [SimpleNamespace(provider=SimpleNamespace(id="theProviderId"))]

    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {},
    )
    result = tested._add_cycle(b"theContent", "content/type")
    expected = [Response(b"Failed to save chunk (AWS S3 failure)", HTTPStatus(503))]
    assert result == expected

    assert executor.mock_calls == []
    assert helper.mock_calls == []
    calls = [call.s3_key_path(identification, 21)]
    assert cycle_data.mock_calls == calls
    calls = [call.get("theNoteId")]
    assert stop_and_go.mock_calls == calls
    calls = [
        call(aws_s3_credentials),
        call().upload_binary_to_s3("theS3Path", b"theContent", "content/type"),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call.info("Failed to save chunk 21 with status None: None")]
    assert log.mock_calls == calls
    calls = [call.get(id="theNoteId")]
    assert note_db.mock_calls == calls
    calls = [
        call.add_waiting_cycle(),
        call.add_waiting_cycle().save(),
    ]
    assert stop_and_go_not_running.mock_calls == calls
    assert stop_and_go_is_running.mock_calls == []
    reset_mocks()
    # AWS S3 upload succeeded
    # -- commander not running
    cycle_data.s3_key_path.side_effect = ["theS3Path"]
    stop_and_go.get.side_effect = [stop_and_go_not_running]
    aws_s3.return_value.upload_binary_to_s3.side_effect = [SimpleNamespace(content=b"Good", status_code=200)]
    note_db.get.side_effect = [SimpleNamespace(provider=SimpleNamespace(id="theProviderId"))]

    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {},
        headers={"canvas-logged-in-user-id": "theUserId"},
    )
    result = tested._add_cycle(b"theContent", "content/type")
    expected = [Response(b"Chunk 21 saved OK", HTTPStatus(201))]
    assert result == expected

    calls = [call.submit(helper.with_cleanup.return_value, identification, "theUserId")]
    assert executor.mock_calls == calls
    calls = [call.with_cleanup(tested.run_commander)]
    assert helper.mock_calls == calls
    calls = [call.s3_key_path(identification, 21)]
    assert cycle_data.mock_calls == calls
    calls = [call.get("theNoteId")]
    assert stop_and_go.mock_calls == calls
    calls = [
        call(aws_s3_credentials),
        call().upload_binary_to_s3("theS3Path", b"theContent", "content/type"),
    ]
    assert aws_s3.mock_calls == calls
    assert log.mock_calls == []
    calls = [call.get(id="theNoteId")]
    assert note_db.mock_calls == calls
    calls = [
        call.add_waiting_cycle(),
        call.add_waiting_cycle().save(),
    ]
    assert stop_and_go_not_running.mock_calls == calls
    assert stop_and_go_is_running.mock_calls == []
    reset_mocks()
    # -- commander is running
    cycle_data.s3_key_path.side_effect = ["theS3Path"]
    stop_and_go.get.side_effect = [stop_and_go_is_running]
    aws_s3.return_value.upload_binary_to_s3.side_effect = [SimpleNamespace(content=b"Good", status_code=200)]
    note_db.get.side_effect = [SimpleNamespace(provider=SimpleNamespace(id="theProviderId"))]

    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {},
        headers={"canvas-logged-in-user-id": "theUserId"},
    )
    result = tested._add_cycle(b"theContent", "content/type")
    expected = [Response(b"Chunk 28 saved OK", HTTPStatus(201))]
    assert result == expected

    assert executor.mock_calls == []
    assert helper.mock_calls == []
    calls = [call.s3_key_path(identification, 28)]
    assert cycle_data.mock_calls == calls
    calls = [call.get("theNoteId")]
    assert stop_and_go.mock_calls == calls
    calls = [
        call(aws_s3_credentials),
        call().upload_binary_to_s3("theS3Path", b"theContent", "content/type"),
    ]
    assert aws_s3.mock_calls == calls
    assert log.mock_calls == []
    calls = [call.get(id="theNoteId")]
    assert note_db.mock_calls == calls
    assert stop_and_go_not_running.mock_calls == []
    calls = [
        call.add_waiting_cycle(),
        call.add_waiting_cycle().save(),
    ]
    assert stop_and_go_is_running.mock_calls == calls
    reset_mocks()
    # -- commander was running but add_waiting_cycle() detected stuck => auto-recover
    stop_and_go_was_stuck = MagicMock(is_running=lambda: False, waiting_cycles=lambda: [21, 22, 23, 24, 25])

    cycle_data.s3_key_path.side_effect = ["theS3Path"]
    stop_and_go.get.side_effect = [stop_and_go_was_stuck]
    aws_s3.return_value.upload_binary_to_s3.side_effect = [SimpleNamespace(content=b"Good", status_code=200)]
    note_db.get.side_effect = [SimpleNamespace(provider=SimpleNamespace(id="theProviderId"))]

    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {},
        headers={"canvas-logged-in-user-id": "theUserId"},
    )
    result = tested._add_cycle(b"theContent", "content/type")
    expected = [Response(b"Chunk 25 saved OK", HTTPStatus(201))]
    assert result == expected

    calls = [call.submit(helper.with_cleanup.return_value, identification, "theUserId")]
    assert executor.mock_calls == calls
    calls = [call.with_cleanup(tested.run_commander)]
    assert helper.mock_calls == calls
    calls = [call.s3_key_path(identification, 25)]
    assert cycle_data.mock_calls == calls
    calls = [call.get("theNoteId")]
    assert stop_and_go.mock_calls == calls
    calls = [
        call(aws_s3_credentials),
        call().upload_binary_to_s3("theS3Path", b"theContent", "content/type"),
    ]
    assert aws_s3.mock_calls == calls
    assert log.mock_calls == []
    calls = [call.get(id="theNoteId")]
    assert note_db.mock_calls == calls
    calls = [
        call.add_waiting_cycle(),
        call.add_waiting_cycle().save(),
    ]
    assert stop_and_go_was_stuck.mock_calls == calls
    assert stop_and_go_not_running.mock_calls == []
    assert stop_and_go_is_running.mock_calls == []
    reset_mocks()


@patch("hyperscribe.handlers.capture_view.StopAndGo")
def test_render_effect_post(stop_and_go):
    def reset_mocks():
        stop_and_go.reset_mock()

    tested = helper_instance()
    tested.request = SimpleNamespace(
        path_params={"patient_id": "patientId", "note_id": "noteId", "user_id": "theUserId"},
        headers={"canvas-logged-in-user-id": "wrongUserId"},
    )

    effects = [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
    # there are paused effects
    stop_and_go.get.return_value.paused_effects.side_effect = [effects]
    result = tested.render_effect_post()
    assert result == effects

    calls = [
        call.get("noteId"),
        call.get().paused_effects(),
        call.get().reset_paused_effect(),
        call.get().reset_paused_effect().set_delay(),
        call.get().reset_paused_effect().set_delay().save(),
    ]
    assert stop_and_go.mock_calls == calls
    reset_mocks()

    # there are NO paused effects
    stop_and_go.get.return_value.paused_effects.side_effect = [[]]

    result = tested.render_effect_post()
    assert result == []

    calls = [
        call.get("noteId"),
        call.get().paused_effects(),
    ]
    assert stop_and_go.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.handlers.capture_view.datetime", wraps=datetime)
@patch("hyperscribe.handlers.capture_view.requests_post")
@patch("hyperscribe.handlers.capture_view.AwsS3")
def test_feedback_post(aws_s3, requests_post, mock_datetime):
    def reset_mocks():
        aws_s3.reset_mock()
        requests_post.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 8, 29, 10, 14, 57, 123456, tzinfo=timezone.utc)

    tested = helper_instance()

    # missing feedback
    aws_s3.return_value.is_ready.side_effect = []
    mock_datetime.now.side_effect = []
    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {},
    )
    result = tested.feedback_post()
    expected = [Response(content=b"Feedback cannot be empty", status_code=HTTPStatus.BAD_REQUEST)]
    assert result == expected

    assert aws_s3.mock_calls == []
    assert mock_datetime.mock_calls == []
    reset_mocks()

    # empty feedback
    aws_s3.return_value.is_ready.side_effect = []
    mock_datetime.now.side_effect = []
    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {"feedback": StringFormPart(name="feedback", value="")},
    )
    result = tested.feedback_post()
    expected = [Response(content=b"Feedback cannot be empty", status_code=HTTPStatus.BAD_REQUEST)]
    assert result == expected

    assert aws_s3.mock_calls == []
    assert mock_datetime.mock_calls == []
    reset_mocks()

    # AWS credentials not provided
    aws_s3.return_value.is_ready.side_effect = [False]
    mock_datetime.now.side_effect = []
    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {"feedback": StringFormPart(name="feedback", value="theFeedback")},
    )
    result = tested.feedback_post()
    expected = [Response(content=b"Storage is not made available", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
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
    mock_response = SimpleNamespace(status_code=200)
    requests_post.side_effect = [mock_response]

    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {"feedback": StringFormPart(name="feedback", value="theFeedback")},
    )
    result = tested.feedback_post()
    expected = [Response(content=b"Feedback saved OK", status_code=HTTPStatus.CREATED)]
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
        call().upload_text_to_s3(
            "hyperscribe-customerIdentifier/feedback/theNoteId/20250829-101457",
            "theFeedback",
        ),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls
    expected_data = NotionFeedbackRecord(
        instance="customerIdentifier",
        note_uuid="theNoteId",
        date_time=date_0.strftime("%Y%m%d-%H%M%S"),
        feedback="theFeedback",
    ).to_json("theNotionFeedbackDatabaseId")
    calls = [
        call(
            Constants.VENDOR_NOTION_API_BASE_URL,
            headers={
                "Authorization": "Bearer theNotionAPIKey",
                "Content-Type": "application/json",
                "Notion-Version": Constants.VENDOR_NOTION_API_VERSION,
            },
            data=expected_data,
        )
    ]
    assert requests_post.mock_calls == calls
    reset_mocks()

    # Notion API failure
    aws_s3.return_value.is_ready.side_effect = [True]
    mock_datetime.now.side_effect = [date_0]
    mock_response = SimpleNamespace(status_code=500, text="Internal Server Error")
    requests_post.side_effect = [mock_response]

    tested.request = SimpleNamespace(
        path_params={"patient_id": "thePatientId", "note_id": "theNoteId"},
        form_data=lambda: {"feedback": StringFormPart(name="feedback", value="theFeedback")},
    )

    # Expect RuntimeError to be raised
    with pytest.raises(
        RuntimeError,
        match="Feedback failed to save via Notion API, status 500, text: Internal Server Error",
    ):
        tested.feedback_post()
    reset_mocks()


@patch.object(Command, "objects")
@patch("hyperscribe.handlers.capture_view.ProgressDisplay")
@patch("hyperscribe.handlers.capture_view.LlmDecisionsReviewer")
@patch("hyperscribe.handlers.capture_view.ImplementedCommands")
@patch("hyperscribe.handlers.capture_view.log")
@patch.object(CaptureView, "session_progress_log")
def test_run_reviewer(session_progress_log, log, implemented_commands, llm_decision_reviewer, progress, command_db):
    def reset_mocks():
        session_progress_log.reset_mock()
        log.reset_mock()
        implemented_commands.reset_mock()
        llm_decision_reviewer.reset_mock()
        progress.reset_mock()
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
        reasoning_llm=False,
        max_workers=5,
        custom_prompts=[],
        is_tuning=False,
        hierarchical_detection_threshold=5,
        send_progress=True,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    credentials = AwsS3Credentials(
        aws_key="theKey",
        aws_secret="theSecret",
        region="theRegion",
        bucket="theBucketLogs",
    )

    tested = helper_instance()
    # no LLM audit
    tested.secrets["AuditLLMDecisions"] = "theNoteId"
    tested.run_reviewer(identification, date_0, 7)

    calls = [call("patientId", "noteId", "EOF")]
    assert session_progress_log.mock_calls == calls
    assert log.mock_calls == []
    assert implemented_commands.mock_calls == []
    assert llm_decision_reviewer.mock_calls == []
    assert progress.mock_calls == []
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

    tested.run_reviewer(identification, date_0, 7)

    calls = [
        call.info("  => final audit started...noteId / 7 cycles"),
        call.info("  => final audit done (noteId / 7 cycles)"),
    ]
    assert log.mock_calls == calls
    calls = [call.schema_key2instruction()]
    assert implemented_commands.mock_calls == calls

    calls = [call("patientId", "noteId", "EOF")]
    assert session_progress_log.mock_calls == calls
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
    assert progress.mock_calls == []
    calls = [
        call.filter(patient__id="patientId", note__id="noteId", state="staged"),
        call.filter().order_by("dbid"),
    ]
    assert command_db.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.handlers.capture_view.Customization")
@patch("hyperscribe.handlers.capture_view.LlmTurnsStore")
@patch("hyperscribe.handlers.capture_view.Commander")
@patch("hyperscribe.handlers.capture_view.ProgressDisplay")
@patch("hyperscribe.handlers.capture_view.MemoryLog")
@patch("hyperscribe.handlers.capture_view.StopAndGo")
@patch("hyperscribe.handlers.capture_view.log")
@patch.object(CaptureView, "session_progress_log")
@patch.object(CaptureView, "run_reviewer")
@patch.object(CaptureView, "trigger_render")
def test_run_commander(
    trigger_render,
    run_reviewer,
    session_progress_log,
    log,
    stop_and_go,
    memory_log,
    progress,
    commander,
    llm_turns_store,
    customization,
    monkeypatch,
):
    monkeypatch.setattr("hyperscribe.handlers.capture_view.version", "theVersion")

    def reset_mocks():
        trigger_render.reset_mock()
        run_reviewer.reset_mock()
        session_progress_log.reset_mock()
        log.reset_mock()
        stop_and_go.reset_mock()
        memory_log.reset_mock()
        progress.reset_mock()
        commander.reset_mock()
        llm_turns_store.reset_mock()
        customization.reset_mock()

    date_0 = datetime(2025, 12, 5, 13, 35, 46, tzinfo=timezone.utc)
    identification = IdentificationParameters(
        patient_uuid="patientId",
        note_uuid="noteId",
        provider_uuid="theProviderId",
        canvas_instance="customerIdentifier",
    )
    settings = [
        Settings(
            api_signing_key="signingKey",
            llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
            llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
            structured_rfv=True,
            audit_llm=True,
            reasoning_llm=False,
            custom_prompts=[
                CustomPrompt(command="theCommand1", prompt="thePrompt1", active=True),
                CustomPrompt(command="theCommand2", prompt="thePrompt2", active=False),
                CustomPrompt(command="theCommand3", prompt="thePrompt3", active=True),
            ],
            is_tuning=False,
            max_workers=5,
            hierarchical_detection_threshold=5,
            send_progress=True,
            commands_policy=AccessPolicy(policy=False, items=[]),
            staffers_policy=AccessPolicy(policy=False, items=[]),
            trial_staffers_policy=AccessPolicy(policy=True, items=[]),
            cycle_transcript_overlap=37,
        ),
        Settings(
            api_signing_key="signingKey",
            llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
            llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
            structured_rfv=True,
            audit_llm=True,
            reasoning_llm=False,
            custom_prompts=[CustomPrompt(command="theCommand1", prompt="thePrompt1", active=True)],
            is_tuning=False,
            max_workers=5,
            hierarchical_detection_threshold=5,
            send_progress=True,
            commands_policy=AccessPolicy(policy=False, items=[]),
            staffers_policy=AccessPolicy(policy=False, items=[]),
            trial_staffers_policy=AccessPolicy(policy=True, items=[]),
            cycle_transcript_overlap=37,
        ),
    ]
    credentials = AwsS3Credentials(
        aws_key="theKey",
        aws_secret="theSecret",
        region="theRegion",
        bucket="theBucketLogs",
    )
    effects = [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
        Effect(type="LOG", payload="Log4"),
    ]

    tested = helper_instance()
    # all good
    # -- already running
    commander.compute_cycle.side_effect = []
    stop_and_go.get.return_value.is_running.side_effect = [True]

    tested.run_commander(identification, "theUserId")

    assert trigger_render.mock_calls == []
    assert run_reviewer.mock_calls == []
    assert session_progress_log.mock_calls == []
    assert log.mock_calls == []
    calls = [
        call.get("noteId"),
        call.get().is_running(),
    ]
    assert stop_and_go.mock_calls == calls
    assert memory_log.mock_calls == []
    assert progress.mock_calls == []
    assert commander.mock_calls == []
    assert llm_turns_store.mock_calls == []
    assert customization.mock_calls == []
    reset_mocks()

    # -- no exception
    tests = [
        (True, [call(identification, date_0, 5)], [call("patientId", "noteId", "finished")]),
        (False, [], []),
    ]
    for is_ended, exp_call_reviewed, exp_call_progress in tests:
        commander.compute_cycle.side_effect = [(False, effects[0:2]), (False, []), (False, effects[2:])]
        stop_and_go.get.return_value.is_running.side_effect = [False]
        stop_and_go.get.return_value.consume_next_waiting_cycles.side_effect = [True, True, True, False]
        stop_and_go.get.return_value.created.side_effect = [date_0]
        stop_and_go.get.return_value.cycle.side_effect = [2, 3, 4, 5]
        stop_and_go.get.return_value.is_ended.side_effect = [is_ended]
        customization.custom_prompts_as_secret.side_effect = [
            {
                "CustomPrompts": '[{"command":"theCommand1","prompt":"thePrompt1","active":true},'
                '{"command":"theCommand2","prompt":"thePrompt2","active":false},'
                '{"command":"theCommand3","prompt":"thePrompt3"}]'
            }
        ]

        tested.run_commander(identification, "theUserId")

        calls = [
            call("patientId", "noteId", "theUserId"),
            call("patientId", "noteId", "theUserId"),
        ]
        assert trigger_render.mock_calls == calls
        assert run_reviewer.mock_calls == exp_call_reviewed
        assert session_progress_log.mock_calls == exp_call_progress
        assert log.mock_calls == []
        calls = [
            call.get("noteId"),
            call.get().is_running(),
            call.get().set_running(True),
            call.get().set_running().save(),
            call.get("noteId"),
            call.get().consume_next_waiting_cycles(True),
            call.get().cycle(),
            call.get("noteId"),
            call.get().add_paused_effects(effects[0:2]),
            call.get().add_paused_effects().save(),
            call.get("noteId"),
            call.get().consume_next_waiting_cycles(True),
            call.get().cycle(),
            call.get("noteId"),
            call.get().consume_next_waiting_cycles(True),
            call.get().cycle(),
            call.get("noteId"),
            call.get().add_paused_effects(effects[2:]),
            call.get().add_paused_effects().save(),
            call.get("noteId"),
            call.get().consume_next_waiting_cycles(True),
            call.get("noteId"),
            call.get().set_running(False),
            call.get().set_running().save(),
            call.get().is_ended(),
        ]
        if is_ended:
            calls.extend(
                [
                    call.get().created(),
                    call.get().cycle(),
                ]
            )
        assert stop_and_go.mock_calls == calls
        calls = [
            call.instance(identification, "main", credentials),
            call.instance().output("SDK: theVersion - Text: theVendorTextLLM - Audio: theVendorAudioLLM - Workers: 5"),
            call.end_session("noteId"),
            call.end_session("noteId"),
            call.end_session("noteId"),
        ]
        assert memory_log.mock_calls == calls
        assert progress.mock_calls == []
        calls = [
            call.compute_cycle(identification, settings[0], credentials, 2),
            call.compute_cycle(identification, settings[0], credentials, 3),
            call.compute_cycle(identification, settings[0], credentials, 4),
        ]
        assert commander.mock_calls == calls
        calls = [
            call.end_session("noteId"),
            call.end_session("noteId"),
            call.end_session("noteId"),
        ]
        assert llm_turns_store.mock_calls == calls
        calls = [call.custom_prompts_as_secret(credentials, "customerIdentifier", "theUserId")]
        assert customization.mock_calls == calls
        reset_mocks()

    # error in Commander.compute_audio
    commander.compute_cycle.side_effect = [Exception("Test error")]
    stop_and_go.get.return_value.is_running.side_effect = [False]
    stop_and_go.get.return_value.consume_next_waiting_cycles.side_effect = [True]
    stop_and_go.get.return_value.cycle.side_effect = [7]
    stop_and_go.get.return_value.is_ended.side_effect = [False]
    customization.custom_prompts_as_secret.side_effect = [
        {"CustomPrompts": '[{"command":"theCommand1","prompt":"thePrompt1","active":true}]'}
    ]

    tested.run_commander(identification, "theUserId")

    assert trigger_render.mock_calls == []
    assert run_reviewer.mock_calls == []
    assert session_progress_log.mock_calls == []
    calls = [
        call.info("************************"),
        call.error("Error while running commander: Test error", exc_info=True),
        call.info("************************"),
    ]
    assert log.mock_calls == calls
    calls = [
        call.get("noteId"),
        call.get().is_running(),
        call.get().set_running(True),
        call.get().set_running().save(),
        call.get("noteId"),
        call.get().consume_next_waiting_cycles(True),
        call.get().cycle(),
        call.get("noteId"),
        call.get().set_running(False),
        call.get().set_running().save(),
        call.get().is_ended(),
    ]
    assert stop_and_go.mock_calls == calls
    calls = [
        call.instance(identification, "main", credentials),
        call.instance().output("SDK: theVersion - Text: theVendorTextLLM - Audio: theVendorAudioLLM - Workers: 5"),
    ]
    assert memory_log.mock_calls == calls
    assert progress.mock_calls == []
    calls = [call.compute_cycle(identification, settings[1], credentials, 7)]
    assert commander.mock_calls == calls
    assert llm_turns_store.mock_calls == []
    calls = [call.custom_prompts_as_secret(credentials, "customerIdentifier", "theUserId")]
    assert customization.mock_calls == calls
    reset_mocks()
