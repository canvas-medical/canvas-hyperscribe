from typing import NamedTuple

from evaluations.structures.experiment_models import ExperimentModels


class ExperimentJob(NamedTuple):
    job_index: int
    experiment_id: int
    experiment_name: str
    case_id: int
    case_name: str
    models: ExperimentModels
    cycle_time: int
    cycle_transcript_overlap: int
    grade_replications: int
