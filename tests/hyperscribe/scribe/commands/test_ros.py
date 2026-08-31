from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.ros import RosParser


@patch("hyperscribe.scribe.commands.ros.render_to_string")
def test_build_renders_template_with_review_of_systems_schema_key(mock_render: MagicMock) -> None:
    mock_render.return_value = "<div><b>Constitutional:</b> Denies fever</div>"
    parser = RosParser()

    with patch("hyperscribe.scribe.commands.ros.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({"sections": [{"title": "Constitutional", "text": "Denies fever"}]}, "note-uuid", "cmd-uuid")

    mock_render.assert_called_once_with(
        "scribe/templates/ros_sections.html",
        {"sections": [{"title": "Constitutional", "text": "Denies fever"}]},
    )
    mock_cmd.assert_called_once_with(
        schema_key="reviewOfSystems",
        content="<div><b>Constitutional:</b> Denies fever</div>",
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


@patch("hyperscribe.scribe.commands.ros.render_to_string")
def test_build_encodes_non_ascii_as_html_entities(mock_render: MagicMock) -> None:
    mock_render.return_value = "<div><b>Constitutional:</b> Temp 38°C</div>"
    parser = RosParser()

    with patch("hyperscribe.scribe.commands.ros.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({"sections": [{"title": "Constitutional", "text": "Temp 38°C"}]}, "n", "c")

    content = mock_cmd.call_args[1]["content"]
    assert "°" not in content
    assert "&#176;" in content


@patch("hyperscribe.scribe.commands.ros.render_to_string")
def test_build_empty_sections(mock_render: MagicMock) -> None:
    mock_render.return_value = ""
    parser = RosParser()

    with patch("hyperscribe.scribe.commands.ros.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({"sections": []}, "note-uuid", "cmd-uuid")

    mock_render.assert_called_once_with("scribe/templates/ros_sections.html", {"sections": []})
    assert mock_cmd.call_args[1]["content"] == ""


@patch("hyperscribe.scribe.commands.ros.render_to_string")
def test_build_ignores_merge_metadata(mock_render: MagicMock) -> None:
    """The merge stamps attribution and restore points onto the proposal's sections.
    None of it may reach the chart: the rendered HTML must match a bare section."""
    mock_render.return_value = "<div><b>Constitutional:</b> Denies fever</div>"
    parser = RosParser()
    bare = {"sections": [{"key": "constitutional", "title": "Constitutional", "text": "Denies fever"}]}
    annotated = {
        "sections": [
            {
                "key": "constitutional",
                "title": "Constitutional",
                "text": "Denies fever",
                "updated": True,
                "template_text": "Denies fever, chills, weight loss",
            }
        ],
        "encounter_sections": [{"key": "constitutional", "title": "Constitutional", "text": "Denies fever"}],
        "reconciled_sections": [{"key": "constitutional", "title": "Constitutional", "text": "Denies fever"}],
        "template_removed": False,
    }

    with patch("hyperscribe.scribe.commands.ros.CustomCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(bare, "n", "c")
        parser.build(annotated, "n", "c")

    first, second = mock_render.call_args_list
    assert first[0][1] == second[0][1] == {"sections": [{"title": "Constitutional", "text": "Denies fever"}]}
    assert mock_cmd.call_args_list[0][1]["content"] == mock_cmd.call_args_list[1][1]["content"]


def test_extract_raises() -> None:
    parser = RosParser()
    try:
        parser.extract("some text")
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass
