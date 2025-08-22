from __future__ import annotations

from typing import NamedTuple

from hyperscribe.structures.question import Question


class Questionnaire(NamedTuple):
    dbid: int
    name: str
    questions: list[Question]

    def to_json(self) -> dict:
        return {"name": self.name, "dbid": self.dbid, "questions": [question.to_json() for question in self.questions]}

    def for_llm_limited_to(self, include_skipped: bool, question_ids: list[int]) -> list:
        return [question.for_llm(include_skipped) for question in self.questions if question.dbid in question_ids]

    def used_questions(self) -> list[dict]:
        return [question.used_json() for question in self.questions]

    def update_from_llm_with(self, json_list: list) -> Questionnaire:
        questions = {q.dbid: q for q in self.questions}
        for data in json_list:
            question = Question.load_from_llm(data)
            questions[question.dbid] = question

        return Questionnaire(dbid=self.dbid, name=self.name, questions=list(questions.values()))

    @classmethod
    def load_from(cls, data: dict) -> Questionnaire:
        return Questionnaire(
            dbid=data["dbid"],
            name=data["name"],
            questions=[Question.load_from(question) for question in data["questions"]],
        )
