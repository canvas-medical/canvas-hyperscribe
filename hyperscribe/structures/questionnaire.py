from __future__ import annotations

from typing_extensions import NamedTuple

from hyperscribe.structures.question import Question


class Questionnaire(NamedTuple):
    dbid: int
    name: str
    questions: list[Question]

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "dbid": self.dbid,
            "questions": [question.to_json() for question in self.questions],
        }

    def for_llm(self, include_skipped: bool) -> list:
        return [question.for_llm(include_skipped) for question in self.questions]

    @classmethod
    def load_from(cls, data: dict) -> Questionnaire:
        return Questionnaire(
            dbid=data["dbid"],
            name=data["name"],
            questions=[Question.load_from(question) for question in data["questions"]],
        )

    @classmethod
    def load_from_llm(cls, dbid: int, name: str, data: list) -> Questionnaire:
        return Questionnaire(
            dbid=dbid,
            name=name,
            questions=[Question.load_from_llm(question) for question in data],
        )
