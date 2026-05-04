from types import SimpleNamespace
from datetime import datetime
from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.prior_sections import get_prior_section_data


def _make_command(
    html: str,
    source_note_id: str = "n1",
    source_date_iso: str = "2026-04-12T14:30:00+00:00",
    schema_key: str = "physicalExam",
    cmd_id: str = "cmd-1",
):
    """Build a stub Command-like object with .data, .note, .id, .schema_key."""
    note = SimpleNamespace(
        id=source_note_id,
        datetime_of_service=datetime.fromisoformat(source_date_iso),
    )
    return SimpleNamespace(id=cmd_id, schema_key=schema_key, data={"content": html}, note=note)


def test_returns_empty_for_missing_note_id() -> None:
    assert get_prior_section_data("") == {"physical_exam": None, "review_of_systems": None}


@patch("hyperscribe.scribe.commands.prior_sections.Note")
def test_returns_empty_when_note_does_not_exist(mock_note_cls):
    class DoesNotExist(Exception):
        pass

    mock_note_cls.DoesNotExist = DoesNotExist
    mock_note_cls.objects.select_related.return_value.get.side_effect = DoesNotExist
    assert get_prior_section_data("missing") == {"physical_exam": None, "review_of_systems": None}


@patch("hyperscribe.scribe.commands.prior_sections.Command")
@patch("hyperscribe.scribe.commands.prior_sections.Note")
def test_returns_payloads_for_each_command_type(mock_note_cls, mock_command_cls) -> None:
    # Note lookup for the current note
    current_note = SimpleNamespace(id="cur", patient_id="p1", provider_id="prov1")
    mock_note_cls.objects.select_related.return_value.get.return_value = current_note

    # Build expected prior commands
    pe_cmd = _make_command(
        "<div><b>Heart:</b> RRR</div><div><b>Lungs:</b> CTAB</div>",
        source_note_id="note-pe",
        source_date_iso="2026-04-12T14:30:00+00:00",
    )
    ros_cmd = _make_command(
        "<div><b>Constitutional:</b> denies fever</div>",
        source_note_id="note-ros",
        source_date_iso="2026-04-20T09:00:00+00:00",
    )

    # Configure the chained query so .filter().exclude().select_related() returns
    # an object with .filter().order_by().first() per schema_key.
    base = MagicMock()
    pe_qs = MagicMock()
    pe_qs.order_by.return_value.first.return_value = pe_cmd
    ros_qs = MagicMock()
    ros_qs.order_by.return_value.first.return_value = ros_cmd

    def side_effect_filter(**kwargs):
        if kwargs.get("schema_key") == "physicalExam":
            return pe_qs
        if kwargs.get("schema_key") == "reviewOfSystems":
            return ros_qs
        return MagicMock()

    base.filter.side_effect = side_effect_filter
    (mock_command_cls.objects.filter.return_value.exclude.return_value.select_related.return_value) = base

    result = get_prior_section_data("cur")
    assert result["physical_exam"]["source_note_id"] == "note-pe"
    assert result["physical_exam"]["sections"] == [
        {"title": "Heart", "text": "RRR"},
        {"title": "Lungs", "text": "CTAB"},
    ]
    assert result["review_of_systems"]["source_note_id"] == "note-ros"
    assert result["review_of_systems"]["sections"] == [
        {"title": "Constitutional", "text": "denies fever"},
    ]


@patch("hyperscribe.scribe.commands.prior_sections.Command")
@patch("hyperscribe.scribe.commands.prior_sections.Note")
def test_returns_none_for_command_type_with_no_prior_match(mock_note_cls, mock_command_cls) -> None:
    current_note = SimpleNamespace(id="cur", patient_id="p1", provider_id="prov1")
    mock_note_cls.objects.select_related.return_value.get.return_value = current_note

    base = MagicMock()
    none_qs = MagicMock()
    none_qs.order_by.return_value.first.return_value = None
    base.filter.return_value = none_qs
    (mock_command_cls.objects.filter.return_value.exclude.return_value.select_related.return_value) = base

    result = get_prior_section_data("cur")
    assert result == {"physical_exam": None, "review_of_systems": None}


@patch("hyperscribe.scribe.commands.prior_sections.Command")
@patch("hyperscribe.scribe.commands.prior_sections.Note")
def test_returns_none_when_html_yields_no_sections(mock_note_cls, mock_command_cls) -> None:
    current_note = SimpleNamespace(id="cur", patient_id="p1", provider_id="prov1")
    mock_note_cls.objects.select_related.return_value.get.return_value = current_note

    pe_cmd = _make_command("<p>some unrecognizable garbage</p>")
    base = MagicMock()
    pe_qs = MagicMock()
    pe_qs.order_by.return_value.first.return_value = pe_cmd
    none_qs = MagicMock()
    none_qs.order_by.return_value.first.return_value = None

    def side_effect_filter(**kwargs):
        return pe_qs if kwargs.get("schema_key") == "physicalExam" else none_qs

    base.filter.side_effect = side_effect_filter
    (mock_command_cls.objects.filter.return_value.exclude.return_value.select_related.return_value) = base

    result = get_prior_section_data("cur")
    assert result["physical_exam"] is None
    assert result["review_of_systems"] is None


@patch("hyperscribe.scribe.commands.prior_sections.Command")
@patch("hyperscribe.scribe.commands.prior_sections.Note")
def test_swallows_query_exceptions(mock_note_cls, mock_command_cls) -> None:
    current_note = SimpleNamespace(id="cur", patient_id="p1", provider_id="prov1")
    mock_note_cls.objects.select_related.return_value.get.return_value = current_note
    mock_command_cls.objects.filter.side_effect = RuntimeError("DB down")
    assert get_prior_section_data("cur") == {"physical_exam": None, "review_of_systems": None}
