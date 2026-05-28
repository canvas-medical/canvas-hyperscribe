import json
from typing import Any

import pytest
from unittest.mock import MagicMock, patch

import pytest
from canvas_generated.messages.effects_pb2 import EffectType
from canvas_sdk.commands.commands.custom_command import CustomCommand
from pydantic import BaseModel, Field, ValidationError

from hyperscribe.scribe.commands.builder import (
    _BUILDERS,
    _format_pydantic_errors,
    CUSTOM_COMMAND_ROUTED_SECTIONS,
    DIRECT_EDIT_SECTIONS,
    EDITABLE_AMEND_SECTIONS,
    NON_EDITABLE_AMEND_COMMAND_TYPES,
    build_amend_delete_effects,
    build_amend_edit_effects,
    build_effects,
    build_metadata_effects,
    prefill_assess_backgrounds,
    validate_proposals,
)


def _make_constrained_int_model(
    ge: int | None = None,
    le: int | None = None,
    gt: int | None = None,
    lt: int | None = None,
) -> type[BaseModel]:
    """Build a tiny Pydantic v2 model with the requested numeric constraint on ``value``.

    Used by the type-string guard test to exercise each branch of
    ``_format_pydantic_errors`` against a real ValidationError, not a synthesized dict.
    """
    field_kwargs: dict[str, Any] = {}
    if ge is not None:
        field_kwargs["ge"] = ge
    if le is not None:
        field_kwargs["le"] = le
    if gt is not None:
        field_kwargs["gt"] = gt
    if lt is not None:
        field_kwargs["lt"] = lt

    class _NumModel(BaseModel):
        value: int = Field(**field_kwargs)

    return _NumModel


def _make_constrained_str_model(
    min_length: int | None = None,
    max_length: int | None = None,
) -> type[BaseModel]:
    """Build a Pydantic v2 model with a string-length constraint on ``value``."""
    field_kwargs: dict[str, Any] = {}
    if min_length is not None:
        field_kwargs["min_length"] = min_length
    if max_length is not None:
        field_kwargs["max_length"] = max_length

    class _StrModel(BaseModel):
        value: str = Field(**field_kwargs)

    return _StrModel


def _make_required_field_model() -> type[BaseModel]:
    """Build a Pydantic v2 model with a required field (no default) to trigger
    ``type=missing``."""

    class _ReqModel(BaseModel):
        value: int

    return _ReqModel


def test_build_effects_routes_all_types() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "rfv", "data": {"comment": "Headache"}},
        {"command_type": "hpi", "data": {"narrative": "Two weeks of headaches"}},
        {"command_type": "vitals", "data": {"pulse": 72, "blood_pressure_systole": 120, "blood_pressure_diastole": 80}},
        {"command_type": "plan", "data": {"narrative": "Start sumatriptan"}},
        {"command_type": "medication_statement", "data": {"medication_text": "Lisinopril 10mg"}},
        {"command_type": "task", "data": {"title": "Follow up"}},
        {"command_type": "prescribe", "data": {"fdb_code": "123", "sig": "daily"}},
        {"command_type": "lab_order", "data": {"comment": "CBC"}},
        {"command_type": "imaging_order", "data": {"comment": "MRI", "priority": "Routine"}},
        {
            "command_type": "history_review",
            "data": {"sections": [{"key": "past_medical_history", "title": "PMH", "text": "HTN"}]},
        },
        {
            "command_type": "chart_review",
            "data": {"sections": [{"key": "allergies", "title": "Allergies", "text": "NKDA"}]},
        },
        {
            "command_type": "allergy",
            "data": {"allergy_text": "Penicillin", "concept_id": None, "concept_id_type": None},
        },
        {
            "command_type": "diagnose",
            "data": {"icd10_code": "G43.009", "today_assessment": "Start sumatriptan"},
        },
        {
            "command_type": "assess",
            "data": {"condition_id": "cond-uuid", "narrative": "Stable"},
        },
    ]
    with (
        patch("hyperscribe.scribe.commands.rfv.ReasonForVisitCommand") as mock_rfv,
        patch("hyperscribe.scribe.commands.hpi.HistoryOfPresentIllnessCommand") as mock_hpi,
        patch("hyperscribe.scribe.commands.plan.PlanCommand") as mock_plan,
        patch("hyperscribe.scribe.commands.vitals.VitalsCommand") as mock_vitals,
        patch("hyperscribe.scribe.commands.medication_statement.MedicationStatementCommand") as mock_med,
        patch("hyperscribe.scribe.commands.task.TaskCommand") as mock_task,
        patch("hyperscribe.scribe.commands.prescription.PrescribeCommand") as mock_rx,
        patch("hyperscribe.scribe.commands.lab_order.LabOrderCommand") as mock_lab,
        patch("hyperscribe.scribe.commands.imaging_order.ImagingOrderCommand") as mock_img,
        patch("hyperscribe.scribe.commands.history_review.render_to_string", return_value=""),
        patch("hyperscribe.scribe.commands.chart_review.render_to_string", return_value=""),
        patch("hyperscribe.scribe.commands.history_review.CustomCommand") as mock_history,
        patch("hyperscribe.scribe.commands.chart_review.CustomCommand") as mock_chart,
        patch("hyperscribe.scribe.commands.allergy.AllergyCommand") as mock_allergy,
        patch("hyperscribe.scribe.commands.diagnose.DiagnoseCommand") as mock_diagnose,
        patch("hyperscribe.scribe.commands.assess.AssessCommand") as mock_assess,
    ):
        all_mocks = [
            mock_rfv,
            mock_hpi,
            mock_plan,
            mock_vitals,
            mock_med,
            mock_task,
            mock_rx,
            mock_lab,
            mock_img,
            mock_history,
            mock_chart,
            mock_allergy,
            mock_diagnose,
            mock_assess,
        ]
        for mock in all_mocks:
            inst = MagicMock()
            inst.originate.return_value = f"{mock._mock_name}_originate"
            inst.commit.return_value = f"{mock._mock_name}_commit"
            inst.review.return_value = f"{mock._mock_name}_review"
            inst.command_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
            inst.note_uuid = "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
            mock.return_value = inst

        effects, metadata_pending, attempted, build_errors = build_effects(
            proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
        )

    # 14 originates + 13 commits + 1 review (prescription)
    assert len(effects) == 28
    assert metadata_pending == []
    assert len(attempted) == 14
    assert {a["command_type"] for a in attempted} == {
        "rfv",
        "hpi",
        "vitals",
        "plan",
        "medication_statement",
        "task",
        "prescribe",
        "lab_order",
        "imaging_order",
        "history_review",
        "chart_review",
        "allergy",
        "diagnose",
        "assess",
    }
    for mock in all_mocks:
        mock.assert_called_once()


def test_build_effects_unknown_type_skipped() -> None:
    proposals: list[dict[str, Any]] = [{"command_type": "unknown_type", "data": {"foo": "bar"}}]
    effects, metadata_pending, attempted, build_errors = build_effects(proposals, "note-uuid")
    assert effects == []
    assert metadata_pending == []
    assert attempted == []


def test_build_effects_empty_list() -> None:
    effects, metadata_pending, attempted, build_errors = build_effects([], "note-uuid")
    assert effects == []
    assert metadata_pending == []
    assert attempted == []


def test_prefill_assess_backgrounds_filters_assess_only_and_loads_note() -> None:
    """``prefill_assess_backgrounds`` filters to assess proposals, loads the
    ``Note``, and delegates to ``carry_forward_assess_background`` per
    proposal.

    This pins the public-function contract: non-assess proposals are skipped
    (no DB lookup chain runs for them), and proposals with non-dict ``data``
    are tolerated without raising.
    """
    proposals: list[dict[str, Any]] = [
        {"command_type": "assess", "data": {"condition_id": "cond-1", "background": None}},
        {"command_type": "plan", "data": {"narrative": "Start naproxen"}},
        # Defensive: malformed proposal must not crash the loop.
        {"command_type": "assess", "data": None},
    ]
    fake_note = MagicMock()
    fake_note.id = "note-uuid-1"
    with (
        patch("hyperscribe.scribe.commands.builder.Note.objects") as mock_note_qs,
        patch("hyperscribe.scribe.commands.builder.carry_forward_assess_background") as mock_carry,
    ):
        mock_note_qs.select_related.return_value.get.return_value = fake_note
        prefill_assess_backgrounds(proposals, "note-uuid-1")
    # Only one valid assess proposal (the one with a dict ``data``) is delegated.
    mock_carry.assert_called_once_with(proposals[0]["data"], fake_note)


def test_prefill_assess_backgrounds_silent_on_malformed_note_uuid() -> None:
    """A non-UUID ``note_uuid`` must NOT raise — the carry-forward is
    best-effort and a malformed identifier should silently skip the
    convenience, not blow up the calling endpoint.

    Django raises ``ValueError`` (not ``Note.DoesNotExist``) for a malformed
    UUID before reaching the SQL layer; both must be swallowed.
    """
    proposals: list[dict[str, Any]] = [
        {"command_type": "assess", "data": {"condition_id": "cond-1", "background": None}},
    ]
    with (
        patch("hyperscribe.scribe.commands.builder.Note.objects") as mock_note_qs,
        patch("hyperscribe.scribe.commands.builder.carry_forward_assess_background") as mock_carry,
    ):
        mock_note_qs.select_related.return_value.get.side_effect = ValueError(
            "badly formed hexadecimal UUID string",
        )
        # Must not raise.
        prefill_assess_backgrounds(proposals, "not-a-uuid")
    mock_carry.assert_not_called()
    # The background on the proposal is left untouched.
    assert proposals[0]["data"]["background"] is None


