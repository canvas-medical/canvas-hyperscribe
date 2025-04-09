from unittest.mock import patch, call

from evaluations.datastores.store_cases import StoreCases
from evaluations.datastores.store_results import StoreResults
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.evaluation_result import EvaluationResult
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.statistic_case_test import StatisticCaseTest
from evaluations.structures.statistic_end2end import StatisticEnd2End
from evaluations.structures.statistic_test import StatisticTest


@patch('evaluations.datastores.store_results.StoreResultPostgres')
@patch('evaluations.datastores.store_results.StoreResultsLite')
@patch.object(StoreCases, 'get')
@patch.object(HelperEvaluation, 'postgres_credentials')
def test_insert(postgres_credentials, case_get, lite_store, postgres_store):
    def reset_mock():
        postgres_credentials.reset_mock()
        case_get.reset_mock()
        lite_store.reset_mock()
        postgres_store.reset_mock()

    result = EvaluationResult(
        run_uuid="theRunUuid",
        commit_uuid="theCommitUuid",
        milliseconds=123456.7,
        passed=False,
        test_file="theTestFile",
        test_name="theTestName",
        test_case="theTestCase",
        errors="theErrors",
    )

    tested = StoreResults

    # database defined
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    postgres_credentials.side_effect = [credentials]
    case_get.side_effect = ["theCase"]
    tested.insert(result)

    calls = [call()]
    assert postgres_credentials.mock_calls == calls
    calls = [call("theTestCase")]
    assert case_get.mock_calls == calls
    calls = []
    assert lite_store.mock_calls == calls
    calls = [
        call(credentials),
        call().insert("theCase", result),
    ]
    assert postgres_store.mock_calls == calls
    reset_mock()

    # database NOT defined
    credentials = PostgresCredentials(
        database="",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    postgres_credentials.side_effect = [credentials]
    case_get.side_effect = ["theCase"]
    tested.insert(result)

    calls = [call()]
    assert postgres_credentials.mock_calls == calls
    calls = [call("theTestCase")]
    assert case_get.mock_calls == calls
    calls = [
        call.insert("theCase", result),
    ]
    assert lite_store.mock_calls == calls
    calls = []
    assert postgres_store.mock_calls == calls
    reset_mock()


@patch('evaluations.datastores.store_results.StoreResultPostgres')
@patch('evaluations.datastores.store_results.StoreResultsLite')
@patch.object(HelperEvaluation, 'postgres_credentials')
def test_case_test_statistics(postgres_credentials, lite_store, postgres_store):
    def reset_mock():
        postgres_credentials.reset_mock()
        lite_store.reset_mock()
        postgres_store.reset_mock()

    statistic_tests = [
        StatisticTest(case_name='theCase1', test_name='audio2transcript', passed_count=1),
        StatisticTest(case_name='theCase1', test_name='instruction2parameters', passed_count=2),
        StatisticTest(case_name='theCase1', test_name='parameters2command', passed_count=1),
        StatisticTest(case_name='theCase1', test_name='transcript2instructions', passed_count=2),
        StatisticTest(case_name='theCase2', test_name='instruction2parameters', passed_count=0),
        StatisticTest(case_name='theCase2', test_name='parameters2command', passed_count=1),
        StatisticTest(case_name='theCase2', test_name='transcript2instructions', passed_count=1),
        StatisticTest(case_name='theCase3', test_name='theTest', passed_count=1),
    ]
    statistic_end2ends = [
        StatisticEnd2End(case_name='theCase1', run_count=2, end2end=2),
        StatisticEnd2End(case_name='theCase2', run_count=1, end2end=0),
        StatisticEnd2End(case_name='theCase3', run_count=1, end2end=1),
    ]
    expected = [
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

    tested = StoreResults

    # database defined
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    postgres_credentials.side_effect = [credentials]
    postgres_store.return_value.statistics_per_test.side_effect = [statistic_tests]
    postgres_store.return_value.statistics_end2end.side_effect = [statistic_end2ends]
    lite_store.statistics_per_test.side_effect = []
    lite_store.statistics_end2end.side_effect = []
    result = tested.case_test_statistics()
    assert result == expected

    calls = [call()]
    assert postgres_credentials.mock_calls == calls
    calls = []
    assert lite_store.mock_calls == calls
    calls = [
        call(credentials),
        call().statistics_per_test(),
        call().statistics_end2end(),
    ]
    assert postgres_store.mock_calls == calls
    reset_mock()

    # database NOT defined
    credentials = PostgresCredentials(
        database="",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    postgres_credentials.side_effect = [credentials]
    postgres_store.return_value.statistics_per_test.side_effect = []
    postgres_store.return_value.statistics_end2end.side_effect = []
    lite_store.statistics_per_test.side_effect = [statistic_tests]
    lite_store.statistics_end2end.side_effect = [statistic_end2ends]
    result = tested.case_test_statistics()
    assert result == expected

    calls = [call()]
    assert postgres_credentials.mock_calls == calls
    calls = [
        call.statistics_per_test(),
        call.statistics_end2end(),
    ]
    assert lite_store.mock_calls == calls
    calls = []
    assert postgres_store.mock_calls == calls
    reset_mock()
