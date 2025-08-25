from evaluations.structures.rubric_criterion import RubricCriterion
from tests.helper import is_namedtuple


def test_class():
    tested = RubricCriterion
    fields = {"criterion": str, "weight": float}

    assert is_namedtuple(tested, fields)


def test_to_json():
    tests = [
        (
            RubricCriterion(criterion="Reward for accuracy", weight=50.0),
            {"criterion": "Reward for accuracy", "weight": 50.0},
        )
    ]

    for tested, expected in tests:
        result = tested.to_json()
        assert result == expected


def test_load_from_json():
    tests = [
        (
            [
                {"criterion": "Reward for accuracy", "weight": 50.0},
                {"criterion": "Reward for completeness", "weight": 30.0},
            ],
            [
                RubricCriterion(criterion="Reward for accuracy", weight=50.0),
                RubricCriterion(criterion="Reward for completeness", weight=30.0),
            ],
        ),
        (
            [
                {"criterion": "Reward for completeness", "weight": 25.0},
            ],
            [
                RubricCriterion(criterion="Reward for completeness", weight=25.0),
            ],
        ),
        (
            [],
            [],
        ),
    ]

    for data, expected in tests:
        result = RubricCriterion.load_from_json(data)
        assert result == expected
