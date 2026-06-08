from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hyperscribe.scribe.charges.enrichment import (
    _find_billing_line_item,
    _normalize_icd10,
    build_assessment_index,
)

# Charge command_uuids must be real UUIDs — _find_billing_line_item pre-validates
# the shape before the ORM lookup (a malformed value would 500 the request).
VALID_UUID = "11111111-1111-4111-8111-111111111111"
VALID_UUID_2 = "22222222-2222-4222-8222-222222222222"


def test_normalize_icd10_strips_dots_and_uppercases():
    assert _normalize_icd10("m25.511") == "M25511"
    assert _normalize_icd10(" K21.9 ") == "K219"
    assert _normalize_icd10("") == ""
    assert _normalize_icd10(None) == ""


def _assessment(assessment_id, codes):
    """A fake Assessment whose condition has the given coding codes."""
    condition = SimpleNamespace(
        codings=SimpleNamespace(all=lambda: [SimpleNamespace(code=c) for c in codes])
    )
    return SimpleNamespace(id=assessment_id, condition=condition)


@patch("hyperscribe.scribe.charges.enrichment.Assessment")
def test_build_assessment_index_maps_normalized_code_to_ids(mock_assessment):
    qs = MagicMock()
    qs.prefetch_related.return_value = [
        _assessment("aid-1", ["M25.511"]),
        _assessment("aid-2", ["K21.9"]),
    ]
    mock_assessment.objects.filter.return_value = qs

    note = SimpleNamespace(dbid=7)
    index = build_assessment_index(note)

    assert index["M25511"] == ["aid-1"]
    assert index["K219"] == ["aid-2"]
    mock_assessment.objects.filter.assert_called_once_with(
        note=note, entered_in_error_id__isnull=True, deleted=False
    )


@patch("hyperscribe.scribe.charges.enrichment.Assessment")
def test_build_assessment_index_skips_assessment_without_condition(mock_assessment):
    qs = MagicMock()
    qs.prefetch_related.return_value = [SimpleNamespace(id="aid-1", condition=None)]
    mock_assessment.objects.filter.return_value = qs

    index = build_assessment_index(SimpleNamespace(dbid=7))
    assert index == {}


@patch("hyperscribe.scribe.charges.enrichment.Assessment")
def test_build_assessment_index_collects_multiple_ids_for_duplicate_code(mock_assessment):
    qs = MagicMock()
    qs.prefetch_related.return_value = [
        _assessment("aid-1", ["E11.9"]),
        _assessment("aid-2", ["E11.9"]),
    ]
    mock_assessment.objects.filter.return_value = qs

    index = build_assessment_index(SimpleNamespace(dbid=7))
    assert index["E119"] == ["aid-1", "aid-2"]


from hyperscribe.scribe.charges.enrichment import (
    CPT_MODIFIER_SYSTEM,
    build_charge_enrichment_effects,
)


def _patch_note(mock_note, dbid=7):
    mock_note.objects.get.return_value = SimpleNamespace(dbid=dbid)


