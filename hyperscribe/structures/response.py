from __future__ import annotations

from typing import NamedTuple


class Response(NamedTuple):
    dbid: int
    value: str | int
    selected: bool
    comment: str | None

    def to_json(self) -> dict:
        return {"dbid": self.dbid, "value": self.value, "selected": self.selected, "comment": self.comment}

    def for_llm(self, include_comment: bool) -> dict:
        comment = {}
        if include_comment:
            comment = {
                "comment": self.comment,
                "description": "add in the comment key any relevant information expanding the answer",
            }
        return {"responseId": self.dbid, "value": self.value, "selected": self.selected} | comment

    @classmethod
    def load_from(cls, data: dict) -> Response:
        return Response(dbid=data["dbid"], value=data["value"], selected=data["selected"], comment=data.get("comment"))

    @classmethod
    def load_from_llm(cls, data: dict) -> Response:
        return Response(
            dbid=data["responseId"],
            value=data["value"],
            selected=data["selected"],
            comment=data.get("comment"),
        )
