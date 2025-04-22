from __future__ import annotations

from typing_extensions import NamedTuple

from hyperscribe.structures.question_type import QuestionType
from hyperscribe.structures.response import Response


class Question(NamedTuple):
    dbid: int
    label: str
    type: QuestionType
    skipped: bool | None
    responses: list[Response]

    def to_json(self) -> dict:
        return {
            "dbid": self.dbid,
            "label": self.label,
            "type": self.type.value,
            "skipped": self.skipped,
            "responses": [response.to_json() for response in self.responses],
        }

    def for_llm(self, include_skipped: bool) -> dict:
        include_comment = bool(self.type == QuestionType.TYPE_CHECKBOX)
        if self.type in [QuestionType.TYPE_INTEGER, QuestionType.TYPE_TEXT]:
            responses = [
                response.for_llm(include_comment) | {"selected": True}
                for response in self.responses[:1]
            ]
        else:
            responses = [
                response.for_llm(include_comment)
                for response in self.responses
            ]

        skipped = {}
        if include_skipped:
            skipped = {"skipped": self.skipped}

        mapping = QuestionType.llm_readable()
        return {
            "questionId": self.dbid,
            "question": self.label,
            "questionType": mapping[self.type],
            "responses": responses,
        } | skipped

    @classmethod
    def load_from(cls, data: dict) -> Question:
        return Question(
            dbid=data["dbid"],
            label=data["label"],
            type=QuestionType(data["type"]),
            skipped=data["skipped"],
            responses=[Response.load_from(response) for response in data["responses"]],
        )

    @classmethod
    def load_from_llm(cls, data: dict) -> Question:
        mapping = {v: k for k, v in QuestionType.llm_readable().items()}
        return Question(
            dbid=data["questionId"],
            label=data["question"],
            type=mapping[data["questionType"]],
            skipped=data.get("skipped"),
            responses=[Response.load_from_llm(response) for response in data["responses"]],
        )
