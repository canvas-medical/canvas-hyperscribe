from hyperscribe.structures.default_tab import DefaultTab


def test_enum():
    tested = DefaultTab
    assert len(tested) == 4
    assert tested.ACTIVITY.value == "activity"
    assert tested.FEEDBACK.value == "feedback"
    assert tested.LOGS.value == "logs"
    assert tested.TRANSCRIPT.value == "transcript"
