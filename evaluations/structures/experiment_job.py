from typing import NamedTuple


class ExperimentJob(NamedTuple):
    job_index: int
    experiment_id: int
    experiment_name: str
    case_id: int
    case_name: str
    model_id: int
    model_vendor: str
    model_name: str
    model_api_key: str
    cycle_time: int
    cycle_transcript_overlap: int
    grade_replications: int
