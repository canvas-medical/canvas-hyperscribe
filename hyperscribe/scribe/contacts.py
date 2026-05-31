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
# Fallback the science import-contacts management command writes when a
# customer-supplied CSV row omits ``business_postal_code`` (see
# ``science/contacts/management/commands/import_contacts.py`` —
# ``row.get("business_postal_code") or "."``). Including "." in the zip
# filter surfaces generic/TBD contacts that came in via that path; otherwise
# they vanish for any patient whose own zip is not literally ".".
_IMPORT_MISSING_POSTAL_CODE = "."
_GENERIC_POSTAL_CODES = (_GENERIC_POSTAL_CODE, _IMPORT_MISSING_POSTAL_CODE)
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


def _search_contacts(
    query: str,
    zip_codes: list[str] | None,
    extra_params: dict[str, str] | None,
    log_label: str,
) -> list[dict[str, Any]]:
    """Shared science-service ``/contacts/`` search helper.

    When ``zip_codes`` is non-empty the request filters by
    ``business_postal_code__in=<zips>,<_GENERIC_POSTAL_CODE>`` in a single API
    call so generic/TBD placeholders appear alongside local results. Results
    are sorted with non-generic contacts first (see ``_is_generic``).

    When the zip-filtered call returns no rows the helper falls back to an
    unfiltered call — preserving the prior behavior of both call sites.

    ``extra_params`` lets callers tack on filters (e.g. ``job_title__icontains
    =radiology`` for the imaging-center variant) without re-implementing the
    rest of the pipeline. ``log_label`` shapes the exception log message so
    failures are attributable to the calling endpoint.
    """
    if not query:
        return []

    base_params: dict[str, str] = {"search": query}
    if extra_params:
        base_params.update(extra_params)

    try:
        if zip_codes:
            # Include both generic postal codes so TBD/placeholder contacts
            # always appear alongside local results — single API call.
            all_zips = list(dict.fromkeys(zip_codes + list(_GENERIC_POSTAL_CODES)))
            params = urlencode({**base_params, "business_postal_code__in": ",".join(all_zips)})
            resp = science_http.get_json(f"/contacts/?{params}")
            raw_results = (resp.json() or {}).get("results", [])
            if raw_results:
                # Sort real contacts before generic placeholders so callers
                # picking results[0] get a local match, not a TBD entry.
                # Bool sort orders False<True, so non-generic comes first.
                raw_results.sort(key=_is_generic)
                return [_format_contact(c) for c in raw_results]
        # No zip codes, or zip-filtered returned nothing — fall back to unfiltered.
        params = urlencode(base_params)
        resp = science_http.get_json(f"/contacts/?{params}")
        raw_results = (resp.json() or {}).get("results", [])
    except Exception as exc:
        # HIPAA: the request URL contains the typed search query, which can
        # carry patient identifiers (provider types patient name as part of
        # refer search). Avoid log.exception/str(exc) — both leak the URL via
        # the traceback or the HTTPError message format. Log only the
        # exception class name.
        log.error("%s failed: %s", log_label, type(exc).__name__)
        return []

    return [_format_contact(c) for c in raw_results]


def search_refer_providers(
    query: str,
    zip_codes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search the science-service contacts database for referral providers.

    When zip codes are available, the search includes the generic postal code
    '11111' alongside the patient's zip so that placeholder entries like
    'Psychiatry TBD' always appear in results regardless of patient location.
    """
    return _search_contacts(
        query=query,
        zip_codes=zip_codes,
        extra_params=None,
        log_label="Refer provider search",
    )


# Imaging-adjacent specialty values from
# ``science/contacts/models.py::Contact.SPECIALTY_CHOICES``. The science
# FilterSet only exposes ``__icontains`` (no ``__in``/``__iregex``), so we
# scope each call to one substring and merge results. "radiology" captures
# both ``Radiology`` and ``Vascular & Interventional Radiology`` in one call;
# ``Nuclear Medicine`` needs its own call. (``Radiation Oncology`` is treatment
# rather than diagnostic imaging and is intentionally excluded — flag for
# product confirmation if patients are missing therapy-providers from search.)
_IMAGING_JOB_TITLE_FILTERS: tuple[str, ...] = ("radiology", "nuclear medicine")


def search_imaging_centers(
    query: str,
    zip_codes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search the science-service contacts database for imaging providers.

    Same single-call + generic-postal-code semantics as
    :func:`search_refer_providers`, but issues one call per imaging-adjacent
    job_title filter (see ``_IMAGING_JOB_TITLE_FILTERS``) and merges results
    de-duplicated by serialized content. This ensures Nuclear Medicine
    providers — which "radiology" alone misses — surface for queries like
    "PET scan", and also keeps the generic-TBD surfacing path
    ("Grove Diagnostic Imaging TBD Radiology") intact across all imaging
    specialties.
    """
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for job_title_filter in _IMAGING_JOB_TITLE_FILTERS:
        results = _search_contacts(
            query=query,
            zip_codes=zip_codes,
            extra_params={"job_title__icontains": job_title_filter},
            log_label=f"Imaging center search ({job_title_filter})",
        )
        for result in results:
            data = result["data"]
            # A contact has exactly one ``job_title`` value, so duplicates
            # across two icontains buckets are rare in practice; key on a
            # stable content tuple to be defensive against future overlaps.
            key = (
                data["first_name"],
                data["last_name"],
                data["practice_name"],
                data["business_address"],
                data["specialty"],
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(result)
    return merged


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
