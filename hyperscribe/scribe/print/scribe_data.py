"""Maps ScribeSummary data structures to print template context.

ScribeSummary stores data differently from Canvas Commands:
- note_data["sections"] contains narrative text keyed by section (chief_complaint, etc.)
- commands[] contains structured command proposals with command_type, display, data, section_key

This module groups both into SOAP sections matching the Scribe tab layout.
"""

from typing import Any

from hyperscribe.scribe.print.command_display import _schema_key_to_label, extract_command_display

# Commands synced from the note body (added outside the Scribe tab) carry this
# section_key. They render in a dedicated block at the bottom of the print,
# matching the Scribe tab's "ADDITIONAL COMMANDS" section (summary.js).
FROM_THE_NOTE_SECTION = "from_the_note"
ADDITIONAL_COMMANDS_TITLE = "ADDITIONAL COMMANDS"

# Scribe tab's SOAP groups with their section_key sets (from summary.js SOAP_GROUPS).
# Defined as ordered lists so we have a canonical ordering within each group.
SCRIBE_SOAP_GROUPS: list[dict[str, Any]] = [
    {
        "title": "SUBJECTIVE",
        "keys": ["chief_complaint", "history_of_present_illness", "review_of_systems"],
    },
    {
        "title": "HISTORY",
        "keys": [
            "past_medical_history",
            "past_surgical_history",
            "past_obstetric_history",
            "family_history",
            "social_history",
        ],
    },
    {
        "title": "OBJECTIVE",
        "keys": [
            "vitals",
            "mental_status_exam",
            "physical_exam",
            "lab_results",
            "imaging_results",
            "current_medications",
            "allergies",
            "immunizations",
        ],
    },
    {
        "title": "ASSESSMENT & PLAN",
        "keys": ["plan", "assessment_and_plan", "prescription", "appointments"],
    },
    {
        "title": "CHARGES",
        "keys": ["charges"],
    },
]

# Maps Hyperscribe command_type to Canvas schema_key for extract_command_display() reuse.
COMMAND_TYPE_TO_SCHEMA_KEY: dict[str, str] = {
    "rfv": "reasonForVisit",
    "hpi": "hpi",
    "plan": "plan",
    "diagnose": "diagnose",
    "assess": "assess",
    "prescribe": "prescribe",
    "medication_statement": "medicationStatement",
    "allergy": "allergy",
    "vitals": "vitals",
    "physical_exam": "physicalExam",
    "mental_status_exam": "mentalStatusExam",
    "ros": "ros",
    "history_review": "historyReview",
    "chart_review": "chartReview",
    "lab_results": "labReview",
    "perform": "perform",
    "refer": "refer",
    "lab_order": "labOrder",
    "imaging_order": "imagingOrder",
    "task": "task",
    "familyHistory": "familyHistory",
    "medicalHistory": "medicalHistory",
    "surgicalHistory": "surgicalHistory",
    "stop_medication": "stopMedication",
    "remove_allergy": "removeAllergy",
    "resolve_condition": "resolveCondition",
    "questionnaire": "questionnaire",
    "follow_up": "followUp",
    "refill": "refill",
    "change_medication": "changeMedication",
    "adjust_prescription": "adjustPrescription",
    "immunize": "immunize",
    "immunizationStatement": "immunizationStatement",
}

# Maps ad-hoc and special section_keys to their parent SOAP group title.
# Includes review-command keys (_ros, _history_review, _chart_review) and
# the _recommended key used for accepted recommendations.
AD_HOC_SECTION_MAP: dict[str, str] = {
    "_ad_hoc": "ASSESSMENT & PLAN",
    "_subjective_ad_hoc": "SUBJECTIVE",
    "_history_ad_hoc": "HISTORY",
    "_objective_ad_hoc": "OBJECTIVE",
    "_charges_ad_hoc": "CHARGES",
    "_ros": "SUBJECTIVE",
    "_history_review": "HISTORY",
    "_chart_review": "OBJECTIVE",
    "_recommended": "OBJECTIVE",
}

