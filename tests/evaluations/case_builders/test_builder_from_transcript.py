import json
from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.case_builders.builder_from_transcript import BuilderFromTranscript
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line


def test_class():
    tested = BuilderFromTranscript
    assert issubclass(tested, BuilderBase)


@patch("evaluations.case_builders.builder_from_transcript.ArgumentParser")
def test__parameters(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    tested = BuilderFromTranscript

    argument_parser.return_value.parse_args.side_effect = ["parse_args called"]
    result = tested._parameters()
    expected = "parse_args called"
    assert result == expected

    calls = [
        call(description="Build the files of the evaluation tests against a patient based on the provided files"),
        call().add_argument("--patient", type=BuilderFromTranscript.validate_patient, required=True, help="Patient UUID"),
        call().add_argument("--case", type=str, required=True, help="Evaluation case"),
        call().add_argument("--group", type=str, help="Group of the case", default="common"),
        call().add_argument("--type", type=str, choices=["situational", "general"], help="Type of the case: situational, general", default="general"),
        call().add_argument("--transcript", type=BuilderFromTranscript.validate_files, help="JSON file with transcript"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_from_transcript.Commander")
@patch("evaluations.case_builders.builder_from_transcript.AudioInterpreter")
@patch("evaluations.case_builders.builder_from_transcript.HelperEvaluation")
@patch("evaluations.case_builders.builder_from_transcript.StoreCases")
@patch.object(BuilderFromTranscript, "_limited_cache_from")
def test__run(
        limited_cache_from,
        store_cases,
        helper,
        audio_interpreter,
        commander,
        capsys,
):
    mock_file = MagicMock()

    def reset_mocks():
        limited_cache_from.reset_mock()
        store_cases.reset_mock()
        helper.reset_mock()
        audio_interpreter.reset_mock()
        commander.reset_mock()
        mock_file.reset_mock()

    tested = BuilderFromTranscript

    lines = [
        Line(speaker="speakerA", text="text1"),
        Line(speaker="speakerB", text="text2"),
        Line(speaker="speakerA", text="text3"),
    ]

    limited_cache_from.return_value.to_json.side_effect = [{"key": "value"}]
    helper.settings.side_effect = ["theSettings"]
    helper.aws_s3_credentials.side_effect = ["theAwsS3Credentials"]
    mock_file.name = "theFile"
    mock_file.open.return_value.__enter__.return_value.read.side_effect = [
        json.dumps([l.to_json() for l in lines]),
    ]

    parameters = Namespace(
        patient="thePatientUuid",
        case="theCase",
        group="theGroup",
        type="theType",
        transcript=mock_file,
    )
    recorder = AuditorFile("theCase")
    identification = IdentificationParameters(
        patient_uuid="thePatient",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    )
    tested._run(parameters, recorder, identification)

    exp_out = [
        'Patient UUID: thePatientUuid',
        'Evaluation Case: theCase',
        'JSON file: theFile',
        '',
    ]
    assert capsys.readouterr().out == "\n".join(exp_out)

    calls = [
        call(identification),
        call().to_json(),
    ]
    assert limited_cache_from.mock_calls == calls
    calls = [call.upsert(EvaluationCase(
        environment="theCanvasInstance",
        patient_uuid="thePatientUuid",
        limited_cache={"key": "value"},
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
        identification,
    )]
    assert audio_interpreter.mock_calls == calls
    calls = [call.transcript2commands(
        recorder,
        lines,
        audio_interpreter.return_value,
        [],
    )]
    assert commander.mock_calls == calls
    calls = [
        call.open('r'),
        call.open().__enter__(),
        call.open().__enter__().read(),
        call.open().__exit__(None, None, None),
    ]
    assert mock_file.mock_calls == calls

    reset_mocks()
