from datetime import datetime, UTC
from typing import LiteralString

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.records.experiment_result_score import ExperimentResultScore as Record


class ExperimentResultScore(Postgres):
    def insert(self, experiment_result_score: Record) -> Record:
        params = {
            "now": datetime.now(UTC),
            "experiment_result_id": experiment_result_score.experiment_result_id,
            "score_id": experiment_result_score.score_id,
            "scoring_result": self.constant_dumps(
                [score.to_json() for score in experiment_result_score.scoring_result]
            ),
        }
        sql: LiteralString = """
                             INSERT INTO "experiment_result_score" ("created", "experiment_result_id",
                                                                    "score_id", "scoring_result")
                             VALUES (%(now)s, %(experiment_result_id)s,
                                     %(score_id)s, %(scoring_result)s) RETURNING id"""
        return Record(
            id=self._alter(sql, params, None),
            experiment_result_id=experiment_result_score.experiment_result_id,
            score_id=experiment_result_score.score_id,
            scoring_result=experiment_result_score.scoring_result,
        )
