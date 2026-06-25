from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.mental_status_exam import MentalStatusExamParser


@patch("hyperscribe.scribe.commands.mental_status_exam.render_to_string")
def test_build_renders_template_with_mental_status_exam_schema_key(mock_render: MagicMock) -> None:
    mock_render.return_value = "<div><b>Mood:</b> Euthymic</div>"
    parser = MentalStatusExamParser()
    data = {"sections": [{"title": "Mood", "text": "Euthymic"}]}

    with patch("hyperscribe.scribe.commands.mental_status_exam.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid-123", "cmd-uuid")

    mock_render.assert_called_once_with(
        "scribe/templates/ros_sections.html",
        {"sections": [{"title": "Mood", "text": "Euthymic"}]},
    )
    mock_cmd.assert_called_once_with(
        schema_key="mentalStatusExam",
        content="<div><b>Mood:</b> Euthymic</div>",
        note_uuid="note-uuid-123",
        command_uuid="cmd-uuid",
    )


@patch("hyperscribe.scribe.commands.mental_status_exam.render_to_string")
def test_build_encodes_non_ascii_as_html_entities(mock_render: MagicMock) -> None:
    mock_render.return_value = "<div><b>Affect:</b> A&amp;O ×3</div>"
    parser = MentalStatusExamParser()

    with patch("hyperscribe.scribe.commands.mental_status_exam.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({"sections": [{"title": "Affect", "text": "A&O ×3"}]}, "n", "c")

    content = mock_cmd.call_args[1]["content"]
    assert "×" not in content
    assert "&#215;" in content


@patch("hyperscribe.scribe.commands.mental_status_exam.render_to_string")
def test_build_multiple_sections(mock_render: MagicMock) -> None:
    mock_render.return_value = "<div><b>Mood:</b> Low</div><div><b>Insight:</b> Good</div>"
    parser = MentalStatusExamParser()
    data = {
        "sections": [
            {"title": "Mood", "text": "Low"},
            {"title": "Insight", "text": "Good"},
        ]
    }

    with patch("hyperscribe.scribe.commands.mental_status_exam.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    rendered_sections = mock_render.call_args[0][1]["sections"]
    assert len(rendered_sections) == 2
    assert rendered_sections[0] == {"title": "Mood", "text": "Low"}
    assert rendered_sections[1] == {"title": "Insight", "text": "Good"}


def test_extract_raises() -> None:
    parser = MentalStatusExamParser()
    try:
        parser.extract("some text")
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass
