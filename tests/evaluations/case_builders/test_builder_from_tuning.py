from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.case_builders.builder_from_tuning import BuilderFromTuning
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.structures.identification_parameters import IdentificationParameters


def test_class():
    tested = BuilderFromTuning
    assert issubclass(tested, BuilderBase)


@patch("evaluations.case_builders.builder_from_tuning.ArgumentParser")
def test__parameters(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    tested = BuilderFromTuning

    argument_parser.return_value.parse_args.side_effect = ["parse_args called"]
    result = tested._parameters()
    expected = "parse_args called"
    assert result == expected

    calls = [
        call(description="Build the files of the evaluation tests against a patient based on the provided files"),
        call().add_argument("--case", type=str, required=True, help="Evaluation case"),
        call().add_argument("--group", type=str, help="Group of the case", default="common"),
        call().add_argument("--type", type=str, choices=["situational", "general"], help="Type of the case: situational, general", default="general"),
        call().add_argument("--tuning-json", required=True, type=BuilderFromTuning.validate_files, help="JSON file with the limited cache content"),
        call().add_argument("--tuning-mp3", required=True, type=BuilderFromTuning.validate_files, help="MP3 file of the discussion"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_from_tuning.Commander")
@patch("evaluations.case_builders.builder_from_tuning.AudioInterpreter")
@patch("evaluations.case_builders.builder_from_tuning.CachedSdk")
@patch("evaluations.case_builders.builder_from_tuning.HelperEvaluation")
@patch("evaluations.case_builders.builder_from_tuning.StoreCases")
@patch("evaluations.case_builders.builder_from_tuning.ImplementedCommands")
@patch("evaluations.case_builders.builder_from_tuning.LimitedCache")
def test__run(
        limited_cache,
        implemented_commands,
        store_cases,
        helper,
        cached_discussion,
        audio_interpreter,
        commander,
        capsys,
):
    mock_json_file = MagicMock()
    mock_mp3_file = MagicMock()
    mock_limited_cache = MagicMock()

    def reset_mocks():
        limited_cache.reset_mock()
        implemented_commands.reset_mock()
        store_cases.reset_mock()
        helper.reset_mock()
        cached_discussion.reset_mock()
        audio_interpreter.reset_mock()
        commander.reset_mock()
        mock_json_file.reset_mock()
        mock_mp3_file.reset_mock()
        mock_limited_cache.reset_mock()

    tested = BuilderFromTuning

    limited_cache.load_from_json.side_effect = [mock_limited_cache]
    mock_limited_cache.staged_commands_as_instructions.side_effect = [["theInitialInstructions"]]
    implemented_commands.schema_key2instruction.side_effect = ["schemaKey2instruction"]
    helper.settings.side_effect = ["theSettings"]
    helper.aws_s3_credentials.side_effect = ["theAwsS3Credentials"]
    mock_json_file.name = "theJsonFile"
    mock_json_file.open.return_value.__enter__.return_value.read.side_effect = ['{"key": "value"}']
    mock_mp3_file.name = "theMp3File"
    mock_mp3_file.open.return_value.__enter__.return_value.read.side_effect = [b"audio content"]

    parameters = Namespace(
        patient="thePatientUuid",
        case="theCase",
        group="theGroup",
        type="theType",
        tuning_json=mock_json_file,
        tuning_mp3=mock_mp3_file,
    )
    recorder = AuditorFile("theCase")
    identification = IdentificationParameters(
        patient_uuid="thePatient",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    )
    audio_interpreter.return_value.identification = identification

    tested._run(parameters, recorder, identification)

    exp_out = [
        'Evaluation Case: theCase',
        'JSON file: theJsonFile',
        'MP3 file: theMp3File',
        '',
    ]
    assert capsys.readouterr().out == "\n".join(exp_out)

    calls = [call.load_from_json({"key": "value"})]
    assert limited_cache.mock_calls == calls
    calls = [call.staged_commands_as_instructions("schemaKey2instruction")]
    assert mock_limited_cache.mock_calls == calls
    calls = [call.schema_key2instruction()]
    assert implemented_commands.mock_calls == calls
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
    calls = [
        call.get_discussion('theNoteUuid'),
        call.get_discussion().set_cycle(1),
        call.get_discussion().save(),
    ]
    assert cached_discussion.mock_calls == calls
    calls = [call(
        "theSettings",
        "theAwsS3Credentials",
        mock_limited_cache,
        identification,
    )]
    assert audio_interpreter.mock_calls == calls
    calls = [call.audio2commands(
        recorder,
        [b'audio content'],
        audio_interpreter.return_value,
        ["theInitialInstructions"],
        "",
    )]
    assert commander.mock_calls == calls
    calls = [
        call.open('r'),
        call.open().__enter__(),
        call.open().__enter__().read(),
        call.open().__exit__(None, None, None),
    ]
    assert mock_json_file.mock_calls == calls
    calls = [
        call.open('rb'),
        call.open().__enter__(),
        call.open().__enter__().read(),
        call.open().__exit__(None, None, None),
    ]
    assert mock_mp3_file.mock_calls == calls

    reset_mocks()
