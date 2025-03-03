from hyperscribe.protocols.auditor import Auditor


def test_identified_transcript():
    tested = Auditor()
    result = tested.identified_transcript(b"", [])
    assert result is True


def test_found_instructions():
    tested = Auditor()
    result = tested.found_instructions([], [])
    assert result is True


def test_computed_parameters():
    tested = Auditor()
    result = tested.computed_parameters([])
    assert result is True


def test_computed_commands():
    tested = Auditor()
    result = tested.computed_commands([], [])
    assert result is True
