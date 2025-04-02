from argparse import Namespace
from unittest.mock import patch, call

from _pytest.capture import CaptureResult

from evaluations.case_builders.builder_delete import BuilderDelete


@patch("evaluations.case_builders.builder_delete.ArgumentParser")
def test_parameters(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    tested = BuilderDelete

    argument_parser.return_value.parse_args.side_effect = ["parse_args called"]
    result = tested._parameters()
    expected = "parse_args called"
    assert result == expected

    calls = [
        call(description="Delete all files and case record related to the built case."),
        call().add_argument("--delete", action="store_true"),
        call().add_argument("--case", type=str),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_delete.StoreCases")
@patch("evaluations.case_builders.builder_delete.AuditorFile")
@patch.object(BuilderDelete, "_parameters")
def test_run(
        parameters,
        auditor_file,
        store_cases,
        capsys,
):
    def reset_mocks():
        parameters.reset_mock()
        auditor_file.reset_mock()
        store_cases.reset_mock()

    tested = BuilderDelete()
    parameters.side_effect = [Namespace(case="theCase")]
    result = tested.run()
    assert result is None

    exp_out = CaptureResult("Evaluation Case 'theCase' deleted (files and record)\n", "")
    assert capsys.readouterr() == exp_out

    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [
        call('theCase'),
        call().reset(),
    ]
    assert auditor_file.mock_calls == calls
    calls = [call.delete('theCase')]
    assert store_cases.mock_calls == calls
    reset_mocks()
