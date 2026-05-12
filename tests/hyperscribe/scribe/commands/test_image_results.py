from unittest.mock import patch

from hyperscribe.scribe.backend.models import ClinicalNote, NoteSection
from hyperscribe.scribe.commands.builder import _BUILDERS
from hyperscribe.scribe.commands.extractor import extract_commands
from hyperscribe.scribe.commands.image_results import (
    ImageResultsParser,
    _narrative_to_html,
)


def test_parser_registered_under_imaging_results_key() -> None:
    parser = _BUILDERS["imaging_results"]
    assert isinstance(parser, ImageResultsParser)
    assert parser.command_type == "imaging_results"
    assert parser.data_field == "narrative"


def test_extract_imaging_results_section_to_proposal() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(
                key="imaging_results",
                title="Imaging Results",
                text="- Chest X-ray: clear lungs.\n- Knee MRI: small effusion.",
            )
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "imaging_results"
    assert proposals[0].section_key == "imaging_results"
    assert proposals[0].data == {
        "narrative": "- Chest X-ray: clear lungs.\n- Knee MRI: small effusion.",
    }


def test_extract_empty_imaging_results_section_yields_no_proposal() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="imaging_results", title="Imaging Results", text="   ")],
    )
    assert extract_commands(note) == []


def test_narrative_to_html_bulletizes_dash_separated_items() -> None:
    html = _narrative_to_html("- Chest X-ray: clear.\n- Knee MRI: small effusion.")
    assert html == "<ul><li>Chest X-ray: clear.</li><li>Knee MRI: small effusion.</li></ul>"


def test_narrative_to_html_wraps_plain_text_in_paragraph() -> None:
    assert _narrative_to_html("Findings unremarkable.") == "<p>Findings unremarkable.</p>"


def test_narrative_to_html_returns_empty_string_for_blank_input() -> None:
    assert _narrative_to_html("   ") == ""
    assert _narrative_to_html("") == ""
    assert _narrative_to_html("\n\n  \n") == ""


def test_narrative_to_html_free_text_after_bullets_does_not_collapse() -> None:
    text = (
        "- Hemoglobin A1c: 6.9%\n"
        "- Platelets: 240 x10/uL\n"
        "new line 1\n"
        "new line 2.\n"
        "new line 3\n"
        "\n"
        "new line 4 with an extra blank line above."
    )
    assert _narrative_to_html(text) == (
        "<ul><li>Hemoglobin A1c: 6.9%</li><li>Platelets: 240 x10/uL</li></ul>"
        "<p>new line 1<br>new line 2.<br>new line 3</p>"
        "<p>new line 4 with an extra blank line above.</p>"
    )


def test_narrative_to_html_blank_line_starts_new_paragraph() -> None:
    assert _narrative_to_html("First paragraph.\n\nSecond paragraph.") == (
        "<p>First paragraph.</p><p>Second paragraph.</p>"
    )


def test_narrative_to_html_hard_line_break_within_paragraph() -> None:
    assert _narrative_to_html("Line A\nLine B") == "<p>Line A<br>Line B</p>"


def test_narrative_to_html_bullets_can_resume_after_paragraph() -> None:
    text = "- first\n\nintroductory text\n\n- second\n- third"
    assert _narrative_to_html(text) == (
        "<ul><li>first</li></ul>"
        "<p>introductory text</p>"
        "<ul><li>second</li><li>third</li></ul>"
    )


def test_narrative_to_html_escapes_non_ascii() -> None:
    html = _narrative_to_html("Café reading 98° normal")
    assert "&#233;" in html  # é
    assert "&#176;" in html  # °


def test_build_creates_custom_command_with_image_result_schema_key() -> None:
    parser = ImageResultsParser()
    with patch("hyperscribe.scribe.commands.image_results.CustomCommand") as mock_cc:
        parser.build(
            data={"narrative": "- MRI brain: no acute findings."},
            note_uuid="note-uuid",
            command_uuid="cmd-uuid",
        )
    mock_cc.assert_called_once_with(
        schema_key="imageResult",
        content="<ul><li>MRI brain: no acute findings.</li></ul>",
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_with_empty_narrative_passes_empty_content() -> None:
    parser = ImageResultsParser()
    with patch("hyperscribe.scribe.commands.image_results.CustomCommand") as mock_cc:
        parser.build(data={}, note_uuid="note-uuid", command_uuid="cmd-uuid")
    mock_cc.assert_called_once_with(
        schema_key="imageResult",
        content="",
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_narrative_to_html_escapes_less_than_in_clinical_text() -> None:
    # K+ <3.0 used to render as malformed markup; now becomes &lt;.
    assert _narrative_to_html("- K+ <3.0 mmol/L") == "<ul><li>K+ &lt;3.0 mmol/L</li></ul>"


def test_narrative_to_html_escapes_greater_than_in_clinical_text() -> None:
    assert _narrative_to_html("- BP > 140/90") == "<ul><li>BP &gt; 140/90</li></ul>"


def test_narrative_to_html_escapes_ampersand() -> None:
    assert _narrative_to_html("Q&A about results") == "<p>Q&amp;A about results</p>"


def test_narrative_to_html_escapes_script_tag_injection() -> None:
    out = _narrative_to_html("<script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out


def test_narrative_to_html_handles_combined_non_ascii_and_metacharacter() -> None:
    out = _narrative_to_html("Café reading 98° was <2 mmHg")
    assert "&#233;" in out  # é
    assert "&#176;" in out  # °
    assert "&lt;2" in out
    assert "<2" not in out
