import json
from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from evaluations.case_builders.builder_base import BuilderBase
from evaluations.case_builders.builder_from_chart_transcript import BuilderFromChartTranscript
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.line import Line


def test_class():
    assert issubclass(BuilderFromChartTranscript, BuilderBase)


@patch("evaluations.case_builders.builder_from_chart_transcript.ArgumentParser")
def test__parameters(argument_parser):
    argument_parser.return_value.parse_args.side_effect = ["parsed"]
    result = BuilderFromChartTranscript._parameters()
    assert result == "parsed"

    calls = [
        call(description="Generate commands summary from chart + transcript"),
        call().add_argument("--case", type=str, required=True, help="Evaluation case name (used as directory)"),
        call().add_argument(
            "--chart",
            type=BuilderFromChartTranscript.validate_files,
            required=True,
            help="Path to limited_cache JSON file",
        ),
        call().add_argument(
            "--transcript",
            type=BuilderFromChartTranscript.validate_files,
            required=True,
            help="Path to transcript JSON file",
        ),
        call().add_argument("--cycles", type=int, default=1, help="Number of transcript cycles"),
        call().add_argument("--render", action="store_true", help="Render commands to UI"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls


@patch("evaluations.case_builders.builder_from_chart_transcript.CachedSdk")
@patch("evaluations.case_builders.builder_from_chart_transcript.Commander")
@patch("evaluations.case_builders.builder_from_chart_transcript.AudioInterpreter")
@patch.object(LimitedCache, "load_from_json")
@patch.object(ImplementedCommands, "schema_key2instruction")
@patch.object(BuilderFromChartTranscript, "_render_in_ui")
def test__run(
    render_in_ui,
    schema_key2instruction,
    limited_cache,
    audio_interpreter,
    commander,
    cached_discussion,
    capsys,
):
    mock_file_chart = MagicMock()
    mock_file_transcript = MagicMock()
    recorder = MagicMock()

    def reset_mocks():
        render_in_ui.reset_mock()
        schema_key2instruction.reset_mock()
        limited_cache.reset_mock()
        audio_interpreter.reset_mock()
        commander.reset_mock()
        cached_discussion.reset_mock()
        mock_file_chart.reset_mock()
        mock_file_transcript.reset_mock()
        recorder.reset_mock()
        #
        recorder.settings = "theSettings"
        recorder.s3_credentials = "theAwsS3Credentials"
        recorder.cycle_key = "theCycleKey"
        mock_file_chart.name = "theChartFile"
        mock_file_transcript.name = "theTranscriptFile"

    reset_mocks()

    tested = BuilderFromChartTranscript

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
        ),
    ]
    identification = IdentificationParameters(
        patient_uuid="thePatient",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    )
    audio_interpreter.return_value.identification = identification
    exp_out = [
        "Evaluation Case: theCase",
        "Chart file: theChartFile",
        "JSON file: theTranscriptFile",
    ]
    exp_limited_cache = [
        call({"chart": "data"}),
        call().to_json(True),
        call().staged_commands_as_instructions("schemaKey2instruction"),
    ]
    exp_schema_key2instruction = [call()]
    exp_audio_interpreter = [
        call("theSettings", "theAwsS3Credentials", limited_cache.return_value, identification),
    ]
    exp_mock_file = [
        call.open("r"),
        call.open().__enter__(),
        call.open().__enter__().read(),
        call.open().__exit__(None, None, None),
    ]

    # cycle 1
    limited_cache.return_value.to_json.side_effect = [{"key": "value"}]
    limited_cache.return_value.staged_commands_as_instructions.side_effect = [instructions]
    schema_key2instruction.side_effect = ["schemaKey2instruction"]
    mock_file_chart.open.return_value.__enter__.return_value.read.side_effect = [json.dumps({"chart": "data"})]
    mock_file_transcript.open.return_value.__enter__.return_value.read.side_effect = [
        json.dumps([l.to_json() for l in lines])
    ]
    commander.transcript2commands.side_effect = [(["previous1"], ["effects1"])]
    parameters = Namespace(
        chart=mock_file_chart,
        case="theCase",
        transcript=mock_file_transcript,
        cycles=1,
        render=True,
    )
    tested._run(parameters, recorder, identification)

    assert capsys.readouterr().out == "\n".join(exp_out + ["Cycles: 1", ""])
    assert limited_cache.mock_calls == exp_limited_cache
    calls = [call(recorder, identification, limited_cache.return_value)]
    assert render_in_ui.mock_calls == calls
    assert schema_key2instruction.mock_calls == exp_schema_key2instruction
    assert audio_interpreter.mock_calls == exp_audio_interpreter
    calls = [call.transcript2commands(recorder, lines, audio_interpreter.return_value, instructions)]
    assert commander.mock_calls == calls
    calls = [call.get_discussion("theNoteUuid"), call.get_discussion().set_cycle(1)]
    assert cached_discussion.mock_calls == calls
    assert mock_file_transcript.mock_calls == exp_mock_file
    calls = [
        call.case_update_limited_cache({"key": "value"}),
        call.set_cycle(1),
        call.upsert_json(
            "audio2transcript",
            {
                "theCycleKey": [
                    {"speaker": "speakerA", "text": "text1"},
                    {"speaker": "speakerB", "text": "text2"},
                    {"speaker": "speakerA", "text": "text3"},
                    {"speaker": "speakerA", "text": "text4"},
                    {"speaker": "speakerB", "text": "text5"},
                    {"speaker": "speakerB", "text": "text6"},
                    {"speaker": "speakerB", "text": "text7"},
                    {"speaker": "speakerA", "text": "text8"},
                    {"speaker": "speakerA", "text": "text9"},
                ],
            },
        ),
    ]
    assert recorder.mock_calls == calls
    reset_mocks()

    # cycle 2
    limited_cache.return_value.to_json.side_effect = [{"key": "value"}]
    limited_cache.return_value.staged_commands_as_instructions.side_effect = [instructions]
    schema_key2instruction.side_effect = ["schemaKey2instruction"]
    mock_file_chart.open.return_value.__enter__.return_value.read.side_effect = [json.dumps({"chart": "data"})]
    mock_file_transcript.open.return_value.__enter__.return_value.read.side_effect = [
        json.dumps([l.to_json() for l in lines])
    ]
    commander.transcript2commands.side_effect = [(["previous1"], ["effects1"]), (["previous2"], ["effects2"])]
    parameters = Namespace(
        chart=mock_file_chart,
        case="theCase",
        type="theType",
        transcript=mock_file_transcript,
        cycles=2,
        render=False,
    )
    tested._run(parameters, recorder, identification)

    assert capsys.readouterr().out == "\n".join(exp_out + ["Cycles: 2", ""])
    assert limited_cache.mock_calls == exp_limited_cache
    assert render_in_ui.mock_calls == []
    assert schema_key2instruction.mock_calls == exp_schema_key2instruction
    assert audio_interpreter.mock_calls == exp_audio_interpreter
    calls = [
        call.transcript2commands(recorder, lines[:5], audio_interpreter.return_value, instructions),
        call.transcript2commands(recorder, lines[5:], audio_interpreter.return_value, ["previous1"]),
    ]
    assert commander.mock_calls == calls
    calls = [call.get_discussion("theNoteUuid"), call.get_discussion().set_cycle(1), call.get_discussion().set_cycle(2)]
    assert cached_discussion.mock_calls == calls
    assert mock_file_chart.mock_calls == exp_mock_file
    assert mock_file_transcript.mock_calls == exp_mock_file
    calls = [
        call.case_update_limited_cache({"key": "value"}),
        call.set_cycle(1),
        call.upsert_json(
            "audio2transcript",
            {
                "theCycleKey": [
                    {"speaker": "speakerA", "text": "text1"},
                    {"speaker": "speakerB", "text": "text2"},
                    {"speaker": "speakerA", "text": "text3"},
                    {"speaker": "speakerA", "text": "text4"},
                    {"speaker": "speakerB", "text": "text5"},
                ],
            },
        ),
        call.set_cycle(2),
        call.upsert_json(
            "audio2transcript",
            {
                "theCycleKey": [
                    {"speaker": "speakerB", "text": "text6"},
                    {"speaker": "speakerB", "text": "text7"},
                    {"speaker": "speakerA", "text": "text8"},
                    {"speaker": "speakerA", "text": "text9"},
                ],
            },
        ),
    ]
    assert recorder.mock_calls == calls
    reset_mocks()

    # cycle 3
    limited_cache.return_value.to_json.side_effect = [{"key": "value"}]
    limited_cache.return_value.staged_commands_as_instructions.side_effect = [instructions]
    schema_key2instruction.side_effect = ["schemaKey2instruction"]
    mock_file_chart.open.return_value.__enter__.return_value.read.side_effect = [json.dumps({"chart": "data"})]
    mock_file_transcript.open.return_value.__enter__.return_value.read.side_effect = [
        json.dumps([l.to_json() for l in lines])
    ]
    commander.transcript2commands.side_effect = [
        (["previous1"], ["effects1"]),
        (["previous2"], ["effects2"]),
        (["previous3"], ["effects3"]),
    ]
    parameters = Namespace(
        chart=mock_file_chart,
        case="theCase",
        transcript=mock_file_transcript,
        cycles=3,
        render=True,
    )
    tested._run(parameters, recorder, identification)

    assert capsys.readouterr().out == "\n".join(exp_out + ["Cycles: 3", ""])
    assert limited_cache.mock_calls == exp_limited_cache
    calls = [call(recorder, identification, limited_cache.return_value)]
    assert render_in_ui.mock_calls == calls
    assert schema_key2instruction.mock_calls == exp_schema_key2instruction
    assert audio_interpreter.mock_calls == exp_audio_interpreter
    calls = [
        call.transcript2commands(recorder, lines[:3], audio_interpreter.return_value, instructions),
        call.transcript2commands(recorder, lines[3:6], audio_interpreter.return_value, ["previous1"]),
        call.transcript2commands(recorder, lines[6:], audio_interpreter.return_value, ["previous2"]),
    ]
    assert commander.mock_calls == calls
    calls = [
        call.get_discussion("theNoteUuid"),
        call.get_discussion().set_cycle(1),
        call.get_discussion().set_cycle(2),
        call.get_discussion().set_cycle(3),
    ]
    assert cached_discussion.mock_calls == calls
    assert mock_file_chart.mock_calls == exp_mock_file
    assert mock_file_transcript.mock_calls == exp_mock_file
    calls = [
        call.case_update_limited_cache({"key": "value"}),
        call.set_cycle(1),
        call.upsert_json(
            "audio2transcript",
            {
                "theCycleKey": [
                    {"speaker": "speakerA", "text": "text1"},
                    {"speaker": "speakerB", "text": "text2"},
                    {"speaker": "speakerA", "text": "text3"},
                ],
            },
        ),
        call.set_cycle(2),
        call.upsert_json(
            "audio2transcript",
            {
                "theCycleKey": [
                    {"speaker": "speakerA", "text": "text4"},
                    {"speaker": "speakerB", "text": "text5"},
                    {"speaker": "speakerB", "text": "text6"},
                ],
            },
        ),
        call.set_cycle(3),
        call.upsert_json(
            "audio2transcript",
            {
                "theCycleKey": [
                    {"speaker": "speakerB", "text": "text7"},
                    {"speaker": "speakerA", "text": "text8"},
                    {"speaker": "speakerA", "text": "text9"},
                ],
            },
        ),
    ]
    assert recorder.mock_calls == calls
    reset_mocks()
