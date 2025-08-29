from unittest.mock import patch, call

from hyperscribe.libraries.auditor_base import AuditorBase
from hyperscribe.libraries.auditor_live import AuditorLive
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> AuditorLive:
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        structured_rfv=True,
        audit_llm=True,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
    )
    s3_credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    identification = IdentificationParameters(
        patient_uuid="thePatientUuid",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    )
    return AuditorLive(7, settings, s3_credentials, identification)


def test_class():
    tested = AuditorLive
    assert issubclass(tested, AuditorBase)


def test___init__():
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        structured_rfv=True,
        audit_llm=True,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
    )
    s3_credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    identification = IdentificationParameters(
        patient_uuid="thePatientUuid",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    )
    tests = [(-1, 0), (0, 0), (1, 1), (3, 3), (10, 10)]
    for cycle, exp_cycle in tests:
        tested = AuditorLive(cycle, settings, s3_credentials, identification)
        assert tested.cycle == exp_cycle
        assert tested.s3_credentials == s3_credentials
        assert tested.settings == settings
        assert tested.identification == identification


@patch("hyperscribe.libraries.auditor_live.AwsS3")
def test_identified_transcript(aws_s3):
    def reset_mocks():
        aws_s3.reset_mock()

    transcript = [
        Line(speaker="speaker1", text="textA"),
        Line(speaker="speaker2", text="textB"),
        Line(speaker="speaker1", text="textC"),
    ]
    tested = helper_instance()

    tests = [
        (
            True,
            [
                call(
                    AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
                ),
                call().is_ready(),
                call().upload_text_to_s3(
                    "hyperscribe-theCanvasInstance/transcripts/theNoteUuid/transcript_07.log",
                    "[\n  "
                    '{\n    "speaker": "speaker1",\n    "text": "textA"\n  },\n  '
                    '{\n    "speaker": "speaker2",\n    "text": "textB"\n  },\n  '
                    '{\n    "speaker": "speaker1",\n    "text": "textC"\n  }\n]',
                ),
            ],
        ),
        (
            False,
            [
                call(
                    AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
                ),
                call().is_ready(),
            ],
        ),
    ]
    for is_ready, exp_calls in tests:
        aws_s3.return_value.is_ready.side_effect = [is_ready]
        result = tested.identified_transcript([b"theAudio"], transcript)
        assert result is True
        assert aws_s3.mock_calls == exp_calls
        reset_mocks()


def test_found_instructions():
    tested = helper_instance()
    result = tested.found_instructions([], [], [])
    assert result is True


def test_computed_parameters():
    tested = helper_instance()
    result = tested.computed_parameters([])
    assert result is True


def test_computed_commands():
    tested = helper_instance()
    result = tested.computed_commands([])
    assert result is True


def test_computed_questionnaires():
    tested = helper_instance()
    result = tested.computed_questionnaires([], [], [])
    assert result is True
