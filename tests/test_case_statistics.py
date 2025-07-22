from unittest.mock import patch, call

from case_statistics import CaseStatistics
from evaluations.datastores.store_results import StoreResults
from evaluations.structures.statistic_case_test import StatisticCaseTest


@patch.object(StoreResults, "case_test_statistics")
def test_run(case_test_statistics, capsys):
    def reset_mocks():
        case_test_statistics.reset_mock()

    tested = CaseStatistics()
    # no records
    case_test_statistics.side_effect = [[]]
    tested.run()

    calls = [call()]
    assert case_test_statistics.mock_calls == calls
    # fmt: off
    exp_out = "\n".join(
        [
            "------------------------------------------------------------------------------------------------------------------------------------------",
            "| case | run count | full run | audio -> questionnaire | audio -> transcript | -> instructions | -> parameters | -> command | end to end |",
            "------------------------------------------------------------------------------------------------------------------------------------------",
            "------------------------------------------------------------------------------------------------------------------------------------------",
            "",
        ],
    )
    # fmt: on
    assert capsys.readouterr().out == exp_out
    reset_mocks()

    # with records
    case_test_statistics.side_effect = [
        [
            StatisticCaseTest(
                case_name="theCase1",
                run_count=2,
                full_run=1,
                staged_questionnaires=1,
                audio2transcript=1,
                transcript2instructions=2,
                instruction2parameters=2,
                parameters2command=1,
                end2end=2,
            ),
            StatisticCaseTest(
                case_name="theCase2",
                run_count=1,
                full_run=0,
                staged_questionnaires=1,
                audio2transcript=-1,
                transcript2instructions=1,
                instruction2parameters=0,
                parameters2command=1,
                end2end=0,
            ),
            StatisticCaseTest(
                case_name="theCase3",
                run_count=1,
                full_run=1,
                staged_questionnaires=-11,
                audio2transcript=-1,
                transcript2instructions=-1,
                instruction2parameters=-1,
                parameters2command=-1,
                end2end=1,
            ),
        ],
    ]
    tested.run()

    calls = [call()]
    assert case_test_statistics.mock_calls == calls
    # ruff: noqa: E501
    exp_out = "\n".join(
        [
            "----------------------------------------------------------------------------------------------------------------------------------------------",
            "| case     | run count | full run | audio -> questionnaire | audio -> transcript | -> instructions | -> parameters | -> command | end to end |",
            "----------------------------------------------------------------------------------------------------------------------------------------------",
            "| theCase1 |     2     |    1     |           1            |          1          |        2        |       2       |     1      |     2      |",
            "| theCase2 |     1     |    0     |           1            |                     |        1        |       0       |     1      |     0      |",
            "| theCase3 |     1     |    1     |                        |                     |                 |               |            |     1      |",
            "----------------------------------------------------------------------------------------------------------------------------------------------",
            "",
        ],
    )
    # End of noqa block
    assert capsys.readouterr().out == exp_out
    reset_mocks()
