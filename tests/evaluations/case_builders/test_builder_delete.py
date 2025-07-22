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
        call().add_argument("--all", action="store_true"),
        call().add_argument("--case", type=str),
        call().add_argument("--audios", action="store_true", default=False, help="delete audio files"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_delete.DatastoreCase")
@patch.object(BuilderDelete, "_parameters")
def test_run(
        parameters,
        datastore_case,
        capsys,
        monkeypatch,
):
    def reset_mocks():
        parameters.reset_mock()
        datastore_case.reset_mock()


    tested = BuilderDelete()

    # all cases?
    tests = [
        ("danger", True),
        ("anything", False),
    ]
    for env_value, done in tests:
        datastore_case.all_names.side_effect = [
            [
                "theCaseName1",
                "theCaseName2",
                "theCaseName3",
            ]
        ]
        monkeypatch.setenv("CanDeleteAllCases", env_value)
        parameters.side_effect = [Namespace(case="", all=True, audios=False)]
        tested.run()

        if done:
            exp_out = CaptureResult(
                "Evaluation Case 'theCaseName1' deleted\n"
                "Evaluation Case 'theCaseName2' deleted\n"
                "Evaluation Case 'theCaseName3' deleted\n",
                "")
            assert capsys.readouterr() == exp_out

            calls = [call()]
            assert parameters.mock_calls == calls
            calls = [
                call.all_names(),
                call.delete('theCaseName1', False),
                call.delete('theCaseName2', False),
                call.delete('theCaseName3', False),
            ]
            assert datastore_case.mock_calls == calls
        else:
            exp_out = CaptureResult("No cases deleted\n", "")
            assert capsys.readouterr() == exp_out

            calls = [call()]
            assert parameters.mock_calls == calls
            assert datastore_case.mock_calls == []

        reset_mocks()

    # include audio files
    for audios in [True, False]:
        parameters.side_effect = [Namespace(case="theCase", audios=audios, all=False)]
        tested.run()

        exp_out = CaptureResult("Evaluation Case 'theCase' deleted\n", "")
        assert capsys.readouterr() == exp_out

        calls = [call()]
        assert parameters.mock_calls == calls
        calls = [call.delete('theCase', audios)]
        assert datastore_case.mock_calls == calls
        reset_mocks()

    # nothing to do
    parameters.side_effect = [Namespace(case="", audios=False, all=False)]
    tested.run()

    exp_out = CaptureResult("No cases deleted\n", "")
    assert capsys.readouterr() == exp_out

    calls = [call()]
    assert parameters.mock_calls == calls
    assert datastore_case.mock_calls == []
    reset_mocks()
