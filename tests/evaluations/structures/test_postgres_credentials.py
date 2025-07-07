from evaluations.structures.postgres_credentials import PostgresCredentials
from tests.helper import is_namedtuple


def test_class():
    tested = PostgresCredentials
    fields = {
        "host": str,
        "port": int,
        "user": str,
        "password": str,
        "database": str,
    }
    assert is_namedtuple(tested, fields)


def test_from_dictionary():
    tested = PostgresCredentials
    #
    result = tested.from_dictionary({
        "EVALUATIONS_DB_HOST": "theHost",
        "EVALUATIONS_DB_PORT": 1234,
        "EVALUATIONS_DB_USERNAME": "theUser",
        "EVALUATIONS_DB_PASSWORD": "thePassword",
        "EVALUATIONS_DB_NAME": "theDatabase",
    })
    expected = PostgresCredentials(
        host="theHost",
        port=1234,
        user="theUser",
        password="thePassword",
        database="theDatabase",
    )
    assert result == expected
    #
    result = tested.from_dictionary({})
    expected = PostgresCredentials(
        host="",
        port=0,
        user="",
        password="",
        database="",
    )
    assert result == expected


def test_is_ready():
    tested = PostgresCredentials(
        host="theHost",
        port=1234,
        user="theUser",
        password="thePassword",
        database="theDatabase",
    )
    result = tested.is_ready()
    assert result is True

    arguments = {
        "host": "",
        "port": 0,
        "user": "",
        "password": "",
        "database": "",
    }
    for field, value in arguments.items():
        args = {
                   "host": "theHost",
                   "port": 1234,
                   "user": "theUser",
                   "password": "thePassword",
                   "database": "theDatabase",
               } | {field: value}
        tested = PostgresCredentials(**args)
        result = tested.is_ready()
        assert result is False
