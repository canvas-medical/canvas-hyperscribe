from evaluations.structures.experiment_models import ExperimentModels
from evaluations.structures.records.model import Model
from tests.helper import is_namedtuple


def test_class():
    tested = ExperimentModels
    fields = {
        "experiment_id": int,
        "model_generator": Model,
        "model_grader": Model,
        "grader_is_reasoning": bool,
    }
    assert is_namedtuple(tested, fields)