# Maps note_data section keys to command_types that cover them.
# When commands of a covering type exist anywhere in the note,
# the narrative section is redundant and should be suppressed.
NARRATIVE_COVERED_BY: dict[str, set[str]] = {
    "chief_complaint": {"rfv"},
    "history_of_present_illness": {"hpi"},
    "review_of_systems": {"ros"},
    "mental_health_exam": {"mental_status_exam"},
    "physical_exam": {"physical_exam"},
    "assessment_and_plan": {"diagnose", "assess"},
    "prescription": {"prescribe"},
    "appointments": {"plan"},
    "current_medications": {"medication_statement"},
    "allergies": {"allergy"},
    "past_medical_history": {"history_review", "medicalHistory"},
    "family_history": {"history_review", "familyHistory"},
    "social_history": {"history_review"},
    "imaging_results": {"imaging_order", "chart_review"},
}

# Friendly titles for note_data sections.
SECTION_TITLES: dict[str, str] = {
    "chief_complaint": "Chief Complaint",
    "history_of_present_illness": "History of Present Illness",
    "review_of_systems": "Review of Systems",
    "past_medical_history": "Past Medical History",
    "past_surgical_history": "Past Surgical History",
    "past_obstetric_history": "Past Obstetric History",
    "family_history": "Family History",
    "social_history": "Social History",
    "vitals": "Vitals",
    "mental_status_exam": "Mental Status Exam",
    "mental_health_exam": "Mental Status Exam",
    "physical_exam": "Physical Exam",
    "lab_results": "Lab Results",
    "imaging_results": "Imaging Results",
    "current_medications": "Current Medications",
    "allergies": "Allergies",
    "immunizations": "Immunizations",
    "plan": "Plan",
    "assessment_and_plan": "Assessment & Plan",
    "prescription": "Prescriptions",
    "appointments": "Appointments",
    "charges": "Charges",
}


def _normalize_key(key: str) -> str:
    """Normalize a section key to lowercase with underscores.

    Hyperscribe note_data sections may use UPPER_CASE keys (e.g. CHIEF_COMPLAINT)
    while SOAP groups use lowercase (chief_complaint). This normalizes both to match.
    """
    return key.lower()


def _section_key_to_soap(section_key: str) -> str:
    """Map a section_key to its SOAP group title. Returns empty string if unmapped."""
    if section_key in AD_HOC_SECTION_MAP:
        return AD_HOC_SECTION_MAP[section_key]
    normalized = _normalize_key(section_key)
    for group in SCRIBE_SOAP_GROUPS:
        if normalized in group["keys"]:
            return str(group["title"])
    return ""


def _should_include_command(cmd: dict[str, Any]) -> bool:
    """Return True if a command should appear in the print output.

    Mirrors the Scribe tab's wasInserted() logic (soap-group.js:341-362).
    Per KOALA-5485 the `already_documented` flag is stamped both on commands
    pulled in from outside the session AND on commands inserted by this
    session's Approve. The two cases are distinguished by `command_uuid`:
    set means we inserted it (show), missing means external context (hide).
    """
    if cmd.get("_added_now"):
        return True
    if cmd.get("already_documented") and not cmd.get("command_uuid"):
        return False
    if not cmd.get("display"):
        return False
    if cmd.get("rejected"):
        return False
    data = cmd.get("data") or {}
    if data.get("rejected"):
        return False
    cmd_type = cmd.get("command_type", "")
    if cmd_type == "imaging_order" and (
        not data.get("image_code")
        or not data.get("service_provider")
        or not data.get("ordering_provider_id")
        or not data.get("diagnosis_codes")
    ):
        return False
    if cmd_type == "prescribe" and (
        not data.get("fdb_code")
        or not data.get("sig")
        or data.get("quantity_to_dispense") is None
        or not data.get("type_to_dispense")
        or data.get("refills") is None
    ):
        return False
    if cmd_type in ("refill", "adjust_prescription") and not data.get("fdb_code"):
        return False
    if cmd_type == "lab_order" and (not data.get("lab_partner") or not data.get("tests_order_codes")):
        return False
    if cmd_type == "refer" and (
        not data.get("service_provider")
        or not data.get("clinical_question")
        or not data.get("notes_to_specialist")
        or not data.get("diagnosis_codes")
    ):
        return False
    if cmd_type == "perform" and (not data.get("cpt_code") or cmd.get("selected") is False):
        return False
    if cmd_type == "diagnose" and (not data.get("icd10_code") or not data.get("accepted")):
        return False
    return True


def _should_include_recommendation(rec: dict[str, Any]) -> bool:
    """Return True if a recommendation should appear in the print output."""
    if not rec.get("accepted"):
        return False
    if rec.get("rejected"):
        return False
    if rec.get("already_documented"):
        return False
    if not rec.get("display"):
        return False
    return True


def _command_to_display(cmd: dict[str, Any]) -> dict[str, Any]:
    """Convert a ScribeSummary command dict to a display dict for the template."""
    command_type = cmd.get("command_type", "")
    schema_key = COMMAND_TYPE_TO_SCHEMA_KEY.get(command_type, command_type)
    data = cmd.get("data") or {}
    display_str = cmd.get("display", "")

    result = extract_command_display(schema_key, data, display_str)
    result["section_header"] = ""
    return result


def _is_from_note_command(cmd: dict[str, Any]) -> bool:
    """Return True for commands synced from the note body (added outside Scribe)."""
    return cmd.get("_from_note") is True or cmd.get("section_key") == FROM_THE_NOTE_SECTION


def _from_note_to_display(cmd: dict[str, Any]) -> dict[str, Any]:
    """Convert a from-the-note command into a print display dict.

    From-note commands have a different shape than Scribe-generated commands:
    a pre-humanized ``label`` and a ``details`` list of ``{label, value}`` rows
    (built by session_view._details_for_command), with no ``display`` or ``data``.
    """
    label = cmd.get("label") or _schema_key_to_label(cmd.get("command_type", ""))
    details = cmd.get("details") or []
    detail_rows = [
        {"label": str(d.get("label", "")), "value": str(d.get("value", ""))}
        for d in details
        if isinstance(d, dict) and d.get("value")
    ]
    return {
        "label": label,
        "content": "",
        "html_content": "",
        "detail_rows": detail_rows,
        "schema_key": "from_note",
        "section_header": "",
    }


