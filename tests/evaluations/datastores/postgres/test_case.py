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
def test_get_case(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()
    tests = [
        ([], Record(name="theName")),
        ([{
            "name": "theName",
            "transcript": [
                {"speaker": "theSpeaker1", "text": "theText1"},
                {"speaker": "theSpeaker2", "text": "theText2"},
                {},
                {"speaker": "theSpeaker3", "text": "theText3"},
            ],
            "limited_chart": {"limited": "chart"},
            "profile": "theProfile",
            "validation_status": "review",
            "batch_identifier": "theBatchIdentifier",
            "tags": {"tag1": "tag1", "tag2": "tag2"},
            "id": 147,
        }],
         Record(
             name="theName",
             transcript=[
                 Line(speaker="theSpeaker1", text="theText1"),
                 Line(speaker="theSpeaker2", text="theText2"),
                 Line(speaker="", text=""),
                 Line(speaker="theSpeaker3", text="theText3"),
             ],
             limited_chart={"limited": "chart"},
             profile="theProfile",
             validation_status=CaseStatus.REVIEW,
             batch_identifier="theBatchIdentifier",
             tags={"tag1": "tag1", "tag2": "tag2"},
             id=147,
         )
        ),
    ]
    for records, expected in tests:
        select.side_effect = [records]
        result = tested.get_case("theName")
        assert result == expected

        assert len(select.mock_calls) == 1
        sql, params = select.mock_calls[0].args
        exp_sql = ('SELECT "id", "name", "transcript", "limited_chart", "profile",'
                   ' "validation_status", "batch_identifier", "tags" '
                   'FROM "case" '
                   'WHERE "name" = %(name)s')
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
        transcript=[
            Line(speaker="theSpeaker1", text="theText1"),
            Line(speaker="theSpeaker2", text="theText2"),
            Line(speaker="", text=""),
            Line(speaker="theSpeaker3", text="theText3"),
        ],
        limited_chart={"limited": "chart"},
        profile="theProfile",
        validation_status=CaseStatus.REVIEW,
        batch_identifier="theBatchIdentifier",
        tags={"tag1": "tag1", "tag2": "tag2"},
        id=333,
    )
    expected = Record(
        name="theName",
        transcript=[
            Line(speaker="theSpeaker1", text="theText1"),
            Line(speaker="theSpeaker2", text="theText2"),
            Line(speaker="", text=""),
            Line(speaker="theSpeaker3", text="theText3"),
        ],
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
    exp_sql = ('INSERT INTO "case" ("created", "updated", "name", "transcript", "limited_chart", '
               ' "profile", "validation_status", "batch_identifier", "tags") '
               'VALUES (%(now)s, %(now)s, %(name)s, %(transcript)s, %(limited_chart)s, '
               ' %(profile)s, %(validation_status)s, %(batch_identifier)s, %(tags)s) '
               'RETURNING id')
    assert compare_sql(sql, exp_sql)
    exp_params = {
        'batch_identifier': 'theBatchIdentifier',
        'limited_chart': '{"limited": "chart"}',
        'name': 'theName',
        'now': date_0,
        'profile': 'theProfile',
        'tags': '{"tag1": "tag1", "tag2": "tag2"}',
        'transcript': '[{"speaker": "theSpeaker1", "text": "theText1"}, {"speaker": "theSpeaker2", "text": "theText2"}, {"speaker": "", "text": ""}, {"speaker": "theSpeaker3", "text": "theText3"}]',
        'validation_status': 'review',
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
    exp_sql = ('UPDATE "case"'
               ' SET "updated"=%(now)s,'
               '     "name"=%(name)s,'
               '     "transcript"=%(transcript)s,'
               '     "limited_chart"=%(limited_chart)s,'
               '     "profile"=%(profile)s,'
               '     "validation_status"=%(validation_status)s,'
               '     "batch_identifier"=%(batch_identifier)s,'
               '     "tags"=%(tags)s'
               ' WHERE "id" = %(id)s'
               '   AND ('
               '     "name" != %(name)s OR'
               '         "transcript"::jsonb != %(transcript)s::jsonb OR'
               '         "limited_chart"::jsonb != %(limited_chart)s::jsonb OR'
               '         "profile" != %(profile)s OR'
               '         "validation_status" != %(validation_status)s OR'
               '         "batch_identifier" != %(batch_identifier)s OR'
               '         "tags"::jsonb != %(tags)s::jsonb'
               '     )')
    assert compare_sql(sql, exp_sql)
    exp_params = {
        'batch_identifier': 'theBatchIdentifier',
        'id': 147,
        'limited_chart': '{"limited": "chart"}',
        'name': 'theName',
        'now': date_0,
        'profile': 'theProfile',
        'tags': '{"tag1": "tag1", "tag2": "tag2"}',
        'transcript': '[{"speaker": "theSpeaker1", "text": "theText1"}, {"speaker": "theSpeaker2", "text": "theText2"}, {"speaker": "", "text": ""}, {"speaker": "theSpeaker3", "text": "theText3"}]',
        'validation_status': 'review',
    }
    assert params == exp_params
    assert involved_id == 147
    reset_mock()
