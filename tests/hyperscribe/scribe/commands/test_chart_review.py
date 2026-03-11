from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.chart_review import ChartReviewParser, _sections_to_html


def test_sections_to_html_multiple() -> None:
    sections = [
        {"key": "current_medications", "title": "Current Medications", "text": "Lisinopril 10mg"},
        {"key": "allergies", "title": "Allergies", "text": "Penicillin (rash)"},
    ]
    html = _sections_to_html(sections)
    assert "<h4>Current Medications</h4>" in html
    assert "<p>Lisinopril 10mg</p>" in html
    assert "<hr>" in html
    assert "<h4>Allergies</h4>" in html
    assert "<p>Penicillin (rash)</p>" in html


def test_sections_to_html_single() -> None:
    sections = [{"key": "allergies", "title": "Allergies", "text": "NKDA"}]
    html = _sections_to_html(sections)
    assert "<h4>Allergies</h4>" in html
    assert "<p>NKDA</p>" in html
    assert "<hr>" not in html


def test_sections_to_html_empty() -> None:
    assert _sections_to_html([]) == ""


def test_build_generates_html() -> None:
    parser = ChartReviewParser()
    data = {
        "sections": [
            {"key": "current_medications", "title": "Current Medications", "text": "Metformin 500mg"},
            {"key": "allergies", "title": "Allergies", "text": "Sulfa (hives)"},
        ]
    }
    with patch("hyperscribe.scribe.commands.chart_review.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid-123", "cmd-uuid")

    mock_cmd.assert_called_once()
    call_kwargs = mock_cmd.call_args[1]
    assert call_kwargs["schema_key"] == "chartReview"
    assert call_kwargs["note_uuid"] == "note-uuid-123"
    assert "<h4>Current Medications</h4>" in call_kwargs["content"]
    assert "<h4>Allergies</h4>" in call_kwargs["content"]


def test_build_empty_sections() -> None:
    parser = ChartReviewParser()
    with patch("hyperscribe.scribe.commands.chart_review.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({"sections": []}, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once()
    assert mock_cmd.call_args[1]["content"] == ""


def test_build_single_section() -> None:
    parser = ChartReviewParser()
    data = {
        "sections": [
            {"key": "immunizations", "title": "Immunizations", "text": "Flu vaccine 2025"},
        ]
    }
    with patch("hyperscribe.scribe.commands.chart_review.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    content = mock_cmd.call_args[1]["content"]
    assert "<h4>Immunizations</h4>" in content
    assert "<hr>" not in content


def test_extract_raises() -> None:
    parser = ChartReviewParser()
    try:
        parser.extract("some text")
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass
