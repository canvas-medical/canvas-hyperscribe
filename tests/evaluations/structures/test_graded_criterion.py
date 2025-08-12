from evaluations.structures.graded_criterion import GradedCriterion
from tests.helper import is_namedtuple


def test_class():
    tested = GradedCriterion
    fields = {"id": int, "rationale": str, "satisfaction": int, "score": float}
    assert is_namedtuple(tested, fields)


def test_to_json():
    tests = [
        (
            GradedCriterion(id=0, rationale="Good work", satisfaction=85, score=8.5),
            {"id": 0, "rationale": "Good work", "satisfaction": 85, "score": 8.5},
        ),
        (
            GradedCriterion(id=1, rationale="Needs improvement", satisfaction=40, score=-2.5),
            {"id": 1, "rationale": "Needs improvement", "satisfaction": 40, "score": -2.5},
        ),
        (
            GradedCriterion(id=2, rationale="Excellent documentation", satisfaction=95, score=0.0),
            {"id": 2, "rationale": "Excellent documentation", "satisfaction": 95, "score": 0.0},
        ),
        (
            GradedCriterion(id=3, rationale="Test rationale", satisfaction=50, score=-0.000),
            {"id": 3, "rationale": "Test rationale", "satisfaction": 50, "score": -0.000},
        ),
    ]

    for tested, expected in tests:
        result = tested.to_json()
        assert result == expected


def test_load_from_json():
    tests = [
        (
            [
                {"id": 0, "rationale": "Good work", "satisfaction": 85},
                {"id": 1, "rationale": "Needs improvement", "satisfaction": 40},
            ],
            [
                GradedCriterion(id=0, rationale="Good work", satisfaction=85, score=-0.000),
                GradedCriterion(id=1, rationale="Needs improvement", satisfaction=40, score=-0.000),
            ],
        )
    ]

    for data, expected in tests:
        result = GradedCriterion.load_from_json(data)
        assert result == expected
