from hyperscribe.scribe.commands._section_html import parse_ros_pe_html


def test_parses_single_section() -> None:
    html = '<div style="margin-bottom: 4px;"><b>Constitutional:</b> denies fever, chills</div>'
    assert parse_ros_pe_html(html) == [
        {"title": "Constitutional", "text": "denies fever, chills"},
    ]


def test_parses_multiple_sections_in_order() -> None:
    html = (
        '<div style="margin-bottom: 4px;"><b>HEENT:</b> denies vision changes</div>'
        '<div style="margin-bottom: 4px;"><b>Cardiovascular:</b> denies chest pain</div>'
        '<div style="margin-bottom: 4px;"><b>Respiratory:</b> denies cough</div>'
    )
    assert parse_ros_pe_html(html) == [
        {"title": "HEENT", "text": "denies vision changes"},
        {"title": "Cardiovascular", "text": "denies chest pain"},
        {"title": "Respiratory", "text": "denies cough"},
    ]


def test_handles_title_with_trailing_colon_in_b_tag() -> None:
    # The template puts the colon inside the <b> tag.
    html = "<div><b>Skin:</b> denies rash</div>"
    assert parse_ros_pe_html(html) == [{"title": "Skin", "text": "denies rash"}]


def test_empty_or_none_returns_empty_list() -> None:
    assert parse_ros_pe_html("") == []
    assert parse_ros_pe_html(None) == []  # type: ignore[arg-type]


def test_unrecognized_html_returns_empty_list() -> None:
    assert parse_ros_pe_html("<p>just some text</p>") == []


def test_section_with_blank_text_keeps_title() -> None:
    html = "<div><b>Genitourinary:</b></div>"
    assert parse_ros_pe_html(html) == [{"title": "Genitourinary", "text": ""}]


def test_skips_section_without_title() -> None:
    html = "<div><b></b> orphan text</div><div><b>HEENT:</b> ok</div>"
    assert parse_ros_pe_html(html) == [{"title": "HEENT", "text": "ok"}]


def test_strips_leading_trailing_whitespace_in_text() -> None:
    html = "<div><b>Neuro:</b>     denies headache    </div>"
    assert parse_ros_pe_html(html) == [{"title": "Neuro", "text": "denies headache"}]


def test_handles_multiline_content() -> None:
    html = "<div><b>Skin:</b>\n  denies rash, lesions\n</div>"
    assert parse_ros_pe_html(html) == [{"title": "Skin", "text": "denies rash, lesions"}]
