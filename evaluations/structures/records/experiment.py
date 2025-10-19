from typing import NamedTuple


class Experiment(NamedTuple):
    name: str = ""
    cycle_times: list = []
    cycle_transcript_overlaps: list = []
    note_replications: int = 0
    grade_replications: int = 0
    id: int = 0
