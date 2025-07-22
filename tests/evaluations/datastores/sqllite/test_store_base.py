from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch, call

import pytest

from evaluations.datastores.sqllite.store_base import StoreBase


def test__create_table_sql():
    tested = StoreBase
    with pytest.raises(NotImplementedError):
        _ = tested._create_table_sql()


def test__update_sql():
    tested = StoreBase
    with pytest.raises(NotImplementedError):
        _ = tested._update_sql()


def test__insert_sql():
    tested = StoreBase
    with pytest.raises(NotImplementedError):
        _ = tested._insert_sql()


def test__delete_sql():
    tested = StoreBase
    with pytest.raises(NotImplementedError):
        _ = tested._delete_sql()


def test__db_path():
    tested = StoreBase
    with pytest.raises(NotImplementedError):
        _ = tested._db_path()


@patch.object(StoreBase, "_insert_sql")
@patch.object(StoreBase, "_create_table_sql")
@patch.object(StoreBase, "_db_path")
def test__insert(db_path, create_table_sql, insert_sql):
    def reset_mocks():
        db_path.reset_mock()
        create_table_sql.reset_mock()
        insert_sql.reset_mock()

    sql_create = (
        "CREATE TABLE IF NOT EXISTS test ("
        "`id` INTEGER PRIMARY KEY AUTOINCREMENT,"
        "`field_1` TEXT NOT NULL,"
        "`field_2` INTEGER NOT NULL)"
    )
    sql_insert = "INSERT INTO `test` (`field_1`,`field_2`) VALUES (:field_1, :field_2)"
    tested = StoreBase
    with NamedTemporaryFile(delete=True) as temp_file:
        db_path.return_value = Path(temp_file.name)
        create_table_sql.return_value = sql_create
        insert_sql.return_value = sql_insert

        # first record
        tested._insert({"field_1": "valueA", "field_2": 3})
        calls = [call()]
        assert db_path.mock_calls == calls
        assert create_table_sql.mock_calls == calls
        assert insert_sql.mock_calls == calls
        reset_mocks()

        result = [
            {"id": record["id"], "field_1": record["field_1"], "field_2": record["field_2"]}
            for record in tested._select("SELECT * FROM test ORDER BY `id`", {})
        ]
        expected = [{"id": 1, "field_1": "valueA", "field_2": 3}]
        assert result == expected
        reset_mocks()

        # second record
        tested._insert({"field_1": "valueB", "field_2": 7})
        calls = [call()]
        assert db_path.mock_calls == calls
        assert create_table_sql.mock_calls == calls
        assert insert_sql.mock_calls == calls
        reset_mocks()

        result = [
            {"id": record["id"], "field_1": record["field_1"], "field_2": record["field_2"]}
            for record in tested._select("SELECT * FROM test ORDER BY `id`", {})
        ]
        expected = [{"id": 1, "field_1": "valueA", "field_2": 3}, {"id": 2, "field_1": "valueB", "field_2": 7}]
        assert result == expected
        reset_mocks()


@patch.object(StoreBase, "_update_sql")
@patch.object(StoreBase, "_insert_sql")
@patch.object(StoreBase, "_create_table_sql")
@patch.object(StoreBase, "_db_path")
def test__upsert(db_path, create_table_sql, insert_sql, update_sql):
    def reset_mocks():
        db_path.reset_mock()
        create_table_sql.reset_mock()
        insert_sql.reset_mock()
        update_sql.reset_mock()

    sql_create = (
        "CREATE TABLE IF NOT EXISTS test ("
        "`id` INTEGER PRIMARY KEY AUTOINCREMENT,"
        "`field_1` TEXT NOT NULL,"
        "`field_2` INTEGER NOT NULL)"
    )
    sql_insert = "INSERT INTO `test` (`id`,`field_1`,`field_2`) VALUES (:id,:field_1, :field_2)"
    sql_update = "UPDATE `test` SET `field_1`=:field_1,`field_2`=:field_2 WHERE `id`=:id"
    tested = StoreBase
    with NamedTemporaryFile(delete=True) as temp_file:
        db_path.return_value = Path(temp_file.name)
        create_table_sql.return_value = sql_create
        insert_sql.return_value = sql_insert
        update_sql.return_value = sql_update

        tests = [
            (
                {"field_1": "valueA", "field_2": 3, "id": 1},
                [call()],
                [call()],
                [{"id": 1, "field_1": "valueA", "field_2": 3}],
            ),
            (
                {"field_1": "valueB", "field_2": 7, "id": 2},
                [call()],
                [call()],
                [{"id": 1, "field_1": "valueA", "field_2": 3}, {"field_1": "valueB", "field_2": 7, "id": 2}],
            ),
            (
                {"field_1": "valueB", "field_2": 8, "id": 2},
                [call()],
                [],
                [{"id": 1, "field_1": "valueA", "field_2": 3}, {"field_1": "valueB", "field_2": 8, "id": 2}],
            ),
            (
                {"field_1": "valueC", "field_2": 3, "id": 1},
                [call()],
                [],
                [{"id": 1, "field_1": "valueC", "field_2": 3}, {"field_1": "valueB", "field_2": 8, "id": 2}],
            ),
        ]
        for parameters, exp_calls_update, exp_calls_insert, exp_records in tests:
            tested._upsert(parameters)
            assert db_path.mock_calls == exp_calls_update
            assert create_table_sql.mock_calls == exp_calls_update
            assert insert_sql.mock_calls == exp_calls_insert
            assert update_sql.mock_calls == exp_calls_update
            reset_mocks()

            result = [
                {"id": record["id"], "field_1": record["field_1"], "field_2": record["field_2"]}
                for record in tested._select("SELECT * FROM test ORDER BY `id`", {})
            ]
            assert result == exp_records
            reset_mocks()


