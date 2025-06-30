from argparse import Namespace
from unittest.mock import patch, call

from _pytest.capture import CaptureResult

from evaluations.case_builders.builder_delete import BuilderDelete
from evaluations.structures.evaluation_case import EvaluationCase


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
        call().add_argument("--all", action="store_true"),
        call().add_argument("--case", type=str),
        call().add_argument("--audios", action="store_true", default=False, help="delete audio files"),
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
        monkeypatch,
):
    def reset_mocks():
        parameters.reset_mock()
        auditor_file.reset_mock()
        store_cases.reset_mock()


    tested = BuilderDelete()

    # all cases?
    tests = [
        ("danger", True),
        ("anything", False),
    ]
    for env_value, done in tests:
        store_cases.all.side_effect = [
            [
                EvaluationCase(case_name="theCaseName1"),
                EvaluationCase(case_name="theCaseName2"),
                EvaluationCase(case_name="theCaseName3"),
            ]
        ]
        monkeypatch.setenv("CanDeleteAllCases", env_value)
        parameters.side_effect = [Namespace(case="", all=True, audios=False)]
        tested.run()

        if done:
            exp_out = CaptureResult(
                "Evaluation Case 'theCaseName1' deleted (files and record)\n"
                "Evaluation Case 'theCaseName2' deleted (files and record)\n"
                "Evaluation Case 'theCaseName3' deleted (files and record)\n",
                "")
            assert capsys.readouterr() == exp_out

            calls = [call()]
            assert parameters.mock_calls == calls
            calls = [
                call('theCaseName1', 0),
                call().reset(False),
                call('theCaseName2', 0),
                call().reset(False),
                call('theCaseName3', 0),
                call().reset(False),
            ]
            assert auditor_file.mock_calls == calls
            calls = [
                call.all(),
                call.delete('theCaseName1'),
                call.delete('theCaseName2'),
                call.delete('theCaseName3'),
            ]
            assert store_cases.mock_calls == calls
        else:
            exp_out = CaptureResult("No cases deleted\n", "")
            assert capsys.readouterr() == exp_out

            calls = [call()]
            assert parameters.mock_calls == calls
            assert auditor_file.mock_calls == []
            assert store_cases.mock_calls == []

        reset_mocks()

    # include audio files
    for audios in [True, False]:
        parameters.side_effect = [Namespace(case="theCase", audios=audios, all=False)]
        tested.run()

        exp_out = CaptureResult("Evaluation Case 'theCase' deleted (files and record)\n", "")
        assert capsys.readouterr() == exp_out

        calls = [call()]
        assert parameters.mock_calls == calls
        calls = [
            call('theCase', 0),
            call().reset(audios),
        ]
        assert auditor_file.mock_calls == calls
        calls = [call.delete('theCase')]
        assert store_cases.mock_calls == calls
        reset_mocks()

    # nothing to do
    parameters.side_effect = [Namespace(case="", audios=False, all=False)]
    tested.run()

    exp_out = CaptureResult("No cases deleted\n", "")
    assert capsys.readouterr() == exp_out

    calls = [call()]
    assert parameters.mock_calls == calls
    assert auditor_file.mock_calls == []
    assert store_cases.mock_calls == []
    reset_mocks()
