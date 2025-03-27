from evaluations.datastores.postgres.store_results import StoreResults as StoreResultPostgres
from evaluations.datastores.sqllite.store_cases import StoreCases
from evaluations.datastores.sqllite.store_results import StoreResults as StoreResultsLite
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.evaluation_result import EvaluationResult
from evaluations.structures.statistic_case_test import StatisticCaseTest


class StoreResults:

    @classmethod
    def insert(cls, result: EvaluationResult):
        sql_store = StoreResultsLite
        if (credentials := HelperEvaluation.postgres_credentials()) and credentials.database:
            sql_store = StoreResultPostgres(credentials)
        case = StoreCases.get(result.test_case)
        sql_store.insert(case, result)

    @classmethod
    def case_test_statistics(cls) -> list[StatisticCaseTest]:
        sql_store = StoreResultsLite
        if (credentials := HelperEvaluation.postgres_credentials()) and credentials.database:
            sql_store = StoreResultPostgres(credentials)

        result: dict[str, StatisticCaseTest] = {}
        # get the statistic for the tests
        for record in sql_store.statistics_per_test():
            if record.case_name not in result:
                result[record.case_name] = StatisticCaseTest(case_name=record.case_name)
            if hasattr(result[record.case_name], record.test_name):
                setattr(result[record.case_name], record.test_name, record.passed_count)
        # get the statistics end to end
        for record in sql_store.statistics_end2end():
            result[record.case_name].run_count = record.run_count
            result[record.case_name].end2end = record.end2end

        return list(result.values())