@patch.object(StoreBase, "_delete_sql")
@patch.object(StoreBase, "_insert_sql")
@patch.object(StoreBase, "_create_table_sql")
@patch.object(StoreBase, "_db_path")
def test__delete(db_path, create_table_sql, insert_sql, delete_sql):
    def reset_mocks():
        db_path.reset_mock()
        create_table_sql.reset_mock()
        insert_sql.reset_mock()
        delete_sql.reset_mock()

    sql_create = (
        "CREATE TABLE IF NOT EXISTS test ("
        "`id` INTEGER PRIMARY KEY AUTOINCREMENT,"
        "`field_1` TEXT NOT NULL,"
        "`field_2` INTEGER NOT NULL)"
    )
    sql_insert = "INSERT INTO `test` (`field_1`,`field_2`) VALUES (:field_1, :field_2)"
    sql_delete = "DELETE FROM `test` WHERE `id`=:id"

    tested = StoreBase
    with NamedTemporaryFile(delete=True) as temp_file:
        db_path.return_value = Path(temp_file.name)
        create_table_sql.return_value = sql_create
        insert_sql.return_value = sql_insert
        delete_sql.return_value = sql_delete

        # insert records
        tested._insert({"field_1": "valueA", "field_2": 3})
        tested._insert({"field_1": "valueB", "field_2": 7})
        calls = [call(), call()]
        assert db_path.mock_calls == calls
        assert create_table_sql.mock_calls == calls
        assert insert_sql.mock_calls == calls
        assert delete_sql.mock_calls == []
        reset_mocks()

        result = [
            {"id": record["id"], "field_1": record["field_1"], "field_2": record["field_2"]}
            for record in tested._select("SELECT * FROM test ORDER BY `id`", {})
        ]
        expected = [{"id": 1, "field_1": "valueA", "field_2": 3}, {"id": 2, "field_1": "valueB", "field_2": 7}]
        assert result == expected
        reset_mocks()

        # delete records
        tests = [
            ({"id": 1}, [call()], [{"id": 2, "field_1": "valueB", "field_2": 7}]),
            ({"id": 1}, [call()], [{"id": 2, "field_1": "valueB", "field_2": 7}]),
            ({"id": 2}, [call()], []),
            ({"id": 2}, [call()], []),
        ]
        for parameters, exp_calls, exp_records in tests:
            tested._delete(parameters)
            assert db_path.mock_calls == exp_calls
            assert create_table_sql.mock_calls == exp_calls
            assert insert_sql.mock_calls == []
            assert delete_sql.mock_calls == exp_calls
            reset_mocks()

            result = [
                {"id": record["id"], "field_1": record["field_1"], "field_2": record["field_2"]}
                for record in tested._select("SELECT * FROM test ORDER BY `id`", {})
            ]
            assert result == exp_records
            reset_mocks()


@patch.object(StoreBase, "_insert_sql")
@patch.object(StoreBase, "_create_table_sql")
@patch.object(StoreBase, "_db_path")
def test__select(db_path, create_table_sql, insert_sql):
    def reset_mocks():
        db_path.reset_mock()
        create_table_sql.reset_mock()
        insert_sql.reset_mock()

    sql_create = (
        "CREATE TABLE IF NOT EXISTS test ("
        "`id` INTEGER PRIMARY KEY AUTOINCREMENT,"
        "`field_1` TEXT NOT NULL,"
        "`field_2` INTEGER NOT NULL)"
    )
    sql_insert = "INSERT INTO `test` (`field_1`,`field_2`) VALUES (:field_1, :field_2)"

    tested = StoreBase
    with NamedTemporaryFile(delete=True) as temp_file:
        db_path.return_value = Path(temp_file.name)
        create_table_sql.return_value = sql_create
        insert_sql.return_value = sql_insert

        # insert records
        tested._insert({"field_1": "valueA", "field_2": 3})
        tested._insert({"field_1": "valueB", "field_2": 7})
        tested._insert({"field_1": "valueC", "field_2": 6})
        calls = [call(), call(), call()]
        assert db_path.mock_calls == calls
        assert create_table_sql.mock_calls == calls
        assert insert_sql.mock_calls == calls
        reset_mocks()

        #
        tests = [
            (
                "SELECT * FROM test ORDER BY `id`",
                {},
                ["id", "field_1", "field_2"],
                [
                    {"id": 1, "field_1": "valueA", "field_2": 3},
                    {"id": 2, "field_1": "valueB", "field_2": 7},
                    {"id": 3, "field_1": "valueC", "field_2": 6},
                ],
            ),
            (
                "SELECT `id`, `field_1` FROM test WHERE `field_2`<:max ORDER BY `id`",
                {"max": 7},
                ["id", "field_1"],
                [{"id": 1, "field_1": "valueA"}, {"id": 3, "field_1": "valueC"}],
            ),
        ]
        for sql, parameters, exp_fields, exp_records in tests:
            result = [{field: record[field] for field in exp_fields} for record in tested._select(sql, parameters)]
            assert result == exp_records
            reset_mocks()
