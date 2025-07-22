from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, call

from evaluations.case_builders.builder_summarize import BuilderSummarize


@patch("evaluations.case_builders.builder_summarize.ArgumentParser")
def test_parameters(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    tested = BuilderSummarize

    argument_parser.return_value.parse_args.side_effect = ["parse_args called"]
    result = tested._parameters()
    expected = "parse_args called"
    assert result == expected

    calls = [
        call(description="Generate a single document with all instructions and generated commands"),
        call().add_argument("--summarize", action="store_true"),
        call().add_argument("--case", type=str, required=True, help="Evaluation case"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_summarize.browser_open")
@patch("evaluations.case_builders.builder_summarize.HelperEvaluation")
@patch.object(BuilderSummarize, "_parameters")
def test_run(parameters, helper, browser_open):
    def reset_mocks():
        parameters.reset_mock()
        helper.reset_mock()
        browser_open.reset_mock()

    tested = BuilderSummarize()

    parameters.side_effect = [Namespace(case="theCase")]
    helper.get_auditor.return_value.generate_html_summary.side_effect = [Path("/from/the/root/file.html")]

    tested.run()

    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call.get_auditor("theCase", 0), call.get_auditor().generate_html_summary()]
    assert helper.mock_calls == calls
    calls = [call("file:///from/the/root/file.html")]
    assert browser_open.mock_calls == calls
    reset_mocks()
