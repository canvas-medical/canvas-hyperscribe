from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.physical_exam import PhysicalExamParser


@patch("hyperscribe.scribe.commands.physical_exam.render_to_string")
def test_build_renders_template(mock_render: MagicMock) -> None:
    mock_render.return_value = "<div><b>General:</b> Well-appearing</div>"
    parser = PhysicalExamParser()
    data = {"sections": [{"title": "General", "text": "Well-appearing"}]}

    with patch("hyperscribe.scribe.commands.physical_exam.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid-123", "cmd-uuid")

    mock_render.assert_called_once_with(
        "scribe/templates/ros_sections.html",
        {"sections": [{"title": "General", "text": "Well-appearing"}]},
    )
    mock_cmd.assert_called_once_with(
        schema_key="physicalExam",
        content="<div><b>General:</b> Well-appearing</div>",
        note_uuid="note-uuid-123",
        command_uuid="cmd-uuid",
    )


@patch("hyperscribe.scribe.commands.physical_exam.render_to_string")
def test_build_multiple_sections(mock_render: MagicMock) -> None:
    mock_render.return_value = "<div><b>General:</b> WA</div><div><b>Lungs:</b> CTA</div>"
    parser = PhysicalExamParser()
    data = {
        "sections": [
            {"title": "General", "text": "WA"},
            {"title": "Lungs", "text": "CTA"},
        ]
    }

    with patch("hyperscribe.scribe.commands.physical_exam.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    rendered_sections = mock_render.call_args[0][1]["sections"]
    assert len(rendered_sections) == 2
    assert rendered_sections[0] == {"title": "General", "text": "WA"}
    assert rendered_sections[1] == {"title": "Lungs", "text": "CTA"}


@patch("hyperscribe.scribe.commands.physical_exam.render_to_string")
def test_build_empty_sections(mock_render: MagicMock) -> None:
    mock_render.return_value = ""
    parser = PhysicalExamParser()

    with patch("hyperscribe.scribe.commands.physical_exam.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({"sections": []}, "note-uuid", "cmd-uuid")

    mock_render.assert_called_once_with(
        "scribe/templates/ros_sections.html",
        {"sections": []},
    )
    assert mock_cmd.call_args[1]["content"] == ""


def test_extract_raises() -> None:
    parser = PhysicalExamParser()
    try:
        parser.extract("some text")
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass
