from hyperscribe.scribe.print.scribe_data import (
    _section_key_to_soap,
    _should_include_command,
    _should_include_recommendation,
    build_scribe_body_items,
)


# --- _section_key_to_soap ---


def test_section_key_to_soap_known_group_key() -> None:
    assert _section_key_to_soap("chief_complaint") == "SUBJECTIVE"
    assert _section_key_to_soap("vitals") == "OBJECTIVE"
    assert _section_key_to_soap("prescription") == "ASSESSMENT & PLAN"
    assert _section_key_to_soap("charges") == "CHARGES"


def test_section_key_to_soap_ad_hoc_keys() -> None:
    assert _section_key_to_soap("_ad_hoc") == "ASSESSMENT & PLAN"
    assert _section_key_to_soap("_subjective_ad_hoc") == "SUBJECTIVE"
    assert _section_key_to_soap("_ros") == "SUBJECTIVE"
    assert _section_key_to_soap("_recommended") == "OBJECTIVE"


def test_section_key_to_soap_uppercase_normalized() -> None:
    assert _section_key_to_soap("CHIEF_COMPLAINT") == "SUBJECTIVE"


def test_section_key_to_soap_unknown_returns_empty() -> None:
    assert _section_key_to_soap("nonsense") == ""


# --- _should_include_command ---


def test_should_include_added_now_overrides_other_checks() -> None:
    assert _should_include_command({"_added_now": True, "rejected": True}) is True


def test_should_exclude_already_documented_without_command_uuid() -> None:
    """External chart commands (no command_uuid) are hidden."""
    assert _should_include_command({"display": "x", "already_documented": True}) is False


def test_should_include_already_documented_with_command_uuid() -> None:
    """Approved scribe-inserted commands carry both flags and must print."""
    cmd = {
        "display": "Test HPI from scribe",
        "command_type": "hpi",
        "command_uuid": "f27eb806-737d-44f8-af56-7764d6c698d6",
        "already_documented": True,
        "data": {"narrative": "Test HPI from scribe"},
    }
    assert _should_include_command(cmd) is True


def test_should_exclude_no_display() -> None:
    assert _should_include_command({"display": ""}) is False


def test_should_exclude_rejected_top_level() -> None:
    assert _should_include_command({"display": "x", "rejected": True}) is False


def test_should_exclude_rejected_in_data() -> None:
    assert _should_include_command({"display": "x", "data": {"rejected": True}}) is False


def test_should_exclude_incomplete_prescribe() -> None:
    cmd = {
        "display": "Lisinopril 10mg",
        "command_type": "prescribe",
        "data": {"fdb_code": "abc"},  # missing sig, quantity, type, refills
    }
    assert _should_include_command(cmd) is False


def test_should_include_complete_prescribe() -> None:
    cmd = {
        "display": "Lisinopril 10mg",
        "command_type": "prescribe",
        "data": {
            "fdb_code": "abc",
            "sig": "Take one daily",
            "quantity_to_dispense": 30,
            "type_to_dispense": "tablet",
            "refills": 2,
        },
    }
    assert _should_include_command(cmd) is True


def test_should_exclude_diagnose_without_icd() -> None:
    cmd = {"display": "x", "command_type": "diagnose", "data": {"accepted": True}}
    assert _should_include_command(cmd) is False


def test_should_exclude_diagnose_not_accepted() -> None:
    cmd = {"display": "x", "command_type": "diagnose", "data": {"icd10_code": "J18.9"}}
    assert _should_include_command(cmd) is False


# --- _should_include_recommendation ---


def test_recommendation_accepted_only() -> None:
    assert _should_include_recommendation({"accepted": True, "display": "x"}) is True
    assert _should_include_recommendation({"accepted": False, "display": "x"}) is False


def test_recommendation_excluded_when_rejected() -> None:
    assert _should_include_recommendation({"accepted": True, "rejected": True, "display": "x"}) is False


def test_recommendation_excluded_when_no_display() -> None:
    assert _should_include_recommendation({"accepted": True, "display": ""}) is False


def test_recommendation_excluded_when_already_documented() -> None:
    assert _should_include_recommendation({"accepted": True, "display": "x", "already_documented": True}) is False


# --- build_scribe_body_items ---


def test_build_with_no_data_returns_empty() -> None:
    assert build_scribe_body_items(None, None, None) == []


def test_build_includes_section_header_for_each_group() -> None:
    note_data = {
        "sections": [{"key": "chief_complaint", "title": "CC", "text": "Cough"}],
    }
    items = build_scribe_body_items(note_data, [], [])

    headers = [item["section_header"] for item in items if item.get("section_header")]
    assert "SUBJECTIVE" in headers
    cc_item = next(item for item in items if not item.get("section_header"))
    assert cc_item["content"] == "Cough"
    assert cc_item["schema_key"] == "narrative"


def test_build_groups_commands_into_correct_soap_section() -> None:
    note_data = {"sections": []}
    commands = [
        {
            "command_type": "task",
            "display": "Schedule follow-up",
            "section_key": "_ad_hoc",
            "data": {},
        },
    ]
    items = build_scribe_body_items(note_data, commands, [])

    # Header for ASSESSMENT & PLAN comes first, then the task item.
    headers = [item["section_header"] for item in items if item.get("section_header")]
    assert headers == ["ASSESSMENT & PLAN"]
    body = [item for item in items if not item.get("section_header")]
    assert len(body) == 1
    assert body[0]["schema_key"] == "task"


def test_build_dedups_commands_by_type_and_display() -> None:
    note_data = {"sections": []}
    commands = [
        {"command_type": "task", "display": "Same task", "section_key": "_ad_hoc", "data": {}},
        {"command_type": "task", "display": "Same task", "section_key": "_ad_hoc", "data": {}},
    ]
    items = build_scribe_body_items(note_data, commands, [])
    body = [item for item in items if not item.get("section_header")]
    assert len(body) == 1


def test_build_suppresses_narrative_when_covering_command_exists() -> None:
    """When a `prescribe` command is present anywhere, the `prescription`
    narrative section is suppressed even if the command lives under _ad_hoc."""
    note_data = {
        "sections": [
            {"key": "prescription", "title": "Prescriptions", "text": "Lisinopril 10mg"},
        ],
    }
    commands = [
        {
            "command_type": "prescribe",
            "display": "Lisinopril 10mg",
            "section_key": "_ad_hoc",
            "data": {
                "fdb_code": "abc",
                "sig": "Take one daily",
                "quantity_to_dispense": 30,
                "type_to_dispense": "tablet",
                "refills": 2,
            },
        },
    ]
    items = build_scribe_body_items(note_data, commands, [])
    # narrative items would have schema_key == "narrative"
    narrative_items = [i for i in items if i.get("schema_key") == "narrative"]
    assert narrative_items == []


def test_build_skips_rejected_recommendations() -> None:
    items = build_scribe_body_items(
        {"sections": []},
        [],
        [
            {"accepted": True, "rejected": True, "display": "x", "command_type": "task"},
            {"accepted": False, "display": "y", "command_type": "task"},
        ],
    )
    assert items == []
