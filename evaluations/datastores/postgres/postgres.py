import json
from datetime import datetime, UTC
from enum import Enum
from hashlib import md5
from typing import Generator, LiteralString, Type

from psycopg import connect, sql as sqlist

from evaluations.structures.postgres_credentials import PostgresCredentials


class Postgres:
    @classmethod
    def constant_dumps(cls, data: dict | list) -> str:
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    @classmethod
    def md5_from(cls, data: str) -> str:
        return md5(data.encode("utf-8")).hexdigest()

    def __init__(self, credentials: PostgresCredentials):
        self.credentials = credentials

    def _select(self, sql: LiteralString, params: dict) -> Generator[dict, None, None]:
        with connect(
            dbname=self.credentials.database,
            host=self.credentials.host,
            user=self.credentials.user,
            password=self.credentials.password,
            port=self.credentials.port,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sqlist.SQL(sql), params)
                column_names = [desc[0] for desc in cursor.description or []]
                for row in cursor.fetchall():
                    yield dict(zip(column_names, row))
                connection.commit()

    def _alter(self, sql: LiteralString, params: dict, involved_id: int | None) -> int:
        # import psycopg
        with connect(
            dbname=self.credentials.database,
            host=self.credentials.host,
            user=self.credentials.user,
            password=self.credentials.password,
            port=self.credentials.port,
            # cursor_factory=psycopg.ClientCursor,
        ) as connection:
            with connection.cursor() as cursor:
                # print("------")
                # print(cursor.mogrify(sql, params))
                # print("------")
                cursor.execute(sqlist.SQL(sql), params)
                if involved_id is None:
                    involved_id = 0
                    if row := cursor.fetchone():
                        involved_id = row[0]
                connection.commit()
        return involved_id

    def _update_fields(self, table: str, record_class: Type, record_id: int, updates: dict) -> None:
        params: dict = {"now": datetime.now(UTC), "id": record_id}
        sql_where: list[str] = []
        sql_sets: list[str] = ['"updated"=%(now)s']
        for field, value in updates.items():
            if not hasattr(record_class, field):
                continue

            sql_sets.append(f'"{field}" = %({field})s')
            where = f'"{field}"!=%({field})s'
            if isinstance(value, dict) or isinstance(value, list):
                params[field] = self.constant_dumps(value)
                where = f'MD5("{field}"::text)!=%({field}_md5)s'
                params[f"{field}_md5"] = self.md5_from(params[field])
            elif isinstance(value, Enum):
                params[field] = value.value
            else:
                params[field] = value
            sql_where.append(where)

        if sql_where:
            sql: LiteralString = (
                f'UPDATE "{table}" SET {", ".join(sql_sets)} WHERE "id" = %(id)s AND ({" OR ".join(sql_where)})'
            )
            self._alter(sql, params, record_id)
