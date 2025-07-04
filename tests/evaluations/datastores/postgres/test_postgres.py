from unittest.mock import patch, MagicMock, call

from psycopg import sql as sqlist

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.postgres_credentials import PostgresCredentials


def helper_instance() -> Postgres:
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return Postgres(credentials)


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


@patch('evaluations.datastores.postgres.postgres.connect')
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
    mock_cursor.description = [
        ["field_1", "meta_1"],
        ["field_2", "meta_2"],
        ["field_3", "meta_3"],
    ]
    mock_cursor.fetchall.side_effect = [
        [
            ["value_1_a", "value_2_a", "value_3_a"],
            ["value_1_b", "value_2_b", "value_3_b"],
        ],
    ]
    result = [
        row
        for row in tested._select("theSQL", {"key": "value"})
    ]
    expected = [
        {"field_1": "value_1_a", "field_2": "value_2_a", "field_3": "value_3_a"},
        {"field_1": "value_1_b", "field_2": "value_2_b", "field_3": "value_3_b"},
    ]
    assert result == expected

    calls = [
        call(dbname='theDatabase', host='theHost', user='theUser', password='thePassword', port=1234),
        call().__enter__(),
        call().__exit__(None, None, None),
    ]
    assert connect.mock_calls == calls
    calls = [
        call.cursor(),
        call.cursor().__enter__(),
        call.commit(),
        call.cursor().__exit__(None, None, None),
    ]
    assert mock_connection.mock_calls == calls
    calls = [
        call.execute(sqlist.SQL('theSQL'), {'key': 'value'}),
        call.fetchall(),
    ]
    assert mock_cursor.mock_calls == calls
    reset_mocks()


@patch('evaluations.datastores.postgres.postgres.connect')
def test__alter(connect):
    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    def reset_mocks():
        connect.reset_mock()
        mock_connection.reset_mock()
        mock_cursor.reset_mock()

    tested = helper_instance()

    tests = [
        (None, [[36]], 36),
        (37, [], 37),
        (None, [[]], 0),
    ]
    for involved_id, fetch_one, expected in tests:
        connect.return_value.__enter__.side_effect = [mock_connection]
        mock_connection.cursor.return_value.__enter__.side_effect = [mock_cursor]
        mock_cursor.fetchone.side_effect = fetch_one
        result = tested._alter("theSQL", {"key": "value"}, involved_id)
        assert result == expected

        calls = [
            call(dbname='theDatabase', host='theHost', user='theUser', password='thePassword', port=1234),
            call().__enter__(),
            call().__exit__(None, None, None),
        ]
        assert connect.mock_calls == calls
        calls = [
            call.cursor(),
            call.cursor().__enter__(),
            call.commit(),
            call.cursor().__exit__(None, None, None),
        ]
        assert mock_connection.mock_calls == calls
        calls = [
            call.execute(sqlist.SQL('theSQL'), {'key': 'value'}),
        ]
        if fetch_one:
            calls.append(call.fetchone())
        assert mock_cursor.mock_calls == calls
        reset_mocks()
