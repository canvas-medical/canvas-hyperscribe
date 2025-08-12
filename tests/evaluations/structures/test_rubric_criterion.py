from evaluations.structures.rubric_criterion import RubricCriterion
from tests.helper import is_namedtuple


def test_class():
    tested = RubricCriterion
    fields = {"criterion": str, "weight": float, "sense": str}

    assert is_namedtuple(tested, fields)


def test_to_json():
    tests = [
        (
            RubricCriterion(criterion="Reward for accuracy", weight=50.0, sense="positive"),
            {"criterion": "Reward for accuracy", "weight": 50.0, "sense": "positive"},
        )
    ]

    for tested, expected in tests:
        result = tested.to_json()
        assert result == expected


def test_load_from_json():
    tests = [
        (
            [
                {"criterion": "Reward for accuracy", "weight": 50.0, "sense": "positive"},
                {"criterion": "Penalize for errors", "weight": 30.0, "sense": "negative"},
            ],
            [
                RubricCriterion(criterion="Reward for accuracy", weight=50.0, sense="positive"),
                RubricCriterion(criterion="Penalize for errors", weight=30.0, sense="negative"),
            ],
        ),
        (
            [
                {"criterion": "Reward for completeness", "weight": 25.0, "sense": "positive"},
            ],
            [
                RubricCriterion(criterion="Reward for completeness", weight=25.0, sense="positive"),
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
