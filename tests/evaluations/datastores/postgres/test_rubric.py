from datetime import datetime, timezone
from unittest.mock import patch, call

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.datastores.postgres.rubric import Rubric
from evaluations.structures.enums.rubric_validation import RubricValidation
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.records.rubric import Rubric as RubricRecord
from tests.helper import compare_sql


def helper_instance() -> Rubric:
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return Rubric(credentials)


def test_class():
    assert issubclass(Rubric, Postgres)


@patch("evaluations.datastores.postgres.rubric.datetime", wraps=datetime)
@patch.object(Rubric, "_alter")
@patch.object(Rubric, "_select")
@patch.object(Rubric, "constant_dumps")
def test_upsert(constant_dumps, select, alter, mock_datetime):
    def reset_mock():
        select.reset_mock()
        alter.reset_mock()
        constant_dumps.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 7, 4, 6, 11, 4, 805952, tzinfo=timezone.utc)
    rubric_data = [
        {"criterion": "theCriterion1", "weight": 1, "sense": "positive"},
        {"criterion": "theCriterion2", "weight": 2, "sense": "positive"},
        {"criterion": "theCriterion3", "weight": 3, "sense": "negative"},
    ]
    rubric = RubricRecord(
        case_id=123,
        parent_rubric_id=456,
        validation_timestamp=date_0,
        validation=RubricValidation.ACCEPTED,
        author="theAuthor",
        rubric=rubric_data,
        case_provenance_classification="theClassification",
        comments="theComments",
        text_llm_vendor="VendorX",
        text_llm_name="ModelY",
        temperature=0.7,
        id=123,
    )

    expected = RubricRecord(
        case_id=123,
        parent_rubric_id=456,
        validation_timestamp=date_0,
        validation=RubricValidation.ACCEPTED,
        author="theAuthor",
        rubric=rubric_data,
        case_provenance_classification="theClassification",
        comments="theComments",
        text_llm_vendor="VendorX",
        text_llm_name="ModelY",
        temperature=0.7,
        id=23,
    )

    tested = helper_instance()

    # insert
    select.side_effect = [[]]
    alter.side_effect = [23]
    mock_datetime.now.side_effect = [date_0]
    constant_dumps.side_effect = ['[{"criterion":"theCriterion1","weight":1,"sense":"positive"}]']

    result = tested.upsert(rubric)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    calls = [call(rubric_data)]
    assert constant_dumps.mock_calls == calls

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    exp_sql = 'SELECT "id" FROM "rubric" WHERE "case_id" = %(case_id)s'
    assert compare_sql(sql, exp_sql)
    exp_params = {"case_id": 123}
    assert params == exp_params

    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = """
                INSERT INTO "rubric" (
                    "created", "updated", "case_id", "parent_rubric_id", "validation_timestamp",
                    "validation", "author", "rubric", "case_provenance_classification",
                    "comments", "text_llm_vendor", "text_llm_name", "temperature"
                )
                VALUES (
                    %(now)s, %(now)s, %(case_id)s, %(parent_rubric_id)s, %(validation_timestamp)s,
                    %(validation)s, %(author)s, %(rubric)s, %(case_provenance_classification)s,
                    %(comments)s, %(text_llm_vendor)s, %(text_llm_name)s, %(temperature)s
                )
                RETURNING id
            """

    assert compare_sql(sql, exp_sql)
    exp_params = {
        "now": date_0,
        "case_id": 123,
        "parent_rubric_id": 456,
        "validation_timestamp": date_0,
        "validation": "accepted",
        "author": "theAuthor",
        "rubric": '[{"criterion":"theCriterion1","weight":1,"sense":"positive"}]',
        "case_provenance_classification": "theClassification",
        "comments": "theComments",
        "text_llm_vendor": "VendorX",
        "text_llm_name": "ModelY",
        "temperature": 0.7,
    }
    assert params == exp_params
    assert involved_id is None
    reset_mock()

    # update
    select.side_effect = [[{"id": 777}]]
    alter.side_effect = [23]
    mock_datetime.now.side_effect = [date_0]
    constant_dumps.side_effect = ['[{"criterion":"theCriterion1","weight":1,"sense":"positive"}]']

    result = tested.upsert(rubric)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    calls = [call(rubric_data)]
    assert constant_dumps.mock_calls == calls

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    exp_sql = 'SELECT "id" FROM "rubric" WHERE "case_id" = %(case_id)s'
    assert compare_sql(sql, exp_sql)
    exp_params = {"case_id": 123}
    assert params == exp_params

    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = """
                UPDATE "rubric"
                SET "updated" = %(now)s,
                    "parent_rubric_id" = %(parent_rubric_id)s,
                    "validation_timestamp" = %(validation_timestamp)s,
                    "validation" = %(validation)s,
                    "author" = %(author)s,
                    "rubric" = %(rubric)s,
                    "case_provenance_classification" = %(case_provenance_classification)s,
                    "comments" = %(comments)s,
                    "text_llm_vendor" = %(text_llm_vendor)s,
                    "text_llm_name" = %(text_llm_name)s,
                    "temperature" = %(temperature)s
                WHERE "id" = %(id)s
            """
    assert compare_sql(sql, exp_sql)
    exp_params = {
        "now": date_0,
        "id": 777,
        "case_id": 123,
        "parent_rubric_id": 456,
        "validation_timestamp": date_0,
        "validation": "accepted",
        "author": "theAuthor",
        "rubric": '[{"criterion":"theCriterion1","weight":1,"sense":"positive"}]',
        "case_provenance_classification": "theClassification",
        "comments": "theComments",
        "text_llm_vendor": "VendorX",
        "text_llm_name": "ModelY",
        "temperature": 0.7,
    }
    assert involved_id == 777
    assert params == exp_params
    reset_mock()


