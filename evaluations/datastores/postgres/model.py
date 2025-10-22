from datetime import datetime, UTC
from typing import LiteralString

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.records.model import Model as Record


class Model(Postgres):
    def get_model(self, model_id: int) -> Record:
        sql: LiteralString = """
                             SELECT "id", "vendor", "api_key"
                             FROM "model"
                             WHERE "id" = %(id)s
                             """
        for record in self._select(sql, {"id": model_id}):
            return Record(
                id=record["id"],
                vendor=record["vendor"],
                api_key=record["api_key"],
            )
        return Record()

    def get_model_by_vendor(self, vendor: str) -> Record:
        sql: LiteralString = """
                             SELECT "id", "vendor", "api_key"
                             FROM "model"
                             WHERE "vendor" = %(vendor)s
                             """
        for record in self._select(sql, {"vendor": vendor}):
            return Record(
                id=record["id"],
                vendor=record["vendor"],
                api_key=record["api_key"],
            )
        return Record()

    def insert(self, model: Record) -> Record:
        params = {
            "now": datetime.now(UTC),
            "vendor": model.vendor,
            "api_key": model.api_key,
        }
        sql: LiteralString = """
                             INSERT INTO "model" ("created", "updated", "vendor", "api_key")
                             VALUES (%(now)s, %(now)s, %(vendor)s, %(api_key)s) RETURNING id"""
        return Record(
            id=self._alter(sql, params, None),
            vendor=model.vendor,
            api_key=model.api_key,
        )

    def update_fields(self, model_id: int, updates: dict) -> None:
        self._update_fields("model", Record, model_id, updates)
