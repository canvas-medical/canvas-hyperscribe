from datetime import datetime, timezone
from unittest.mock import patch, call

from evaluations.datastores.postgres.model import Model
from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.records.model import Model as Record
from tests.helper import compare_sql


def helper_instance() -> Model:
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return Model(credentials)


def test_class():
    assert issubclass(Model, Postgres)


@patch.object(Model, "_select")
def test_get_model(select):
    def reset_mock():
        select.reset_mock()

    tested = helper_instance()

    tests = [
        ([], Record()),
        (
            [{"id": 123, "name": "theModel", "vendor": "theVendor", "api_key": "theApiKey"}],
            Record(id=123, name="theModel", vendor="theVendor", api_key="theApiKey"),
        ),
    ]
    for select_side_effect, expected in tests:
        select.side_effect = [select_side_effect]
        result = tested.get_model(77)
        assert result == expected

        assert len(select.mock_calls) == 1
        sql, params = select.mock_calls[0].args
        exp_sql = 'SELECT "id", "name", "vendor", "api_key" FROM "model" WHERE "id" = %(id)s'
        assert compare_sql(sql, exp_sql)
        exp_params = {"id": 77}
        assert params == exp_params
        reset_mock()


@patch("evaluations.datastores.postgres.model.datetime", wraps=datetime)
@patch.object(Model, "_alter")
def test_insert(alter, mock_datetime):
    def reset_mock():
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 10, 17, 13, 56, 47, 123456, tzinfo=timezone.utc)
    model = Record(
        vendor="theVendor",
        name="theName",
        api_key="theApiKey",
        id=333,
    )
    expected = Record(
        vendor="theVendor",
        name="theName",
        api_key="theApiKey",
        id=351,
    )

    tested = helper_instance()

    alter.side_effect = [351]
    mock_datetime.now.side_effect = [date_0]

    result = tested.insert(model)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = (
        'INSERT INTO "experiment_result" ("created", "updated", "name", "vendor", "api_key") '
        "VALUES (%(now)s, %(now)s, %(name)s, %(vendor)s, %(api_key)s) RETURNING id"
    )
    assert compare_sql(sql, exp_sql)
    exp_params = {
        "name": "theName",
        "vendor": "theVendor",
        "api_key": "theApiKey",
        "now": date_0,
    }
    assert params == exp_params
    assert involved_id is None
    reset_mock()


@patch.object(Model, "_update_fields")
def test_update_fields(update_fields):
    def reset_mock():
        update_fields.reset_mock()

    tested = helper_instance()
    tested.update_fields(34, {"theField": "theValue"})

    calls = [call("model", Record, 34, {"theField": "theValue"})]
    assert update_fields.mock_calls == calls
    reset_mock()