@patch("evaluations.datastores.postgres.rubric.datetime", wraps=datetime)
@patch.object(Rubric, "_alter")
@patch.object(Rubric, "constant_dumps")
def test_insert(constant_dumps, alter, mock_datetime):
    def reset_mocks():
        alter.reset_mock()
        constant_dumps.reset_mock()
        mock_datetime.reset_mock()

    # Test insert creates new rubric record
    date_0 = datetime(2025, 7, 4, 6, 11, 4, 805952, tzinfo=timezone.utc)
    rubric_data = [
        {"criterion": "theCriterion1", "weight": 1, "sense": "positive"},
        {"criterion": "theCriterion2", "weight": 2, "sense": "positive"},
        {"criterion": "theCriterion3", "weight": 3, "sense": "negative"},
    ]
    rubric = RubricRecord(
        case_id=123,
        parent_rubric_id=456,
        validation_timestamp=date_0,
        validation=RubricValidation.ACCEPTED,
        author="theAuthor",
        rubric=rubric_data,
        case_provenance_classification="theClassification",
        comments="theComments",
        text_llm_vendor="VendorX",
        text_llm_name="ModelY",
        temperature=0.7,
        id=123,
    )

    alter.side_effect = [23]
    mock_datetime.now.side_effect = [date_0]
    constant_dumps.side_effect = ['[{"criterion":"theCriterion1","weight":1,"sense":"positive"}]']

    tested = helper_instance()
    result = tested.insert(rubric)
    expected = RubricRecord(
        case_id=123,
        parent_rubric_id=456,
        validation_timestamp=date_0,
        validation=RubricValidation.ACCEPTED,
        author="theAuthor",
        rubric=rubric_data,
        case_provenance_classification="theClassification",
        comments="theComments",
        text_llm_vendor="VendorX",
        text_llm_name="ModelY",
        temperature=0.7,
        id=23,
    )
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls
    calls = [call(rubric_data)]
    assert constant_dumps.mock_calls == calls
    calls = [
        call(
            """
            INSERT INTO "rubric" (
                "created", "updated", "case_id", "parent_rubric_id", "validation_timestamp",
                "validation", "author", "rubric", "case_provenance_classification",
                "comments", "text_llm_vendor", "text_llm_name", "temperature"
            )
            VALUES (
                %(now)s, %(now)s, %(case_id)s, %(parent_rubric_id)s, %(validation_timestamp)s,
                %(validation)s, %(author)s, %(rubric)s, %(case_provenance_classification)s,
                %(comments)s, %(text_llm_vendor)s, %(text_llm_name)s, %(temperature)s
            )
            RETURNING id
        """,
            {
                "now": date_0,
                "case_id": 123,
                "parent_rubric_id": 456,
                "validation_timestamp": date_0,
                "validation": "accepted",
                "author": "theAuthor",
                "rubric": '[{"criterion":"theCriterion1","weight":1,"sense":"positive"}]',
                "case_provenance_classification": "theClassification",
                "comments": "theComments",
                "text_llm_vendor": "VendorX",
                "text_llm_name": "ModelY",
                "temperature": 0.7,
            },
            None,
        )
    ]
    assert alter.mock_calls == calls
    reset_mocks()


@patch.object(Rubric, "_select")
def test_get_rubric(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()

    # Test rubric found
    rubric_data = [
        {"criterion": "theCriterion1", "weight": 1, "sense": "positive"},
        {"criterion": "theCriterion2", "weight": 2, "sense": "positive"},
    ]
    select.side_effect = [[{"rubric": rubric_data}]]

    result = tested.get_rubric(123)
    assert result == rubric_data

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    exp_sql = 'SELECT "rubric" FROM "rubric" WHERE "id" = %(id)s'
    assert compare_sql(sql, exp_sql)
    exp_params = {"id": 123}
    assert params == exp_params
    reset_mock()

    # Test rubric not found
    select.side_effect = [[]]

    result = tested.get_rubric(456)
    assert result == []

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    exp_sql = 'SELECT "rubric" FROM "rubric" WHERE "id" = %(id)s'
    assert compare_sql(sql, exp_sql)
    exp_params = {"id": 456}
    assert params == exp_params
    reset_mock()
