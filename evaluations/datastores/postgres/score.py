import json
from datetime import datetime, UTC
from typing import LiteralString

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.records.score import Score as ScoreRecord


class Score(Postgres):
    def insert(self, score: ScoreRecord) -> ScoreRecord:
        params = {
            "now": datetime.now(UTC),
            "rubric_id": score.rubric_id,
            "generated_note_id": score.generated_note_id,
            "scoring_result": json.dumps(score.scoring_result),
            "overall_score": score.overall_score,
            "comments": score.comments,
            "text_llm_vendor": score.text_llm_vendor,
            "text_llm_name": score.text_llm_name,
            "temperature": score.temperature,
            "experiment": score.experiment,
        }
        sql: LiteralString = """
                             INSERT INTO "score" ("created", "updated", "rubric_id", "generated_note_id",
                                                  "scoring_result", "overall_score", "comments",
                                                  "text_llm_vendor", "text_llm_name", "temperature", "experiment")
                             VALUES (%(now)s, %(now)s, %(rubric_id)s, %(generated_note_id)s,
                                     %(scoring_result)s, %(overall_score)s, %(comments)s,
                                     %(text_llm_vendor)s, %(text_llm_name)s, %(temperature)s,
                                     %(experiment)s) RETURNING id"""
        return ScoreRecord(
            id=self._alter(sql, params, None),
            rubric_id=score.rubric_id,
            generated_note_id=score.generated_note_id,
            scoring_result=score.scoring_result,
            overall_score=score.overall_score,
            comments=score.comments,
            text_llm_vendor=score.text_llm_vendor,
            text_llm_name=score.text_llm_name,
            temperature=score.temperature,
            experiment=score.experiment,
        )
