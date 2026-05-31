from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from canvas_sdk.v1.data import Note
from canvas_sdk.v1.data.patient import PatientAddress
from logger import log

from canvas_sdk.utils.http import science_http


def _format_contact(c: dict[str, Any]) -> dict[str, Any]:
    """Format a raw science-service contact into the standard result shape."""
    first = c.get("firstName", "")
    last = c.get("lastName", "")
    practice = c.get("practiceName", "")
    specialty = c.get("specialty", "")

    parts: list[str] = []
    if first:
        parts.append(first)
    if last and last != first:
        parts.append(last)
    if practice and practice != first:
        parts.append(f"({practice}),")
    if specialty and specialty not in (first, last, practice):
        parts.append(specialty)
    name = " ".join(parts).strip()

    desc_parts: list[str] = []
    phone = c.get("businessPhone")
    fax = c.get("businessFax")
    address = c.get("businessAddress")
    if phone:
        desc_parts.append(f"Phone: {phone}")
    if fax:
        desc_parts.append(f"Fax: {fax}")
    if address:
        desc_parts.append(f"Address: {address}")

    return {
        "name": name,
        "description": " ".join(desc_parts),
        "data": {
            "first_name": first,
            "last_name": last,
            "specialty": specialty,
            "practice_name": practice,
            "business_fax": fax,
            "business_phone": phone,
            "business_address": address,
        },
    }


_GENERIC_POSTAL_CODE = "11111"
_GENERIC_LAST_NAME = "(TBD)"


def _is_generic(c: dict[str, Any]) -> bool:
    """Return True if a raw science-service contact is a generic/placeholder entry.

    Science-service marks generic entries with ``last_name = "(TBD)"`` at import
    time (see ``science/contacts/management/commands/import_contacts.py``). The
    contact serializer does NOT include ``business_postal_code`` in its response
    fields, so the only structural signal available client-side is ``lastName``.

    We previously tried to detect generics by substring-matching the generic
    postal code against ``businessAddress``. That gives false positives on real
    addresses that happen to contain the digits (street numbers, ZIP+4, etc.),
    so a real provider at e.g. ``"11111 Main St"`` would be sorted as generic
    and bumped behind the placeholder. Matching ``lastName == "(TBD)"`` is
    exact and tied to the import sentinel, not to display content.
    """
    return (c.get("lastName") or "").strip() == _GENERIC_LAST_NAME


def search_refer_providers(
    query: str,
    zip_codes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search the science-service contacts database and return formatted results.

    When zip codes are available, the search includes the generic postal code
    '11111' alongside the patient's zip so that placeholder entries like
    'Psychiatry TBD' always appear in results regardless of patient location.
    """
    if not query:
        return []

    try:
        if zip_codes:
            # Include generic postal code so TBD/placeholder providers always
            # appear alongside local results — single API call.
            all_zips = list(dict.fromkeys(zip_codes + [_GENERIC_POSTAL_CODE]))
            params = urlencode({"search": query, "business_postal_code__in": ",".join(all_zips)})
            resp = science_http.get_json(f"/contacts/?{params}")
            raw_results = (resp.json() or {}).get("results", [])
            if raw_results:
                # Sort real providers before generic placeholders so callers
                # picking results[0] get a local match, not a TBD entry.
                # Bool sort orders False<True, so non-generic comes first.
                raw_results.sort(key=_is_generic)
                return [_format_contact(c) for c in raw_results]
        # No zip codes, or zip-filtered returned nothing — fall back to unfiltered.
        params = urlencode({"search": query})
        resp = science_http.get_json(f"/contacts/?{params}")
        raw_results = (resp.json() or {}).get("results", [])
    except Exception:
        log.exception("Refer provider search failed")
        return []

    return [_format_contact(c) for c in raw_results]


def resolve_zip_codes(patient_id: str = "", note_id: str = "") -> list[str]:
    """Resolve zip codes from patient address or note location."""
    zip_codes: list[str] = []
    if patient_id:
        patient_zip = (
            PatientAddress.objects.filter(patient__id=patient_id).values_list("postal_code", flat=True).first()
        )
        if patient_zip:
            zip_codes = [patient_zip]
    if not zip_codes and note_id:
        try:
            note = Note.objects.select_related("location").get(id=note_id)
            if note.location:
                loc_zip = note.location.addresses.values_list("postal_code", flat=True).first()
                if loc_zip:
                    zip_codes = [loc_zip]
        except Note.DoesNotExist:
            pass
    return zip_codes
