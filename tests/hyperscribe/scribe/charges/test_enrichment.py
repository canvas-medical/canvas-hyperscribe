from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hyperscribe.scribe.charges.enrichment import _normalize_icd10, build_assessment_index


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
    mock_assessment.objects.filter.assert_called_once_with(note=note, entered_in_error_id__isnull=True)


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
