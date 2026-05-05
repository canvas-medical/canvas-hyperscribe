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


# --- HTML entity decoding (write path uses xmlcharrefreplace + Django autoescape) ---


def test_decodes_decimal_numeric_character_references() -> None:
    # `Temp 100.4°F` is stored as `Temp 100.4&#176;F` after xmlcharrefreplace.
    html = "<div><b>Vitals:</b> Temp 100.4&#176;F</div>"
    assert parse_ros_pe_html(html) == [{"title": "Vitals", "text": "Temp 100.4°F"}]


def test_decodes_hex_numeric_character_references() -> None:
    # Django autoescape emits `&#x27;` for the apostrophe character.
    html = "<div><b>HPI:</b> pt&#x27;s pain has improved</div>"
    assert parse_ros_pe_html(html) == [{"title": "HPI", "text": "pt's pain has improved"}]


def test_decodes_named_xml_entity_references() -> None:
    html = "<div><b>Plan:</b> rule out A &amp; B; SBP &lt; 140; &quot;watchful waiting&quot;</div>"
    assert parse_ros_pe_html(html) == [
        {"title": "Plan", "text": 'rule out A & B; SBP < 140; "watchful waiting"'},
    ]


def test_decodes_entities_in_title() -> None:
    html = "<div><b>Allergies &amp; reactions:</b> NKDA</div>"
    assert parse_ros_pe_html(html) == [{"title": "Allergies & reactions", "text": "NKDA"}]


def test_decodes_extended_unicode_entities() -> None:
    # Non-Latin: micro sign (U+00B5), em-dash (U+2014), accented letter.
    html = "<div><b>Meds:</b> 5 &#181;g — caf&#233; au lait</div>"
    assert parse_ros_pe_html(html) == [{"title": "Meds", "text": "5 µg — café au lait"}]


def test_invalid_numeric_ref_passes_through() -> None:
    # Codepoints out of range or malformed don't crash the parser; they pass
    # through verbatim so providers see something rather than a blank section.
    html = "<div><b>X:</b> &#999999999999;</div>"
    assert parse_ros_pe_html(html) == [{"title": "X", "text": "&#999999999999;"}]
