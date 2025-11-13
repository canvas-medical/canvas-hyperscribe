from hyperscribe.structures.model_spec import ModelSpec


def test_enum():
    tested = ModelSpec
    assert len(tested) == 3
    assert tested.SIMPLER.value == "simpler"
    assert tested.COMPLEX.value == "complex"
    assert tested.LISTED.value == "listed"
