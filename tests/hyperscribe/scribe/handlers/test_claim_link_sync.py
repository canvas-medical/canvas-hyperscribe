"""Tests for `ClaimLinkSync` — the per-perform-commit handler that writes
Scribe's CPT->ICD picks onto BillingLineItem.assessment_ids.

The handler's I/O is event.context-in, list[Effect]-out. Every data lookup
goes through Django ORM-style managers (Command, ScribeSummary, Assessment,
BillingLineItem) — all mockable. The Canvas SDK's `UpdateBillingLineItem`
effect is also mocked so the tests don't depend on Canvas's effect runtime."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hyperscribe.scribe.handlers.claim_link_sync import (
    ClaimLinkSync,
    PerformBillingLineItemRemoval,
    _strip,
)


# ---------------------------------------------------------------------------
# _strip helper
# ---------------------------------------------------------------------------


def test_strip_normalizes_dotted_codes() -> None:
    assert _strip("E11.9") == "E119"


def test_strip_normalizes_undotted_codes() -> None:
    assert _strip("e119") == "E119"


def test_strip_handles_whitespace_and_dots() -> None:
    assert _strip("  e11.9  ") == "E119"


def test_strip_handles_empty_and_none() -> None:
    assert _strip("") == ""
    assert _strip(None) == ""  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Handler scaffolding
# ---------------------------------------------------------------------------


def _make_handler(target_id: str | None = "cmd-uuid") -> ClaimLinkSync:
    """Build a handler with a fake event whose target.id returns the supplied
    value. Avoids the real Event/EventRequest plumbing that would require a
    full Canvas event payload."""
    handler = ClaimLinkSync.__new__(ClaimLinkSync)
    target = SimpleNamespace(id=target_id) if target_id is not None else None
    handler.event = SimpleNamespace(target=target, context={})
    handler.secrets = {}
    handler.environment = {}
    return handler


def _fake_assessment(assess_id: str, *icd_codes: str) -> SimpleNamespace:
    """Build a fake Assessment whose .condition.codings.all() returns coding
    rows shaped like ConditionCoding (with a `code` attr)."""
    codings_qs = MagicMock()
    codings_qs.all.return_value = [SimpleNamespace(code=c) for c in icd_codes]
    condition = SimpleNamespace(codings=codings_qs)
    return SimpleNamespace(id=assess_id, condition=condition)


# ---------------------------------------------------------------------------
# RESPONDS_TO contract
# ---------------------------------------------------------------------------


def test_responds_to_perform_command_post_commit() -> None:
    assert ClaimLinkSync.RESPONDS_TO == ["PERFORM_COMMAND__POST_COMMIT"]


# ---------------------------------------------------------------------------
# Early bail-outs (compute returns []) — exercise every guard branch.
# ---------------------------------------------------------------------------


def test_compute_no_event_target_returns_empty() -> None:
    handler = _make_handler(target_id=None)
    assert handler.compute() == []


def test_compute_event_with_no_target_attr_returns_empty() -> None:
    handler = ClaimLinkSync.__new__(ClaimLinkSync)
    handler.event = None
    assert handler.compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_command_does_not_exist_returns_empty(mock_command_cls: MagicMock) -> None:
    class DoesNotExist(Exception):
        pass

    mock_command_cls.DoesNotExist = DoesNotExist
    mock_command_cls.objects.select_related.return_value.get.side_effect = DoesNotExist
    handler = _make_handler()
    assert handler.compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_no_cpt_in_command_data_returns_empty(mock_command_cls: MagicMock) -> None:
    cmd = SimpleNamespace(id="x", data={}, note=SimpleNamespace(dbid=1, id="note-uuid"))
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    handler = _make_handler()
    assert handler.compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_no_note_on_command_returns_empty(mock_command_cls: MagicMock) -> None:
    cmd = SimpleNamespace(id="x", data={"perform": {"value": "99213"}}, note=None)
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    handler = _make_handler()
    assert handler.compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.ScribeSummary")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_no_scribe_summary_returns_empty(
    mock_command_cls: MagicMock, mock_summary_cls: MagicMock
) -> None:
    cmd = SimpleNamespace(
        id="x", data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    mock_summary_cls.objects.filter.return_value.first.return_value = None
    handler = _make_handler()
    assert handler.compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.ScribeSummary")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_summary_with_no_commands_returns_empty(
    mock_command_cls: MagicMock, mock_summary_cls: MagicMock
) -> None:
    cmd = SimpleNamespace(
        id="x", data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    summary = SimpleNamespace(commands=None)
    mock_summary_cls.objects.filter.return_value.first.return_value = summary
    handler = _make_handler()
    assert handler.compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.ScribeSummary")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_no_perform_in_summary_for_this_cpt_returns_empty(
    mock_command_cls: MagicMock, mock_summary_cls: MagicMock
) -> None:
    cmd = SimpleNamespace(
        id="x", data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    # Summary has performs but for a different CPT.
    summary = SimpleNamespace(commands=[
        {"command_type": "perform", "data": {"cpt_code": "99214", "linked_icd10_codes": ["E11.9"]}},
        {"command_type": "diagnose", "data": {"icd10_code": "E11.9"}},
    ])
    mock_summary_cls.objects.filter.return_value.first.return_value = summary
    handler = _make_handler()
    assert handler.compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.ScribeSummary")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_perform_with_empty_links_returns_empty(
    mock_command_cls: MagicMock, mock_summary_cls: MagicMock
) -> None:
    cmd = SimpleNamespace(
        id="x", data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    summary = SimpleNamespace(commands=[
        {"command_type": "perform", "data": {"cpt_code": "99213", "linked_icd10_codes": []}},
    ])
    mock_summary_cls.objects.filter.return_value.first.return_value = summary
    handler = _make_handler()
    assert handler.compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.ScribeSummary")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_perform_with_non_list_links_returns_empty(
    mock_command_cls: MagicMock, mock_summary_cls: MagicMock
) -> None:
    cmd = SimpleNamespace(
        id="x", data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    summary = SimpleNamespace(commands=[
        {"command_type": "perform", "data": {"cpt_code": "99213", "linked_icd10_codes": "E11.9"}},
    ])
    mock_summary_cls.objects.filter.return_value.first.return_value = summary
    handler = _make_handler()
    assert handler.compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.Assessment")
@patch("hyperscribe.scribe.handlers.claim_link_sync.ScribeSummary")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_no_assessments_match_returns_empty(
    mock_command_cls: MagicMock,
    mock_summary_cls: MagicMock,
    mock_assessment_cls: MagicMock,
) -> None:
    cmd = SimpleNamespace(
        id="x", data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    summary = SimpleNamespace(commands=[
        {"command_type": "perform", "data": {"cpt_code": "99213", "linked_icd10_codes": ["E11.9"]}},
    ])
    mock_summary_cls.objects.filter.return_value.first.return_value = summary
    # Assessments exist but their codings don't match the wanted ICD.
    mock_assessment_cls.objects.filter.return_value.select_related.return_value.prefetch_related.return_value = [
        _fake_assessment("a-1", "I10"),
    ]
    handler = _make_handler()
    assert handler.compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.BillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Assessment")
@patch("hyperscribe.scribe.handlers.claim_link_sync.ScribeSummary")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_no_billing_line_item_returns_empty(
    mock_command_cls: MagicMock,
    mock_summary_cls: MagicMock,
    mock_assessment_cls: MagicMock,
    mock_bli_cls: MagicMock,
) -> None:
    cmd = SimpleNamespace(
        id="x", data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    summary = SimpleNamespace(commands=[
        {"command_type": "perform", "data": {"cpt_code": "99213", "linked_icd10_codes": ["E11.9"]}},
    ])
    mock_summary_cls.objects.filter.return_value.first.return_value = summary
    mock_assessment_cls.objects.filter.return_value.select_related.return_value.prefetch_related.return_value = [
        _fake_assessment("a-1", "E11.9"),
    ]
    mock_bli_cls.objects.filter.return_value.values_list.return_value = []
    handler = _make_handler()
    assert handler.compute() == []


# ---------------------------------------------------------------------------
# Happy path + interesting edge cases — assert effects are produced.
# ---------------------------------------------------------------------------


@patch("hyperscribe.scribe.handlers.claim_link_sync.UpdateBillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.BillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Assessment")
@patch("hyperscribe.scribe.handlers.claim_link_sync.ScribeSummary")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_emits_update_with_translated_assessment_ids(
    mock_command_cls: MagicMock,
    mock_summary_cls: MagicMock,
    mock_assessment_cls: MagicMock,
    mock_bli_cls: MagicMock,
    mock_update_cls: MagicMock,
) -> None:
    cmd = SimpleNamespace(
        id="x", data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=42, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    summary = SimpleNamespace(commands=[
        # Two ICDs linked: E11.9 (matches assessment a-1) and I10 (matches a-2).
        {"command_type": "perform", "data": {"cpt_code": "99213", "linked_icd10_codes": ["E11.9", "I10"]}},
        # A non-matching perform (different CPT) should be ignored.
        {"command_type": "perform", "data": {"cpt_code": "99214", "linked_icd10_codes": ["K21.9"]}},
        # Non-perform commands should be ignored.
        {"command_type": "diagnose", "data": {"icd10_code": "E11.9"}},
    ])
    mock_summary_cls.objects.filter.return_value.first.return_value = summary
    mock_assessment_cls.objects.filter.return_value.select_related.return_value.prefetch_related.return_value = [
        _fake_assessment("a-1", "E119"),  # undotted form → still matches via _strip
        _fake_assessment("a-2", "I10"),
        _fake_assessment("a-3", "K21.9"),  # not wanted for this CPT
    ]
    mock_bli_cls.objects.filter.return_value.values_list.return_value = ["bli-1"]
    mock_update_cls.return_value.apply.return_value = "effect-1"

    handler = _make_handler()
    effects = handler.compute()

    assert effects == ["effect-1"]
    # Verify the call passed the right BLI id and a translated assessment_ids list.
    # Assert exact list equality (NOT sorted): the linked_icd10_codes
    # ordering is the provider's intended primary-vs-secondary diagnosis
    # pointer order on CMS-1500 box 24E. linked_icd10_codes was ["E11.9",
    # "I10"], so the resulting assessment_ids must be ["a-1", "a-2"] in
    # that order — a hash-randomized set in the handler would scramble it.
    call_kwargs = mock_update_cls.call_args.kwargs
    assert call_kwargs["billing_line_item_id"] == "bli-1"
    assert call_kwargs["assessment_ids"] == ["a-1", "a-2"]


@patch("hyperscribe.scribe.handlers.claim_link_sync.UpdateBillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.BillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Assessment")
@patch("hyperscribe.scribe.handlers.claim_link_sync.ScribeSummary")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_skips_assessments_with_no_condition(
    mock_command_cls: MagicMock,
    mock_summary_cls: MagicMock,
    mock_assessment_cls: MagicMock,
    mock_bli_cls: MagicMock,
    mock_update_cls: MagicMock,
) -> None:
    cmd = SimpleNamespace(
        id="x", data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    summary = SimpleNamespace(commands=[
        {"command_type": "perform", "data": {"cpt_code": "99213", "linked_icd10_codes": ["E11.9"]}},
    ])
    mock_summary_cls.objects.filter.return_value.first.return_value = summary
    # Assessment without a condition is silently skipped.
    no_condition = SimpleNamespace(id="a-noop", condition=None)
    mock_assessment_cls.objects.filter.return_value.select_related.return_value.prefetch_related.return_value = [
        no_condition,
        _fake_assessment("a-1", "E11.9"),
    ]
    mock_bli_cls.objects.filter.return_value.values_list.return_value = ["bli-1"]
    mock_update_cls.return_value.apply.return_value = "effect-1"

    handler = _make_handler()
    effects = handler.compute()

    assert effects == ["effect-1"]
    assert mock_update_cls.call_args.kwargs["assessment_ids"] == ["a-1"]


@patch("hyperscribe.scribe.handlers.claim_link_sync.UpdateBillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.BillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Assessment")
@patch("hyperscribe.scribe.handlers.claim_link_sync.ScribeSummary")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_emits_one_effect_per_billing_line_item(
    mock_command_cls: MagicMock,
    mock_summary_cls: MagicMock,
    mock_assessment_cls: MagicMock,
    mock_bli_cls: MagicMock,
    mock_update_cls: MagicMock,
) -> None:
    """Edge case: theoretically multiple BLIs can share a CPT on one note."""
    cmd = SimpleNamespace(
        id="x", data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    summary = SimpleNamespace(commands=[
        {"command_type": "perform", "data": {"cpt_code": "99213", "linked_icd10_codes": ["E11.9"]}},
    ])
    mock_summary_cls.objects.filter.return_value.first.return_value = summary
    mock_assessment_cls.objects.filter.return_value.select_related.return_value.prefetch_related.return_value = [
        _fake_assessment("a-1", "E11.9"),
    ]
    mock_bli_cls.objects.filter.return_value.values_list.return_value = ["bli-1", "bli-2"]
    mock_update_cls.return_value.apply.side_effect = ["effect-1", "effect-2"]

    handler = _make_handler()
    effects = handler.compute()

    assert effects == ["effect-1", "effect-2"]
    assert mock_update_cls.call_count == 2
    bli_args = [c.kwargs["billing_line_item_id"] for c in mock_update_cls.call_args_list]
    assert bli_args == ["bli-1", "bli-2"]


@patch("hyperscribe.scribe.handlers.claim_link_sync.UpdateBillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.BillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Assessment")
@patch("hyperscribe.scribe.handlers.claim_link_sync.ScribeSummary")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_dedupes_links_across_multiple_perform_entries_for_same_cpt(
    mock_command_cls: MagicMock,
    mock_summary_cls: MagicMock,
    mock_assessment_cls: MagicMock,
    mock_bli_cls: MagicMock,
    mock_update_cls: MagicMock,
) -> None:
    """Two perform entries for the same CPT in summary.commands should
    have their linked ICDs unioned, not duplicated."""
    cmd = SimpleNamespace(
        id="x", data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    summary = SimpleNamespace(commands=[
        {"command_type": "perform", "data": {"cpt_code": "99213", "linked_icd10_codes": ["E11.9"]}},
        {"command_type": "perform", "data": {"cpt_code": "99213", "linked_icd10_codes": ["E11.9", "I10"]}},
    ])
    mock_summary_cls.objects.filter.return_value.first.return_value = summary
    mock_assessment_cls.objects.filter.return_value.select_related.return_value.prefetch_related.return_value = [
        _fake_assessment("a-1", "E11.9"),
        _fake_assessment("a-2", "I10"),
    ]
    mock_bli_cls.objects.filter.return_value.values_list.return_value = ["bli-1"]
    mock_update_cls.return_value.apply.return_value = "effect-1"

    handler = _make_handler()
    handler.compute()

    sent_ids = mock_update_cls.call_args.kwargs["assessment_ids"]
    # Order matters (CMS-1500 box 24E primary-vs-secondary). The first
    # entry's [E11.9] establishes the position, the second entry's
    # [E11.9, I10] adds I10 at the end. Dedup is append-if-not-seen,
    # so the resulting order is deterministic: [E11.9, I10] -> [a-1, a-2].
    assert sent_ids == ["a-1", "a-2"]


@patch("hyperscribe.scribe.handlers.claim_link_sync.UpdateBillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.BillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Assessment")
@patch("hyperscribe.scribe.handlers.claim_link_sync.ScribeSummary")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_first_assessment_wins_on_icd_collision(
    mock_command_cls: MagicMock,
    mock_summary_cls: MagicMock,
    mock_assessment_cls: MagicMock,
    mock_bli_cls: MagicMock,
    mock_update_cls: MagicMock,
) -> None:
    """If two assessments share an ICD code (rare but possible), the
    handler picks the first one encountered — `if stripped not in icd_to_assessment`
    guard. Verifies that branch."""
    cmd = SimpleNamespace(
        id="x", data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    summary = SimpleNamespace(commands=[
        {"command_type": "perform", "data": {"cpt_code": "99213", "linked_icd10_codes": ["E11.9"]}},
    ])
    mock_summary_cls.objects.filter.return_value.first.return_value = summary
    mock_assessment_cls.objects.filter.return_value.select_related.return_value.prefetch_related.return_value = [
        _fake_assessment("a-first", "E11.9"),
        _fake_assessment("a-second", "E11.9"),
    ]
    mock_bli_cls.objects.filter.return_value.values_list.return_value = ["bli-1"]
    mock_update_cls.return_value.apply.return_value = "effect-1"

    handler = _make_handler()
    handler.compute()

    assert mock_update_cls.call_args.kwargs["assessment_ids"] == ["a-first"]


@patch("hyperscribe.scribe.handlers.claim_link_sync.UpdateBillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.BillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Assessment")
@patch("hyperscribe.scribe.handlers.claim_link_sync.ScribeSummary")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_compute_preserves_provider_click_order_for_diagnosis_pointers(
    mock_command_cls: MagicMock,
    mock_summary_cls: MagicMock,
    mock_assessment_cls: MagicMock,
    mock_bli_cls: MagicMock,
    mock_update_cls: MagicMock,
) -> None:
    """Regression guard for the `wanted: set[str]` ordering bug: the order
    of `linked_icd10_codes` IS the diagnosis-pointer sequence on CMS-1500
    box 24E (primary, secondary, …). The previous implementation used a
    set, which scrambled order via hash-randomized iteration. This test
    feeds the codes in REVERSE alphabetical order and asserts the same
    reverse order survives all the way to assessment_ids — a sorted or
    set-iterated impl would reorder them and fail."""
    cmd = SimpleNamespace(
        id="x", data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    # Provider clicked the cells in reverse-alphabetical order: M, K, I, E.
    summary = SimpleNamespace(commands=[
        {"command_type": "perform", "data": {
            "cpt_code": "99213",
            "linked_icd10_codes": ["M54.5", "K21.9", "I10", "E11.9"],
        }},
    ])
    mock_summary_cls.objects.filter.return_value.first.return_value = summary
    # Assessments returned in a DIFFERENT order than the linked_icd10_codes,
    # to confirm the order is driven by the click order, not the assessment
    # query order.
    mock_assessment_cls.objects.filter.return_value.select_related.return_value.prefetch_related.return_value = [
        _fake_assessment("a-e119", "E11.9"),
        _fake_assessment("a-i10", "I10"),
        _fake_assessment("a-k219", "K21.9"),
        _fake_assessment("a-m545", "M54.5"),
    ]
    mock_bli_cls.objects.filter.return_value.values_list.return_value = ["bli-1"]
    mock_update_cls.return_value.apply.return_value = "effect-1"

    handler = _make_handler()
    handler.compute()

    # Strict list equality. assessment_ids must follow the click order
    # ["M54.5", "K21.9", "I10", "E11.9"] → ["a-m545", "a-k219", "a-i10", "a-e119"].
    assert mock_update_cls.call_args.kwargs["assessment_ids"] == [
        "a-m545", "a-k219", "a-i10", "a-e119",
    ]


# ---------------------------------------------------------------------------
# PerformBillingLineItemRemoval — voids the BLI when a perform is EIE'd.
# ---------------------------------------------------------------------------


def _make_removal_handler(target_id: str | None = "cmd-uuid") -> PerformBillingLineItemRemoval:
    handler = PerformBillingLineItemRemoval.__new__(PerformBillingLineItemRemoval)
    target = SimpleNamespace(id=target_id) if target_id is not None else None
    handler.event = SimpleNamespace(target=target, context={})
    handler.secrets = {}
    handler.environment = {}
    return handler


def test_removal_responds_to_perform_command_post_enter_in_error() -> None:
    assert PerformBillingLineItemRemoval.RESPONDS_TO == ["PERFORM_COMMAND__POST_ENTER_IN_ERROR"]


def test_removal_no_event_target_returns_empty() -> None:
    assert _make_removal_handler(target_id=None).compute() == []


def test_removal_event_none_returns_empty() -> None:
    handler = PerformBillingLineItemRemoval.__new__(PerformBillingLineItemRemoval)
    handler.event = None
    assert handler.compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_removal_command_does_not_exist_returns_empty(mock_command_cls: MagicMock) -> None:
    class DoesNotExist(Exception):
        pass

    mock_command_cls.DoesNotExist = DoesNotExist
    mock_command_cls.objects.select_related.return_value.get.side_effect = DoesNotExist
    assert _make_removal_handler().compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_removal_no_cpt_returns_empty(mock_command_cls: MagicMock) -> None:
    cmd = SimpleNamespace(dbid=11, data={}, note=SimpleNamespace(dbid=1, id="note-uuid"))
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    assert _make_removal_handler().compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_removal_no_note_returns_empty(mock_command_cls: MagicMock) -> None:
    cmd = SimpleNamespace(dbid=11, data={"perform": {"value": "99213"}}, note=None)
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    assert _make_removal_handler().compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.BillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_removal_no_active_bli_for_command_returns_empty(
    mock_command_cls: MagicMock,
    mock_bli_cls: MagicMock,
) -> None:
    cmd = SimpleNamespace(
        dbid=11,
        data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    mock_bli_cls.objects.filter.return_value.values_list.return_value = []
    assert _make_removal_handler().compute() == []


@patch("hyperscribe.scribe.handlers.claim_link_sync.RemoveBillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.BillingLineItem")
@patch("hyperscribe.scribe.handlers.claim_link_sync.Command")
def test_removal_emits_remove_effect_filtered_by_cpt_note_active(
    mock_command_cls: MagicMock,
    mock_bli_cls: MagicMock,
    mock_remove_cls: MagicMock,
) -> None:
    """Matches the SDK-docs pattern: filter by cpt + note + ACTIVE so that
    rows previously removed by this handler are skipped, and the BLI tied
    to the just-voided perform is removed."""
    cmd = SimpleNamespace(
        dbid=11,
        data={"perform": {"value": "99213"}},
        note=SimpleNamespace(dbid=1, id="note-uuid"),
    )
    mock_command_cls.objects.select_related.return_value.get.return_value = cmd
    mock_bli_cls.objects.filter.return_value.values_list.return_value = ["bli-1"]
    mock_remove_cls.return_value.apply.return_value = "effect-1"

    effects = _make_removal_handler().compute()

    assert effects == ["effect-1"]
    filter_kwargs = mock_bli_cls.objects.filter.call_args.kwargs
    assert filter_kwargs["cpt"] == "99213"
    assert filter_kwargs["note_id"] == 1
    assert filter_kwargs["status"].name == "ACTIVE"
    assert mock_remove_cls.call_args.kwargs == {"billing_line_item_id": "bli-1"}
