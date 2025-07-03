import json
from argparse import Namespace
from unittest.mock import patch, call, MagicMock

from evaluations.case_builders.builder_from_chart_transcript import BuilderFromChartTranscript
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.structures.identification_parameters import IdentificationParameters


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
        call().add_argument("--chart", type=BuilderFromChartTranscript.validate_files, required=True, help="Path to limited_cache JSON file"),
        call().add_argument("--transcript", type=BuilderFromChartTranscript.validate_files, required=True, help="Path to transcript JSON file"),
        call().add_argument("--group", type=str, default="common", help="Group of the case"),
        call().add_argument("--type", type=str, choices=["situational", "general"], default="general", help="Type of the case"),
        call().add_argument("--cycles", type=int, default=1, help="Number of transcript cycles"),
        call().add_argument("--render", action="store_true", help="Render commands to UI"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls


@patch("evaluations.case_builders.builder_from_chart_transcript.CachedSdk")
@patch("evaluations.case_builders.builder_from_chart_transcript.Commander")
@patch("evaluations.case_builders.builder_from_chart_transcript.AudioInterpreter")
@patch("evaluations.case_builders.builder_from_chart_transcript.HelperEvaluation")
@patch("evaluations.case_builders.builder_from_chart_transcript.StoreCases")
@patch("evaluations.case_builders.builder_from_chart_transcript.LimitedCache")
@patch("evaluations.case_builders.builder_from_chart_transcript.Line")
@patch.object(BuilderFromChartTranscript, "_render_in_ui")
def test__run_single_cycle(
    render_in_ui,
    Line,
    LimitedCache,
    StoreCases,
    HelperEvaluation,
    AudioInterpreter,
    Commander,
    CachedSdk
):
    # Setup
    parameters = Namespace(
        case="TestCase",
        chart=MagicMock(),
        transcript=MagicMock(),
        group="common",
        type="general",
        cycles=1,
        render=True,
    )

    identification = IdentificationParameters(
        patient_uuid="patient123",
        note_uuid="note123",
        provider_uuid="provider123",
        canvas_instance="canvas123"
    )

    # Fake JSON inputs
    chart_json = {"fake": "chart"}
    transcript_json = [{"speaker": "Clinician", "text": "Take your meds"}]

    parameters.chart.open.return_value.__enter__.return_value.read.return_value = json.dumps(chart_json)
    parameters.transcript.open.return_value.__enter__.return_value.read.return_value = json.dumps(transcript_json)

    LimitedCache.load_from_json.return_value.staged_commands_as_instructions.return_value = ["prev_cmd"]
    CachedSdk.get_discussion.return_value.set_cycle = MagicMock()
    Commander.transcript2commands.return_value = None

    # Run test
    BuilderFromChartTranscript._run(parameters, MagicMock(), identification)

    # Assertions
    assert StoreCases.upsert.call_count == 1
    assert AudioInterpreter.call_count == 1
    Commander.transcript2commands.assert_called_once()
    CachedSdk.get_discussion.return_value.set_cycle.assert_called_once_with(1)
    render_in_ui.assert_called_once()


@patch("evaluations.case_builders.builder_from_chart_transcript.CachedSdk")
@patch("evaluations.case_builders.builder_from_chart_transcript.Commander")
@patch("evaluations.case_builders.builder_from_chart_transcript.AudioInterpreter")
@patch("evaluations.case_builders.builder_from_chart_transcript.HelperEvaluation")
@patch("evaluations.case_builders.builder_from_chart_transcript.StoreCases")
@patch("evaluations.case_builders.builder_from_chart_transcript.LimitedCache")
@patch("evaluations.case_builders.builder_from_chart_transcript.Line")
@patch.object(BuilderFromChartTranscript, "_render_in_ui")
def test__run_multi_cycle(
    render_in_ui,
    Line,
    LimitedCache,
    StoreCases,
    HelperEvaluation,
    AudioInterpreter,
    Commander,
    CachedSdk
):
    parameters = Namespace(
        case="MultiCycleCase",
        chart=MagicMock(),
        transcript=MagicMock(),
        group="common",
        type="general",
        cycles=2,
        render=False,
    )

    identification = IdentificationParameters(
        patient_uuid="p", note_uuid="n", provider_uuid="x", canvas_instance="c"
    )

    transcript_lines = [{"speaker": "C", "text": "t1"}, {"speaker": "P", "text": "t2"}]
    parameters.chart.open.return_value.__enter__.return_value.read.return_value = json.dumps({"chart": "data"})
    parameters.transcript.open.return_value.__enter__.return_value.read.return_value = json.dumps(transcript_lines)

    LimitedCache.load_from_json.return_value.staged_commands_as_instructions.return_value = ["prev"]
    CachedSdk.get_discussion.return_value.set_cycle = MagicMock()
    Commander.transcript2commands.side_effect = [("prev1", None), ("prev2", None)]

    BuilderFromChartTranscript._run(parameters, MagicMock(), identification)

    assert Commander.transcript2commands.call_count == 2
    CachedSdk.get_discussion.return_value.set_cycle.assert_has_calls([call(1), call(2)])
    render_in_ui.assert_not_called()
