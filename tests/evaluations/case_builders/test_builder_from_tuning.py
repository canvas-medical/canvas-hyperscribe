from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from evaluations.case_builders.builder_base import BuilderBase
from evaluations.case_builders.builder_from_tuning import BuilderFromTuning
from hyperscribe.libraries.commander import Commander
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.line import Line


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
        call().add_argument(
            "--tuning-json",
            required=True,
            type=BuilderFromTuning.validate_files,
            help="JSON file with the limited cache content",
        ),
        call().add_argument(
            "--tuning-mp3",
            required=True,
            nargs="+",
            type=BuilderFromTuning.validate_files,
            help="MP3 files of the discussion",
        ),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_from_tuning.AudioInterpreter")
@patch("evaluations.case_builders.builder_from_tuning.CachedSdk")
@patch("evaluations.case_builders.builder_from_tuning.ImplementedCommands")
@patch("evaluations.case_builders.builder_from_tuning.LimitedCacheLoader")
@patch.object(BuilderFromTuning, "_run_cycle")
def test__run(run_cycle, limited_cache, implemented_commands, cached_discussion, audio_interpreter, capsys):
    recorder = MagicMock()
    mock_limited_cache = MagicMock()
    mock_json_file = MagicMock()
    mock_mp3_files = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        run_cycle.reset_mock()
        limited_cache.reset_mock()
        implemented_commands.reset_mock()
        cached_discussion.reset_mock()
        audio_interpreter.reset_mock()
        recorder.reset_mock()
        mock_limited_cache.reset_mock()
        mock_json_file.reset_mock()
        for idx, item in enumerate(mock_mp3_files):
            item.reset_mock()
            item.name = f"audio file {idx}"
            item.open.return_value.__enter__.return_value.read.side_effect = [f"audio content {idx}".encode("utf-8")]

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
    lines = [
        Line(speaker="speaker", text="last words 1"),
        Line(speaker="speaker", text="last words 2"),
        Line(speaker="speaker", text="last words 3"),
        Line(speaker="speaker", text="last words 4"),
        Line(speaker="speaker", text="last words 5"),
    ]

    tested = BuilderFromTuning
    reset_mocks()
    tests = [
        (
            2,
            [
                [b"audio content 0"],
                [b"audio content 0", b"audio content 1"],
                [b"audio content 0", b"audio content 1", b"audio content 2"],
                [b"audio content 1", b"audio content 2", b"audio content 3"],
                [b"audio content 2", b"audio content 3", b"audio content 4"],
            ],
        ),
        (
            0,
            [
                [b"audio content 0"],
                [b"audio content 1"],
                [b"audio content 2"],
                [b"audio content 3"],
                [b"audio content 4"],
            ],
        ),
    ]
    for max_previous_audios, exp_combined in tests:
        with patch.object(Commander, "MAX_PREVIOUS_AUDIOS", max_previous_audios):
            limited_cache.load_from_json.side_effect = [mock_limited_cache]
            mock_limited_cache.staged_commands_as_instructions.side_effect = [instructions[:1]]
            mock_limited_cache.to_json.side_effect = [{"limited": "cache"}]
            implemented_commands.schema_key2instruction.side_effect = ["schemaKey2instruction"]
            recorder.settings = "theSettings"
            recorder.s3_credentials = "theAwsS3Credentials"
            mock_json_file.name = "theJsonFile"
            mock_json_file.open.return_value.__enter__.return_value.read.side_effect = ['{"key": "value"}']

            run_cycle.side_effect = [
                (instructions[:2], lines[0]),
                (instructions[:3], lines[1]),
                (instructions[:4], lines[2]),
                (instructions[:5], lines[3]),
                (instructions[:6], lines[4]),
            ]

            parameters = Namespace(
                patient="thePatientUuid",
                case="theCase",
                tuning_json=mock_json_file,
                tuning_mp3=mock_mp3_files,
            )
            identification = IdentificationParameters(
                patient_uuid="thePatient",
                note_uuid="theNoteUuid",
                provider_uuid="theProviderUuid",
                canvas_instance="theCanvasInstance",
            )
            audio_interpreter.return_value.identification = identification

            tested._run(parameters, recorder, identification)

            exp_out = [
                "Evaluation Case: theCase",
                "JSON file: theJsonFile",
                "MP3 files:",
                "- audio file 0",
                "- audio file 1",
                "- audio file 2",
                "- audio file 3",
                "- audio file 4",
                "",
            ]
            assert capsys.readouterr().out == "\n".join(exp_out)

            calls = [call.load_from_json({"key": "value"})]
            assert limited_cache.mock_calls == calls
            calls = [
                call.case_update_limited_cache({"limited": "cache"}),
                call.set_cycle(1),
                call.set_cycle(2),
                call.set_cycle(3),
                call.set_cycle(4),
                call.set_cycle(5),
            ]
            assert recorder.mock_calls == calls
            calls = [call.to_json(), call.staged_commands_as_instructions("schemaKey2instruction")]
            assert mock_limited_cache.mock_calls == calls
            calls = [call.schema_key2instruction()]
            assert implemented_commands.mock_calls == calls
            calls = [
                call.get_discussion("theNoteUuid"),
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
                call(recorder, exp_combined[0], audio_interpreter.return_value, instructions[:1], []),
                call(recorder, exp_combined[1], audio_interpreter.return_value, instructions[:2], lines[0]),
                call(recorder, exp_combined[2], audio_interpreter.return_value, instructions[:3], lines[1]),
                call(recorder, exp_combined[3], audio_interpreter.return_value, instructions[:4], lines[2]),
                call(recorder, exp_combined[4], audio_interpreter.return_value, instructions[:5], lines[3]),
            ]
            assert run_cycle.mock_calls == calls
            calls = [
                call.open("r"),
                call.open().__enter__(),
                call.open().__enter__().read(),
                call.open().__exit__(None, None, None),
            ]
            assert mock_json_file.mock_calls == calls
            calls = [
                call.open("rb"),
                call.open().__enter__(),
                call.open().__enter__().read(),
                call.open().__exit__(None, None, None),
            ]
            for idx, mock_file in enumerate(mock_mp3_files):
                assert mock_file.mock_calls == calls

            reset_mocks()
