from datetime import datetime, UTC
from typing import LiteralString

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.records.model import Model as Record


class Model(Postgres):
    def get_model(self, model_id: int) -> Record:
        sql: LiteralString = """
                             SELECT "id", "vendor", "api_key", "model"
                             FROM "model"
                             WHERE "id" = %(id)s
                             """
        for record in self._select(sql, {"id": model_id}):
            return Record(
                id=record["id"],
                vendor=record["vendor"],
                api_key=record["api_key"],
                model=record["model"],
            )
        return Record()

    def get_models_by_vendor(self, vendor: str) -> list[Record]:
        sql: LiteralString = """
                             SELECT "id", "vendor", "api_key", "model"
                             FROM "model"
                             WHERE "vendor" = %(vendor)s
                             ORDER BY "id"
                             """
        return [
            Record(
                id=record["id"],
                vendor=record["vendor"],
                api_key=record["api_key"],
                model=record["model"],
            )
            for record in self._select(sql, {"vendor": vendor})
        ]

    def insert(self, model: Record) -> Record:
        params = {
            "now": datetime.now(UTC),
            "vendor": model.vendor,
            "api_key": model.api_key,
            "model": model.model,
        }
        sql: LiteralString = """
                             INSERT INTO "model" ("created", "updated", "vendor", "api_key", "model")
                             VALUES (%(now)s, %(now)s, %(vendor)s, %(api_key)s, %(model)s) RETURNING id"""
        return Record(
            id=self._alter(sql, params, None),
            vendor=model.vendor,
            api_key=model.api_key,
            model=model.model,
        )

    def update_fields(self, model_id: int, updates: dict) -> None:
        self._update_fields("model", Record, model_id, updates)
