from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.history_review import HistoryReviewParser, _sections_to_html


def test_sections_to_html_multiple() -> None:
    sections = [
        {"key": "past_medical_history", "title": "Past Medical History", "text": "Hypertension"},
        {"key": "family_history", "title": "Family History", "text": "Father had diabetes"},
    ]
    html = _sections_to_html(sections)
    assert "<h4>Past Medical History</h4>" in html
    assert "<p>Hypertension</p>" in html
    assert "<hr>" in html
    assert "<h4>Family History</h4>" in html
    assert "<p>Father had diabetes</p>" in html


def test_sections_to_html_single() -> None:
    sections = [{"key": "social_history", "title": "Social History", "text": "Non-smoker"}]
    html = _sections_to_html(sections)
    assert "<h4>Social History</h4>" in html
    assert "<p>Non-smoker</p>" in html
    assert "<hr>" not in html


def test_sections_to_html_empty() -> None:
    assert _sections_to_html([]) == ""


def test_build_generates_html() -> None:
    parser = HistoryReviewParser()
    data = {
        "sections": [
            {"key": "past_medical_history", "title": "Past Medical History", "text": "Hypertension"},
            {"key": "social_history", "title": "Social History", "text": "Non-smoker"},
        ]
    }
    with patch("hyperscribe.scribe.commands.history_review.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid-123")

    mock_cmd.assert_called_once()
    call_kwargs = mock_cmd.call_args[1]
    assert call_kwargs["schema_key"] == "historyReview"
    assert call_kwargs["note_uuid"] == "note-uuid-123"
    assert "<h4>Past Medical History</h4>" in call_kwargs["content"]
    assert "<h4>Social History</h4>" in call_kwargs["content"]


def test_build_empty_sections() -> None:
    parser = HistoryReviewParser()
    with patch("hyperscribe.scribe.commands.history_review.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({"sections": []}, "note-uuid")

    mock_cmd.assert_called_once()
    assert mock_cmd.call_args[1]["content"] == ""


def test_build_single_section() -> None:
    parser = HistoryReviewParser()
    data = {
        "sections": [
            {"key": "family_history", "title": "Family History", "text": "Mother had asthma"},
        ]
    }
    with patch("hyperscribe.scribe.commands.history_review.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid")

    content = mock_cmd.call_args[1]["content"]
    assert "<h4>Family History</h4>" in content
    assert "<p>Mother had asthma</p>" in content
    assert "<hr>" not in content


def test_extract_raises() -> None:
    parser = HistoryReviewParser()
    try:
        parser.extract("some text")
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass
