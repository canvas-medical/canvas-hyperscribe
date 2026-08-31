from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.chart_review import ChartReviewParser, _prepare_sections


def test_prepare_sections_uses_title() -> None:
    sections = [{"key": "allergies", "title": "Allergies", "text": "NKDA"}]
    result = _prepare_sections(sections)
    assert result == [{"title": "Allergies", "text": "NKDA"}]


def test_prepare_sections_falls_back_to_title_map() -> None:
    sections = [{"key": "current_medications", "text": "Lisinopril 10mg"}]
    result = _prepare_sections(sections)
    assert result == [{"title": "Current Medications", "text": "Lisinopril 10mg"}]


def test_prepare_sections_empty() -> None:
    assert _prepare_sections([]) == []


@patch("hyperscribe.scribe.commands.chart_review.render_to_string")
def test_build_renders_template(mock_render: MagicMock) -> None:
    mock_render.return_value = "<h4>Allergies</h4><p>NKDA</p>"
    parser = ChartReviewParser()
    data = {"sections": [{"key": "allergies", "title": "Allergies", "text": "NKDA"}]}

    with patch("hyperscribe.scribe.commands.chart_review.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid-123", "cmd-uuid")

    mock_render.assert_called_once_with(
        "scribe/templates/review_sections.html",
        {"sections": [{"title": "Allergies", "text": "NKDA"}]},
    )
    mock_cmd.assert_called_once_with(
        schema_key="chartReview",
        content="<h4>Allergies</h4><p>NKDA</p>",
        note_uuid="note-uuid-123",
        command_uuid="cmd-uuid",
    )


@patch("hyperscribe.scribe.commands.chart_review.render_to_string")
def test_build_empty_sections(mock_render: MagicMock) -> None:
    mock_render.return_value = ""
    parser = ChartReviewParser()

    with patch("hyperscribe.scribe.commands.chart_review.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({"sections": []}, "note-uuid", "cmd-uuid")

    mock_render.assert_called_once_with(
        "scribe/templates/review_sections.html",
        {"sections": []},
    )
    assert mock_cmd.call_args[1]["content"] == ""


def test_extract_raises() -> None:
    parser = ChartReviewParser()
    try:
        parser.extract("some text")
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass
