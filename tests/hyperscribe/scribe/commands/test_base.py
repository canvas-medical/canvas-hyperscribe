import pytest

from hyperscribe.scribe.commands.base import CommandParser


def test_extract_raises_when_data_field_is_none() -> None:
    """Structured parsers that forget to override extract get a clear error."""

    class BrokenParser(CommandParser):
        command_type = "broken"

        def build(self, data: dict, note_uuid: str):  # type: ignore[override]
            pass

    with pytest.raises(NotImplementedError, match="BrokenParser must override extract"):
        BrokenParser().extract("some text")


def test_extract_default_for_text_field() -> None:
    """Text-based parsers get a working default extract from the base class."""

    class SimpleParser(CommandParser):
        command_type = "simple"
        data_field = "narrative"

        def build(self, data: dict, note_uuid: str):  # type: ignore[override]
            pass

    proposal = SimpleParser().extract("Hello world")
    assert proposal is not None
    assert proposal.command_type == "simple"
    assert proposal.data == {"narrative": "Hello world"}
    assert proposal.display == "Hello world"
    assert proposal.selected is True