@patch("hyperscribe.scribe.charges.enrichment.UpdateBillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
@patch("hyperscribe.scribe.charges.enrichment.build_assessment_index")
@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_update_effect_built_for_charge_with_pointer_and_modifier(
    mock_note, mock_index, mock_command, mock_bli, mock_update
):
    from canvas_sdk.v1.data.billing import BillingLineItemStatus
    _patch_note(mock_note)
    mock_index.return_value = {"M25511": ["aid-1"]}
    mock_command.objects.get.return_value = SimpleNamespace(dbid=42)
    bli = SimpleNamespace(id="bli-1")
    bli_qs = MagicMock()
    bli_qs.first.return_value = bli
    mock_bli.objects.filter.return_value = bli_qs
    mock_update.return_value = SimpleNamespace(apply=lambda: "UPDATE_EFFECT")

    charges = [{
        "command_uuid": VALID_UUID,
        "diagnosis_pointers": [{"command_uuid": "d0", "icd10_code": "M25.511"}],
        "modifiers": ["25"],
    }]
    effects, enriched, errors = build_charge_enrichment_effects(charges, [], "note-uuid")

    assert effects == ["UPDATE_EFFECT"]
    assert errors == []
    assert enriched == [{"command_uuid": VALID_UUID, "billing_line_item_id": "bli-1",
                         "assessment_ids": ["aid-1"], "modifiers": ["25"]}]
    mock_update.assert_called_once_with(
        billing_line_item_id="bli-1",
        assessment_ids=["aid-1"],
        modifiers=[{"code": "25", "system": CPT_MODIFIER_SYSTEM}],
    )
    mock_bli.objects.filter.assert_called_once_with(
        note=mock_note.objects.get.return_value, command_id=42,
        status=BillingLineItemStatus.ACTIVE,
    )


@patch("hyperscribe.scribe.charges.enrichment.UpdateBillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
@patch("hyperscribe.scribe.charges.enrichment.build_assessment_index")
@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_missing_bli_records_error_and_no_effect(
    mock_note, mock_index, mock_command, mock_bli, mock_update
):
    _patch_note(mock_note)
    mock_index.return_value = {"M25511": ["aid-1"]}
    mock_command.objects.get.return_value = SimpleNamespace(dbid=42)
    bli_qs = MagicMock()
    bli_qs.first.return_value = None
    mock_bli.objects.filter.return_value = bli_qs

    charges = [{
        "command_uuid": VALID_UUID,
        "diagnosis_pointers": [{"command_uuid": "d0", "icd10_code": "M25.511"}],
        "modifiers": [],
    }]
    effects, enriched, errors = build_charge_enrichment_effects(charges, [], "note-uuid")

    assert effects == []
    assert enriched == []
    assert errors == [{"command_uuid": VALID_UUID, "reason": "billing_line_item_not_found"}]
    mock_update.assert_not_called()


@patch("hyperscribe.scribe.charges.enrichment.RemoveBillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
@patch("hyperscribe.scribe.charges.enrichment.build_assessment_index")
@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_removed_charge_emits_remove_effect(
    mock_note, mock_index, mock_command, mock_bli, mock_remove
):
    _patch_note(mock_note)
    mock_index.return_value = {}
    mock_command.objects.get.return_value = SimpleNamespace(dbid=99)
    bli = SimpleNamespace(id="bli-9")
    bli_qs = MagicMock()
    bli_qs.first.return_value = bli
    mock_bli.objects.filter.return_value = bli_qs
    mock_remove.return_value = SimpleNamespace(apply=lambda: "REMOVE_EFFECT")

    effects, enriched, errors = build_charge_enrichment_effects([], [VALID_UUID], "note-uuid")

    assert effects == ["REMOVE_EFFECT"]
    assert enriched == []
    assert errors == []
    mock_remove.assert_called_once_with(billing_line_item_id="bli-9")


@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_unknown_note_returns_error(mock_note):
    mock_note.DoesNotExist = Exception
    mock_note.objects.get.side_effect = mock_note.DoesNotExist
    effects, enriched, errors = build_charge_enrichment_effects([], [], "bad-uuid")
    assert effects == []
    assert enriched == []
    assert errors == [{"command_uuid": "", "reason": "note_not_found"}]


@patch("hyperscribe.scribe.charges.enrichment.UpdateBillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
@patch("hyperscribe.scribe.charges.enrichment.build_assessment_index")
@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_unresolvable_command_uuid_records_error(
    mock_note, mock_index, mock_command, mock_bli, mock_update
):
    _patch_note(mock_note)
    mock_index.return_value = {"M25511": ["aid-1"]}
    mock_command.DoesNotExist = Exception
    mock_command.objects.get.side_effect = mock_command.DoesNotExist

    charges = [{
        "command_uuid": VALID_UUID,
        "diagnosis_pointers": [{"command_uuid": "d0", "icd10_code": "M25.511"}],
        "modifiers": [],
    }]
    effects, enriched, errors = build_charge_enrichment_effects(charges, [], "note-uuid")
    assert effects == []
    assert errors == [{"command_uuid": VALID_UUID, "reason": "billing_line_item_not_found"}]
    mock_update.assert_not_called()


@patch("hyperscribe.scribe.charges.enrichment.UpdateBillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
@patch("hyperscribe.scribe.charges.enrichment.build_assessment_index")
@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_empty_pointers_clears_bli_without_error(
    mock_note, mock_index, mock_command, mock_bli, mock_update
):
    """When diagnosis_pointers is empty the backend emits an explicit
    UpdateBillingLineItem(assessment_ids=[]) clear — covers advisory-only new
    charges (no-op, BLI was already empty) and amendment unlink-all (clears old
    links). No no_assessment_resolved error should be produced."""
    _patch_note(mock_note)
    mock_index.return_value = {}
    mock_command.objects.get.return_value = SimpleNamespace(dbid=42)
    bli = SimpleNamespace(id="bli-1")
    bli_qs = MagicMock()
    bli_qs.first.return_value = bli
    mock_bli.objects.filter.return_value = bli_qs
    mock_update.return_value = SimpleNamespace(apply=lambda: "CLEAR_EFFECT")

    charges = [{"command_uuid": VALID_UUID, "diagnosis_pointers": [], "modifiers": []}]
    effects, enriched, errors = build_charge_enrichment_effects(charges, [], "note-uuid")

    assert errors == []
    assert effects == ["CLEAR_EFFECT"]
    mock_update.assert_called_once_with(
        billing_line_item_id="bli-1",
        assessment_ids=[],
        modifiers=[],
    )


@patch("hyperscribe.scribe.charges.enrichment.UpdateBillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
@patch("hyperscribe.scribe.charges.enrichment.build_assessment_index")
@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_pointer_not_in_index_reports_error_and_does_not_clear(
    mock_note, mock_index, mock_command, mock_bli, mock_update
):
    _patch_note(mock_note)
    mock_index.return_value = {}  # no assessment matches the pointer's code
    mock_command.objects.get.return_value = SimpleNamespace(dbid=42)
    bli = SimpleNamespace(id="bli-1")
    bli_qs = MagicMock()
    bli_qs.first.return_value = bli
    mock_bli.objects.filter.return_value = bli_qs

    charges = [{
        "command_uuid": VALID_UUID,
        "diagnosis_pointers": [{"command_uuid": "d0", "icd10_code": "Z00.00"}],
        "modifiers": [],
    }]
    effects, enriched, errors = build_charge_enrichment_effects(charges, [], "note-uuid")

    assert effects == []
    assert enriched == []
    assert errors == [{"command_uuid": VALID_UUID, "reason": "no_assessment_resolved"}]
    mock_update.assert_not_called()


@patch("hyperscribe.scribe.charges.enrichment.UpdateBillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
@patch("hyperscribe.scribe.charges.enrichment.build_assessment_index")
@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_partial_pointer_resolution_reports_error_and_does_not_write(
    mock_note, mock_index, mock_command, mock_bli, mock_update
):
    """A multi-pointer charge where only SOME codes resolve must surface
    no_assessment_resolved and emit NO effect — never write a truncated
    assessment_ids set (which would silently drop a pointer from the claim).
    Reachable as a timing race: one diagnosis's Condition codings have committed
    while a sibling's have not yet."""
    _patch_note(mock_note)
    mock_index.return_value = {"M25511": ["aid-1"]}  # M25.511 resolves; E11.9 does not
    mock_command.objects.get.return_value = SimpleNamespace(dbid=42)
    bli = SimpleNamespace(id="bli-1")
    bli_qs = MagicMock()
    bli_qs.first.return_value = bli
    mock_bli.objects.filter.return_value = bli_qs

    charges = [{
        "command_uuid": VALID_UUID,
        "diagnosis_pointers": [
            {"command_uuid": "d0", "icd10_code": "M25.511"},
            {"command_uuid": "d1", "icd10_code": "E11.9"},
        ],
        "modifiers": [],
    }]
    effects, enriched, errors = build_charge_enrichment_effects(charges, [], "note-uuid")

    assert effects == []
    assert enriched == []
    assert errors == [{"command_uuid": VALID_UUID, "reason": "no_assessment_resolved"}]
    mock_update.assert_not_called()


@patch("hyperscribe.scribe.charges.enrichment.UpdateBillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
@patch("hyperscribe.scribe.charges.enrichment.build_assessment_index")
@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_all_pointers_resolve_writes_full_set(
    mock_note, mock_index, mock_command, mock_bli, mock_update
):
    """When EVERY sent code resolves, the full assessment_ids set is written and
    no error is recorded (guards against the partial-resolution check over-firing
    on a fully-resolvable multi-pointer charge)."""
    _patch_note(mock_note)
    mock_index.return_value = {"M25511": ["aid-1"], "E119": ["aid-2"]}
    mock_command.objects.get.return_value = SimpleNamespace(dbid=42)
    bli = SimpleNamespace(id="bli-1")
    bli_qs = MagicMock()
    bli_qs.first.return_value = bli
    mock_bli.objects.filter.return_value = bli_qs
    mock_update.return_value = SimpleNamespace(apply=lambda: "UPDATE_EFFECT")

    charges = [{
        "command_uuid": VALID_UUID,
        "diagnosis_pointers": [
            {"command_uuid": "d0", "icd10_code": "M25.511"},
            {"command_uuid": "d1", "icd10_code": "E11.9"},
        ],
        "modifiers": [],
    }]
    effects, enriched, errors = build_charge_enrichment_effects(charges, [], "note-uuid")

    assert errors == []
    assert effects == ["UPDATE_EFFECT"]
    mock_update.assert_called_once_with(
        billing_line_item_id="bli-1",
        assessment_ids=["aid-1", "aid-2"],
        modifiers=[],
    )


@patch("hyperscribe.scribe.charges.enrichment.UpdateBillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
@patch("hyperscribe.scribe.charges.enrichment.build_assessment_index")
@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_multiple_charges_accumulate_enriched_and_errors_independently(
    mock_note, mock_index, mock_command, mock_bli, mock_update
):
    _patch_note(mock_note)
    mock_index.return_value = {"M25511": ["aid-1"]}
    mock_command.objects.get.return_value = SimpleNamespace(dbid=42)
    # first charge's BLI is found; second charge's BLI is missing
    found_qs = MagicMock(); found_qs.first.return_value = SimpleNamespace(id="bli-1")
    missing_qs = MagicMock(); missing_qs.first.return_value = None
    mock_bli.objects.filter.side_effect = [found_qs, missing_qs]
    mock_update.return_value = SimpleNamespace(apply=lambda: "UPDATE_EFFECT")

    charges = [
        {
            "command_uuid": VALID_UUID,
            "diagnosis_pointers": [{"command_uuid": "d0", "icd10_code": "M25.511"}],
            "modifiers": [],
        },
        {
            "command_uuid": VALID_UUID_2,
            "diagnosis_pointers": [{"command_uuid": "d1", "icd10_code": "M25.511"}],
            "modifiers": [],
        },
    ]
    effects, enriched, errors = build_charge_enrichment_effects(charges, [], "note-uuid")

    assert effects == ["UPDATE_EFFECT"]
    assert [e["command_uuid"] for e in enriched] == [VALID_UUID]
    assert errors == [{"command_uuid": VALID_UUID_2, "reason": "billing_line_item_not_found"}]


# ── _find_billing_line_item: ambiguous CPT fallback guard ──


@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
def test_find_billing_line_item_fallback_ambiguous_cpt_returns_none(mock_command, mock_bli):
    """When the primary command_id lookup misses and multiple ACTIVE BLIs share
    the same CPT, the fallback must return None instead of picking arbitrarily
    — otherwise it would silently overwrite the wrong charge's claim data."""
    from canvas_sdk.v1.data.billing import BillingLineItemStatus

    note = SimpleNamespace(dbid=1)
    command = SimpleNamespace(dbid=42, data={"cpt_code": "99213"})
    mock_command.objects.get.return_value = command

    primary_qs = MagicMock()
    primary_qs.first.return_value = None  # command_id lookup misses

    fallback_qs = MagicMock()
    fallback_qs.count.return_value = 2   # two BLIs share this CPT

    mock_bli.objects.filter.side_effect = [primary_qs, fallback_qs]

    result = _find_billing_line_item(note, VALID_UUID)

    assert result is None
    fallback_qs.first.assert_not_called()  # must not pick blindly
    mock_bli.objects.filter.assert_any_call(
        note=note, cpt="99213", status=BillingLineItemStatus.ACTIVE
    )


@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
def test_find_billing_line_item_fallback_unambiguous_cpt_returns_bli(mock_command, mock_bli):
    """When the primary command_id lookup misses but exactly one ACTIVE BLI
    shares the CPT, the fallback may safely call .first() and return it."""
    from canvas_sdk.v1.data.billing import BillingLineItemStatus

    note = SimpleNamespace(dbid=1)
    expected_bli = SimpleNamespace(id="bli-1")
    command = SimpleNamespace(dbid=42, data={"cpt_code": "99213"})
    mock_command.objects.get.return_value = command

    primary_qs = MagicMock()
    primary_qs.first.return_value = None  # command_id lookup misses

    fallback_qs = MagicMock()
    fallback_qs.count.return_value = 1
    fallback_qs.first.return_value = expected_bli

    mock_bli.objects.filter.side_effect = [primary_qs, fallback_qs]

    result = _find_billing_line_item(note, VALID_UUID)

    assert result is expected_bli
    fallback_qs.first.assert_called_once()


# ── Coverage gap: ambiguous ICD-10 warning path in _resolve_assessment_ids ──

from hyperscribe.scribe.charges.enrichment import _resolve_assessment_ids


def test_resolve_assessment_ids_warns_on_ambiguous_code():
    """When an ICD-10 code maps to more than one assessment, all ids are
    included in the resolved list and a warning is logged."""
    index = {"E119": ["aid-1", "aid-2"]}
    pointers = [{"icd10_code": "E11.9"}]
    with patch("hyperscribe.scribe.charges.enrichment.log") as mock_log:
        result = _resolve_assessment_ids(pointers, index)
    assert result == ["aid-1", "aid-2"]
    mock_log.warning.assert_called_once()
    call_args = mock_log.warning.call_args[0]
    assert "E119" in call_args[1]
    assert call_args[2] == 2


def test_resolve_assessment_ids_deduplicates_across_pointers():
    """Two pointers sharing the same ICD-10 code should not produce duplicate
    assessment ids in the resolved list."""
    index = {"E119": ["aid-1"]}
    pointers = [{"icd10_code": "E11.9"}, {"icd10_code": "E11.9"}]
    result = _resolve_assessment_ids(pointers, index)
    assert result == ["aid-1"]


# ── Coverage gap: idempotent removal path (BLI already absent) ──

@patch("hyperscribe.scribe.charges.enrichment.RemoveBillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
@patch("hyperscribe.scribe.charges.enrichment.build_assessment_index")
@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_removed_charge_already_absent_is_silently_skipped(
    mock_note, mock_index, mock_command, mock_bli, mock_remove
):
    """When the BLI for a removed command can't be found, no error is recorded
    and no RemoveBillingLineItem effect is emitted (idempotent removal)."""
    _patch_note(mock_note)
    mock_index.return_value = {}
    mock_command.DoesNotExist = Exception
    mock_command.objects.get.side_effect = mock_command.DoesNotExist

    effects, enriched, errors = build_charge_enrichment_effects([], [VALID_UUID], "note-uuid")

    assert effects == []
    assert enriched == []
    assert errors == []
    mock_remove.assert_not_called()


@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
def test_find_billing_line_item_invalid_uuid_returns_none_without_orm(mock_command, mock_bli):
    """A malformed/empty command_uuid must be rejected before the ORM lookup —
    Command.objects.get on a UUIDField raises django ValidationError (uncatchable
    in the plugin sandbox) which would 500 the whole /enrich-charges request."""
    for bad in ("", "perform-1", "not-a-uuid", None):
        assert _find_billing_line_item(SimpleNamespace(dbid=1), bad) is None
    mock_command.objects.get.assert_not_called()
    mock_bli.objects.filter.assert_not_called()
