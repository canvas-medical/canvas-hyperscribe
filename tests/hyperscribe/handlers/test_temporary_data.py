from hyperscribe.handlers.temporary_data import LastNoteStateEvent


def test_editable():
    tests = [
        ("NEW", True),
        ("PSH", True),
        ("LKD", False),
        ("ULK", True),
        ("DLT", False),
        ("RLK", False),
        ("RST", True),
        ("RCL", False),
        ("UND", True),
    ]
    for state, expected in tests:
        tested = LastNoteStateEvent(dbid=7458, state=state, note_id=778)
        result = tested.editable()
        assert result is expected, f"---> {state}"
