from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.case_builders.builder_from_mp3 import BuilderFromMp3
from evaluations.structures.evaluation_case import EvaluationCase


def test_class():
    tested = BuilderFromMp3
    assert issubclass(tested, BuilderBase)


@patch("evaluations.case_builders.builder_from_mp3.ArgumentParser")
def test__parameters(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    tested = BuilderFromMp3

    argument_parser.return_value.parse_args.side_effect = ["parse_args called"]
    result = tested._parameters()
    expected = "parse_args called"
    assert result == expected

    calls = [
        call(description="Build the files of the evaluation tests against a patient based on the provided files"),
        call().add_argument("--patient", type=BuilderFromMp3.validate_patient, required=True, help="Patient UUID"),
        call().add_argument("--case", type=str, required=True, help="Evaluation case"),
        call().add_argument("--group", type=str, help="Group of the case", default="common"),
        call().add_argument("--type", type=str, choices=["situational", "general"], help="Type of the case: situational, general", default="general"),
        call().add_argument("--mp3", required=True, nargs="+", type=BuilderFromMp3.validate_files, help="List of MP3 files"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_from_mp3.Commander")
@patch("evaluations.case_builders.builder_from_mp3.AudioInterpreter")
@patch("evaluations.case_builders.builder_from_mp3.HelperEvaluation")
@patch("evaluations.case_builders.builder_from_mp3.StoreCases")
@patch.object(BuilderFromMp3, "_limited_cache_from")
def test__run(
        limited_cache_from,
        store_cases,
        helper,
        audio_interpreter,
        commander,
        monkeypatch,
        capsys,
):
    mock_files = [MagicMock(), MagicMock()]

    def reset_mocks():
        limited_cache_from.reset_mock()
        store_cases.reset_mock()
        helper.reset_mock()
        audio_interpreter.reset_mock()
        commander.reset_mock()
        for mock_file in mock_files:
            mock_file.reset_mock()

    tested = BuilderFromMp3

    monkeypatch.setenv("CANVAS_SDK_DB_HOST", "theSDKDbHost")
    limited_cache_from.return_value.to_json.side_effect = [{"key": "value"}]
    helper.settings.side_effect = ["theSettings"]
    helper.aws_s3_credentials.side_effect = ["theAwsS3Credentials"]
    for idx, mock_file in enumerate(mock_files):
        mock_file.name = f"audio file {idx}"
        mock_file.open.return_value.__enter__.return_value.read.side_effect = [f"audio content {idx}".encode('utf-8')]

    parameters = Namespace(
        patient="thePatientUuid",
        case="theCase",
        group="theGroup",
        type="theType",
        mp3=mock_files,
    )
    recorder = AuditorFile("theCase")
    tested._run(parameters, recorder, "theNoteUuid", "theProviderUuid")

    exp_out = [
        'Patient UUID: thePatientUuid',
        'Evaluation Case: theCase',
        'MP3 Files:',
        '- audio file 0',
        '- audio file 1',
        '',
    ]
    assert capsys.readouterr().out == "\n".join(exp_out)

    calls = [
        call(parameters, "theNoteUuid"),
        call().to_json(),
    ]
    assert limited_cache_from.mock_calls == calls
    calls = [call.upsert(EvaluationCase(
        environment="theSDKDbHost",
        patient_uuid="thePatientUuid",
        limited_cache='{"key": "value"}',
        case_name="theCase",
        case_group="theGroup",
        case_type="theType",
        description="theCase",
    ))]
    assert store_cases.mock_calls == calls
    calls = [
        call.settings(),
        call.aws_s3_credentials(),
    ]
    assert helper.mock_calls == calls
    calls = [call(
        "theSettings",
        "theAwsS3Credentials",
        limited_cache_from.return_value,
        "thePatientUuid",
        "theNoteUuid",
        "theProviderUuid",
    )]
    assert audio_interpreter.mock_calls == calls
    calls = [call.audio2commands(
        recorder,
        [b'audio content 0', b'audio content 1'],
        audio_interpreter.return_value,
        [],
    )]
    assert commander.mock_calls == calls
    calls = [
        call.open('rb'),
        call.open().__enter__(),
        call.open().__enter__().read(),
        call.open().__exit__(None, None, None),
    ]
    for mock_file in mock_files:
        assert mock_file.mock_calls == calls

    reset_mocks()
