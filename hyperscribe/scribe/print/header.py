"""Shared context-building logic for the scribe print view."""

from typing import Any

import arrow

from hyperscribe.scribe.print.command_display import _format_phone


def build_note_header_context(note: Any) -> dict[str, Any]:
    """Build the template context dict for the print header, footer, and signature.

    Returns all fields needed by print_base.html except 'commands' (body content).
    """
    patient = note.patient
    provider = note.provider

    patient_mrn = ""
    try:
        patient_mrn = patient.mrn
    except Exception:
        pass

    signed_by = None
    signed_at = None
    try:
        current = note.current_state
        if current and current.state in ("SGN", "LKD", "RLK"):
            sign_event = note.state_history.filter(state__in=("SGN", "LKD", "RLK")).order_by("-created").first()
            if sign_event and sign_event.originator:
                person = sign_event.originator.person_subclass
                signed_by = f"{person.first_name} {person.last_name}"
                signed_at = sign_event.created
    except Exception:
        pass

    practice_name = ""
    practice_address = ""
    practice_phone = ""
    practice_fax = ""
    try:
        location = note.location
        if location:
            practice_name = location.full_name or ""
            addr = location.addresses.first()
            if addr:
                addr_parts = [addr.line1 or ""]
                if addr.line2:
                    addr_parts.append(addr.line2)
                city_state = f"{addr.city}, {addr.state_code} {addr.postal_code}".strip()
                if city_state.strip(",").strip():
                    addr_parts.append(city_state)
                practice_address = "\n".join(p for p in addr_parts if p)
            for cp in location.telecom.all():
                if cp.system == "phone" and not practice_phone:
                    practice_phone = _format_phone(cp.value)
                elif cp.system == "fax" and not practice_fax:
                    practice_fax = _format_phone(cp.value)
    except Exception:
        pass

    return {
        "patient_name": f"{patient.first_name} {patient.last_name}",
        "patient_dob": patient.birth_date,
        "patient_sex": patient.sex_at_birth,
        "patient_mrn": patient_mrn,
        "provider_name": getattr(provider, "credentialed_name", None) or f"{provider.first_name} {provider.last_name}",
        "date_of_service": note.datetime_of_service,
        "note_type": note.note_type_version.name,
        "signed_by": signed_by,
        "signed_at": signed_at,
        "practice_name": practice_name,
        "practice_address": practice_address,
        "practice_phone": practice_phone,
        "practice_fax": practice_fax,
        "now": arrow.now().datetime,
    }
