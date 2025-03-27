from __future__ import annotations

from typing import NamedTuple

from evaluations.constants import Constants


class PostgresCredentials(NamedTuple):
    host: str
    port: int
    user: str
    password: str
    database: str

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> PostgresCredentials:
        return PostgresCredentials(
            database=dictionary.get(Constants.EVALUATIONS_DB_NAME, ""),
            user=dictionary.get(Constants.EVALUATIONS_DB_USERNAME, ""),
            password=dictionary.get(Constants.EVALUATIONS_DB_PASSWORD, ""),
            host=dictionary.get(Constants.EVALUATIONS_DB_HOST, ""),
            port=int(dictionary.get(Constants.EVALUATIONS_DB_PORT, 0)),
        )
