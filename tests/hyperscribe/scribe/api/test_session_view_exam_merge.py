"""Step 2.5: merging a visit template's exam scaffold into the generated commands.

Exercises ``_reconcile_exam_templates`` directly rather than driving the whole
``post_generate_summary``, so the gating, the per-kind routing, the circuit breaker,
and the audit payloads are each pinned without a Nabla or Anthropic round trip.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from hyperscribe.scribe.api.session_view import _clean_template_sections, _reconcile_exam_templates

PE_TEMPLATE = [{"key": "general", "title": "General", "text": "Well-appearing."}]
ROS_TEMPLATE = [{"key": "constitutional", "title": "Constitutional", "text": "Denies fever."}]
MSE_TEMPLATE = [{"key": "mood", "title": "Mood", "text": "Euthymic."}]


def _pe_command(sections: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "command_type": "physical_exam",
        "display": "General",
        "data": {
            "sections": sections if sections is not None else [{"key": "general", "title": "General", "text": "Ill."}]
        },
        "selected": True,
        "section_key": "physical_exam",
        "already_documented": False,
    }


def _merged(title: str = "General", text: str = "Ill.", updated: bool = True) -> list[dict[str, Any]]:
    return [
        {"key": title.lower(), "title": title, "text": text, "updated": updated, "template_text": "Well-appearing."}
    ]


def _run(commands: list[dict[str, Any]], data: dict[str, Any], **kwargs: Any) -> None:
    params: dict[str, Any] = {
        "note_uuid": "note-uuid",
        "is_psychiatry": False,
        "merge_kinds": {"ros", "physical_exam", "mental_status_exam"},
        "api_key": "key",
    }
    params.update(kwargs)
    _reconcile_exam_templates(commands, data, **params)


# ── the off switch ──


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_empty_merge_kinds_is_a_no_op(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    commands = [_pe_command()]
    before = [dict(c) for c in commands]

    _run(commands, {"template_pe_sections": PE_TEMPLATE}, merge_kinds=set())

    assert commands == before
    mock_reconcile.assert_not_called()
    mock_audit.assert_not_called()


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_kind_not_enabled_is_skipped(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    commands = [_pe_command()]

    _run(commands, {"template_pe_sections": PE_TEMPLATE}, merge_kinds={"ros"})

    mock_reconcile.assert_not_called()
    assert "encounter_sections" not in commands[0]["data"]


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_no_template_for_kind_is_skipped(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    commands = [_pe_command()]

    _run(commands, {})

    mock_reconcile.assert_not_called()
    assert commands[0]["data"] == {"sections": [{"key": "general", "title": "General", "text": "Ill."}]}


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_malformed_template_payload_is_skipped(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    commands = [_pe_command()]

    _run(commands, {"template_pe_sections": "not a list"})

    mock_reconcile.assert_not_called()


# ── the psychiatry gate on MSE ──


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_mse_skipped_on_non_psychiatry_visit(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    commands: list[dict[str, Any]] = []

    _run(commands, {"template_mse_sections": MSE_TEMPLATE}, is_psychiatry=False)

    mock_reconcile.assert_not_called()
    assert commands == []


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_mse_runs_on_psychiatry_visit(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    mock_reconcile.return_value = (_merged("Mood", "Euthymic.", False), True)
    commands: list[dict[str, Any]] = []

    _run(commands, {"template_mse_sections": MSE_TEMPLATE}, is_psychiatry=True)

    assert len(commands) == 1
    assert commands[0]["command_type"] == "mental_status_exam"
    assert commands[0]["section_key"] == "mental_status_exam"


# ── merging into an existing command ──


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_existing_command_gets_sections_display_and_reference_keys(
    mock_reconcile: MagicMock, mock_audit: MagicMock
) -> None:
    merged = _merged() + [
        {"key": "lungs", "title": "Lungs", "text": "Clear.", "updated": False, "template_text": "Clear."}
    ]
    mock_reconcile.return_value = (merged, True)
    encounter = [{"key": "general", "title": "General", "text": "Ill."}]
    commands = [_pe_command(encounter)]

    _run(commands, {"template_pe_sections": PE_TEMPLATE})

    data = commands[0]["data"]
    assert data["sections"] == merged
    assert commands[0]["display"] == "General | Lungs"
    assert data["encounter_sections"] == encounter
    assert data["reconciled_sections"] == merged
    assert data["template_removed"] is False
    # The restore points must not alias the live list, or an edit to sections would
    # silently rewrite what the toggle reverts to.
    assert data["encounter_sections"] is not encounter
    assert data["reconciled_sections"] is not merged
    assert data["reconciled_sections"][0] is not merged[0]


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_encounter_sections_passed_to_reconcile(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    mock_reconcile.return_value = (_merged(), True)
    encounter = [{"key": "general", "title": "General", "text": "Ill."}]

    _run([_pe_command(encounter)], {"template_pe_sections": PE_TEMPLATE})

    args = mock_reconcile.call_args
    assert args[0][0] == PE_TEMPLATE
    assert args[0][1] == encounter
    assert args[0][3] == "Physical Exam"


# ── creating a command generation did not produce ──


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_missing_command_is_created_from_the_template(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    merged = _merged("General", "Well-appearing.", False)
    mock_reconcile.return_value = (merged, True)
    commands: list[dict[str, Any]] = []

    _run(commands, {"template_pe_sections": PE_TEMPLATE})

    assert mock_reconcile.call_args[0][1] == []
    assert len(commands) == 1
    created = commands[0]
    assert created["command_type"] == "physical_exam"
    assert created["section_key"] == "physical_exam"
    assert created["selected"] is True
    assert created["already_documented"] is False
    assert created["display"] == "General"
    assert created["data"]["encounter_sections"] == []


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_ros_command_created_with_underscore_section_key(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    mock_reconcile.return_value = (_merged("Constitutional", "Denies fever.", False), True)
    commands: list[dict[str, Any]] = []

    _run(commands, {"template_ros_sections": ROS_TEMPLATE})

    assert commands[0]["section_key"] == "_ros"


# ── the circuit breaker ──


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_first_refine_failure_disables_the_llm_for_later_kinds(
    mock_reconcile: MagicMock, mock_audit: MagicMock
) -> None:
    mock_reconcile.side_effect = [(_merged(), False), (_merged(), False)]

    _run([], {"template_ros_sections": ROS_TEMPLATE, "template_pe_sections": PE_TEMPLATE})

    # ROS runs first and is allowed to try; PE then takes the deterministic merge.
    assert mock_reconcile.call_args_list[0][1]["allow_refine"] is True
    assert mock_reconcile.call_args_list[1][1]["allow_refine"] is False


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_success_leaves_the_circuit_closed(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    mock_reconcile.side_effect = [(_merged(), True), (_merged(), True)]

    _run([], {"template_ros_sections": ROS_TEMPLATE, "template_pe_sections": PE_TEMPLATE})

    assert all(call[1]["allow_refine"] is True for call in mock_reconcile.call_args_list)


# ── audit ──


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_reconciled_audit_payload(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    merged = [
        {"key": "general", "title": "General", "text": "Ill.", "updated": True, "template_text": "Well."},
        {"key": "lungs", "title": "Lungs", "text": "Clear.", "updated": False, "template_text": "Clear."},
    ]
    mock_reconcile.return_value = (merged, True)

    _run([_pe_command()], {"template_pe_sections": PE_TEMPLATE})

    mock_audit.assert_called_once_with(
        "note-uuid",
        "TEMPLATE_RECONCILED",
        {
            "kind": "physical_exam",
            "template_section_count": 1,
            "encounter_section_count": 1,
            "updated_count": 1,
            "refined": True,
        },
    )


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_refine_failure_audits_llm_failed_then_circuit_open(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    mock_reconcile.side_effect = [(_merged(), False), (_merged(), False)]

    _run([], {"template_ros_sections": ROS_TEMPLATE, "template_pe_sections": PE_TEMPLATE})

    reasons = [call.args[2]["reason"] for call in mock_audit.call_args_list if call.args[1] == "TEMPLATE_REFINE_FAILED"]
    assert reasons == ["llm_failed", "circuit_open"]


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_missing_api_key_audits_no_api_key(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    mock_reconcile.return_value = (_merged(), False)

    _run([], {"template_pe_sections": PE_TEMPLATE}, api_key="")

    failures = [call for call in mock_audit.call_args_list if call.args[1] == "TEMPLATE_REFINE_FAILED"]
    assert failures[0].args[2] == {"kind": "physical_exam", "reason": "no_api_key"}


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_no_audit_payload_carries_section_text(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    secret_text = "PATIENT-IDENTIFIABLE FINDING"
    mock_reconcile.return_value = (
        [{"key": "general", "title": "General", "text": secret_text, "updated": True, "template_text": secret_text}],
        False,
    )

    _run([_pe_command()], {"template_pe_sections": [{"key": "g", "title": "General", "text": secret_text}]})

    for call in mock_audit.call_args_list:
        assert secret_text not in str(call.args[2])


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_merge_still_runs_without_a_note_uuid(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    mock_reconcile.return_value = (_merged(), True)
    commands = [_pe_command()]

    _run(commands, {"template_pe_sections": PE_TEMPLATE}, note_uuid="")

    assert "encounter_sections" in commands[0]["data"]
    mock_audit.assert_not_called()


# ── payload coercion ──


def test_clean_template_sections_coerces_and_filters() -> None:
    assert _clean_template_sections(None) == []
    assert _clean_template_sections("nope") == []
    assert _clean_template_sections([{"key": "a", "title": "A", "text": "b"}, "junk", 7]) == [
        {"key": "a", "title": "A", "text": "b"}
    ]
    assert _clean_template_sections([{"title": "A"}]) == [{"key": "", "title": "A", "text": ""}]
