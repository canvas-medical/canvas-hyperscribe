from __future__ import annotations

from typing_extensions import NamedTuple


class Response(NamedTuple):
    dbid: int
    value: str | int
    selected: bool

    def to_json(self) -> dict:
        return {
            "dbid": self.dbid,
            "value": self.value,
            "selected": self.selected,
        }

    def for_llm(self) -> dict:
        return {
            "responseId": self.dbid,
            "value": self.value,
            "selected": self.selected,
        }

    @classmethod
    def load_from(cls, data: dict) -> Response:
        return Response(
            dbid=data["dbid"],
            value=data["value"],
            selected=data["selected"],
        )

    @classmethod
    def load_from_llm(cls, data: dict) -> Response:
        return Response(
            dbid=data["responseId"],
            value=data["value"],
            selected=data["selected"],
        )
