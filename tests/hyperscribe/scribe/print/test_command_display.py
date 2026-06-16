from pathlib import Path

import hyperscribe
from django.conf import settings
from django.template import Context, Engine

from hyperscribe.scribe.print.command_display import (
    SOAP_SECTIONS,
    _decode_b64_html,
    _format_date,
    _format_icd_code,
    _format_phone,
    _sanitize_html,
    _schema_key_to_label,
    extract_command_display,
)


def _render_print_note(commands: list[dict]) -> str:
    """Render the real print_scribe_note.html template with the given body commands.

    The SDK's ``render_to_string`` requires plugin context (unavailable in unit
    tests), so drive Django's template engine directly against the template dir.
    This exercises the actual template — including the perform/charge branch that
    prints a charge comment (``perform.notes``).
    """
    if not settings.configured:
        settings.configure(USE_TZ=True)
        import django

        django.setup()
    templates_root = str(Path(hyperscribe.__file__).resolve().parent)
    engine = Engine(dirs=[templates_root])
    template = engine.get_template("scribe/print/templates/print_scribe_note.html")
    return template.render(Context({"patient_name": "Test Patient", "commands": commands}))


# --- helpers ---


def test_format_phone_10_digit() -> None:
    assert _format_phone("4155551234") == "(415) 555-1234"


def test_format_phone_11_digit_with_country_code() -> None:
    assert _format_phone("14155551234") == "(415) 555-1234"


def test_format_phone_passthrough_when_unparseable() -> None:
    assert _format_phone("garbage") == "garbage"


def test_format_date_iso_string() -> None:
    assert _format_date("2026-04-14") == "04/14/2026"


def test_format_date_dict_form() -> None:
    assert _format_date({"date": "2026-04-14"}) == "04/14/2026"


def test_format_date_passthrough_on_bad_format() -> None:
    assert _format_date("not-a-date") == "not-a-date"


def test_format_icd_code_inserts_dot() -> None:
    assert _format_icd_code("J189") == "J18.9"


def test_format_icd_code_already_dotted() -> None:
    assert _format_icd_code("J18.9") == "J18.9"


def test_schema_key_to_label_known() -> None:
    assert _schema_key_to_label("hpi") == "History of Present Illness"


def test_schema_key_to_label_camel_case_unknown_falls_back_to_titlecase() -> None:
    assert _schema_key_to_label("myCustomKey") == "My Custom Key"


# --- sanitization ---


def test_sanitize_html_strips_scripts() -> None:
    raw = "<p>safe</p><script>alert('x')</script>"
    cleaned = _sanitize_html(raw)
    assert "<script>" not in cleaned
    assert "alert" not in cleaned


def test_sanitize_html_strips_event_handlers() -> None:
    raw = '<a href="x" onclick="bad()">click</a>'
    assert "onclick" not in _sanitize_html(raw)


def test_sanitize_html_strips_iframes() -> None:
    raw = "<p>before</p><iframe src='evil'></iframe><p>after</p>"
    assert "<iframe" not in _sanitize_html(raw)


def test_sanitize_html_converts_double_asterisk_to_strong() -> None:
    assert _sanitize_html("**bold**") == "<strong>bold</strong>"


def test_decode_b64_html_handles_bad_input() -> None:
    assert _decode_b64_html("@@@not-base64@@@") == ""


# --- extract_command_display sample per major schema_key ---


def test_extract_hpi() -> None:
    result = extract_command_display("hpi", {"narrative": "Sore throat x 3 days."})
    assert result["label"] == "History of Present Illness"
    assert result["content"] == "Sore throat x 3 days."


def test_extract_diagnose_with_icd_and_text() -> None:
    result = extract_command_display(
        "diagnose",
        {"icd10_code": "J189", "icd10_display": "Pneumonia, unspecified organism"},
    )
    assert result["icd_code"] == "J18.9"
    assert result["icd_display"] == "Pneumonia, unspecified organism"


def test_extract_prescribe_assembles_details() -> None:
    result = extract_command_display(
        "prescribe",
        {
            "medication_text": "Amoxicillin 500mg",
            "sig": "1 cap TID x 7d",
            "quantity_to_dispense": 21,
            "type_to_dispense_label": "capsule",
            "days_supply": 7,
            "refills": 0,
            "pharmacy_name": "Local Rx",
        },
    )
    assert result["name"] == "Amoxicillin 500mg"
    assert result["sig"] == "1 cap TID x 7d"
    assert "Qty: 21 x capsule" in result["details"]
    assert "7d supply" in result["details"]
    assert "0 refills" in result["details"]
    assert result["pharmacy"] == "Local Rx"


def test_extract_vitals_collects_recognized_fields() -> None:
    result = extract_command_display(
        "vitals",
        {
            "blood_pressure_systole": 120,
            "blood_pressure_diastole": 80,
            "pulse": 72,
            "body_temperature": 98.6,
        },
    )
    labels = {part["label"] for part in result["vitals_parts"]}
    assert {"BP", "HR", "Temp"} <= labels


def test_extract_perform_with_cpt_inline() -> None:
    result = extract_command_display(
        "perform",
        {"description": "Office visit, established patient (CPT 99213)"},
    )
    assert result["cpt_code"] == "99213"
    assert "CPT" not in result["description"]


def test_extract_perform_with_comment_notes() -> None:
    """A charge comment (perform.notes) surfaces as `notes` so the print template
    renders it beneath the CPT/description."""
    result = extract_command_display(
        "perform",
        {"cpt_code": "96372", "description": "Injection", "notes": "Given in left deltoid per protocol."},
    )
    assert result["cpt_code"] == "96372"
    assert result["notes"] == "Given in left deltoid per protocol."
    assert "Given in left deltoid per protocol." in result["content"]


def test_extract_perform_without_comment_has_empty_notes() -> None:
    result = extract_command_display("perform", {"cpt_code": "99213", "description": "Office visit"})
    assert result["notes"] == ""


def test_print_template_renders_perform_comment() -> None:
    """The print template renders a charge comment (perform.notes) under the charge."""
    html = _render_print_note(
        [
            {
                "schema_key": "perform",
                "cpt_code": "96372",
                "description": "Injection",
                "notes": "Given in left deltoid per protocol.",
            }
        ]
    )
    assert "Given in left deltoid per protocol." in html
    # the comment is wrapped in the order-view-details div (CSS rule uses
    # `.order-view-details {`, so matching `class="..."` targets the rendered div)
    assert 'class="order-view-details"' in html


def test_print_template_omits_empty_perform_comment() -> None:
    """A charge with no comment renders no comment div."""
    html = _render_print_note(
        [{"schema_key": "perform", "cpt_code": "99213", "description": "Office visit", "notes": ""}]
    )
    assert "99213" in html
    assert 'class="order-view-details"' not in html


def test_extract_action_command_stop_medication() -> None:
    result = extract_command_display(
        "stopMedication",
        {"medication_text": "Lisinopril", "rationale": "Side effects"},
    )
    assert result["name"] == "Lisinopril"
    assert result["action"] == "STOP"
    assert result["rationale"] == "Side effects"


def test_extract_fallback_uses_narrative() -> None:
    """An unknown schema_key falls through to the catch-all narrative."""
    result = extract_command_display("unknownSchemaKey", {"narrative": "free text"})
    assert result["content"] == "free text"


def test_soap_sections_includes_charges() -> None:
    assert SOAP_SECTIONS["perform"] == "CHARGES"
