from hyperscribe.structures.cycle_data_source import CycleDataSource


def test_enum():
    tested = CycleDataSource
    assert len(tested) == 2
    assert tested.AUDIO.value == "audio"
    assert tested.TRANSCRIPT.value == "transcript"
