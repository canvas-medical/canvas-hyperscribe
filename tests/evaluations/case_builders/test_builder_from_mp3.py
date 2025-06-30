from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.case_builders.builder_from_mp3 import BuilderFromMp3
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.handlers.commander import Commander
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.line import Line


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
        call().add_argument('--combined', action='store_true', default=False, help="Combine the audio files into a single audio"),
        call().add_argument('--render', action='store_true', default=False, help="Upsert the commands of the last cycle to the patient's last note"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_from_mp3.AudioInterpreter")
@patch("evaluations.case_builders.builder_from_mp3.HelperEvaluation")
@patch("evaluations.case_builders.builder_from_mp3.StoreCases")
@patch.object(CachedSdk, "get_discussion")
@patch.object(ImplementedCommands, "schema_key2instruction")
@patch.object(BuilderFromMp3, "_render_in_ui")
@patch.object(BuilderFromMp3, "_run_cycle")
@patch.object(BuilderFromMp3, "_combined_audios")
@patch.object(BuilderFromMp3, "_limited_cache_from")
def test__run(
        limited_cache_from,
        combined_audios,
        run_cycle,
        render_in_ui,
        schema_key2instruction,
        get_discussion,
        store_cases,
        helper,
        audio_interpreter,
        capsys,
):
    mock_files = [MagicMock(), MagicMock(), MagicMock()]
    for idx in range(len(mock_files)):
        mock_files[idx].name = f"audio file {idx}"

    def reset_mocks():
        limited_cache_from.reset_mock()
        combined_audios.reset_mock()
        run_cycle.reset_mock()
        render_in_ui.reset_mock()
        schema_key2instruction.reset_mock()
        get_discussion.reset_mock()
        store_cases.reset_mock()
        helper.reset_mock()
        audio_interpreter.reset_mock()
        for item in mock_files:
            item.reset_mock()

    tested = BuilderFromMp3

    recorder = AuditorFile("theCase", 0)
    identification = IdentificationParameters(
        patient_uuid="thePatient",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    )
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
    ]
    tests = [
        ([0, 1, 2], '- audio file 0\n- audio file 1\n- audio file 2', True),
        ([0, 1, 2], '- audio file 0\n- audio file 1\n- audio file 2', True),
        ([1], '- audio file 1', False),
        ([1], '- audio file 1', False),
    ]
    for files, exp_file_out, is_render in tests:
        limited_cache_from.return_value.to_json.side_effect = [{"key": "value"}]
        limited_cache_from.return_value.staged_commands_as_instructions.side_effect = [instructions[:1]]
        schema_key2instruction.side_effect = ["schemaKey2instruction"]
        helper.settings.side_effect = ["theSettings"]
        helper.aws_s3_credentials.side_effect = ["theAwsS3Credentials"]
        combined_audios.side_effect = [[
            [b"audio1"],
            [b"audio1", b"audio2"],
            [b"audio2", b"audio3"],
        ]]
        run_cycle.side_effect = [
            (instructions[:2], lines[0]),
            (instructions[:3], lines[1]),
            (instructions[:4], lines[2]),
        ]
        parameters = Namespace(
            patient="thePatientUuid",
            case="theCase",
            group="theGroup",
            type="theType",
            mp3=[mock_files[idx] for idx in files],
            combined=True,
            render=is_render,
        )
        tested._run(parameters, recorder, identification)

        exp_out = [
            'Patient UUID: thePatientUuid',
            'Evaluation Case: theCase',
            'MP3 Files:',
            exp_file_out,
            '',
        ]
        assert capsys.readouterr().out == "\n".join(exp_out)

        calls = [
            call(identification, "theSettings"),
            call().to_json(True),
            call().staged_commands_as_instructions("schemaKey2instruction"),
        ]
        assert limited_cache_from.mock_calls == calls
        calls = [call()]
        assert schema_key2instruction.mock_calls == calls
        calls = [call.upsert(EvaluationCase(
            environment="theCanvasInstance",
            patient_uuid="thePatientUuid",
            limited_cache={"key": "value"},
            case_name="theCase",
            case_group="theGroup",
            case_type="theType",
            cycles=3,
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
        calls = [
            call(audio_interpreter.return_value.identification.note_uuid),
            call().set_cycle(1),
            call().set_cycle(2),
            call().set_cycle(3),
        ]
        assert get_discussion.mock_calls == calls
        calls = [call(parameters)]
        assert combined_audios.mock_calls == calls
        calls = [
            call('theCase', 0, [b'audio1'], audio_interpreter.return_value, instructions[:1], []),
            call('theCase', 1, [b'audio1', b'audio2'], audio_interpreter.return_value, instructions[:2], lines[0]),
            call('theCase', 2, [b'audio2', b'audio3'], audio_interpreter.return_value, instructions[:3], lines[1]),
        ]
        assert run_cycle.mock_calls == calls
        calls = []
        if is_render:
            calls = [call("theCase", identification, limited_cache_from.return_value)]
        assert render_in_ui.mock_calls == calls
        for idx, mock_file in enumerate(mock_files):
            assert mock_file.mock_calls == []

        reset_mocks()


def test__combined_audios():
    mock_files = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        for idx, item in enumerate(mock_files):
            item.reset_mock()
            item.open.return_value.__enter__.return_value.read.side_effect = [f"audio content {idx}".encode('utf-8')]

    tested = BuilderFromMp3

    tests = [
        (2, True, [[b'audio content 0', b'audio content 1', b'audio content 2', b'audio content 3', b'audio content 4']]),
        (0, True, [[b'audio content 0', b'audio content 1', b'audio content 2', b'audio content 3', b'audio content 4']]),
        (2, False, [
            [b'audio content 0'],
            [b'audio content 0', b'audio content 1'],
            [b'audio content 0', b'audio content 1', b'audio content 2'],
            [b'audio content 1', b'audio content 2', b'audio content 3'],
            [b'audio content 2', b'audio content 3', b'audio content 4'],
        ]),
        (0, False, [
            [b'audio content 0'],
            [b'audio content 1'],
            [b'audio content 2'],
            [b'audio content 3'],
            [b'audio content 4'],
        ]),
    ]
    reset_mocks()
    for max_previous_audios, combined, expected in tests:
        with patch.object(Commander, "MAX_PREVIOUS_AUDIOS", max_previous_audios):
            parameters = Namespace(
                patient="thePatientUuid",
                case="theCase",
                group="theGroup",
                type="theType",
                mp3=mock_files,
                combined=combined,
                render=True,
            )
            result = tested._combined_audios(parameters)
            assert result == expected
            calls = [
                call.open('rb'),
                call.open().__enter__(),
                call.open().__enter__().read(),
                call.open().__exit__(None, None, None),
            ]
            for idx, mock_file in enumerate(mock_files):
                assert mock_file.mock_calls == calls
            reset_mocks()
