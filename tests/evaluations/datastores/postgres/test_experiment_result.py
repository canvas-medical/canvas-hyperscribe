from datetime import datetime, timezone
from unittest.mock import patch, call

from evaluations.datastores.postgres.experiment_result import ExperimentResult
from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.records.experiment_result import ExperimentResult as Record
from tests.helper import compare_sql


def helper_instance() -> ExperimentResult:
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return ExperimentResult(credentials)


def test_class():
    assert issubclass(ExperimentResult, Postgres)


@patch("evaluations.datastores.postgres.experiment_result.datetime", wraps=datetime)
@patch.object(ExperimentResult, "_alter")
def test_insert(alter, mock_datetime):
    def reset_mock():
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 10, 17, 14, 13, 15, 123456, tzinfo=timezone.utc)
    experiment_result = Record(
        experiment_id=523,
        experiment_name="theExperimentName",
        hyperscribe_version="theHyperscribeVersion",
        hyperscribe_tags={"tag1": "value1", "tag2": "value2"},
        case_id=254,
        case_name="theCaseName",
        text_llm_vendor="theTextLLMVendor",
        text_llm_name="theTextLLMName",
        cycle_time=45,
        cycle_transcript_overlap=125,
        failed=True,
        errors={"case": "errors"},
        generated_note_id=631,
        note_json=["note1", "note2"],
        id=333,
    )
    expected = Record(
        experiment_id=523,
        experiment_name="theExperimentName",
        hyperscribe_version="theHyperscribeVersion",
        hyperscribe_tags={"tag1": "value1", "tag2": "value2"},
        case_id=254,
        case_name="theCaseName",
        text_llm_vendor="theTextLLMVendor",
        text_llm_name="theTextLLMName",
        cycle_time=45,
        cycle_transcript_overlap=125,
        failed=True,
        errors={"case": "errors"},
        generated_note_id=631,
        note_json=["note1", "note2"],
        id=351,
    )

    tested = helper_instance()

    alter.side_effect = [351]
    mock_datetime.now.side_effect = [date_0]

    result = tested.insert(experiment_result)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = (
        'INSERT INTO "experiment_result" ("created", "updated",'
        '   "experiment_id", "experiment_name",'
        '   "hyperscribe_version", "hyperscribe_tags",'
        '   "case_id", "case_name",'
        '   "text_llm_vendor", "text_llm_name",'
        '   "cycle_time", "cycle_transcript_overlap",'
        '   "failed", "errors", "generated_note_id",'
        '   "note_json") '
        "VALUES (%(now)s, %(now)s,"
        "  %(experiment_id)s, %(experiment_name)s,"
        "  %(hyperscribe_version)s, %(hyperscribe_tags)s,"
        "  %(case_id)s, %(case_name)s,"
        "  %(text_llm_vendor)s, %(text_llm_name)s,"
        "  %(cycle_time)s, %(cycle_transcript_overlap)s,"
        "  %(failed)s, %(errors)s, %(generated_note_id)s,"
        "  %(note_json)s) "
        "RETURNING id"
    )
    assert compare_sql(sql, exp_sql)
    exp_params = {
        "case_id": 254,
        "case_name": "theCaseName",
        "cycle_time": 45,
        "cycle_transcript_overlap": 125,
        "errors": '{"case":"errors"}',
        "experiment_id": 523,
        "experiment_name": "theExperimentName",
        "failed": True,
        "generated_note_id": 631,
        "hyperscribe_tags": '{"tag1":"value1","tag2":"value2"}',
        "hyperscribe_version": "theHyperscribeVersion",
        "note_json": '["note1","note2"]',
        "text_llm_name": "theTextLLMName",
        "text_llm_vendor": "theTextLLMVendor",
        "now": date_0,
    }
    assert params == exp_params
    assert involved_id is None
    reset_mock()


@patch.object(ExperimentResult, "_update_fields")
def test_update_fields(update_fields):
    def reset_mock():
        update_fields.reset_mock()

    tested = helper_instance()
    tested.update_fields(34, {"theField": "theValue"})

    calls = [call("experiment_result", Record, 34, {"theField": "theValue"})]
    assert update_fields.mock_calls == calls
    reset_mock()


@patch.object(ExperimentResult, "_select")
def test_get_generated_note_id(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()

    # record found
    select.side_effect = [[{"generated_note_id": 117}]]

    result = tested.get_generated_note_id(123)
    expected = 117
    assert result == expected

    exp_sql = 'SELECT "generated_note_id" FROM "experiment_result" WHERE "id" = %(id)s'
    exp_params = {"id": 123}
    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    reset_mock()

    # record not found
    select.side_effect = [[]]

    result = tested.get_generated_note_id(123)
    expected = 0
    assert result == expected

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    reset_mock()