def test_prefill_assess_backgrounds_no_assess_proposals_short_circuits() -> None:
    """If there are no assess proposals, skip the Note lookup entirely.

    This is an N+1 / latency guard: a request with only non-assess commands
    should not pay for the ``Note.objects.select_related("patient").get(...)``
    query.
    """
    proposals: list[dict[str, Any]] = [
        {"command_type": "plan", "data": {"narrative": "Start naproxen"}},
    ]
    with patch("hyperscribe.scribe.commands.builder.Note.objects") as mock_note_qs:
        prefill_assess_backgrounds(proposals, "note-uuid-1")
    mock_note_qs.select_related.assert_not_called()


def test_build_effects_no_longer_calls_prefill_assess_backgrounds() -> None:
    """``build_effects`` is symmetric with ``annotate_duplicates`` — both
    are called by ``session_view`` at the same layer, NOT from inside
    ``build_effects``. This test pins that placement so a future refactor
    can't silently re-hide the carry-forward inside ``build_effects``.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "assess",
            "data": {
                "condition_id": "cond-uuid-abc",
                "narrative": "Stable today",
                "background": "Provider-typed",
            },
        },
    ]
    with (
        patch("hyperscribe.scribe.commands.builder.prefill_assess_backgrounds") as mock_prefill,
        patch("hyperscribe.scribe.commands.assess.AssessCommand") as mock_assess,
    ):
        inst = MagicMock()
        inst.originate.return_value = "assess_originate"
        inst.commit.return_value = "assess_commit"
        inst.command_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        inst.note_uuid = "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
        mock_assess.return_value = inst

        build_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

        # Symmetry guard: ``build_effects`` does not call the carry-forward.
        # The caller (session_view) is responsible.
        mock_prefill.assert_not_called()


def test_build_effects_medication_with_alert_facility_emits_yes_inline() -> None:
    """Flag on + alert_facility True: originate, UPSERT_COMMAND_METADATA="Yes" inline, commit.

    Pins the exact protobuf payload so any SDK schema change for
    UPSERT_COMMAND_METADATA breaks CI rather than silently diverging.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "medication_statement",
            "data": {"medication_text": "Lisinopril 10mg", "alert_facility": True},
        },
    ]
    with patch("hyperscribe.scribe.commands.medication_statement.MedicationStatementCommand") as mock_med:
        inst = MagicMock()
        inst.originate.return_value = "med_originate"
        inst.commit.return_value = "med_commit"
        inst.command_uuid = "d6a96b19-a087-458a-9619-b46537a8c121"
        inst.note_uuid = "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
        inst.Meta.key = "medicationStatement"
        mock_med.return_value = inst

        effects, metadata_pending, attempted, build_errors = build_effects(
            proposals,
            "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
            feature_flags={"AlertFacilityEnabled": True},
        )

    assert len(effects) == 3
    assert effects[0] == "med_originate"
    assert effects[2] == "med_commit"
    meta_effect = effects[1]
    assert EffectType.Name(meta_effect.type) == "UPSERT_COMMAND_METADATA"
    assert json.loads(meta_effect.payload) == {
        "data": {
            "schema_key": "medicationStatement",
            "command_id": "d6a96b19-a087-458a-9619-b46537a8c121",
            "key": "alert_facility",
            "value": "Yes",
        },
    }
    assert metadata_pending == []
    assert len(attempted) == 1
    assert attempted[0]["command_type"] == "medication_statement"


def test_build_effects_medication_alert_facility_false_writes_no_inline() -> None:
    """Flag on + alert_facility falsy: still emits inline metadata, value="No"."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "medication_statement",
            "data": {"medication_text": "Lisinopril 10mg"},
        },
    ]
    with patch("hyperscribe.scribe.commands.medication_statement.MedicationStatementCommand") as mock_med:
        inst = MagicMock()
        inst.originate.return_value = "med_originate"
        inst.commit.return_value = "med_commit"
        inst.command_uuid = "d6a96b19-a087-458a-9619-b46537a8c121"
        inst.note_uuid = "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
        inst.Meta.key = "medicationStatement"
        mock_med.return_value = inst

        effects, metadata_pending, attempted, build_errors = build_effects(
            proposals,
            "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
            feature_flags={"AlertFacilityEnabled": True},
        )

    assert len(effects) == 3
    assert json.loads(effects[1].payload)["data"]["value"] == "No"
    assert metadata_pending == []


def test_build_effects_medication_alert_facility_flag_off_no_metadata() -> None:
    """Flag off: no metadata effect emitted, just originate + commit."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "medication_statement",
            "data": {"medication_text": "Lisinopril 10mg", "alert_facility": True},
        },
    ]
    with patch("hyperscribe.scribe.commands.medication_statement.MedicationStatementCommand") as mock_med:
        inst = MagicMock()
        inst.originate.return_value = "med_originate"
        inst.commit.return_value = "med_commit"
        inst.command_uuid = "d6a96b19-a087-458a-9619-b46537a8c121"
        inst.note_uuid = "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
        mock_med.return_value = inst

        effects, metadata_pending, attempted, build_errors = build_effects(
            proposals,
            "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
            feature_flags={"AlertFacilityEnabled": False},
        )

    assert len(effects) == 2
    assert effects == ["med_originate", "med_commit"]
    assert metadata_pending == []


def test_build_metadata_effects() -> None:
    """Phase 2 builds upsert_metadata effects from pending items."""
    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "d6a96b19-a087-458a-9619-b46537a8c121",
            "command_type": "medication_statement",
            "note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
            "metadata": {"alert_facility": "true"},
        },
    ]
    stub = MagicMock()
    stub.upsert_metadata.return_value = "upsert_effect"
    with patch.object(_BUILDERS["medication_statement"], "build_stub", return_value=stub):
        effects = build_metadata_effects(pending)

    assert len(effects) == 1
    assert effects[0] == "upsert_effect"
    stub.upsert_metadata.assert_called_once_with("alert_facility", "true")


def test_build_metadata_effects_empty() -> None:
    """Empty pending list returns no effects."""
    effects = build_metadata_effects([])
    assert effects == []


def test_build_metadata_effects_unknown_type() -> None:
    """Unknown command type in pending is skipped."""
    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "command_type": "nonexistent_type",
            "note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
            "metadata": {"key": "val"},
        },
    ]
    effects = build_metadata_effects(pending)
    assert effects == []


def test_validate_proposals_all_valid() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "diagnose", "data": {"today_assessment": "Short text"}, "display": "Migraine"},
        {"command_type": "assess", "data": {"narrative": "Brief"}, "display": "HTN"},
        {"command_type": "prescribe", "data": {"sig": "Take daily"}, "display": "Lisinopril"},
    ]
    assert validate_proposals(proposals) == []


def test_validate_proposals_diagnose_over_limit() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "diagnose", "data": {"today_assessment": "x" * 2049}, "display": "Migraine"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert errors[0]["command_type"] == "diagnose"
    assert errors[0]["display"] == "Migraine"
    assert "2048" in errors[0]["errors"][0]


def test_validate_proposals_assess_over_limit() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "assess", "data": {"narrative": "x" * 2049}, "display": "HTN"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert errors[0]["command_type"] == "assess"


def test_validate_proposals_prescription_sig_over_limit() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "prescribe", "data": {"sig": "x" * 1001}, "display": "Lisinopril"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert "Sig" in errors[0]["errors"][0]


def test_validate_proposals_prescription_note_to_pharmacist_over_limit() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "prescribe", "data": {"sig": "ok", "note_to_pharmacist": "x" * 1025}, "display": "Lisinopril"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert "pharmacist" in errors[0]["errors"][0].lower()


def test_validate_proposals_multiple_failures() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "diagnose", "data": {"today_assessment": "x" * 2049}, "display": "Migraine"},
        {"command_type": "prescribe", "data": {"sig": "x" * 1001, "note_to_pharmacist": "x" * 1025}, "display": "Rx"},
        {"command_type": "allergy", "data": {"reaction": "x" * 513}, "display": "Penicillin"},
        {"command_type": "lab_order", "data": {"comment": "x" * 129}, "display": "CBC"},
        {
            "command_type": "imaging_order",
            "data": {"additional_details": "x" * 1025, "comment": "x" * 1025},
            "display": "MRI",
        },
        {"command_type": "stop_medication", "data": {"rationale": "x" * 1025}, "display": "Stop med"},
        {"command_type": "refer", "data": {}, "display": "Cardiology"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 7
    # Prescription has 2 errors (sig + note_to_pharmacist)
    rx_errors = next(e for e in errors if e["command_type"] == "prescribe")
    assert len(rx_errors["errors"]) == 2
    # Imaging has 4 errors (ordering provider + indications + details + comment)
    img_errors = next(e for e in errors if e["command_type"] == "imaging_order")
    assert len(img_errors["errors"]) == 4
    # Refer has 2 errors (notes_to_specialist + indications)
    refer_errors = next(e for e in errors if e["command_type"] == "refer")
    assert len(refer_errors["errors"]) == 2


def test_validate_proposals_unknown_type_skipped() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "unknown", "data": {"text": "x" * 99999}, "display": "???"},
    ]
    assert validate_proposals(proposals) == []


def test_validate_imaging_order_missing_provider_and_indications() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "imaging_order", "data": {"comment": "MRI"}, "display": "MRI Brain"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert len(errors[0]["errors"]) == 2
    error_text = " ".join(errors[0]["errors"])
    assert "Ordering provider" in error_text
    assert "indication" in error_text.lower()


def test_validate_imaging_order_with_required_fields() -> None:
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "imaging_order",
            "data": {"ordering_provider_id": "staff-uuid", "diagnosis_codes": ["J06.9"]},
            "display": "MRI",
        },
    ]
    assert validate_proposals(proposals) == []


