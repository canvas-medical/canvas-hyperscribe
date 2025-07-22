from datetime import datetime, timezone
from enum import Enum
from typing import NamedTuple
from unittest.mock import patch, MagicMock, call

from psycopg import sql as sqlist

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.postgres_credentials import PostgresCredentials
from tests.helper import compare_sql


def helper_instance() -> Postgres:
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return Postgres(credentials)


def test_constant_dumps():
    tested = Postgres
    tests = [
        ({}, "{}"),
        ({"b": "word1", "c": "word2", "a": "word3"}, '{"a":"word3","b":"word1","c":"word2"}'),
        ({"b": "word1", "a": "word3", "c": "word2"}, '{"a":"word3","b":"word1","c":"word2"}'),
    ]
    for data, expected in tests:
        result = tested.constant_dumps(data)
        assert result == expected, f"---> {data}"


def test_md5_from():
    tested = Postgres
    tests = [
        ("", "d41d8cd98f00b204e9800998ecf8427e"),
        ("abcd", "e2fc714c4727ee9395f324cd2e7f331f"),
        ("1234", "81dc9bdb52d04dc20036dbd8313ed055"),
    ]
    for data, expected in tests:
        result = tested.md5_from(data)
        assert result == expected, f"---> {data}"


def test___init__():
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    tested = Postgres(credentials)
    assert tested.credentials == credentials


@patch("evaluations.datastores.postgres.postgres.connect")
def test__select(connect):
    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    def reset_mocks():
        connect.reset_mock()
        mock_connection.reset_mock()
        mock_cursor.reset_mock()

    tested = helper_instance()

    connect.return_value.__enter__.side_effect = [mock_connection]
    mock_connection.cursor.return_value.__enter__.side_effect = [mock_cursor]
    mock_cursor.description = [["field_1", "meta_1"], ["field_2", "meta_2"], ["field_3", "meta_3"]]
    mock_cursor.fetchall.side_effect = [
        [["value_1_a", "value_2_a", "value_3_a"], ["value_1_b", "value_2_b", "value_3_b"]],
    ]
    result = [row for row in tested._select("theSQL", {"key": "value"})]
    expected = [
        {"field_1": "value_1_a", "field_2": "value_2_a", "field_3": "value_3_a"},
        {"field_1": "value_1_b", "field_2": "value_2_b", "field_3": "value_3_b"},
    ]
    assert result == expected

    calls = [
        call(dbname="theDatabase", host="theHost", user="theUser", password="thePassword", port=1234),
        call().__enter__(),
        call().__exit__(None, None, None),
    ]
    assert connect.mock_calls == calls
    calls = [call.cursor(), call.cursor().__enter__(), call.commit(), call.cursor().__exit__(None, None, None)]
    assert mock_connection.mock_calls == calls
    calls = [call.execute(sqlist.SQL("theSQL"), {"key": "value"}), call.fetchall()]
    assert mock_cursor.mock_calls == calls
    reset_mocks()


@patch("evaluations.datastores.postgres.postgres.connect")
def test__alter(connect):
    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    def reset_mocks():
        connect.reset_mock()
        mock_connection.reset_mock()
        mock_cursor.reset_mock()

    tested = helper_instance()

    tests = [(None, [[36]], 36), (37, [], 37), (None, [[]], 0)]
    for involved_id, fetch_one, expected in tests:
        connect.return_value.__enter__.side_effect = [mock_connection]
        mock_connection.cursor.return_value.__enter__.side_effect = [mock_cursor]
        mock_cursor.fetchone.side_effect = fetch_one
        result = tested._alter("theSQL", {"key": "value"}, involved_id)
        assert result == expected

        calls = [
            call(dbname="theDatabase", host="theHost", user="theUser", password="thePassword", port=1234),
            call().__enter__(),
            call().__exit__(None, None, None),
        ]
        assert connect.mock_calls == calls
        calls = [call.cursor(), call.cursor().__enter__(), call.commit(), call.cursor().__exit__(None, None, None)]
        assert mock_connection.mock_calls == calls
        calls = [call.execute(sqlist.SQL("theSQL"), {"key": "value"})]
        if fetch_one:
            calls.append(call.fetchone())
        assert mock_cursor.mock_calls == calls
        reset_mocks()


@patch("evaluations.datastores.postgres.postgres.datetime", wraps=datetime)
@patch.object(Postgres, "_alter")
def test_update_fields(alter, mock_datetime):
    def reset_mock():
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 7, 7, 12, 45, 21, 805952, tzinfo=timezone.utc)

    class EnumTest(Enum):
        TEST = "test"

    class Record(NamedTuple):
        field_1: bool
        field_2: dict
        field_3: int
        field_4: str
        field_5: EnumTest

    tests = [
        # no field
        ({}, 0, "", {}),
        # unknown field
        ({"unknown": "field"}, 0, "", {}),
        # regular field
        (
            {"field_1": True},
            1,
            'UPDATE "theTable" '
            'SET "updated"=%(now)s, "field_1" = %(field_1)s '
            'WHERE "id" = %(id)s AND ("field_1"!=%(field_1)s)',
            {"field_1": True, "id": 347, "now": date_0},
        ),
        # json field
        (
            {"field_2": {"key": "data"}},
            1,
            'UPDATE "theTable" '
            'SET "updated"=%(now)s, "field_2" = %(field_2)s '
            'WHERE "id" = %(id)s AND (MD5("field_2"::text)!=%(field_2_md5)s)',
            {"field_2": '{"key":"data"}', "field_2_md5": "f992a945d8f807fe5fd55afeecd9ac4b", "id": 347, "now": date_0},
        ),
        # several fields
        (
            {"field_1": True, "field_2": {"key2": "data2"}, "field_3": 11, "field_4": "text", "field_5": EnumTest.TEST},
            1,
            'UPDATE "theTable" SET "updated"=%(now)s, "field_1" = %(field_1)s, "field_2" = %(field_2)s,'
            ' "field_3" = %(field_3)s, "field_4" = %(field_4)s, "field_5" = %(field_5)s '
            'WHERE "id" = %(id)s AND ("field_1"!=%(field_1)s OR MD5("field_2"::text)!=%(field_2_md5)s'
            ' OR "field_3"!=%(field_3)s OR "field_4"!=%(field_4)s OR "field_5"!=%(field_5)s)',
            {
                "field_1": True,
                "field_2": '{"key2":"data2"}',
                "field_2_md5": "d0391c6b7fb7500a5ec69a3eff6b3725",
                "field_3": 11,
                "field_4": "text",
                "field_5": "test",
                "id": 347,
                "now": date_0,
            },
        ),
    ]

    tested = helper_instance()
    for updates, exp_count, exp_sql, exp_params in tests:
        mock_datetime.now.side_effect = [date_0]

        tested._update_fields("theTable", Record, 347, updates)

        assert len(alter.mock_calls) == exp_count
        if exp_count > 0:
            sql, params, involved_id = alter.mock_calls[0].args
            assert compare_sql(sql, exp_sql)
            assert params == exp_params
            assert involved_id == 347
        reset_mock()
