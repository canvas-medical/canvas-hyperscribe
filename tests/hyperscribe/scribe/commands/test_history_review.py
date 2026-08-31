from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.history_review import HistoryReviewParser, _prepare_sections


def test_prepare_sections_uses_title() -> None:
    sections = [{"key": "family_history", "title": "Family History", "text": "Father had diabetes"}]
    result = _prepare_sections(sections)
    assert result == [{"title": "Family History", "text": "Father had diabetes"}]


def test_prepare_sections_falls_back_to_title_map() -> None:
    sections = [{"key": "past_medical_history", "text": "Hypertension"}]
    result = _prepare_sections(sections)
    assert result == [{"title": "Past Medical History", "text": "Hypertension"}]


def test_prepare_sections_empty() -> None:
    assert _prepare_sections([]) == []


@patch("hyperscribe.scribe.commands.history_review.render_to_string")
def test_build_renders_template(mock_render: MagicMock) -> None:
    mock_render.return_value = "<h4>Past Medical History</h4><p>HTN</p>"
    parser = HistoryReviewParser()
    data = {"sections": [{"key": "past_medical_history", "title": "Past Medical History", "text": "HTN"}]}

    with patch("hyperscribe.scribe.commands.history_review.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid-123", "cmd-uuid")

    mock_render.assert_called_once_with(
        "scribe/templates/review_sections.html",
        {"sections": [{"title": "Past Medical History", "text": "HTN"}]},
    )
    mock_cmd.assert_called_once_with(
        schema_key="historyReview",
        content="<h4>Past Medical History</h4><p>HTN</p>",
        note_uuid="note-uuid-123",
        command_uuid="cmd-uuid",
    )


@patch("hyperscribe.scribe.commands.history_review.render_to_string")
def test_build_empty_sections(mock_render: MagicMock) -> None:
    mock_render.return_value = ""
    parser = HistoryReviewParser()

    with patch("hyperscribe.scribe.commands.history_review.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({"sections": []}, "note-uuid", "cmd-uuid")

    mock_render.assert_called_once_with(
        "scribe/templates/review_sections.html",
        {"sections": []},
    )
    assert mock_cmd.call_args[1]["content"] == ""


def test_extract_raises() -> None:
    parser = HistoryReviewParser()
    try:
        parser.extract("some text")
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass
