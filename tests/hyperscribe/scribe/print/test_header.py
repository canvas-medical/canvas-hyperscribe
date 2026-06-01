from types import SimpleNamespace
from unittest.mock import MagicMock

from hyperscribe.scribe.print.header import build_note_header_context


def _stub_note(**overrides: object) -> MagicMock:
    """Build a minimal mock Note with the attributes header reads."""
    patient = MagicMock()
    patient.first_name = "Jane"
    patient.last_name = "Doe"
    patient.birth_date = "1990-01-01"
    patient.sex_at_birth = "F"
    patient.mrn = "MRN-1"

    provider = MagicMock()
    provider.credentialed_name = "Dr. House, MD"
    provider.first_name = "Greg"
    provider.last_name = "House"

    note_type_version = MagicMock(name="Office Visit")
    note_type_version.name = "Office Visit"

    note = MagicMock()
    note.patient = patient
    note.provider = provider
    note.datetime_of_service = "2026-05-28T10:00:00Z"
    note.note_type_version = note_type_version
    # Default: no signature, no location
    note.current_state = SimpleNamespace(state="NEW")
    note.location = None

    for attr, value in overrides.items():
        setattr(note, attr, value)
    return note


def test_context_does_not_include_logo_url() -> None:
    """No logo in print header per KOALA-5600 requirement #2."""
    note = _stub_note()
    context = build_note_header_context(note)
    assert "logo_url" not in context


def test_context_has_expected_keys() -> None:
    note = _stub_note()
    context = build_note_header_context(note)
    expected_keys = {
        "patient_name",
        "patient_dob",
        "patient_sex",
        "patient_mrn",
        "provider_name",
        "date_of_service",
        "note_type",
        "signed_by",
        "signed_at",
        "practice_name",
        "practice_address",
        "practice_phone",
        "practice_fax",
        "now",
    }
    assert expected_keys <= set(context.keys())


def test_unsigned_note_returns_none_signature_fields() -> None:
    note = _stub_note()
    context = build_note_header_context(note)
    assert context["signed_by"] is None
    assert context["signed_at"] is None


def test_patient_name_concatenates_first_last() -> None:
    note = _stub_note()
    context = build_note_header_context(note)
    assert context["patient_name"] == "Jane Doe"


def test_provider_name_prefers_credentialed_name() -> None:
    note = _stub_note()
    context = build_note_header_context(note)
    assert context["provider_name"] == "Dr. House, MD"


def test_provider_name_falls_back_to_first_last_when_no_credentialed_name() -> None:
    note = _stub_note()
    note.provider.credentialed_name = None
    context = build_note_header_context(note)
    assert context["provider_name"] == "Greg House"


def test_signed_note_populates_signature_fields() -> None:
    sign_event = MagicMock()
    sign_event.originator.person_subclass.first_name = "Anna"
    sign_event.originator.person_subclass.last_name = "Smith"
    sign_event.created = "2026-05-27T12:00:00Z"

    history_qs = MagicMock()
    history_qs.filter.return_value.order_by.return_value.first.return_value = sign_event

    note = _stub_note()
    note.current_state = SimpleNamespace(state="SGN")
    note.state_history = history_qs

    context = build_note_header_context(note)
    assert context["signed_by"] == "Anna Smith"
    assert context["signed_at"] == "2026-05-27T12:00:00Z"


def test_location_telecom_phone_and_fax_extracted() -> None:
    location = MagicMock()
    location.full_name = "Main Clinic"
    location.addresses.first.return_value = None

    phone_cp = SimpleNamespace(system="phone", value="4155551234")
    fax_cp = SimpleNamespace(system="fax", value="4155555678")
    location.telecom.all.return_value = [phone_cp, fax_cp]

    note = _stub_note()
    note.location = location
    context = build_note_header_context(note)

    assert context["practice_name"] == "Main Clinic"
    assert context["practice_phone"] == "(415) 555-1234"
    assert context["practice_fax"] == "(415) 555-5678"
