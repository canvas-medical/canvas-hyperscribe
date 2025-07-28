from argparse import Namespace
from unittest.mock import patch, call

from _pytest.capture import CaptureResult

from evaluations.case_builders.builder_audit_url import BuilderAuditUrl
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


@patch("evaluations.case_builders.builder_audit_url.ArgumentParser")
def test_parameters(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    tested = BuilderAuditUrl

    argument_parser.return_value.parse_args.side_effect = ["parse_args called"]
    result = tested._parameters()
    expected = "parse_args called"
    assert result == expected

    calls = [
        call(description="Generate the URL to access the audit logs."),
        call().add_argument("--audit", action="store_true"),
        call().add_argument("--patient", required=True, help="Patient UUID"),
        call().add_argument("--note", required=True, help="Note UUID"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch.object(BuilderAuditUrl, "presigned_url")
@patch.object(BuilderAuditUrl, "_parameters")
def test_run(parameters, presigned_url):
    def reset_mocks():
        parameters.reset_mock()
        presigned_url.reset_mock()

    tested = BuilderAuditUrl()
    parameters.side_effect = [Namespace(patient="thePatient", note="theNote")]
    result = tested.run()
    assert result is None
    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call("thePatient", "theNote")]
    assert presigned_url.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_audit_url.Authenticator")
@patch("evaluations.case_builders.builder_audit_url.HelperEvaluation")
@patch("evaluations.case_builders.builder_audit_url.AwsS3")
def test_presigned_url(aws_s3, helper, authenticator, capsys):
    def reset_mocks():
        aws_s3.reset_mock()
        helper.reset_mock()
        authenticator.reset_mock()

    aws_s3_credentials = AwsS3Credentials(
        aws_key="theKey",
        aws_secret="theSecret",
        region="theRegion",
        bucket="theBucket",
    )

    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        science_host="theScienceHost",
        ontologies_host="theOntologiesHost",
        pre_shared_key="thePreSharedKey",
        structured_rfv=True,
        audit_llm=False,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
    )

    tested = BuilderAuditUrl()

    # aws not ready
    aws_s3.return_value.is_ready.side_effect = [False]
    helper.aws_s3_credentials.side_effect = [aws_s3_credentials]
    helper.get_canvas_instance.side_effect = []
    authenticator.presigned_url.side_effect = []

    tested.presigned_url("thePatient", "theNote")

    exp_out = CaptureResult("audits cannot be seen with without proper AWS S3 credentials\n", "")
    assert capsys.readouterr() == exp_out

    calls = [call(aws_s3_credentials), call().is_ready()]
    assert aws_s3.mock_calls == calls
    calls = [call.aws_s3_credentials()]
    assert helper.mock_calls == calls
    calls = []
    assert authenticator.mock_calls == calls
    reset_mocks()

    # aws is ready
    aws_s3.return_value.is_ready.side_effect = [True]
    helper.aws_s3_credentials.side_effect = [aws_s3_credentials]
    helper.settings.side_effect = [settings]
    helper.get_canvas_host.side_effect = ["https://canvasInstance"]
    authenticator.presigned_url.side_effect = ["/presignedUrl"]

    tested.presigned_url("thePatient", "theNote")

    exp_out = CaptureResult(
        "\n".join(
            [
                "audits can be seen with:",
                "",
                "https://canvasInstance/presignedUrl",
                "",
                "to regenerate the URL, run the command:",
                " uv run python case_builder.py --audit --patient thePatient --note theNote",
                "",
                "",
            ],
        ),
        "",
    )
    assert capsys.readouterr() == exp_out

    calls = [call(aws_s3_credentials), call().is_ready()]
    assert aws_s3.mock_calls == calls
    calls = [call.aws_s3_credentials(), call.settings(), call.get_canvas_host()]
    assert helper.mock_calls == calls
    calls = [
        call.presigned_url(
            "theApiSigningKey",
            "/plugin-io/api/hyperscribe/reviewer",
            {"patient_id": "thePatient", "note_id": "theNote"},
        ),
    ]
    assert authenticator.mock_calls == calls
    reset_mocks()