def test_validate_refer_missing_notes_and_indications() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "refer", "data": {"service_provider": {"first_name": "Dr"}}, "display": "Cardiology"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert len(errors[0]["errors"]) == 2
    error_text = " ".join(errors[0]["errors"])
    assert "Notes to specialist" in error_text
    assert "indication" in error_text.lower()


def test_validate_refer_with_required_fields() -> None:
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "refer",
            "data": {"notes_to_specialist": "Evaluate murmur", "diagnosis_codes": ["I10"]},
            "display": "Cardiology",
        },
    ]
    assert validate_proposals(proposals) == []


def test_validate_proposals_refill_and_adjust() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "refill", "data": {"sig": "x" * 1001}, "display": "Refill"},
        {"command_type": "adjust_prescription", "data": {"sig": "x" * 1001}, "display": "Adjust"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 2


def test_build_effects_vitals_out_of_range_returns_build_error() -> None:
    """Pydantic ValidationError from the SDK is caught and surfaced as a structured per-command error.

    Regression for KOALA-5476: previously, a single out-of-range vital made the entire
    insert-commands batch crash with a generic 500.

    Per UAT feedback on PR #273, the error message must be a concise plain-English
    sentence (no raw input dump, no Pydantic-internal phrasing). The display label
    is set to the friendly command name ("Vitals") so the rendered output reads
    "Vitals: pulse must be greater than or equal to 30 (currently 8)".
    """
    proposals: list[dict[str, Any]] = [
        {"command_type": "vitals", "data": {"pulse": 8}, "display": "HR 8"},
    ]
    effects, metadata_pending, attempted, build_errors = build_effects(proposals, "note-uuid")
    assert effects == []
    assert metadata_pending == []
    assert attempted == []
    assert len(build_errors) == 1
    err = build_errors[0]
    assert err["command_type"] == "vitals"
    assert err["display"] == "Vitals"
    assert err["errors"] == ["pulse must be greater than or equal to 30 (currently 8)"]


def test_build_effects_vitals_too_low_message_format() -> None:
    """A too-low vital value renders as ``<field> must be greater than or equal to <min> (currently <value>)``."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"blood_pressure_systole": 5},
            "display": "BP 5/?",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    assert build_errors[0]["display"] == "Vitals"
    assert build_errors[0]["errors"] == [
        "blood_pressure_systole must be greater than or equal to 30 (currently 5)",
    ]


def test_build_effects_vitals_too_high_message_format() -> None:
    """A too-high vital value renders as ``<field> must be less than or equal to <max> (currently <value>)``."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"blood_pressure_systole": 999},
            "display": "BP 999/?",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    assert build_errors[0]["display"] == "Vitals"
    assert build_errors[0]["errors"] == [
        "blood_pressure_systole must be less than or equal to 305 (currently 999)",
    ]


def test_build_effects_vitals_multiple_invalid_fields_each_render_one_line() -> None:
    """When multiple vital fields fail validation, each error renders on its own line.

    Mirrors what the UI does (one ``<li>`` per error). The display label stays "Vitals";
    each error is the field-specific sentence with no raw input dictionary in it.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"blood_pressure_systole": 5, "pulse": 8},
            "display": "BP 5/?, HR 8",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    err = build_errors[0]
    assert err["display"] == "Vitals"
    assert set(err["errors"]) == {
        "blood_pressure_systole must be greater than or equal to 30 (currently 5)",
        "pulse must be greater than or equal to 30 (currently 8)",
    }
    # No raw input dictionary or Pydantic-internal phrasing leaks into the message.
    for msg in err["errors"]:
        assert "Input should be" not in msg
        assert "(got " not in msg


def test_build_effects_vitals_string_too_long_does_not_leak_input() -> None:
    """For string-length violations, the message names the field and limit but never includes
    the raw input string (which could carry free-text PHI in the note field)."""
    long_note = "x" * 200
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"pulse": 80, "note": long_note},
            "display": "HR 80, long note",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    err = build_errors[0]
    assert err["display"] == "Vitals"
    assert err["errors"] == ["note must be at most 150 characters"]
    for msg in err["errors"]:
        assert long_note not in msg


def test_build_effects_one_invalid_does_not_block_others() -> None:
    """A bad vitals proposal does not prevent other commands from being originated."""
    proposals: list[dict[str, Any]] = [
        {"command_type": "vitals", "data": {"pulse": 8}, "display": "HR 8"},
        {"command_type": "rfv", "data": {"comment": "Headache"}, "display": "Headache"},
    ]
    with patch("hyperscribe.scribe.commands.rfv.ReasonForVisitCommand") as mock_rfv:
        inst = MagicMock()
        inst.originate.return_value = "rfv_originate"
        inst.commit.return_value = "rfv_commit"
        inst.command_uuid = "rfv-uuid"
        mock_rfv.return_value = inst
        effects, metadata_pending, attempted, build_errors = build_effects(proposals, "note-uuid")
    assert effects == ["rfv_originate", "rfv_commit"]
    assert len(attempted) == 1
    assert attempted[0]["command_type"] == "rfv"
    assert len(build_errors) == 1
    assert build_errors[0]["command_type"] == "vitals"


def test_build_effects_vitals_invalid_enum_returns_build_error() -> None:
    """ValueError raised by enum coercion in build() is also caught and surfaced.

    The display label uses the friendly command name ("Vitals"), matching the
    ValidationError branch — the LLM-supplied ``display`` field is untrusted
    free text and must not leak into the response payload.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"blood_pressure_position_and_site": 999},
            "display": "BP bad site",
        },
    ]
    effects, metadata_pending, attempted, build_errors = build_effects(proposals, "note-uuid")
    assert effects == []
    assert attempted == []
    assert len(build_errors) == 1
    assert build_errors[0]["command_type"] == "vitals"
    assert build_errors[0]["display"] == "Vitals"


def test_build_effects_vitals_int_type_does_not_leak_input() -> None:
    """A non-numeric pulse hits the ``else:`` fallback in ``_format_pydantic_errors``.

    The fallback path historically echoed ``input_value`` verbatim into the rendered
    message, which would leak any LLM-supplied free text (potentially PHI) into both
    the HTTP response and the persisted ``VALIDATION_FAILED`` audit log.

    The PHI marker MUST NOT appear anywhere in the rendered error string.
    """
    phi_marker = "PHI_PLACEHOLDER_xyz"
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"pulse": phi_marker},
            "display": "HR free text",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    assert len(build_errors) == 1
    assert build_errors[0]["command_type"] == "vitals"
    assert build_errors[0]["display"] == "Vitals"
    rendered = " ".join(build_errors[0]["errors"])
    assert phi_marker not in rendered, f"PHI marker leaked into error message: {rendered!r}"


def test_build_effects_vitals_enum_value_error_does_not_leak_input() -> None:
    """An invalid ``blood_pressure_position_and_site`` raises ``ValueError`` from enum
    coercion in ``VitalsParser.build`` (the parser's ``validate`` does not guard the
    enum domain, see commands/base.py:44). The legacy implementation used
    ``str(exc)`` in the ``except ValueError`` branch, which echoes the raw input
    value verbatim into the message.

    Critical leak sink: ``session_view.py`` writes ``build_errors`` to
    ``audit_event("VALIDATION_FAILED", source="build")``, so any echoed PHI is
    persisted to audit logs — a direct HIPAA violation.

    The PHI marker MUST NOT appear anywhere in the rendered error string.
    """
    phi_marker = "PHI_PLACEHOLDER_abc"
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"blood_pressure_position_and_site": phi_marker},
            "display": "BP free text",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    assert len(build_errors) == 1
    assert build_errors[0]["command_type"] == "vitals"
    assert build_errors[0]["display"] == "Vitals"
    rendered = " ".join(build_errors[0]["errors"])
    assert phi_marker not in rendered, f"PHI marker leaked into error message: {rendered!r}"


