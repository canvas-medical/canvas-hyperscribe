from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.case_builders.builder_from_mp3 import BuilderFromMp3
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.handlers.implemented_commands import ImplementedCommands
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction


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
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_from_mp3.AudioInterpreter")
@patch("evaluations.case_builders.builder_from_mp3.HelperEvaluation")
@patch("evaluations.case_builders.builder_from_mp3.StoreCases")
@patch.object(ImplementedCommands, "schema_key2instruction")
@patch.object(BuilderFromMp3, "_run_chunked")
@patch.object(BuilderFromMp3, "_run_combined")
@patch.object(BuilderFromMp3, "_limited_cache_from")
def test__run(
        limited_cache_from,
        run_combined,
        run_chunked,
        schema_key2instruction,
        store_cases,
        helper,
        audio_interpreter,
        capsys,
):
    mock_files = [MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        limited_cache_from.reset_mock()
        run_combined.reset_mock()
        run_chunked.reset_mock()
        schema_key2instruction.reset_mock()
        store_cases.reset_mock()
        helper.reset_mock()
        audio_interpreter.reset_mock()
        for item in mock_files:
            item.reset_mock()

    tested = BuilderFromMp3

    recorder = AuditorFile("theCase")
    identification = IdentificationParameters(
        patient_uuid="thePatient",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    )
    instructions = [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=False,
            is_updated=True,
        )
    ]
    tests = [
        (
            True,
            [0, 1, 2],
            '- audio file 0\n- audio file 1\n- audio file 2',
            [b'audio content 0', b'audio content 1', b'audio content 2'],
            True,
            False,
        ),
        (
            False,
            [0, 1, 2],
            '- audio file 0\n- audio file 1\n- audio file 2',
            [b'audio content 0', b'audio content 1', b'audio content 2'],
            False,
            True,
        ),
        (
            True,
            [1],
            '- audio file 1',
            [b'audio content 1'],
            True,
            False,
        ),
        (
            False,
            [1],
            '- audio file 1',
            [b'audio content 1'],
            True,
            False,
        ),
    ]
    for is_combined, files, exp_file_out, exp_file_content, is_run_combined, is_run_chunked in tests:
        limited_cache_from.return_value.to_json.side_effect = [{"key": "value"}]
        limited_cache_from.return_value.staged_commands_as_instructions.side_effect = [instructions]
        schema_key2instruction.side_effect = ["schemaKey2instruction"]
        helper.settings.side_effect = ["theSettings"]
        helper.aws_s3_credentials.side_effect = ["theAwsS3Credentials"]

        for idx in files:
            mock_files[idx].name = f"audio file {idx}"
            mock_files[idx].open.return_value.__enter__.return_value.read.side_effect = [f"audio content {idx}".encode('utf-8')]

        parameters = Namespace(
            patient="thePatientUuid",
            case="theCase",
            group="theGroup",
            type="theType",
            mp3=[mock_files[idx] for idx in files],
            combined=is_combined,
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
            call(identification),
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

        calls = []
        if is_run_combined:
            calls = [call(recorder, audio_interpreter.return_value, exp_file_content, instructions)]
        assert run_combined.mock_calls == calls
        calls = []
        if is_run_chunked:
            calls = [call(parameters, audio_interpreter.return_value, exp_file_content, instructions)]
        assert run_chunked.mock_calls == calls
        for idx, mock_file in enumerate(mock_files):
            calls = []
            if idx in files:
                calls = [
                    call.open('rb'),
                    call.open().__enter__(),
                    call.open().__enter__().read(),
                    call.open().__exit__(None, None, None),
                ]
            assert mock_file.mock_calls == calls

        reset_mocks()


@patch("evaluations.case_builders.builder_from_mp3.CachedDiscussion")
@patch("evaluations.case_builders.builder_from_mp3.Commander")
def test__run_combined(commander, cached_discussion):
    mock_chatter = MagicMock()

    def reset_mocks():
        commander.reset_mock()
        cached_discussion.reset_mock()
        mock_chatter.reset_mock()

    tested = BuilderFromMp3

    audios = [b'audio content 0', b'audio content 1']
    instructions = [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=False,
            is_updated=True,
        )
    ]
    mock_chatter.identification = IdentificationParameters(
        patient_uuid="thePatient",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    )

    recorder = AuditorFile("theCase")
    tested._run_combined(recorder, mock_chatter, audios, instructions)
    calls = [call.audio2commands(recorder, audios, mock_chatter, instructions, "")]
    assert commander.mock_calls == calls
    calls = [
        call.get_discussion('theNoteUuid'),
        call.get_discussion().add_one(),
    ]
    assert cached_discussion.mock_calls == calls

    reset_mocks()


@patch("evaluations.case_builders.builder_from_mp3.AuditorFile")
@patch("evaluations.case_builders.builder_from_mp3.CachedDiscussion")
@patch("evaluations.case_builders.builder_from_mp3.Commander")
def test__run_chunked(commander, cached_discussion, auditor):
    mock_chatter = MagicMock()

    def reset_mocks():
        commander.reset_mock()
        cached_discussion.reset_mock()
        auditor.reset_mock()
        mock_chatter.reset_mock()

    tested = BuilderFromMp3

    audios = [
        b'audio content 0',
        b'audio content 1',
        b'audio content 2',
        b'audio content 3',
        b'audio content 4',
    ]
    instructions = [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=False,
            is_updated=True,
        )
    ]
    parameters = Namespace(
        patient="thePatientUuid",
        case="theCase",
        group="theGroup",
        type="theType",
        mp3=[],
        combined=True,
    )
    commander.MAX_PREVIOUS_AUDIOS = 3
    commander.audio2commands.side_effect = [
        (["previous1"], ["effects1"], "the last words 1"),
        (["previous2"], ["effects2"], "the last words 2"),
        (["previous3"], ["effects3"], "the last words 3"),
        (["previous4"], ["effects4"], "the last words 4"),
        (["previous9"], ["effects9"], "the last words 9"),
    ]
    mock_chatter.identification = IdentificationParameters(
        patient_uuid="thePatient",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    )

    tested._run_chunked(parameters, mock_chatter, audios, instructions)
    calls = [
        call('theCase_cycle00'),
        call('theCase_cycle01'),
        call('theCase_cycle02'),
        call('theCase_cycle03'),
        call('theCase_cycle04'),
    ]
    assert auditor.mock_calls == calls
    calls = [
        call.audio2commands(
            auditor.return_value,
            [b'audio content 0'],
            mock_chatter,
            instructions,
            "",
        ),
        call.audio2commands(
            auditor.return_value, [b'audio content 0', b'audio content 1'],
            mock_chatter,
            ['previous1'],
            "the last words 1",
        ),
        call.audio2commands(
            auditor.return_value, [b'audio content 0', b'audio content 1', b'audio content 2'],
            mock_chatter,
            ['previous2'],
            "the last words 2",
        ),
        call.audio2commands(
            auditor.return_value, [b'audio content 1', b'audio content 2', b'audio content 3'],
            mock_chatter,
            ['previous3'],
            "the last words 3",
        ),
        call.audio2commands(
            auditor.return_value, [b'audio content 2', b'audio content 3', b'audio content 4'],
            mock_chatter,
            ['previous4'],
            "the last words 4",
        ),
    ]
    assert commander.mock_calls == calls
    calls = [
        call.get_discussion('theNoteUuid'),
        call.get_discussion().add_one(),
        call.get_discussion().add_one(),
        call.get_discussion().add_one(),
        call.get_discussion().add_one(),
        call.get_discussion().add_one()
    ]
    assert cached_discussion.mock_calls == calls

    reset_mocks()
