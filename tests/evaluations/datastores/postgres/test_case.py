from datetime import datetime, timezone
from unittest.mock import patch, call

from evaluations.datastores.postgres.case import Case
from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.enums.case_status import CaseStatus
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.records.case import Case as Record
from hyperscribe.structures.line import Line
from tests.helper import compare_sql


def helper_instance() -> Case:
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return Case(credentials)


def test_class():
    assert issubclass(Case, Postgres)


@patch.object(Case, "_select")
def test_all_names(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()

    select.side_effect = [[{"name": "name1"}, {"name": "name2"}, {"name": "name3"}]]
    result = tested.all_names()
    expected = ["name1", "name2", "name3"]
    assert result == expected

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    exp_sql = 'SELECT "name" FROM "case" ORDER BY "name"'
    assert compare_sql(sql, exp_sql)
    assert params == {}
    reset_mock()


@patch.object(Case, "_select")
def test_get_first_n_cases(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()

    tests = [
        (5, [{"name": "case1"}, {"name": "case2"}, {"name": "case3"}], ["case1", "case2", "case3"]),
        (2, [{"name": "case1"}, {"name": "case2"}], ["case1", "case2"]),
        (10, [], []),
        (1, [{"name": "case1"}], ["case1"]),
    ]
    for n, records, expected in tests:
        select.side_effect = [records]
        result = tested.get_first_n_cases(n)
        assert result == expected

        assert len(select.mock_calls) == 1
        sql, params = select.mock_calls[0].args
        exp_sql = 'SELECT "name" FROM "case" ORDER BY "id" LIMIT %(limit)s'
        assert compare_sql(sql, exp_sql)
        exp_params = {"limit": n}
        assert params == exp_params
        reset_mock()


@patch.object(Case, "_select")
def test_get_id(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()

    test = [([{"id": 34}], 34), ([], 0)]
    for records, expected in test:
        select.side_effect = [records]
        result = tested.get_id("theCase")
        assert result == expected

        assert len(select.mock_calls) == 1
        sql, params = select.mock_calls[0].args
        exp_sql = 'SELECT "id" FROM "case" WHERE "name" = %(name)s'
        assert compare_sql(sql, exp_sql)
        exp_params = {"name": "theCase"}
        assert params == exp_params
        reset_mock()


@patch.object(Case, "_select")
def test_get_limited_chart(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()

    test = [([{"limited_chart": {"limited": "chart"}}], {"limited": "chart"}), ([], {})]
    for records, expected in test:
        select.side_effect = [records]
        result = tested.get_limited_chart(34)
        assert result == expected

        assert len(select.mock_calls) == 1
        sql, params = select.mock_calls[0].args
        exp_sql = 'SELECT "limited_chart" FROM "case" WHERE "id" = %(case_id)s'
        assert compare_sql(sql, exp_sql)
        exp_params = {"case_id": 34}
        assert params == exp_params
        reset_mock()


@patch.object(Case, "_select")
def test_get_transcript(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()

    test = [
        (
            [
                {
                    "transcript": {
                        "cycle_001": [
                            {"speaker": "theSpeaker1", "text": "theText1"},
                            {"speaker": "theSpeaker2", "text": "theText2"},
                            {},
                        ],
                        "cycle_002": [{"speaker": "theSpeaker3", "text": "theText3"}],
                    },
                },
            ],
            {
                "cycle_001": [
                    Line(speaker="theSpeaker1", text="theText1"),
                    Line(speaker="theSpeaker2", text="theText2"),
                    Line(speaker="", text=""),
                ],
                "cycle_002": [Line(speaker="theSpeaker3", text="theText3")],
            },
        ),
        ([], {}),
    ]
    for records, expected in test:
        select.side_effect = [records]
        result = tested.get_transcript(34)
        assert result == expected

        assert len(select.mock_calls) == 1
        sql, params = select.mock_calls[0].args
        exp_sql = 'SELECT "transcript" FROM "case" WHERE "id" = %(case_id)s'
        assert compare_sql(sql, exp_sql)
        exp_params = {"case_id": 34}
        assert params == exp_params
        reset_mock()


@patch.object(Case, "_select")
def test_get_case(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()
    tests = [
        ([], Record(name="theName")),
        (
            [
                {
                    "name": "theName",
                    "transcript": {
                        "cycle_001": [
                            {"speaker": "theSpeaker1", "text": "theText1"},
                            {"speaker": "theSpeaker2", "text": "theText2"},
                            {},
                        ],
                        "cycle_002": [{"speaker": "theSpeaker3", "text": "theText3"}],
                    },
                    "limited_chart": {"limited": "chart"},
                    "profile": "theProfile",
                    "validation_status": "review",
                    "batch_identifier": "theBatchIdentifier",
                    "tags": {"tag1": "tag1", "tag2": "tag2"},
                    "id": 147,
                },
            ],
            Record(
                name="theName",
                transcript={
                    "cycle_001": [
                        Line(speaker="theSpeaker1", text="theText1"),
                        Line(speaker="theSpeaker2", text="theText2"),
                        Line(speaker="", text=""),
                    ],
                    "cycle_002": [Line(speaker="theSpeaker3", text="theText3")],
                },
                limited_chart={"limited": "chart"},
                profile="theProfile",
                validation_status=CaseStatus.REVIEW,
                batch_identifier="theBatchIdentifier",
                tags={"tag1": "tag1", "tag2": "tag2"},
                id=147,
            ),
        ),
    ]
    for records, expected in tests:
        select.side_effect = [records]
        result = tested.get_case("theName")
        assert result == expected

        assert len(select.mock_calls) == 1
        sql, params = select.mock_calls[0].args
        exp_sql = (
            'SELECT "id", "name", "transcript", "limited_chart", "profile",'
            ' "validation_status", "batch_identifier", "tags" '
            'FROM "case" '
            'WHERE "name" = %(name)s'
        )
        assert compare_sql(sql, exp_sql)
        exp_params = {"name": "theName"}
        assert params == exp_params
        reset_mock()


@patch("evaluations.datastores.postgres.case.datetime", wraps=datetime)
@patch.object(Case, "_alter")
@patch.object(Case, "_select")
def test_upsert(select, alter, mock_datetime):
    def reset_mock():
        select.reset_mock()
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 7, 4, 6, 11, 4, 805952, tzinfo=timezone.utc)
    case = Record(
        name="theName",
        transcript={
            "cycle_001": [
                Line(speaker="theSpeaker1", text="theText1"),
                Line(speaker="theSpeaker2", text="theText2"),
                Line(speaker="", text=""),
            ],
            "cycle_002": [Line(speaker="theSpeaker3", text="theText3")],
        },
        limited_chart={"limited": "chart"},
        profile="theProfile",
        validation_status=CaseStatus.REVIEW,
        batch_identifier="theBatchIdentifier",
        tags={"tag1": "tag1", "tag2": "tag2"},
        id=333,
    )
    expected = Record(
        name="theName",
        transcript={
            "cycle_001": [
                Line(speaker="theSpeaker1", text="theText1"),
                Line(speaker="theSpeaker2", text="theText2"),
                Line(speaker="", text=""),
            ],
            "cycle_002": [Line(speaker="theSpeaker3", text="theText3")],
        },
        limited_chart={"limited": "chart"},
        profile="theProfile",
        validation_status=CaseStatus.REVIEW,
        batch_identifier="theBatchIdentifier",
        tags={"tag1": "tag1", "tag2": "tag2"},
        id=351,
    )

    tested = helper_instance()
    # insert
    select.side_effect = [[]]
    alter.side_effect = [351]
    mock_datetime.now.side_effect = [date_0]

    result = tested.upsert(case)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    exp_sql = 'SELECT "id" FROM "case" WHERE "name"=%(name)s'
    assert compare_sql(sql, exp_sql)
    exp_params = {"name": "theName"}
    assert params == exp_params
    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = (
        'INSERT INTO "case" ("created", "updated", "name", "transcript", "limited_chart", '
        ' "profile", "validation_status", "batch_identifier", "tags") '
        "VALUES (%(now)s, %(now)s, %(name)s, %(transcript)s, %(limited_chart)s, "
        " %(profile)s, %(validation_status)s, %(batch_identifier)s, %(tags)s) "
        "RETURNING id"
    )
    assert compare_sql(sql, exp_sql)
    exp_params = {
        "batch_identifier": "theBatchIdentifier",
        "limited_chart": '{"limited":"chart"}',
        "name": "theName",
        "now": date_0,
        "profile": "theProfile",
        "tags": '{"tag1":"tag1","tag2":"tag2"}',
        "transcript": '{"cycle_001":[{"speaker":"theSpeaker1","text":"theText1"},'
        '{"speaker":"theSpeaker2","text":"theText2"},{"speaker":"","text":""}],'
        '"cycle_002":[{"speaker":"theSpeaker3","text":"theText3"}]}',
        "validation_status": "review",
    }
    assert params == exp_params
    assert involved_id is None
    reset_mock()

    # update
    select.side_effect = [[{"id": 147}]]
    alter.side_effect = [351]
    mock_datetime.now.side_effect = [date_0]

    result = tested.upsert(case)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    exp_sql = 'SELECT "id" FROM "case" WHERE "name"=%(name)s'
    assert compare_sql(sql, exp_sql)
    exp_params = {"name": "theName"}
    assert params == exp_params
    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = (
        'UPDATE "case" SET "updated"=%(now)s, "name"=%(name)s, "transcript"=%(transcript)s, '
        '"limited_chart"=%(limited_chart)s, "profile"=%(profile)s, "validation_status"=%(validation_status)s, '
        '"batch_identifier"=%(batch_identifier)s, "tags"=%(tags)s '
        'WHERE "id" = %(id)s AND ( "name" != %(name)s'
        ' OR MD5("transcript"::text) != %(transcript_md5)s'
        ' OR MD5("limited_chart"::text) != %(limited_chart_md5)s'
        ' OR "profile" != %(profile)s'
        ' OR "validation_status" != %(validation_status)s'
        ' OR "batch_identifier" != %(batch_identifier)s'
        ' OR MD5("tags"::text) != %(tags_md5)s )'
    )
    assert compare_sql(sql, exp_sql)
    exp_params = {
        "batch_identifier": "theBatchIdentifier",
        "id": 147,
        "limited_chart": '{"limited":"chart"}',
        "limited_chart_md5": "940793dd3b4d27e6d56dbec1e1ba59ed",
        "name": "theName",
        "now": date_0,
        "profile": "theProfile",
        "tags": '{"tag1":"tag1","tag2":"tag2"}',
        "tags_md5": "d4e924bd09088665e5dd1403881a7f09",
        "transcript": '{"cycle_001":['
        '{"speaker":"theSpeaker1","text":"theText1"},'
        '{"speaker":"theSpeaker2","text":"theText2"},'
        '{"speaker":"","text":""}],'
        '"cycle_002":[{"speaker":"theSpeaker3","text":"theText3"}]}',
        "transcript_md5": "5d164dbf3550fdf5531b449c69d9cae9",
        "validation_status": "review",
    }
    assert params == exp_params
    assert involved_id == 147
    reset_mock()


@patch.object(Case, "_update_fields")
def test_update_fields(update_fields):
    def reset_mock():
        update_fields.reset_mock()

    tested = helper_instance()
    tested.update_fields(34, {"theField": "theValue"})

    calls = [call("case", Record, 34, {"theField": "theValue"})]
    assert update_fields.mock_calls == calls
    reset_mock()
