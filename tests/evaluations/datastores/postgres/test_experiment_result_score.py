from datetime import datetime, timezone
from unittest.mock import patch, call

from evaluations.datastores.postgres.experiment_result_score import ExperimentResultScore
from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.graded_criterion import GradedCriterion
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.records.experiment_result_score import ExperimentResultScore as Record
from tests.helper import compare_sql


def helper_instance() -> ExperimentResultScore:
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return ExperimentResultScore(credentials)


def test_class():
    assert issubclass(ExperimentResultScore, Postgres)


@patch("evaluations.datastores.postgres.experiment_result_score.datetime", wraps=datetime)
@patch.object(ExperimentResultScore, "_alter")
def test_insert(alter, mock_datetime):
    def reset_mock():
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 10, 17, 14, 7, 21, 123456, tzinfo=timezone.utc)
    experiment_result_score = Record(
        experiment_result_id=133,
        score_id=435,
        scoring_result=[GradedCriterion(id=0, rationale="good work", satisfaction=85, score=8.5)],
        id=333,
    )
    expected = Record(
        experiment_result_id=133,
        score_id=435,
        scoring_result=[GradedCriterion(id=0, rationale="good work", satisfaction=85, score=8.5)],
        id=351,
    )

    tested = helper_instance()

    alter.side_effect = [351]
    mock_datetime.now.side_effect = [date_0]

    result = tested.insert(experiment_result_score)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = (
        'INSERT INTO "experiment_result_score" ("created", "experiment_result_id", "score_id", "scoring_result") '
        "VALUES (%(now)s, %(experiment_result_id)s, %(score_id)s, %(scoring_result)s) "
        "RETURNING id"
    )
    assert compare_sql(sql, exp_sql)
    exp_params = {
        "experiment_result_id": 133,
        "score_id": 435,
        "scoring_result": '[{"id":0,"rationale":"good work","satisfaction":85,"score":8.5}]',
        "now": date_0,
    }
    assert params == exp_params
    assert involved_id is None
    reset_mock()
