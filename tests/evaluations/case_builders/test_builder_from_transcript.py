import json
from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.case_builders.builder_from_transcript import BuilderFromTranscript
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
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
        call().add_argument("--cycles", type=int, help="Split the transcript in as many cycles", default=1),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_from_transcript.AuditorFile")
@patch("evaluations.case_builders.builder_from_transcript.CachedDiscussion")
@patch("evaluations.case_builders.builder_from_transcript.Commander")
@patch("evaluations.case_builders.builder_from_transcript.AudioInterpreter")
@patch("evaluations.case_builders.builder_from_transcript.HelperEvaluation")
@patch("evaluations.case_builders.builder_from_transcript.StoreCases")
@patch.object(ImplementedCommands, "schema_key2instruction")
@patch.object(BuilderFromTranscript, "_limited_cache_from")
def test__run(
        limited_cache_from,
        schema_key2instruction,
        store_cases,
        helper,
        audio_interpreter,
        commander,
        cached_discussion,
        auditor,
        capsys,
):
    mock_file = MagicMock()

    def reset_mocks():
        limited_cache_from.reset_mock()
        schema_key2instruction.reset_mock()
        store_cases.reset_mock()
        helper.reset_mock()
        audio_interpreter.reset_mock()
        commander.reset_mock()
        cached_discussion.reset_mock()
        auditor.reset_mock()
        mock_file.reset_mock()

    tested = BuilderFromTranscript

    lines = [
        Line(speaker="speakerA", text="text1"),
        Line(speaker="speakerB", text="text2"),
        Line(speaker="speakerA", text="text3"),
        Line(speaker="speakerA", text="text4"),
        Line(speaker="speakerB", text="text5"),
        Line(speaker="speakerB", text="text6"),
        Line(speaker="speakerB", text="text7"),
        Line(speaker="speakerA", text="text8"),
        Line(speaker="speakerA", text="text9"),
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
    recorder = AuditorFile("theCase")
    identification = IdentificationParameters(
        patient_uuid="thePatient",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    )
    audio_interpreter.return_value.identification = identification
    exp_out = [
        'Patient UUID: thePatientUuid',
        'Evaluation Case: theCase',
        'JSON file: theFile',
    ]
    exp_limited_cache = [
        call(identification),
        call().to_json(True),
        call().staged_commands_as_instructions('schemaKey2instruction'),
    ]
    exp_schema_key2instruction = [call()]
    exp_store_cases = [call.upsert(EvaluationCase(
        environment="theCanvasInstance",
        patient_uuid="thePatientUuid",
        limited_cache={"key": "value"},
        case_name="theCase",
        case_group="theGroup",
        case_type="theType",
        description="theCase",
    ))]
    exp_helper = [
        call.settings(),
        call.aws_s3_credentials(),
    ]
    exp_audio_interpreter = [call(
        "theSettings",
        "theAwsS3Credentials",
        limited_cache_from.return_value,
        identification,
    )]
    exp_mock_file = [
        call.open('r'),
        call.open().__enter__(),
        call.open().__enter__().read(),
        call.open().__exit__(None, None, None),
    ]

    # cycle 1
    limited_cache_from.return_value.to_json.side_effect = [{"key": "value"}]
    limited_cache_from.return_value.staged_commands_as_instructions.side_effect = [instructions]
    schema_key2instruction.side_effect = ["schemaKey2instruction"]
    helper.settings.side_effect = ["theSettings"]
    helper.aws_s3_credentials.side_effect = ["theAwsS3Credentials"]
    mock_file.name = "theFile"
    mock_file.open.return_value.__enter__.return_value.read.side_effect = [
        json.dumps([l.to_json() for l in lines]),
    ]
    commander.transcript2commands.side_effect = [(["previous1"], ["effects1"])]
    auditor.side_effect = []
    parameters = Namespace(
        patient="thePatientUuid",
        case="theCase",
        group="theGroup",
        type="theType",
        transcript=mock_file,
        cycles=1,
    )
    tested._run(parameters, recorder, identification)

    assert capsys.readouterr().out == "\n".join(exp_out + ["Cycles: 1", ""])
    assert limited_cache_from.mock_calls == exp_limited_cache
    assert schema_key2instruction.mock_calls == exp_schema_key2instruction
    assert store_cases.mock_calls == exp_store_cases
    assert helper.mock_calls == exp_helper
    assert audio_interpreter.mock_calls == exp_audio_interpreter
    calls = [call.transcript2commands(
        recorder,
        lines,
        audio_interpreter.return_value,
        instructions,
    )]
    assert commander.mock_calls == calls
    calls = [
        call.get_discussion('theNoteUuid'),
        call.get_discussion().set_cycle(1),
    ]
    assert cached_discussion.mock_calls == calls
    assert auditor.mock_calls == []
    assert mock_file.mock_calls == exp_mock_file

    reset_mocks()

    # cycle 2
    limited_cache_from.return_value.to_json.side_effect = [{"key": "value"}]
    limited_cache_from.return_value.staged_commands_as_instructions.side_effect = [instructions]
    schema_key2instruction.side_effect = ["schemaKey2instruction"]
    helper.settings.side_effect = ["theSettings"]
    helper.aws_s3_credentials.side_effect = ["theAwsS3Credentials"]
    mock_file.name = "theFile"
    mock_file.open.return_value.__enter__.return_value.read.side_effect = [
        json.dumps([l.to_json() for l in lines]),
    ]
    commander.transcript2commands.side_effect = [
        (["previous1"], ["effects1"]),
        (["previous2"], ["effects2"]),
    ]
    auditor.side_effect = ["auditor1", "auditor2"]
    parameters = Namespace(
        patient="thePatientUuid",
        case="theCase",
        group="theGroup",
        type="theType",
        transcript=mock_file,
        cycles=2,
    )
    tested._run(parameters, recorder, identification)

    assert capsys.readouterr().out == "\n".join(exp_out + ["Cycles: 2", ""])
    assert limited_cache_from.mock_calls == exp_limited_cache
    assert schema_key2instruction.mock_calls == exp_schema_key2instruction
    assert store_cases.mock_calls == exp_store_cases
    assert helper.mock_calls == exp_helper
    assert audio_interpreter.mock_calls == exp_audio_interpreter
    calls = [
        call.transcript2commands(
            "auditor1",
            lines[:5],
            audio_interpreter.return_value,
            instructions,
        ),
        call.transcript2commands(
            "auditor2",
            lines[5:],
            audio_interpreter.return_value,
            ["previous1"],
        ),
    ]
    assert commander.mock_calls == calls
    calls = [
        call.get_discussion('theNoteUuid'),
        call.get_discussion().set_cycle(1),
        call.get_discussion().set_cycle(2),
    ]
    assert cached_discussion.mock_calls == calls
    calls = [
        call("theCase_cycle00"),
        call("theCase_cycle01"),
    ]
    assert auditor.mock_calls == calls
    assert mock_file.mock_calls == exp_mock_file

    reset_mocks()

    # cycle 3
    limited_cache_from.return_value.to_json.side_effect = [{"key": "value"}]
    limited_cache_from.return_value.staged_commands_as_instructions.side_effect = [instructions]
    schema_key2instruction.side_effect = ["schemaKey2instruction"]
    helper.settings.side_effect = ["theSettings"]
    helper.aws_s3_credentials.side_effect = ["theAwsS3Credentials"]
    mock_file.name = "theFile"
    mock_file.open.return_value.__enter__.return_value.read.side_effect = [
        json.dumps([l.to_json() for l in lines]),
    ]
    commander.transcript2commands.side_effect = [
        (["previous1"], ["effects1"]),
        (["previous2"], ["effects2"]),
        (["previous3"], ["effects3"]),
    ]
    auditor.side_effect = ["auditor1", "auditor2", "auditor3"]
    parameters = Namespace(
        patient="thePatientUuid",
        case="theCase",
        group="theGroup",
        type="theType",
        transcript=mock_file,
        cycles=3,
    )
    tested._run(parameters, recorder, identification)

    assert capsys.readouterr().out == "\n".join(exp_out + ["Cycles: 3", ""])
    assert limited_cache_from.mock_calls == exp_limited_cache
    assert schema_key2instruction.mock_calls == exp_schema_key2instruction
    assert store_cases.mock_calls == exp_store_cases
    assert helper.mock_calls == exp_helper
    assert audio_interpreter.mock_calls == exp_audio_interpreter
    calls = [
        call.transcript2commands(
            "auditor1",
            lines[:3],
            audio_interpreter.return_value,
            instructions,
        ),
        call.transcript2commands(
            "auditor2",
            lines[3:6],
            audio_interpreter.return_value,
            ["previous1"],
        ),
        call.transcript2commands(
            "auditor3",
            lines[6:],
            audio_interpreter.return_value,
            ["previous2"],
        ),
    ]
    assert commander.mock_calls == calls
    calls = [
        call.get_discussion('theNoteUuid'),
        call.get_discussion().set_cycle(1),
        call.get_discussion().set_cycle(2),
        call.get_discussion().set_cycle(3),
    ]
    assert cached_discussion.mock_calls == calls
    calls = [
        call("theCase_cycle00"),
        call("theCase_cycle01"),
        call("theCase_cycle02"),
    ]
    assert auditor.mock_calls == calls
    assert mock_file.mock_calls == exp_mock_file

    reset_mocks()
