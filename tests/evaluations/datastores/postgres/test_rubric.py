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


@patch("evaluations.datastores.postgres.rubric.datetime", wraps=datetime)
@patch.object(Rubric, "insert")
@patch.object(Rubric, "_alter")
@patch.object(Rubric, "_select")
@patch.object(Rubric, "constant_dumps")
def test_upsert(constant_dumps, select, alter, mock_insert, mock_datetime):
    def reset_mock():
        select.reset_mock()
        alter.reset_mock()
        constant_dumps.reset_mock()
        mock_insert.reset_mock()
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
    mock_insert.side_effect = [expected]

    result = tested.upsert(rubric)
    assert result == expected

    calls = [call('SELECT "id" FROM "rubric" WHERE "case_id" = %(case_id)s', {"case_id": 123})]
    assert select.mock_calls == calls

    calls = [call(rubric)]
    assert mock_insert.mock_calls == calls
    assert alter.mock_calls == []
    assert constant_dumps.mock_calls == []
    assert mock_datetime.mock_calls == []
    reset_mock()

    # update
    select.side_effect = [[{"id": 777}]]
    alter.side_effect = [23]
    mock_datetime.now.side_effect = [date_0]
    constant_dumps.side_effect = ['[{"criterion":"theCriterion1","weight":1,"sense":"positive"}]']

    result = tested.upsert(rubric)
    assert result == expected

    assert mock_insert.mock_calls == []
    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    calls = [call(rubric_data)]
    assert constant_dumps.mock_calls == calls

    calls = [call('SELECT "id" FROM "rubric" WHERE "case_id" = %(case_id)s', {"case_id": 123})]
    assert select.mock_calls == calls

    calls = [
        call(
            """
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
            """,
            {
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
            },
            777,
        )
    ]
    assert alter.mock_calls == calls
    reset_mock()


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

    calls = [call('SELECT "rubric" FROM "rubric" WHERE "id" = %(id)s', {"id": 123})]
    assert select.mock_calls == calls
    reset_mock()

    # Test rubric not found
    select.side_effect = [[]]

    result = tested.get_rubric(456)
    assert result == []

    calls = [call('SELECT "rubric" FROM "rubric" WHERE "id" = %(id)s', {"id": 456})]
    assert select.mock_calls == calls
    reset_mock()


@patch.object(Rubric, "_select")
def test_get_last_accepted(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()

    select.side_effect = [[{"rubric_id": 177}, {"rubric_id": 173}, {"rubric_id": 221}]]

    result = tested.get_last_accepted(123)
    expected = [177, 173, 221]
    assert result == expected

    exp_sql = (
        "WITH latest_by_author AS (SELECT DISTINCT "
        "ON (author) "
        "    id as rubric_id, "
        "    author, "
        "    validation_timestamp "
        "FROM rubric "
        "WHERE case_id = %(case_id)s "
        "  AND validation = %(accepted)s "
        "  AND author LIKE %(email_like)s "
        "ORDER BY author, validation_timestamp DESC "
        "    ) "
        "SELECT rubric_id "
        "FROM latest_by_author "
        "ORDER BY validation_timestamp DESC "
    )
    exp_params = {
        "accepted": "accepted",
        "case_id": 123,
        "email_like": "%@%",
    }
    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    reset_mock()

    # Test rubric not found
    select.side_effect = [[]]

    result = tested.get_last_accepted(123)
    assert result == []

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    assert compare_sql(sql, exp_sql)
    assert params == exp_params
    reset_mock()
