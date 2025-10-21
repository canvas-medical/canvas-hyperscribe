from datetime import datetime, timezone
from unittest.mock import patch, call

from evaluations.datastores.postgres.experiment import Experiment
from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.experiment_models import ExperimentModels
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.records.case_id import CaseId as CaseIdRecord
from evaluations.structures.records.experiment import Experiment as Record
from evaluations.structures.records.model import Model as ModelRecord
from tests.helper import compare_sql


def helper_instance() -> Experiment:
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return Experiment(credentials)


def test_class():
    assert issubclass(Experiment, Postgres)


@patch.object(Experiment, "_select")
def test_get_experiment(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()

    # record found
    select.side_effect = [
        [
            {
                "id": 117,
                "name": "theName",
                "cycle_times": [15, 30, 60],
                "cycle_transcript_overlaps": [125],
                "note_replications": 2,
                "grade_replications": 5,
            }
        ]
    ]

    result = tested.get_experiment(123)
    expected = Record(
        id=117,
        name="theName",
        cycle_times=[15, 30, 60],
        cycle_transcript_overlaps=[125],
        note_replications=2,
        grade_replications=5,
    )
    assert result == expected

    exp_sql = (
        'SELECT "id",'
        '       "name",'
        '       "cycle_times",'
        '       "cycle_transcript_overlaps",'
        '       "note_replications",'
        '       "grade_replications" '
        'FROM "experiment" '
        'WHERE "id" = %(id)s'
    )
    exp_params = {"id": 123}
    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    reset_mock()

    # record not found
    select.side_effect = [[]]

    result = tested.get_experiment(123)
    expected = Record()
    assert result == expected

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    reset_mock()


@patch.object(Experiment, "_select")
def test_get_cases(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()

    # record found
    select.side_effect = [
        [
            {"id": 117, "name": "theCase1"},
            {"id": 132, "name": "theCase2"},
            {"id": 147, "name": "theCase3"},
        ]
    ]

    result = tested.get_cases(123)
    expected = [
        CaseIdRecord(id=117, name="theCase1"),
        CaseIdRecord(id=132, name="theCase2"),
        CaseIdRecord(id=147, name="theCase3"),
    ]
    assert result == expected

    exp_sql = (
        'SELECT c."id", c."name" '
        'FROM "experiment_case" ec'
        '         JOIN "case" c ON ec."case_id" = c."id" '
        'WHERE ec."experiment_id" = %(experiment_id)s '
        'ORDER BY c."id"'
    )
    exp_params = {"experiment_id": 123}
    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    reset_mock()

    # record not found
    select.side_effect = [[]]

    result = tested.get_cases(123)
    assert result == []

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    reset_mock()


@patch.object(Experiment, "_select")
def test_get_models(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()

    # record found
    select.side_effect = [
        [
            {
                "generator_id": 117,
                "generator_vendor": "theVendor1",
                "generator_api_key": "theApiKey1",
                "grader_id": 217,
                "grader_vendor": "theVendor4",
                "grader_api_key": "theApiKey4",
                "is_reasoning": True,
            },
            {
                "generator_id": 132,
                "generator_vendor": "theVendor2",
                "generator_api_key": "theApiKey2",
                "grader_id": 232,
                "grader_vendor": "theVendor5",
                "grader_api_key": "theApiKey5",
                "is_reasoning": True,
            },
            {
                "generator_id": 147,
                "generator_vendor": "theVendor3",
                "generator_api_key": "theApiKey3",
                "grader_id": 247,
                "grader_vendor": "theVendor6",
                "grader_api_key": "theApiKey6",
                "is_reasoning": False,
            },
        ]
    ]

    result = tested.get_models(123)
    expected = [
        ExperimentModels(
            experiment_id=123,
            model_generator=ModelRecord(id=117, vendor="theVendor1", api_key="theApiKey1"),
            model_grader=ModelRecord(id=217, vendor="theVendor4", api_key="theApiKey4"),
            grader_is_reasoning=True,
        ),
        ExperimentModels(
            experiment_id=123,
            model_generator=ModelRecord(id=132, vendor="theVendor2", api_key="theApiKey2"),
            model_grader=ModelRecord(id=232, vendor="theVendor5", api_key="theApiKey5"),
            grader_is_reasoning=True,
        ),
        ExperimentModels(
            experiment_id=123,
            model_generator=ModelRecord(id=147, vendor="theVendor3", api_key="theApiKey3"),
            model_grader=ModelRecord(id=247, vendor="theVendor6", api_key="theApiKey6"),
            grader_is_reasoning=False,
        ),
    ]
    assert result == expected

    exp_sql = (
        'SELECT n."id"                              as "generator_id",'
        '       n."vendor"                          as "generator_vendor",'
        '       n."api_key"                         as "generator_api_key",'
        '       g."id"                              as "grader_id",'
        '       g."vendor"                          as "grader_vendor",'
        '       g."api_key"                         as "grader_api_key",'
        '       em."model_note_grader_is_reasoning" as "is_reasoning" '
        'FROM "experiment_model" em '
        '         JOIN "model" n ON em."model_note_generator_id" = n."id" '
        '         JOIN "model" g ON em."model_note_grader_id" = g."id" '
        'WHERE em."experiment_id" = %(experiment_id)s '
        'ORDER BY n."id", g."id" '
    )
    exp_params = {"experiment_id": 123}
    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    reset_mock()

    # record not found
    select.side_effect = [[]]

    result = tested.get_models(123)
    assert result == []

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    reset_mock()


@patch("evaluations.datastores.postgres.experiment.datetime", wraps=datetime)
@patch.object(Experiment, "_alter")
@patch.object(Experiment, "_select")
def test_upsert(select, alter, mock_datetime):
    def reset_mock():
        select.reset_mock()
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 10, 17, 14, 39, 4, 123456, tzinfo=timezone.utc)
    record = Record(
        name="theName",
        cycle_times=[15, 30, 60],
        cycle_transcript_overlaps=[100, 180],
        note_replications=3,
        grade_replications=5,
        id=333,
    )
    expected = Record(
        name="theName",
        cycle_times=[15, 30, 60],
        cycle_transcript_overlaps=[100, 180],
        note_replications=3,
        grade_replications=5,
        id=351,
    )

    tested = helper_instance()
    # insert
    select.side_effect = [[]]
    alter.side_effect = [351]
    mock_datetime.now.side_effect = [date_0]

    result = tested.upsert(record)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    exp_sql = 'SELECT "id" FROM "experiment" WHERE "name"=%(name)s'
    exp_params = {"name": "theName"}
    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params

    exp_sql = (
        'INSERT INTO "experiment" ("created", "updated", "name",'
        ' "cycle_times", "cycle_transcript_overlaps",'
        ' "note_replications", "grade_replications") '
        "VALUES (%(now)s, %(now)s, %(name)s,"
        " %(cycle_times)s, %(cycle_transcript_overlaps)s,"
        " %(note_replications)s, %(grade_replications)s) "
        " RETURNING id"
    )
    exp_params = {
        "name": "theName",
        "cycle_times": "[15,30,60]",
        "cycle_transcript_overlaps": "[100,180]",
        "note_replications": 3,
        "grade_replications": 5,
        "now": date_0,
    }
    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    assert involved_id is None
    reset_mock()

    # update
    select.side_effect = [[{"id": 147}]]
    alter.side_effect = [351]
    mock_datetime.now.side_effect = [date_0]

    result = tested.upsert(record)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    exp_sql = 'SELECT "id" FROM "experiment" WHERE "name"=%(name)s'
    exp_params = {"name": "theName"}
    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params

    exp_sql = (
        'UPDATE "experiment" '
        'SET "updated"=%(now)s,'
        '    "cycle_times"=%(cycle_times)s,'
        '    "cycle_transcript_overlaps"=%(cycle_transcript_overlaps)s,'
        '    "note_replications"=%(note_replications)s,'
        '    "grade_replications"=%(grade_replications)s '
        'WHERE "id" = %(id)s'
        "  AND ("
        '    MD5("cycle_times"::text) != %(cycle_times_md5)s OR'
        '        MD5("cycle_transcript_overlaps"::text) != %(cycle_transcript_overlaps_md5)s OR'
        '        "note_replications" != %(note_replications)s OR'
        '        "grade_replications" != %(grade_replications)s'
        "    )"
    )
    exp_params = {
        "name": "theName",
        "cycle_times": "[15,30,60]",
        "cycle_times_md5": "904053c01f23c0dc343d8e4affb8d841",
        "cycle_transcript_overlaps": "[100,180]",
        "cycle_transcript_overlaps_md5": "dfce538b11e165218931d3e1c8c4cbe9",
        "note_replications": 3,
        "grade_replications": 5,
        "now": date_0,
        "id": 147,
    }
    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    assert involved_id == 147
    reset_mock()


@patch("evaluations.datastores.postgres.experiment.datetime", wraps=datetime)
@patch.object(Experiment, "_alter")
@patch.object(Experiment, "_select")
def test_add_case(select, alter, mock_datetime):
    def reset_mock():
        select.reset_mock()
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 10, 18, 6, 59, 43, 123456, tzinfo=timezone.utc)

    tested = helper_instance()
    # the couple does not exist yet
    select.side_effect = [[]]
    alter.side_effect = [351]
    mock_datetime.now.side_effect = [date_0]

    result = tested.add_case(157, 325)
    expected = 351
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    exp_sql_select = (
        'SELECT "id" FROM "experiment_case" WHERE "experiment_id" = %(experiment_id)s AND "case_id" = %(case_id)s'
    )
    exp_params = {
        "now": date_0,
        "experiment_id": 157,
        "case_id": 325,
    }
    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql_select)
    assert params == exp_params

    exp_sql = (
        'INSERT INTO "experiment_case"("created", "experiment_id", "case_id") '
        "VALUES (%(now)s, %(experiment_id)s, %(case_id)s) RETURNING id"
    )
    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    assert involved_id is None
    reset_mock()

    # the couple does already exist
    select.side_effect = [[{"id": 147}]]
    alter.side_effect = []
    mock_datetime.now.side_effect = [date_0]

    result = tested.add_case(157, 325)
    expected = 147
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql_select)
    assert params == exp_params

    assert alter.mock_calls == []
    reset_mock()


