from typing import Type

from evaluations.datastores.postgres.store_results import StoreResults as StoreResultPostgres
from evaluations.datastores.sqllite.store_results import StoreResults as StoreResultsLite
from evaluations.datastores.store_cases import StoreCases
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.evaluation_result import EvaluationResult
from evaluations.structures.statistic_case_test import StatisticCaseTest


class StoreResults:

    @classmethod
    def insert(cls, result: EvaluationResult) -> None:
        sql_store: Type[StoreResultsLite] | StoreResultPostgres = StoreResultsLite
        if (credentials := HelperEvaluation.postgres_credentials()) and credentials.database:
            sql_store = StoreResultPostgres(credentials)
        case = StoreCases.get(result.case_name)
        sql_store.insert(case, result)

    @classmethod
    def case_test_statistics(cls) -> list[StatisticCaseTest]:
        sql_store: Type[StoreResultsLite] | StoreResultPostgres = StoreResultsLite
        if (credentials := HelperEvaluation.postgres_credentials()) and credentials.database:
            sql_store = StoreResultPostgres(credentials)

        result: dict[str, StatisticCaseTest] = {}
        # get the statistic for the tests
        for per_test in sql_store.statistics_per_test():
            if per_test.case_name not in result:
                result[per_test.case_name] = StatisticCaseTest(case_name=per_test.case_name)
            if hasattr(result[per_test.case_name], per_test.test_name):
                setattr(result[per_test.case_name], per_test.test_name, per_test.passed_count)
        # get the statistics end to end
        for end2end in sql_store.statistics_end2end():
            result[end2end.case_name].run_count = end2end.run_count
            result[end2end.case_name].end2end = end2end.end2end

        return list(result.values())
