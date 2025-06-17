from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.case_builders.builder_from_tuning import BuilderFromTuning
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.handlers.commander import Commander
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction


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
        call().add_argument("--tuning-mp3", required=True, nargs='+', type=BuilderFromTuning.validate_files, help="MP3 files of the discussion"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_from_tuning.AudioInterpreter")
@patch("evaluations.case_builders.builder_from_tuning.CachedSdk")
@patch("evaluations.case_builders.builder_from_tuning.HelperEvaluation")
@patch("evaluations.case_builders.builder_from_tuning.StoreCases")
@patch("evaluations.case_builders.builder_from_tuning.ImplementedCommands")
@patch("evaluations.case_builders.builder_from_tuning.LimitedCache")
@patch.object(BuilderFromTuning, "_run_cycle")
def test__run(
        run_cycle,
        limited_cache,
        implemented_commands,
        store_cases,
        helper,
        cached_discussion,
        audio_interpreter,
        capsys,
):
    mock_limited_cache = MagicMock()
    mock_json_file = MagicMock()
    mock_mp3_files = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        run_cycle.reset_mock()
        limited_cache.reset_mock()
        implemented_commands.reset_mock()
        store_cases.reset_mock()
        helper.reset_mock()
        cached_discussion.reset_mock()
        audio_interpreter.reset_mock()
        mock_limited_cache.reset_mock()
        mock_json_file.reset_mock()
        for idx, item in enumerate(mock_mp3_files):
            item.reset_mock()
            item.name = f"audio file {idx}"
            item.open.return_value.__enter__.return_value.read.side_effect = [f"audio content {idx}".encode('utf-8')]

    instructions = [
        Instruction(
            uuid=f"uuid{idx}",
            index=idx,
            instruction=f"theInstruction{idx}",
            information=f"theInformation{idx}",
            is_new=False,
            is_updated=True,
        )
        for idx in range(5)
    ]

    tested = BuilderFromTuning
    reset_mocks()
    tests = [
        (2, [
            [b'audio content 0'],
            [b'audio content 0', b'audio content 1'],
            [b'audio content 0', b'audio content 1', b'audio content 2'],
            [b'audio content 1', b'audio content 2', b'audio content 3'],
            [b'audio content 2', b'audio content 3', b'audio content 4'],
        ]),
        (0, [
            [b'audio content 0'],
            [b'audio content 1'],
            [b'audio content 2'],
            [b'audio content 3'],
            [b'audio content 4'],
        ]),
    ]
    for max_previous_audios, exp_combined in tests:
        with patch.object(Commander, "MAX_PREVIOUS_AUDIOS", max_previous_audios):
            limited_cache.load_from_json.side_effect = [mock_limited_cache]
            mock_limited_cache.staged_commands_as_instructions.side_effect = [instructions[:1]]
            implemented_commands.schema_key2instruction.side_effect = ["schemaKey2instruction"]
            helper.settings.side_effect = ["theSettings"]
            helper.aws_s3_credentials.side_effect = ["theAwsS3Credentials"]
            mock_json_file.name = "theJsonFile"
            mock_json_file.open.return_value.__enter__.return_value.read.side_effect = ['{"key": "value"}']

            run_cycle.side_effect = [
                (instructions[:2], "last words 1"),
                (instructions[:3], "last words 2"),
                (instructions[:4], "last words 3"),
                (instructions[:5], "last words 4"),
                (instructions[:6], "last words 5"),
            ]

            parameters = Namespace(
                patient="thePatientUuid",
                case="theCase",
                group="theGroup",
                type="theType",
                tuning_json=mock_json_file,
                tuning_mp3=mock_mp3_files,
            )
            recorder = AuditorFile("theCase", 0)
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
                'MP3 files:',
                '- audio file 0',
                '- audio file 1',
                '- audio file 2',
                '- audio file 3',
                '- audio file 4',
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
                cycles=5,
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
                call.get_discussion().set_cycle(2),
                call.get_discussion().set_cycle(3),
                call.get_discussion().set_cycle(4),
                call.get_discussion().set_cycle(5),
            ]
            assert cached_discussion.mock_calls == calls
            calls = [call("theSettings", "theAwsS3Credentials", mock_limited_cache, identification)]
            assert audio_interpreter.mock_calls == calls
            calls = [
                call('theCase', 0, exp_combined[0], audio_interpreter.return_value, instructions[:1], ""),
                call('theCase', 1, exp_combined[1], audio_interpreter.return_value, instructions[:2], "last words 1"),
                call('theCase', 2, exp_combined[2], audio_interpreter.return_value, instructions[:3], "last words 2"),
                call('theCase', 3, exp_combined[3], audio_interpreter.return_value, instructions[:4], "last words 3"),
                call('theCase', 4, exp_combined[4], audio_interpreter.return_value, instructions[:5], "last words 4"),
            ]
            assert run_cycle.mock_calls == calls
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
            for idx, mock_file in enumerate(mock_mp3_files):
                assert mock_file.mock_calls == calls

            reset_mocks()