@patch("evaluations.datastores.postgres.experiment.datetime", wraps=datetime)
@patch.object(Experiment, "_alter")
@patch.object(Experiment, "_select")
def test_add_model(select, alter, mock_datetime):
    def reset_mock():
        select.reset_mock()
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 10, 18, 6, 59, 43, 123456, tzinfo=timezone.utc)

    tested = helper_instance()
    # the couple does not exist yet
    select.side_effect = [[]]
    alter.side_effect = [351]
    mock_datetime.now.side_effect = [date_0]

    result = tested.add_model(157, 325)
    expected = 351
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    exp_sql_select = (
        'SELECT "id" FROM "experiment_model" WHERE "experiment_id" = %(experiment_id)s AND "model_id" = %(model_id)s'
    )
    exp_params = {
        "now": date_0,
        "experiment_id": 157,
        "model_id": 325,
    }
    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql_select)
    assert params == exp_params

    exp_sql = (
        'INSERT INTO "experiment_model"("created", "experiment_id", "model_id") '
        "VALUES (%(now)s, %(experiment_id)s, %(model_id)s) RETURNING id"
    )
    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    assert involved_id is None
    reset_mock()

    # the couple does already exist
    select.side_effect = [[{"id": 147}]]
    alter.side_effect = []
    mock_datetime.now.side_effect = [date_0]

    result = tested.add_model(157, 325)
    expected = 147
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql_select)
    assert params == exp_params

    assert alter.mock_calls == []
    reset_mock()


@patch.object(Experiment, "_update_fields")
def test_update_fields(update_fields):
    def reset_mock():
        update_fields.reset_mock()

    tested = helper_instance()
    tested.update_fields(34, {"theField": "theValue"})

    calls = [call("experiment", Record, 34, {"theField": "theValue"})]
    assert update_fields.mock_calls == calls
    reset_mock()
