from __future__ import annotations

from typing import NamedTuple


class CaseExchangeSummary(NamedTuple):
    title: str
    summary: str

    @classmethod
    def load_from_json(cls, json_list: list) -> list[CaseExchangeSummary]:
        return [cls(title=json_object["title"], summary=json_object["summary"]) for json_object in json_list]

    def to_json(self) -> dict:
        return {"title": self.title, "summary": self.summary}
