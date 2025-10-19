from evaluations.structures.records.experiment import Experiment
from tests.helper import is_namedtuple


def test_class():
    tested = Experiment
    fields = {
        "name": str,
        "cycle_times": list,
        "cycle_transcript_overlaps": list,
        "note_replications": int,
        "grade_replications": int,
        "id": int,
    }
    assert is_namedtuple(tested, fields)


def test_default():
    result = Experiment()
    assert result.name == ""
    assert result.cycle_times == []
    assert result.cycle_transcript_overlaps == []
    assert result.note_replications == 0
    assert result.grade_replications == 0
    assert result.id == 0
