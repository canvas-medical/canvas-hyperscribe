from __future__ import annotations

from typing import Any

from logger import log

from canvas_sdk.utils.http import science_http


def _format_contact(c: dict[str, Any]) -> dict[str, Any]:
    """Format a raw science-service contact into the standard result shape."""
    first = c.get("firstName", "")
    last = c.get("lastName", "")
    practice = c.get("practiceName", "")
    specialty = c.get("specialty", "")

    parts: list[str] = []
    if first and first != "(TBD)":
        parts.append(first)
    if last and last != first:
        parts.append(last)
    if practice and practice != "(TBD)":
        parts.append(f"({practice}),")
    if specialty and specialty not in (first, last, practice):
        parts.append(specialty)
    if first == "(TBD)":
        parts.append(first)
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


def search_refer_providers(
    query: str,
    zip_codes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search the science-service contacts database and return formatted results."""
    if not query:
        return []

    params = f"?search={query}"
    if zip_codes:
        params += f"&business_postal_code__in={','.join(zip_codes)}"
    try:
        resp = science_http.get_json(f"/contacts/{params}")
        raw_results = (resp.json() or {}).get("results", [])
    except Exception:
        log.exception("Refer provider search failed")
        return []

    return [_format_contact(c) for c in raw_results]