def build_scribe_body_items(
    note_data: dict[str, Any] | None,
    commands: list[dict[str, Any]] | None,
    recommendations: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build an ordered list of display items grouped by SOAP section.

    Combines narrative sections from note_data with structured commands,
    matching the Scribe tab's SOAP grouping and ordering.

    Returns a list of dicts suitable for the print template, with section_header
    sentinel items inserted between SOAP groups.
    """
    commands = commands or []
    recommendations = recommendations or []
    sections = note_data.get("sections", []) if note_data else []

    section_by_key: dict[str, dict[str, str]] = {}
    for sec in sections:
        if isinstance(sec, dict) and sec.get("key"):
            section_by_key[_normalize_key(sec["key"])] = sec

    commands_by_section: dict[str, list[dict[str, Any]]] = {}

    cmd_section_key_order: list[str] = []
    cmd_section_key_seen: set[str] = set()

    all_command_types: set[str] = set()

    # Deduplicate commands by (command_type, display) to prevent identical content
    # rendering twice when ScribeSummary has the same command under different
    # section_keys (e.g., physical_exam under both "physical_exam" and "_objective_ad_hoc",
    # or duplicate entries from template reconciliation).
    rendered_commands: set[tuple[str, str]] = set()

    # Commands added outside the Scribe tab (synced from the note body) render
    # in a dedicated "ADDITIONAL COMMANDS" block at the bottom, preserving the
    # order they appear in the command list (matching the Scribe tab).
    from_note_items: list[dict[str, Any]] = []

    for cmd in commands:
        if _is_from_note_command(cmd):
            from_note_items.append(_from_note_to_display(cmd))
            continue
        if not _should_include_command(cmd):
            continue
        cmd_type = cmd.get("command_type", "")
        cmd_display = cmd.get("display", "")
        dedup_key = (cmd_type, cmd_display)
        if dedup_key in rendered_commands:
            continue
        rendered_commands.add(dedup_key)

        section_key = cmd.get("section_key", "")
        norm_key = _normalize_key(section_key) if not section_key.startswith("_") else section_key
        commands_by_section.setdefault(norm_key, []).append(_command_to_display(cmd))
        all_command_types.add(cmd_type)
        if norm_key not in cmd_section_key_seen:
            cmd_section_key_order.append(norm_key)
            cmd_section_key_seen.add(norm_key)

    for rec in recommendations:
        if not _should_include_recommendation(rec):
            continue
        rec_type = rec.get("command_type", "")
        rec_display = rec.get("display", "")
        dedup_key = (rec_type, rec_display)
        if dedup_key in rendered_commands:
            continue
        rendered_commands.add(dedup_key)

        section_key = rec.get("section_key", "")
        norm_key = _normalize_key(section_key) if not section_key.startswith("_") else section_key
        commands_by_section.setdefault(norm_key, []).append(_command_to_display(rec))
        all_command_types.add(rec_type)
        if norm_key not in cmd_section_key_seen:
            cmd_section_key_order.append(norm_key)
            cmd_section_key_seen.add(norm_key)

    body_items: list[dict[str, Any]] = []

    ordered_section_keys = [_normalize_key(sec["key"]) for sec in sections if isinstance(sec, dict) and sec.get("key")]

    for group in SCRIBE_SOAP_GROUPS:
        group_title = group["title"]
        group_keys_list: list[str] = group["keys"]
        group_keys_set = set(group_keys_list)

        # Priority: (1) canonical SOAP group order, (2) note_data order, (3) command order.
        group_ordered_keys: list[str] = []
        seen: set[str] = set()

        note_data_keys_in_group = [k for k in ordered_section_keys if k in group_keys_set]
        if note_data_keys_in_group:
            for key in note_data_keys_in_group:
                if key not in seen:
                    group_ordered_keys.append(key)
                    seen.add(key)
        else:
            for key in group_keys_list:
                if key not in seen:
                    group_ordered_keys.append(key)
                    seen.add(key)

        for key in cmd_section_key_order:
            soap = _section_key_to_soap(key)
            if soap == group_title and key not in seen:
                group_ordered_keys.append(key)
                seen.add(key)

        group_items: list[dict[str, Any]] = []
        for key in group_ordered_keys:
            key_cmds = commands_by_section.get(key, [])
            # Two dedup checks:
            #   1) Commands exist for this exact section_key
            #   2) Commands of a covering type exist anywhere (e.g. prescribe
            #      commands use _ad_hoc key but cover the "prescription" narrative)
            covering_types = NARRATIVE_COVERED_BY.get(key, set())
            covered_by_commands = bool(key_cmds) or bool(covering_types & all_command_types)
            if not covered_by_commands:
                sec = section_by_key.get(key)
                if sec and sec.get("text", "").strip():
                    title = sec.get("title") or SECTION_TITLES.get(key, key.replace("_", " ").title())
                    group_items.append(
                        {
                            "label": title,
                            "content": sec["text"],
                            "html_content": "",
                            "schema_key": "narrative",
                            "section_header": "",
                        }
                    )
            group_items.extend(key_cmds)

        if not group_items:
            continue

        body_items.append(
            {
                "label": "",
                "content": "",
                "html_content": "",
                "section_header": group_title,
            }
        )
        body_items.extend(group_items)

    # Additional commands entered outside the Scribe tab, appended last in their
    # original list order (KOALA-5600 requirement #6).
    if from_note_items:
        body_items.append(
            {
                "label": "",
                "content": "",
                "html_content": "",
                "section_header": ADDITIONAL_COMMANDS_TITLE,
            }
        )
        body_items.extend(from_note_items)

    return body_items
