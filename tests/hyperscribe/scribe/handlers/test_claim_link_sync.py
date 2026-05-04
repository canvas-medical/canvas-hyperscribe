"""Tests for `ClaimLinkSync` — the per-perform-commit handler that writes
Scribe's CPT->ICD picks onto BillingLineItem.assessment_ids.

The handler's I/O is event.context-in, list[Effect]-out. Every data lookup
goes through Django ORM-style managers (Command, ScribeSummary, Assessment,
BillingLineItem) — all mockable. The Canvas SDK's `UpdateBillingLineItem`
effect is also mocked so the tests don't depend on Canvas's effect runtime."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hyperscribe.scribe.handlers.claim_link_sync import ClaimLinkSync, _strip


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
    mock_assessment_cls.objects.filter.return_value.select_related.return_value = [
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
    mock_assessment_cls.objects.filter.return_value.select_related.return_value = [
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
    mock_assessment_cls.objects.filter.return_value.select_related.return_value = [
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
    call_kwargs = mock_update_cls.call_args.kwargs
    assert call_kwargs["billing_line_item_id"] == "bli-1"
    assert sorted(call_kwargs["assessment_ids"]) == ["a-1", "a-2"]


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
    mock_assessment_cls.objects.filter.return_value.select_related.return_value = [
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
    mock_assessment_cls.objects.filter.return_value.select_related.return_value = [
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
    mock_assessment_cls.objects.filter.return_value.select_related.return_value = [
        _fake_assessment("a-1", "E11.9"),
        _fake_assessment("a-2", "I10"),
    ]
    mock_bli_cls.objects.filter.return_value.values_list.return_value = ["bli-1"]
    mock_update_cls.return_value.apply.return_value = "effect-1"

    handler = _make_handler()
    handler.compute()

    sent_ids = mock_update_cls.call_args.kwargs["assessment_ids"]
    # Two distinct assessments, in any order.
    assert sorted(sent_ids) == ["a-1", "a-2"]


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
    mock_assessment_cls.objects.filter.return_value.select_related.return_value = [
        _fake_assessment("a-first", "E11.9"),
        _fake_assessment("a-second", "E11.9"),
    ]
    mock_bli_cls.objects.filter.return_value.values_list.return_value = ["bli-1"]
    mock_update_cls.return_value.apply.return_value = "effect-1"

    handler = _make_handler()
    handler.compute()

    assert mock_update_cls.call_args.kwargs["assessment_ids"] == ["a-first"]
