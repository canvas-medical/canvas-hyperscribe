from datetime import datetime, timezone
from unittest.mock import patch, call

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.datastores.postgres.score import Score
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.records.score import Score as ScoreRecord
from tests.helper import compare_sql


def helper_instance() -> Score:
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return Score(credentials)


def test_class():
    assert issubclass(Score, Postgres)


@patch("evaluations.datastores.postgres.score.datetime", wraps=datetime)
@patch.object(Score, "_alter")
def test_insert(alter, mock_datetime):
    def reset_mock():
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 7, 4, 6, 11, 4, 805952, tzinfo=timezone.utc)
    score = ScoreRecord(
        rubric_id=123,
        generated_note_id=456,
        scoring_result={"criterion1": 8.5, "criterion2": 7.2, "criterion3": 9.1},
        overall_score=8.3,
        comments="theComments",
        text_llm_vendor="theTextLlmVendor",
        text_llm_name="theTextLlmName",
        temperature=0.7,
        experiment=False,
        id=789,
    )
    expected = ScoreRecord(
        rubric_id=123,
        generated_note_id=456,
        scoring_result={"criterion1": 8.5, "criterion2": 7.2, "criterion3": 9.1},
        overall_score=8.3,
        comments="theComments",
        text_llm_vendor="theTextLlmVendor",
        text_llm_name="theTextLlmName",
        temperature=0.7,
        experiment=False,
        id=351,
    )

    tested = helper_instance()

    alter.side_effect = [351]
    mock_datetime.now.side_effect = [date_0]

    result = tested.insert(score)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = """
              INSERT INTO "score" ("created", "updated", "rubric_id", "generated_note_id", "scoring_result",
                                   "overall_score", "comments", "text_llm_vendor", "text_llm_name",
                                   "temperature", "experiment")
              VALUES (%(now)s, %(now)s, %(rubric_id)s, %(generated_note_id)s, %(scoring_result)s,
                      %(overall_score)s, %(comments)s, %(text_llm_vendor)s, %(text_llm_name)s,
                      %(temperature)s, %(experiment)s)
              RETURNING id"""
    assert compare_sql(sql, exp_sql)
    exp_params = {
        "now": date_0,
        "rubric_id": 123,
        "generated_note_id": 456,
        "scoring_result": '{"criterion1":8.5,"criterion2":7.2,"criterion3":9.1}',
        "overall_score": 8.3,
        "comments": "theComments",
        "text_llm_vendor": "theTextLlmVendor",
        "text_llm_name": "theTextLlmName",
        "temperature": 0.7,
        "experiment": False,
    }
    assert params == exp_params
    assert involved_id is None
    reset_mock()
