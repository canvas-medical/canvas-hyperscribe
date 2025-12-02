from __future__ import annotations

from typing import NamedTuple


class CompletedJob(NamedTuple):
    case_id: int
    model_generator_id: int
    model_grader_id: int
    cycle_overlap: int

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, CompletedJob)
            and self.case_id == other.case_id
            and self.model_generator_id == other.model_generator_id
            and self.model_grader_id == other.model_grader_id
            and self.cycle_overlap == other.cycle_overlap
        )