def test_value_error_branch_message_preserves_field_name() -> None:
    """The ``except ValueError`` branch must surface the failing field name (``loc``)
    so the clinician knows *which* field is wrong and can re-prompt / correct it.

    Paired contract with ``test_build_effects_vitals_enum_value_error_does_not_leak_input``:
    that test guards against echoing the *raw input* (PHI leak); this test guards against
    over-sanitizing into a generic message that loses the field name (a UX regression).
    Together they pin both directions: field name in, raw input out.

    The field name is developer-defined (``blood_pressure_position_and_site``), not
    user/LLM input, so PHI-safe. See the loc-invariant comment in builder.py.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"blood_pressure_position_and_site": "sitting-and-on-the-left-wrist"},
            "display": "BP bad site",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    assert len(build_errors) == 1
    rendered = " ".join(build_errors[0]["errors"])
    assert "blood_pressure_position_and_site" in rendered, (
        f"Field name missing from rendered ValueError-branch message: {rendered!r}. "
        "Clinician must see which field is wrong; a generic 'invalid value' is unactionable."
    )


# Pydantic v2 type-string contract: each row is (type_string, model_factory, bad_input,
# friendly_substring). The point of this parametrized test is to catch the day Pydantic
# renames any of these type strings — the current implementation matches them by string
# in an if/elif chain, and a silent rename would degrade every match into the ``else:``
# fallback (PHI-leak branch). This test fails loudly instead.
@pytest.mark.parametrize(
    ("type_string", "model_factory", "bad_input", "friendly_substring"),
    [
        (
            "greater_than_equal",
            lambda: _make_constrained_int_model(ge=10),
            5,
            "greater than or equal to 10",
        ),
        (
            "less_than_equal",
            lambda: _make_constrained_int_model(le=100),
            200,
            "less than or equal to 100",
        ),
        (
            "greater_than",
            lambda: _make_constrained_int_model(gt=0),
            -1,
            "greater than 0",
        ),
        (
            "less_than",
            lambda: _make_constrained_int_model(lt=100),
            200,
            "less than 100",
        ),
        (
            "string_too_long",
            lambda: _make_constrained_str_model(max_length=5),
            "x" * 10,
            "at most 5 characters",
        ),
        (
            "string_too_short",
            lambda: _make_constrained_str_model(min_length=5),
            "ab",
            "at least 5 characters",
        ),
        (
            "missing",
            lambda: _make_required_field_model(),
            None,  # sentinel - factory triggers a missing-field error itself
            "is required",
        ),
    ],
)
def test_format_pydantic_errors_recognized_type_strings_take_friendly_path(
    type_string: str,
    model_factory: Any,
    bad_input: Any,
    friendly_substring: str,
) -> None:
    """Each Pydantic v2 type string in the if/elif chain must produce its friendly
    rendering — never the ``else:`` fallback (which is the PHI-leak branch).

    Mechanism: construct a real Pydantic v2 BaseModel with the matching constraint,
    instantiate with bad input, catch the real ValidationError, run it through
    ``_format_pydantic_errors``, then assert (a) the resulting message contains the
    friendly substring and (b) the canonical "Input should be" / "(got " Pydantic
    phrasing is absent — which is how the fallback branch renders.
    """
    model = model_factory()
    try:
        if type_string == "missing":
            model()  # type: ignore[call-arg]
        else:
            model(value=bad_input)
    except ValidationError as exc:
        # First confirm Pydantic still emits this exact type string. If this assertion
        # fails, Pydantic renamed the type and the if/elif chain in builder.py is now
        # silently degrading into the fallback.
        emitted_types = [err.get("type") for err in exc.errors()]
        assert type_string in emitted_types, (
            f"Pydantic emitted {emitted_types!r}, expected {type_string!r}. "
            "The if/elif chain in _format_pydantic_errors will now fall through "
            "to the PHI-leak fallback for this constraint."
        )
        messages = _format_pydantic_errors(exc)
    else:
        raise AssertionError("Expected ValidationError but none was raised")

    rendered = " ".join(messages)
    assert friendly_substring in rendered, (
        f"Friendly substring {friendly_substring!r} missing from rendered "
        f"messages {messages!r} - likely fell through to the fallback branch."
    )
    # The fallback formats as "<loc>: <msg> (currently <input>)" where <msg> is
    # Pydantic's "Input should be ..." phrasing. None of those markers should appear.
    assert "Input should be" not in rendered
    assert "(got " not in rendered


# ----------------------------------------------------------------------
# Amendment edit path (KOALA-5485): editing already-documented commands
# in the seven sections Alexia listed (plus chart_review by default).
#
# Two routes:
#   - direct edit (RFV/chief_complaint only): single EDIT effect; uuid stays
#   - void+recreate (everything else): EnterInError(old) + Originate(new)
#     + Commit(new); uuid changes
#
# The direct-edit route exists because home-app does NOT wire either
# COMMIT_REASON_FOR_VISIT_COMMAND nor ENTER_IN_ERROR_REASON_FOR_VISIT_COMMAND
# (plugin_io/interpreters/commands/__init__.py:395 and absent EIE entry).
# Routing RFV through ENTER_IN_ERROR would be a silent no-op and corrupt
# data. RFV always stays staged, so EDIT_REASON_FOR_VISIT_COMMAND works
# directly.
# ----------------------------------------------------------------------


def test_build_amend_edit_effects_rfv_emits_edit_only_no_enter_in_error() -> None:
    """Critical regression: amending chief_complaint MUST NOT emit ENTER_IN_ERROR.

    RFV does not have a wired ENTER_IN_ERROR interpreter in home-app, so
    routing it through void+recreate would silently no-op and corrupt the
    plugin's local state. Direct EDIT keeps the same command_uuid and works
    because RFV is never committed (no COMMIT handler either).
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "rfv",
            "command_uuid": "old-rfv-uuid-aaaa-bbbb-cccccccccccc",
            "section_key": "chief_complaint",
            "data": {"comment": "Updated chief complaint text"},
            "display": "Updated chief complaint text",
        },
    ]
    with patch("hyperscribe.scribe.commands.rfv.ReasonForVisitCommand") as mock_rfv:
        inst = MagicMock()
        inst.edit.return_value = "rfv_edit_effect"
        inst.command_uuid = "old-rfv-uuid-aaaa-bbbb-cccccccccccc"
        inst.note_uuid = "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
        mock_rfv.return_value = inst

        effects, attempted = build_amend_edit_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    # Must be exactly one EDIT effect, no originate/commit/enter-in-error.
    assert effects == ["rfv_edit_effect"]
    inst.edit.assert_called_once_with()
    inst.enter_in_error.assert_not_called()
    inst.originate.assert_not_called()
    inst.commit.assert_not_called()

    # Attempted entry pins the audit-log fields the API layer surfaces.
    assert len(attempted) == 1
    assert attempted[0]["section_key"] == "chief_complaint"
    assert attempted[0]["command_type"] == "rfv"
    assert attempted[0]["mode"] == "direct_edit"
    assert attempted[0]["old_command_uuid"] == "old-rfv-uuid-aaaa-bbbb-cccccccccccc"
    # For direct edit the uuid does not change, so new == old.
    assert attempted[0]["new_command_uuid"] == "old-rfv-uuid-aaaa-bbbb-cccccccccccc"


def test_build_amend_edit_effects_rfv_command_built_with_existing_uuid() -> None:
    """The RFV command for direct EDIT must be built with the existing
    command_uuid, not a fresh one, so the EDIT effect targets the right row."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "rfv",
            "command_uuid": "the-existing-rfv-uuid-1234-5678-90ab-cdef",
            "section_key": "chief_complaint",
            "data": {"comment": "x"},
            "display": "x",
        },
    ]
    with patch("hyperscribe.scribe.commands.rfv.ReasonForVisitCommand") as mock_rfv:
        inst = MagicMock()
        inst.edit.return_value = "rfv_edit_effect"
        inst.command_uuid = "the-existing-rfv-uuid-1234-5678-90ab-cdef"
        mock_rfv.return_value = inst

        build_amend_edit_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    # The builder must reuse the existing command_uuid (third arg position),
    # not invent a new one.
    args, kwargs = mock_rfv.call_args
    assert kwargs.get("command_uuid") == "the-existing-rfv-uuid-1234-5678-90ab-cdef"


def test_build_amend_edit_effects_hpi_void_and_recreate() -> None:
    """HPI in amendment mode emits EnterInError(old) + Originate(new) + Commit(new).

    The new command_uuid is freshly minted by the builder and surfaced via
    the attempted entry so the frontend can re-stamp ScribeSummary.commands.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "hpi",
            "command_uuid": "old-hpi-uuid-aaaa-bbbb-cccccccccccc",
            "section_key": "history_of_present_illness",
            "data": {"narrative": "Updated HPI narrative"},
            "display": "Updated HPI narrative",
        },
    ]
    minted_uuid = "fresh-hpi-uuid-1111-2222-3333-444444444444"
    with (
        patch("hyperscribe.scribe.commands.hpi.HistoryOfPresentIllnessCommand") as mock_hpi,
        patch("hyperscribe.scribe.commands.builder.uuid.uuid4", return_value=minted_uuid),
    ):
        # Two instances are created during this flow:
        #  - one for the OLD command (to call .enter_in_error())
        #  - one for the NEW command (to call .originate() and .commit())
        old_inst = MagicMock()
        old_inst.enter_in_error.return_value = "hpi_enter_in_error"
        old_inst.command_uuid = "old-hpi-uuid-aaaa-bbbb-cccccccccccc"
        new_inst = MagicMock()
        new_inst.originate.return_value = "hpi_originate"
        new_inst.commit.return_value = "hpi_commit"
        new_inst.command_uuid = minted_uuid
        mock_hpi.side_effect = [old_inst, new_inst]

        effects, attempted = build_amend_edit_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    # Order: enter_in_error first, then originate, then commit.
    assert effects == ["hpi_enter_in_error", "hpi_originate", "hpi_commit"]
    old_inst.enter_in_error.assert_called_once_with()
    new_inst.originate.assert_called_once()
    new_inst.commit.assert_called_once()
    # Direct-edit shortcut must NOT be taken for HPI.
    old_inst.edit.assert_not_called()
    new_inst.edit.assert_not_called()

    # The old command must be constructed with the OLD uuid (so the EIE
    # effect targets the right row), the new one with the freshly-minted
    # uuid (so originate creates a new row).
    construction_calls = mock_hpi.call_args_list
    assert len(construction_calls) == 2
    assert construction_calls[0].kwargs.get("command_uuid") == "old-hpi-uuid-aaaa-bbbb-cccccccccccc"
    assert construction_calls[1].kwargs.get("command_uuid") == minted_uuid

    assert len(attempted) == 1
    assert attempted[0]["section_key"] == "history_of_present_illness"
    assert attempted[0]["command_type"] == "hpi"
    assert attempted[0]["mode"] == "void_recreate"
    assert attempted[0]["old_command_uuid"] == "old-hpi-uuid-aaaa-bbbb-cccccccccccc"
    assert attempted[0]["new_command_uuid"] == minted_uuid


