from typing import NamedTuple

from evaluations.structures.records.model import Model


class ExperimentModels(NamedTuple):
    experiment_id: int
    model_generator: Model
    model_grader: Model
    grader_is_reasoning: bool
