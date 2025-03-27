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
    exp_out = "\n".join([
        "------------------------------------------------------------------------------------------------------",
        "| case | run count | audio -> transcript | -> instructions | -> parameters | -> command | end to end |",
        "------------------------------------------------------------------------------------------------------",
        "------------------------------------------------------------------------------------------------------",
        "",
    ])
    assert capsys.readouterr().out == exp_out
    reset_mocks()

    # with records
    case_test_statistics.side_effect = [
        [
            StatisticCaseTest(
                case_name='theCase1',
                run_count=2,
                audio2transcript=1,
                transcript2instructions=2,
                instruction2parameters=2,
                parameters2command=1,
                end2end=2,
            ),
            StatisticCaseTest(
                case_name='theCase2',
                run_count=1,
                audio2transcript=-1,
                transcript2instructions=1,
                instruction2parameters=0,
                parameters2command=1,
                end2end=0,
            ),
            StatisticCaseTest(
                case_name='theCase3',
                run_count=1,
                audio2transcript=-1,
                transcript2instructions=-1,
                instruction2parameters=-1,
                parameters2command=-1,
                end2end=1,
            ),
        ]
    ]
    tested.run()

    calls = [call()]
    assert case_test_statistics.mock_calls == calls
    exp_out = "\n".join([
        "----------------------------------------------------------------------------------------------------------",
        "| case     | run count | audio -> transcript | -> instructions | -> parameters | -> command | end to end |",
        "----------------------------------------------------------------------------------------------------------",
        "| theCase1 |     2     |          1          |        2        |       2       |     1      |     2      |",
        "| theCase2 |     1     |                     |        1        |       0       |     1      |     0      |",
        "| theCase3 |     1     |                     |                 |               |            |     1      |",
        "----------------------------------------------------------------------------------------------------------",
        "",
    ])
    assert capsys.readouterr().out == exp_out
    reset_mocks()