def test_build_amend_edit_effects_covers_all_void_recreate_sections() -> None:
    """All non-RFV editable sections route through EnterInError(old) +
    Originate(new), with an optional Commit(new) for dedicated-SDK-class
    sections. CustomCommand-routed sections (ros, history_review,
    chart_review, physical_exam, lab_results, imaging_results) skip the
    explicit commit because the SDK has no COMMIT_CUSTOM_COMMAND_COMMAND
    enum (.commit() raises ValueError) and home-app auto-commits after
    OriginateCustomCommand.
    """
    # (section_key, command_type, parser_module, command_class_name, data, expects_commit)
    cases: list[tuple[str, str, str, str, dict[str, Any], bool]] = [
        ("history_of_present_illness", "hpi", "hpi", "HistoryOfPresentIllnessCommand", {"narrative": "x"}, True),
        (
            "_ros",
            "ros",
            "ros",
            "CustomCommand",
            {"sections": [{"key": "general", "title": "General", "text": "WNL"}]},
            False,
        ),
        (
            "_history_review",
            "history_review",
            "history_review",
            "CustomCommand",
            {"sections": [{"key": "past_medical_history", "title": "PMH", "text": "HTN"}]},
            False,
        ),
        (
            "_chart_review",
            "chart_review",
            "chart_review",
            "CustomCommand",
            {"sections": [{"key": "allergies", "title": "Allergies", "text": "NKDA"}]},
            False,
        ),
        (
            "physical_exam",
            "physical_exam",
            "physical_exam",
            "CustomCommand",
            {"sections": [{"key": "general", "title": "General", "text": "WNL"}]},
            False,
        ),
        ("lab_results", "lab_results", "lab_results", "CustomCommand", {"narrative": "Labs reviewed"}, False),
        (
            "imaging_results",
            "imaging_results",
            "image_results",
            "CustomCommand",
            {"narrative": "Chest X-ray unremarkable"},
            False,
        ),
        (
            "current_medications",
            "medication_statement",
            "medication_statement",
            "MedicationStatementCommand",
            {"medication_text": "Lisinopril 10mg"},
            True,
        ),
    ]
    proposals: list[dict[str, Any]] = [
        {
            "command_type": ct,
            "command_uuid": f"old-{ct}-uuid",
            "section_key": sk,
            "data": data,
            "display": "x",
        }
        for sk, ct, _, _, data, _ in cases
    ]

    # Pre-mint a deterministic uuid per case so the test can assert the
    # exact new uuids that come back in `attempted`.
    minted_uuids = [f"minted-{ct}-uuid-1111-2222-3333-444444444444" for _, ct, _, _, _, _ in cases]

    patches = []
    instances: list[tuple[MagicMock, MagicMock, str, bool]] = []
    for case, minted in zip(cases, minted_uuids):
        sk, ct, mod, cls, _, expects_commit = case
        p = patch(f"hyperscribe.scribe.commands.{mod}.{cls}")
        m = p.start()
        old = MagicMock()
        old.enter_in_error.return_value = f"{ct}_eie"
        old.command_uuid = f"old-{ct}-uuid"
        new = MagicMock()
        new.originate.return_value = f"{ct}_originate"
        new.commit.return_value = f"{ct}_commit"
        new.command_uuid = minted
        m.side_effect = [old, new]
        patches.append(p)
        instances.append((old, new, ct, expects_commit))

    try:
        with (
            patch("hyperscribe.scribe.commands.history_review.render_to_string", return_value=""),
            patch("hyperscribe.scribe.commands.chart_review.render_to_string", return_value=""),
            patch("hyperscribe.scribe.commands.ros.render_to_string", return_value=""),
            patch("hyperscribe.scribe.commands.physical_exam.render_to_string", return_value=""),
            patch("hyperscribe.scribe.commands.builder.uuid.uuid4", side_effect=minted_uuids),
        ):
            effects, attempted = build_amend_edit_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")
    finally:
        for p in patches:
            p.stop()

    # Dedicated-class sections contribute 3 effects; CustomCommand sections contribute 2.
    expected_effect_count = sum(3 if ec else 2 for _, _, _, _, _, ec in cases)
    assert len(effects) == expected_effect_count
    # No direct edits anywhere. EIE + Originate always called; Commit only for dedicated classes.
    for old, new, ct, expects_commit in instances:
        old.edit.assert_not_called()
        new.edit.assert_not_called()
        old.enter_in_error.assert_called_once()
        new.originate.assert_called_once()
        if expects_commit:
            new.commit.assert_called_once()
        else:
            new.commit.assert_not_called()

    # Every attempted entry surfaces both uuids. Mode depends on routing.
    expected_pairs = {(sk, f"old-{ct}-uuid", minted) for (sk, ct, _, _, _, _), minted in zip(cases, minted_uuids)}
    actual_pairs = {(a["section_key"], a["old_command_uuid"], a["new_command_uuid"]) for a in attempted}
    assert actual_pairs == expected_pairs
    mode_by_section = {a["section_key"]: a["mode"] for a in attempted}
    for sk, _, _, _, _, expects_commit in cases:
        assert mode_by_section[sk] == ("void_recreate" if expects_commit else "void_recreate_custom")
    for entry in attempted:
        assert entry["old_command_uuid"] != entry["new_command_uuid"]


def test_build_amend_edit_effects_skips_disallowed_section() -> None:
    """Sections not in the editable allowlist are silently dropped.

    Defense in depth: even if the frontend sent a stale or hand-crafted
    payload pointing at, e.g., the recommendation/order buckets, the backend
    refuses to emit any effects rather than blindly trusting it.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "prescribe",
            "command_uuid": "rx-uuid",
            "section_key": "_recommended",  # NOT in EDITABLE_AMEND_SECTIONS
            "data": {"sig": "daily"},
            "display": "Lisinopril",
        },
        {
            "command_type": "questionnaire",
            "command_uuid": "q-uuid",
            "section_key": "_subjective_ad_hoc",  # NOT in EDITABLE_AMEND_SECTIONS
            "data": {"questionnaire_dbid": 42, "questions": []},
            "display": "PHQ-9",
        },
    ]
    effects, attempted = build_amend_edit_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")
    assert effects == []
    assert attempted == []


# ----------------------------------------------------------------------
# Routing tests for every command_type in _BUILDERS that is in the editable
# allowlist. One parametrized test per bucket so the mode/effect-shape
# assertions stay legible per command.
#
# Excluded by design (covered by `test_orders_remain_locked...` and
# `test_build_amend_edit_effects_section_remains_locked`):
#   * orders: prescribe, refill, adjust_prescription, refer, imaging_order, lab_order
#   * questionnaire (deferred - needs 4-effect amend route)
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "command_type,section_key,parser_module,sdk_class,data",
    [
        # Dedicated SDK class (full ORIGINATE+COMMIT+EIE interpreter wiring).
        # Each tuple covers a single representative section_key per command_type;
        # if multiple section_keys land on a command, the additional ones are
        # tested via `test_void_recreate_routing_per_section_key` below.
        ("vitals", "vitals", "vitals", "VitalsCommand", {"pulse": 72}),
        ("allergy", "allergies", "allergy", "AllergyCommand", {"allergy_text": "Penicillin"}),
        (
            "medication_statement",
            "_objective_ad_hoc",
            "medication_statement",
            "MedicationStatementCommand",
            {"medication_text": "Lisinopril 10mg"},
        ),
        (
            "stop_medication",
            "_objective_ad_hoc",
            "stop_medication",
            "StopMedicationCommand",
            {"medication_id": "med-1", "rationale": "side effect"},
        ),
        (
            "remove_allergy",
            "_objective_ad_hoc",
            "remove_allergy",
            "RemoveAllergyCommand",
            {"allergy_id": "all-1"},
        ),
        (
            "medicalHistory",
            "past_medical_history",
            "medical_history",
            "MedicalHistoryCommand",
            {"past_medical_history": "HTN"},
        ),
        (
            "surgicalHistory",
            "past_surgical_history",
            "surgical_history",
            "PastSurgicalHistoryCommand",
            {"procedure_display": "Appendectomy"},
        ),
        (
            "familyHistory",
            "family_history",
            "family_history",
            "FamilyHistoryCommand",
            {"condition_display": "CAD"},
        ),
        ("plan", "assessment_and_plan", "plan", "PlanCommand", {"narrative": "Continue plan"}),
        ("plan", "plan", "plan", "PlanCommand", {"narrative": "Plan body"}),
        ("plan", "_ad_hoc", "plan", "PlanCommand", {"narrative": "Ad-hoc plan"}),
        (
            "diagnose",
            "assessment_and_plan",
            "diagnose",
            "DiagnoseCommand",
            {"icd10_code": "G43.009", "today_assessment": "Migraine"},
        ),
        (
            "assess",
            "assessment_and_plan",
            "assess",
            "AssessCommand",
            {"condition_id": "cond-1", "narrative": "Stable"},
        ),
        (
            "resolve_condition",
            "_ad_hoc",
            "resolve_condition",
            "ResolveConditionCommand",
            {"condition_id": "cond-1"},
        ),
        (
            "task",
            "_ad_hoc",
            "task",
            "TaskCommand",
            {"title": "Follow up next week"},
        ),
        (
            "perform",
            "_charges_ad_hoc",
            "perform",
            "PerformCommand",
            {"cpt_code": "99213", "notes": ""},
        ),
        # Ad-hoc history rows (handleAddHistory ships section_key='_history_ad_hoc'
        # for any of the history command_types).
        (
            "medicalHistory",
            "_history_ad_hoc",
            "medical_history",
            "MedicalHistoryCommand",
            {"past_medical_history": "Asthma"},
        ),
    ],
)
def test_void_recreate_routing_per_section_key(
    command_type: str,
    section_key: str,
    parser_module: str,
    sdk_class: str,
    data: dict[str, Any],
) -> None:
    """Every void+recreate-bucketed (section_key, command_type) emits exactly
    EIE(old) + Originate(new) + Commit(new) with mode='void_recreate'.

    Pins each newly-classified command_type's routing into the default bucket
    (dedicated SDK class with full home-app interpreter wiring).
    """
    minted = "minted-uuid-1111-2222-3333-444444444444"
    proposals: list[dict[str, Any]] = [
        {
            "command_type": command_type,
            "command_uuid": "old-uuid-aaaa-bbbb-cccccccccccc",
            "section_key": section_key,
            "data": data,
            "display": "x",
        },
    ]
    with (
        patch(f"hyperscribe.scribe.commands.{parser_module}.{sdk_class}") as mock_cls,
        patch("hyperscribe.scribe.commands.builder.uuid.uuid4", return_value=minted),
    ):
        old_inst, new_inst = MagicMock(), MagicMock()
        old_inst.enter_in_error.return_value = f"{command_type}_eie"
        new_inst.originate.return_value = f"{command_type}_originate"
        new_inst.commit.return_value = f"{command_type}_commit"
        mock_cls.side_effect = [old_inst, new_inst]

        effects, attempted = build_amend_edit_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    assert effects == [
        f"{command_type}_eie",
        f"{command_type}_originate",
        f"{command_type}_commit",
    ]
    old_inst.enter_in_error.assert_called_once_with()
    new_inst.originate.assert_called_once()
    new_inst.commit.assert_called_once()
    # Direct-edit shortcut MUST NOT be used.
    old_inst.edit.assert_not_called()
    new_inst.edit.assert_not_called()

    assert len(attempted) == 1
    assert attempted[0]["section_key"] == section_key
    assert attempted[0]["command_type"] == command_type
    assert attempted[0]["mode"] == "void_recreate"
    assert attempted[0]["old_command_uuid"] == "old-uuid-aaaa-bbbb-cccccccccccc"
    assert attempted[0]["new_command_uuid"] == minted


def test_imaging_results_routes_through_custom_command_bucket() -> None:
    """imaging_results is the newly-added CustomCommand-routed section.

    Parser builds a ``CustomCommand(schema_key='imageResult')`` instance, so
    .commit() would raise ValueError. Amend route emits EIE+Originate only.
    """
    minted = "fresh-img-uuid-1111-2222-3333-444444444444"
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "imaging_results",
            "command_uuid": "old-img-uuid-aaaa-bbbb-cccccccccccc",
            "section_key": "imaging_results",
            "data": {"narrative": "Chest X-ray unremarkable"},
            "display": "Chest X-ray unremarkable",
        },
    ]
    with (
        patch("hyperscribe.scribe.commands.builder.uuid.uuid4", return_value=minted),
    ):
        effects, attempted = build_amend_edit_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    # CustomCommand path: real EIE + Originate emitted; no .commit() (would raise).
    assert len(effects) == 2
    assert EffectType.Name(effects[0].type) == "ENTER_IN_ERROR_CUSTOM_COMMAND_COMMAND"
    assert EffectType.Name(effects[1].type) == "ORIGINATE_CUSTOM_COMMAND_COMMAND"

    assert len(attempted) == 1
    assert attempted[0]["section_key"] == "imaging_results"
    assert attempted[0]["command_type"] == "imaging_results"
    assert attempted[0]["mode"] == "void_recreate_custom"
    assert attempted[0]["old_command_uuid"] == "old-img-uuid-aaaa-bbbb-cccccccccccc"
    assert attempted[0]["new_command_uuid"] == minted


@pytest.mark.parametrize(
    "section_key,command_type",
    [
        # Orders: clinical workflow side effects (pharmacy dispatch, lab tickets,
        # referral letters) make void+recreate unsafe. Explicitly excluded.
        ("prescription", "prescribe"),
        ("_recommended", "prescribe"),
        ("_recommended", "refill"),
        ("_recommended", "adjust_prescription"),
        ("_recommended", "refer"),
        ("_recommended", "imaging_order"),
        ("_recommended", "lab_order"),
        ("_ad_hoc", "prescribe"),
        # Questionnaire: insert flow is originate+edit+commit (the edit applies
        # responses). Amendment would need a 4-effect EIE+Originate+Edit+Commit
        # bucket that does not exist yet; deferred to a follow-up ticket.
        ("_subjective_ad_hoc", "questionnaire"),
        # Recommended bucket: recommendations get accepted and inserted, not
        # amended directly. Anything landing here at amend time is a
        # stale/hand-crafted payload.
        ("_recommended", "medication_statement"),
        ("_recommended", "allergy"),
        ("_recommended", "task"),
    ],
)
def test_build_amend_edit_effects_section_remains_locked(section_key: str, command_type: str) -> None:
    """Sections outside the editable allowlist stay locked.

    Covers two categories: (a) clinical orders whose downstream workflow
    side-effects make void+recreate unsafe, (b) command types deferred for
    structural reasons (questionnaire's 4-effect amend route), (c) the
    ``_recommended`` pseudo-section that recommendations carry before
    acceptance/insertion.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": command_type,
            "command_uuid": "some-uuid",
            "section_key": section_key,
            "data": {},
            "display": "x",
        },
    ]
    effects, attempted = build_amend_edit_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")
    assert effects == []
    assert attempted == []


