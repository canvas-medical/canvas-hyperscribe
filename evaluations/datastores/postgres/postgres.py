from typing import Generator, LiteralString

from psycopg import connect, sql as sqlist

from evaluations.structures.postgres_credentials import PostgresCredentials


class Postgres:
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
