import sqlite3
from pathlib import Path
from typing import Generator


class StoreBase:

    @classmethod
    def _create_table_sql(cls) -> str:
        raise NotImplementedError

    @classmethod
    def _update_sql(cls) -> str:
        raise NotImplementedError

    @classmethod
    def _insert_sql(cls) -> str:
        raise NotImplementedError

    @classmethod
    def _delete_sql(cls) -> str:
        raise NotImplementedError

    @classmethod
    def _db_path(cls) -> Path:
        raise NotImplementedError

    @classmethod
    def _insert(cls, parameters: dict) -> None:
        with sqlite3.connect(cls._db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(cls._create_table_sql())
            cursor.execute(cls._insert_sql(), parameters)
            conn.commit()

    @classmethod
    def _upsert(cls, parameters: dict) -> None:
        with sqlite3.connect(cls._db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(cls._create_table_sql())
            cursor.execute(cls._update_sql(), parameters)
            if cursor.rowcount == 0:  # no rows were updated -> insert a new record
                cursor.execute(cls._insert_sql(), parameters)
            conn.commit()

    @classmethod
    def _delete(cls, parameters: dict) -> None:
        with sqlite3.connect(cls._db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(cls._create_table_sql())
            cursor.execute(cls._delete_sql(), parameters)
            conn.commit()

    @classmethod
    def _select(cls, sql: str, parameter: dict) -> Generator[sqlite3.Row, None, None]:
        with sqlite3.connect(cls._db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(cls._create_table_sql())
            cursor.execute(sql, parameter)
            for row in cursor.fetchall():
                yield row