@pytest.mark.parametrize(
    "command_type,section_key",
    [
        ("prescribe", "_ad_hoc"),
        ("refill", "_recommended"),
        ("adjust_prescription", "_recommended"),
        ("refer", "_recommended"),
        ("imaging_order", "_recommended"),
        ("lab_order", "_recommended"),
    ],
)
def test_orders_remain_locked_and_return_section_not_editable(command_type: str, section_key: str) -> None:
    """Pin: clinical orders (prescribe/refill/adjust_prescription/refer/
    imaging_order/lab_order) must NEVER be amendable, regardless of which
    section_key they land on.

    Orders trigger external action: pharmacy dispatch (prescribe family),
    specialist referral letters (refer), imaging-center scheduling
    (imaging_order), and lab-partner tickets (lab_order). Void+recreate in
    those flows would either re-fire external dispatch (if home-app is too
    permissive about replays) or strand the original in a half-cancelled
    state (if home-app rejects the EIE). The user product call: keep them
    locked and surface a separate "amend an order" workflow if needed.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": command_type,
            "command_uuid": "some-order-uuid",
            "section_key": section_key,
            "data": {},
            "display": "x",
        },
    ]
    effects, attempted = build_amend_edit_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")
    assert effects == []
    assert attempted == []


def test_build_amend_edit_effects_skips_missing_command_uuid() -> None:
    """Without an existing command_uuid we cannot target a row to edit/void.

    Dropping the proposal beats inventing a uuid and inserting a fresh
    command - that would re-introduce the double-insertion bug the
    amendment flow was specifically built to prevent.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "rfv",
            "section_key": "chief_complaint",
            "data": {"comment": "no uuid here"},
            "display": "x",
        },
    ]
    effects, attempted = build_amend_edit_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")
    assert effects == []
    assert attempted == []


def test_build_amend_edit_effects_empty_list() -> None:
    effects, attempted = build_amend_edit_effects([], "note-uuid")
    assert effects == []
    assert attempted == []


def test_editable_amend_sections_contains_expected_keys() -> None:
    """Pin the editable allowlist so accidental shrinks/expansions trip CI.

    Covers every ``_BUILDERS`` command_type except orders (prescribe, refill,
    adjust_prescription, refer, imaging_order, lab_order) and questionnaires
    (deferred: needs a 4-effect amend route).
    """
    assert EDITABLE_AMEND_SECTIONS == frozenset(
        {
            # DIRECT_EDIT
            "chief_complaint",
            # CUSTOM_COMMAND_ROUTED
            "_ros",
            "_history_review",
            "_chart_review",
            "physical_exam",
            "lab_results",
            "imaging_results",
            # VOID_RECREATE - SOAP-section-anchored
            "history_of_present_illness",
            "current_medications",
            "allergies",
            "vitals",
            "past_medical_history",
            "past_surgical_history",
            "family_history",
            "assessment_and_plan",
            "plan",
            # VOID_RECREATE - ad-hoc buckets
            "_ad_hoc",
            "_objective_ad_hoc",
            "_history_ad_hoc",
            "_charges_ad_hoc",
        }
    )


def test_every_builders_command_type_is_either_editable_or_explicitly_excluded() -> None:
    """Structural pin: every command_type in ``_BUILDERS`` must be accounted
    for at amendment time - either by appearing in at least one section_key
    that's amendable for that command_type, or by being explicitly listed in
    ``NON_EDITABLE_AMEND_COMMAND_TYPES``.

    This is the user's acceptance criterion: "every command in `_BUILDERS`
    is EITHER in the allowlist (correctly bucketed) OR explicitly excluded
    with rationale."

    Adding a new parser to ``_BUILDERS`` without a routing decision will
    fail this test, forcing the author to either (a) add it to the denylist
    with a clear "why this can't be amended" rationale, or (b) confirm it
    has a path through one of the amendable section_keys.
    """
    # Command types that can legitimately reach amendment via some section_key.
    # This list is the structural inverse of NON_EDITABLE_AMEND_COMMAND_TYPES.
    expected_editable_command_types = {
        "rfv",
        "hpi",
        "ros",
        "physical_exam",
        "history_review",
        "chart_review",
        "lab_results",
        "imaging_results",
        "medication_statement",
        "vitals",
        "allergy",
        "stop_medication",
        "remove_allergy",
        "medicalHistory",
        "surgicalHistory",
        "familyHistory",
        "plan",
        "diagnose",
        "assess",
        "resolve_condition",
        "task",
        "perform",
    }
    all_builders = set(_BUILDERS.keys())
    accounted_for = expected_editable_command_types | set(NON_EDITABLE_AMEND_COMMAND_TYPES)
    missing = all_builders - accounted_for
    assert not missing, (
        f"command_types in _BUILDERS are unaccounted for at amendment time: {missing}. "
        f"Add each to either the routing classification (allow amend) or to "
        f"NON_EDITABLE_AMEND_COMMAND_TYPES (deny amend, with rationale)."
    )
    extras = accounted_for - all_builders
    assert not extras, (
        f"command_types listed as editable/excluded that are not in _BUILDERS: {extras}. "
        f"Drop them from the routing classification."
    )


