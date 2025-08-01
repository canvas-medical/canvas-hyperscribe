import pytest

from hyperscribe.libraries.auditor_base import AuditorBase


def test_identified_transcript():
    tested = AuditorBase()
    with pytest.raises(NotImplementedError):
        _ = tested.identified_transcript([b""], [])


def test_found_instructions():
    tested = AuditorBase()
    with pytest.raises(NotImplementedError):
        _ = tested.found_instructions([], [], [])


def test_computed_parameters():
    tested = AuditorBase()
    with pytest.raises(NotImplementedError):
        _ = tested.computed_parameters([])


def test_computed_commands():
    tested = AuditorBase()
    with pytest.raises(NotImplementedError):
        _ = tested.computed_commands([])


def test_computed_questionnaires():
    tested = AuditorBase()
    with pytest.raises(NotImplementedError):
        _ = tested.computed_questionnaires([], [], [])