def test_non_editable_amend_command_types_contains_orders_and_questionnaire() -> None:
    """Pin the command-type denylist so accidentally dropping an order from
    it (which would re-fire pharmacy/lab/imaging-center dispatch on amend)
    or adding a non-order to it (silently breaking that feature) trips CI.

    Orders trigger external action; questionnaire needs a 4-effect amend
    route deferred to a follow-up ticket.
    """
    assert NON_EDITABLE_AMEND_COMMAND_TYPES == frozenset(
        {
            # Orders
            "prescribe",
            "refill",
            "adjust_prescription",
            "refer",
            "imaging_order",
            "lab_order",
            # Deferred
            "questionnaire",
        }
    )


def test_direct_edit_sections_only_contains_chief_complaint() -> None:
    """Pin the direct-edit set. Only chief_complaint (RFV) belongs here
    because RFV is the only section whose home-app interpreter handles
    EDIT but NOT ENTER_IN_ERROR. Adding any other section here would emit
    EDIT effects on a committed command, which EditCommandEffectInterpreter
    rejects with `Command must be staged in order to be edited.`"""
    assert DIRECT_EDIT_SECTIONS == frozenset({"chief_complaint"})


def test_custom_command_routed_sections_literal_pin() -> None:
    """Literal pin on the CustomCommand-routed set; the structural check is manual.

    These section_keys MUST match exactly the parsers whose ``build()`` returns
    a ``CustomCommand`` instance. A true introspection test would synthesize
    each parser's ``build(data, ...)`` and ``isinstance(..., CustomCommand)``
    against the actual return value - but there is no production
    ``section_key -> command_type`` mapping (the frontend ships both fields
    side-by-side), each parser's ``build`` takes parser-specific data shapes
    (HPI: ``{narrative}``, ROS: ``{sections}``, etc.), and some parsers call
    ``render_to_string`` at build time which would need mocking. Synthesizing
    that across 6+ parsers is its own moving target and would re-introduce
    the same single-sourcing problem this is meant to detect.

    Mismatch means either (a) a CustomCommand section is missing from the set
    and will crash with ValueError when build_amend_edit_effects emits
    ``.commit()``, or (b) a dedicated-SDK-class section is wrongly in the set
    and will silently skip its needed commit effect (home-app would never
    finalize the row). Reviewers: when adding to EDITABLE_AMEND_SECTIONS,
    cross-check the parser's ``build()`` return type and update this set
    accordingly.
    """
    assert CUSTOM_COMMAND_ROUTED_SECTIONS == frozenset(
        {
            "_ros",
            "_history_review",
            "_chart_review",
            "physical_exam",
            "lab_results",
            "imaging_results",
        }
    )


def test_custom_command_commit_raises_value_error_in_sdk() -> None:
    """SDK contract: ``CustomCommand.commit()`` raises ``ValueError`` because
    ``COMMIT_CUSTOM_COMMAND_COMMAND`` is not declared in the protobuf enum.

    This is the load-bearing reason the amend path for CustomCommand-routed
    sections (ros, physical_exam, chart_review, history_review, lab_results)
    skips the explicit commit effect. If a future SDK release adds the enum
    and changes this behavior, this test will fail loudly so build_amend_edit_effects
    can be revisited.

    No mocks: this asserts the real SDK behavior against the installed canvas
    package.
    """
    cmd = CustomCommand(
        schema_key="reviewOfSystems",
        content="dummy",
        note_uuid="5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
        command_uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    )
    # Originate works (the enum is defined).
    originate_effect = cmd.originate()
    assert EffectType.Name(originate_effect.type) == "ORIGINATE_CUSTOM_COMMAND_COMMAND"
    # EnterInError works (the enum is defined as of canvas>=0.155).
    eie_effect = cmd.enter_in_error()
    assert EffectType.Name(eie_effect.type) == "ENTER_IN_ERROR_CUSTOM_COMMAND_COMMAND"
    # Commit raises - this is the contract we depend on.
    with pytest.raises(ValueError, match=r'unknown enum label "COMMIT_CUSTOM_COMMAND_COMMAND"'):
        cmd.commit()
    # Edit also raises (same reason). Confirms why CustomCommand sections
    # can never use the DIRECT_EDIT path.
    with pytest.raises(ValueError, match=r'unknown enum label "EDIT_CUSTOM_COMMAND_COMMAND"'):
        cmd.edit()


def test_custom_command_amend_emits_eie_and_originate_only_no_commit() -> None:
    """Empirical: amending a CustomCommand-routed section (here: ros) emits
    EnterInError(old) + Originate(new) and stops there. No .commit() call -
    that would raise ValueError. Uses the real CustomCommand class, not a mock,
    to pin the integration with the SDK.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "ros",
            "command_uuid": "old-ros-uuid-aaaa-bbbb-cccccccccccc",
            "section_key": "_ros",
            "data": {"sections": [{"key": "general", "title": "General", "text": "WNL"}]},
            "display": "ROS updated",
        },
    ]
    minted = "fresh-ros-uuid-1111-2222-3333-444444444444"
    with (
        patch("hyperscribe.scribe.commands.ros.render_to_string", return_value="<p>WNL</p>"),
        patch("hyperscribe.scribe.commands.builder.uuid.uuid4", return_value=minted),
    ):
        effects, attempted = build_amend_edit_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    # Two effects only: EIE on the old row, Originate of the new row.
    assert len(effects) == 2
    assert EffectType.Name(effects[0].type) == "ENTER_IN_ERROR_CUSTOM_COMMAND_COMMAND"
    assert EffectType.Name(effects[1].type) == "ORIGINATE_CUSTOM_COMMAND_COMMAND"

    assert len(attempted) == 1
    assert attempted[0]["section_key"] == "_ros"
    assert attempted[0]["mode"] == "void_recreate_custom"
    assert attempted[0]["old_command_uuid"] == "old-ros-uuid-aaaa-bbbb-cccccccccccc"
    assert attempted[0]["new_command_uuid"] == minted


def test_build_amend_edit_effects_double_edit_same_row_uses_new_uuid() -> None:
    """In-session re-edit: provider amends HPI twice before saving. The
    second edit must target the new uuid produced by the first amend's
    re-stamp, not the original (now entered-in-error) uuid.

    This test simulates what the frontend does: after the first amend,
    `commands[i].command_uuid` is swapped from old -> new, and a second
    amend re-submits with the new uuid as `command_uuid`. We assert
    build_amend_edit_effects treats that as a fresh proposal and emits
    EIE(new) + Originate(newer) - i.e., it doesn't somehow remember the
    original uuid (which would emit an EIE on an already-voided row).
    """
    minted_first = "fresh-hpi-uuid-1111-2222-3333-444444444444"
    minted_second = "fresher-hpi-uuid-aaaa-bbbb-cccccccccccc"

    proposals_first: list[dict[str, Any]] = [
        {
            "command_type": "hpi",
            "command_uuid": "original-hpi-uuid-1234-5678-90ab-cdef",
            "section_key": "history_of_present_illness",
            "data": {"narrative": "First edit"},
            "display": "First edit",
        },
    ]
    with (
        patch("hyperscribe.scribe.commands.hpi.HistoryOfPresentIllnessCommand") as mock_hpi,
        patch("hyperscribe.scribe.commands.builder.uuid.uuid4", return_value=minted_first),
    ):
        old_inst, new_inst = MagicMock(), MagicMock()
        old_inst.enter_in_error.return_value = "hpi_eie_1"
        new_inst.originate.return_value = "hpi_originate_1"
        new_inst.commit.return_value = "hpi_commit_1"
        mock_hpi.side_effect = [old_inst, new_inst]
        effects_1, attempted_1 = build_amend_edit_effects(proposals_first, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")
    assert attempted_1[0]["old_command_uuid"] == "original-hpi-uuid-1234-5678-90ab-cdef"
    assert attempted_1[0]["new_command_uuid"] == minted_first

    # Frontend re-stamp: the second proposal carries the uuid from the first attempt.
    proposals_second: list[dict[str, Any]] = [
        {
            "command_type": "hpi",
            "command_uuid": minted_first,  # the new uuid from amend #1
            "section_key": "history_of_present_illness",
            "data": {"narrative": "Second edit"},
            "display": "Second edit",
        },
    ]
    with (
        patch("hyperscribe.scribe.commands.hpi.HistoryOfPresentIllnessCommand") as mock_hpi,
        patch("hyperscribe.scribe.commands.builder.uuid.uuid4", return_value=minted_second),
    ):
        old_inst2, new_inst2 = MagicMock(), MagicMock()
        old_inst2.enter_in_error.return_value = "hpi_eie_2"
        new_inst2.originate.return_value = "hpi_originate_2"
        new_inst2.commit.return_value = "hpi_commit_2"
        mock_hpi.side_effect = [old_inst2, new_inst2]
        effects_2, attempted_2 = build_amend_edit_effects(proposals_second, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")
    # Second amend's EIE must target minted_first (NOT the original uuid).
    # We verify via the constructor args.
    construction_calls = mock_hpi.call_args_list
    assert len(construction_calls) == 2
    assert construction_calls[0].kwargs.get("command_uuid") == minted_first, (
        "Second amend must EIE the FIRST amend's new uuid, not the original. "
        "Otherwise the second EIE lands on an already-voided row."
    )
    assert construction_calls[1].kwargs.get("command_uuid") == minted_second
    assert attempted_2[0]["old_command_uuid"] == minted_first
    assert attempted_2[0]["new_command_uuid"] == minted_second


# ----------------------------------------------------------------------
# Amendment delete path (KOALA-5485 regression)
#
# Charges (perform commands) are rendered as a checkbox list, not as
# editable ChargeRow widgets, so the only amend gesture available to the
# provider is "uncheck the box." Without a dedicated delete route, the
# uncheck silently no-ops: handleInsert filters the deselected command
# out of the insertable list, and because no actual edit happened, the
# `_amend_edited` tag is never set either, so the amend POST drops it
# too. The charge stays committed in the chart.
#
# build_amend_delete_effects emits ONLY EnterInError(old) for each valid
# perform proposal. Same eligibility filter as build_amend_edit_effects
# (section_key allowlist + command_type denylist + command_uuid present),
# same drop-and-WARN defense-in-depth. Display field is intentionally
# omitted from the attempted dict (HIPAA PHI guard).
# ----------------------------------------------------------------------


def test_build_amend_delete_effects_perform_emits_enter_in_error_only() -> None:
    """Critical regression: deleting an already-documented perform command MUST
    emit ENTER_IN_ERROR(old) only - no Originate, no Commit, no Edit. The user
    unchecked the charge in the amend-mode checklist; the chart row needs to
    be marked entered-in-error and nothing else.

    The attempted entry pins the audit-log shape the API layer surfaces, and
    must NOT carry a ``display`` field (HIPAA PHI guard - keep the audit
    payload to structural identifiers only).
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "perform",
            "command_uuid": "old-perform-uuid-aaaa-bbbb-cccccccccccc",
            "section_key": "_charges_ad_hoc",
            "data": {"cpt_code": "99213", "description": "Office visit"},
            "display": "99213 - Office visit",
        },
    ]
    with patch("hyperscribe.scribe.commands.perform.PerformCommand") as mock_perform:
        inst = MagicMock()
        inst.enter_in_error.return_value = "perform_eie_effect"
        inst.command_uuid = "old-perform-uuid-aaaa-bbbb-cccccccccccc"
        mock_perform.return_value = inst

        effects, attempted = build_amend_delete_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    assert effects == ["perform_eie_effect"]
    inst.enter_in_error.assert_called_once_with()
    inst.originate.assert_not_called()
    inst.commit.assert_not_called()
    inst.edit.assert_not_called()

    assert len(attempted) == 1
    entry = attempted[0]
    assert entry["section_key"] == "_charges_ad_hoc"
    assert entry["command_type"] == "perform"
    assert entry["command_uuid"] == "old-perform-uuid-aaaa-bbbb-cccccccccccc"
    assert entry["mode"] == "amend_delete"
    # HIPAA: display must NOT survive into the audit-feeding attempted record.
    # Mirrors the AMEND_EXISTING_COMMANDS PHI hardening - same audit log,
    # same PHI rules.
    assert "display" not in entry


def test_build_amend_delete_effects_built_with_existing_uuid() -> None:
    """The perform command for delete must be built with the existing
    command_uuid (so the EIE targets the right row), not a fresh one."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "perform",
            "command_uuid": "the-existing-perform-uuid-1234-5678-90ab-cdef",
            "section_key": "_charges_ad_hoc",
            "data": {"cpt_code": "99213", "description": "x"},
            "display": "x",
        },
    ]
    with patch("hyperscribe.scribe.commands.perform.PerformCommand") as mock_perform:
        inst = MagicMock()
        inst.enter_in_error.return_value = "perform_eie_effect"
        inst.command_uuid = "the-existing-perform-uuid-1234-5678-90ab-cdef"
        mock_perform.return_value = inst

        build_amend_delete_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    args, kwargs = mock_perform.call_args
    assert kwargs.get("command_uuid") == "the-existing-perform-uuid-1234-5678-90ab-cdef"


def test_build_amend_delete_effects_skips_missing_command_uuid() -> None:
    """Without an existing command_uuid we cannot target a row to void.

    Dropping the proposal is the safe default - same defense-in-depth as
    build_amend_edit_effects. A frontend that omits command_uuid is buggy
    or stale, not a user-visible condition.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "perform",
            "section_key": "_charges_ad_hoc",
            "data": {"cpt_code": "99213"},
            "display": "x",
        },
    ]
    effects, attempted = build_amend_delete_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")
    assert effects == []
    assert attempted == []


def test_build_amend_delete_effects_skips_disallowed_section() -> None:
    """Section keys outside EDITABLE_AMEND_SECTIONS are silently dropped. A
    frontend that ships a delete with section_key="_recommended" or
    "_subjective_ad_hoc" is buggy - WARN log catches it; no effects emitted.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "perform",
            "command_uuid": "perform-uuid",
            "section_key": "_recommended",
            "data": {"cpt_code": "99213"},
            "display": "x",
        },
    ]
    effects, attempted = build_amend_delete_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")
    assert effects == []
    assert attempted == []


def test_build_amend_delete_effects_skips_denied_command_type() -> None:
    """command_types in NON_EDITABLE_AMEND_COMMAND_TYPES (orders, questionnaire)
    are categorically denied regardless of section_key. A prescribe ad-hoc'd
    into _charges_ad_hoc (impossible via UI but defensible) must NOT be
    void-able via this route - cancel/resend is the right shape for orders.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "prescribe",
            "command_uuid": "rx-uuid",
            "section_key": "_charges_ad_hoc",
            "data": {},
            "display": "x",
        },
    ]
    effects, attempted = build_amend_delete_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")
    assert effects == []
    assert attempted == []


def test_build_amend_delete_effects_unknown_command_type_dropped() -> None:
    """Unknown command_type (no parser in _BUILDERS) is silently dropped."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "made_up_command",
            "command_uuid": "some-uuid",
            "section_key": "_charges_ad_hoc",
            "data": {},
            "display": "x",
        },
    ]
    effects, attempted = build_amend_delete_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")
    assert effects == []
    assert attempted == []


def test_build_amend_delete_effects_empty_list() -> None:
    """No proposals -> no effects, no attempted."""
    effects, attempted = build_amend_delete_effects([], "note-uuid")
    assert effects == []
    assert attempted == []


def test_build_amend_delete_effects_mixed_valid_and_dropped_batch() -> None:
    """A batch with one valid perform delete and one dropped (missing uuid)
    surfaces only the valid one - effect count and attempted count both match
    the count of valid proposals.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "perform",
            "command_uuid": "valid-uuid",
            "section_key": "_charges_ad_hoc",
            "data": {"cpt_code": "99213"},
            "display": "x",
        },
        {
            # Dropped: missing command_uuid
            "command_type": "perform",
            "section_key": "_charges_ad_hoc",
            "data": {"cpt_code": "99214"},
            "display": "x",
        },
        {
            # Dropped: section not editable
            "command_type": "perform",
            "command_uuid": "another-uuid",
            "section_key": "_recommended",
            "data": {"cpt_code": "99215"},
            "display": "x",
        },
    ]
    with patch("hyperscribe.scribe.commands.perform.PerformCommand") as mock_perform:
        inst = MagicMock()
        inst.enter_in_error.return_value = "perform_eie"
        inst.command_uuid = "valid-uuid"
        mock_perform.return_value = inst
        effects, attempted = build_amend_delete_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    assert effects == ["perform_eie"]
    assert len(attempted) == 1
    assert attempted[0]["command_uuid"] == "valid-uuid"
    assert attempted[0]["mode"] == "amend_delete"


def test_build_amend_delete_effects_supports_void_recreate_command_types() -> None:
    """Although the immediate driver is the perform-charge regression, the
    helper accepts any editable command_type. A non-perform command (e.g.,
    medical history) routed through delete also emits EIE only - the same
    eligibility filter applies.

    This keeps the route generic so a future "delete an already-documented
    vitals/medication/task" UX can reuse the same backend handler without
    growing a parallel codepath per command_type.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "medicalHistory",
            "command_uuid": "old-pmh-uuid",
            "section_key": "past_medical_history",
            "data": {"past_medical_history": "HTN"},
            "display": "x",
        },
    ]
    with patch("hyperscribe.scribe.commands.medical_history.MedicalHistoryCommand") as mock_pmh:
        inst = MagicMock()
        inst.enter_in_error.return_value = "pmh_eie"
        inst.command_uuid = "old-pmh-uuid"
        mock_pmh.return_value = inst
        effects, attempted = build_amend_delete_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    assert effects == ["pmh_eie"]
    inst.enter_in_error.assert_called_once_with()
    inst.originate.assert_not_called()
    inst.commit.assert_not_called()
    assert attempted[0]["mode"] == "amend_delete"
    assert "display" not in attempted[0]


def test_build_amend_delete_effects_emits_real_enter_in_error_perform_effect_type() -> None:
    """Empirical: deleting a perform command via build_amend_delete_effects
    emits a real ENTER_IN_ERROR_PERFORM_COMMAND protobuf effect.

    Without this test the delete branch could quietly swap to a different
    SDK call (e.g., .commit() on a CustomCommand-typed command) and the
    bug would only surface in UAT. Uses the real PerformCommand class, no
    mocks - pins the SDK integration. Mirrors
    ``test_custom_command_amend_emits_eie_and_originate_only_no_commit``
    which does the same for the edit path.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "perform",
            "command_uuid": "old-perform-uuid-aaaa-bbbb-cccccccccccc",
            "section_key": "_charges_ad_hoc",
            "data": {"cpt_code": "99213", "description": "Office visit"},
            "display": "99213 - Office visit",
        },
    ]
    effects, attempted = build_amend_delete_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    # One effect: EIE on the old perform row.
    assert len(effects) == 1
    assert EffectType.Name(effects[0].type) == "ENTER_IN_ERROR_PERFORM_COMMAND"

    assert len(attempted) == 1
    assert attempted[0]["section_key"] == "_charges_ad_hoc"
    assert attempted[0]["command_type"] == "perform"
    assert attempted[0]["mode"] == "amend_delete"
    assert attempted[0]["command_uuid"] == "old-perform-uuid-aaaa-bbbb-cccccccccccc"
    # No PHI in attempted.
    assert "display" not in attempted[0]
