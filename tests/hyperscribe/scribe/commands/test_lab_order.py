from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.lab_order import LabOrderParser


def test_extract() -> None:
    parser = LabOrderParser()
    proposal = parser.extract("CBC with differential")
    assert proposal is not None
    assert proposal.command_type == "lab_order"
    assert proposal.data["comment"] == "CBC with differential"
    assert proposal.display == "CBC with differential"


def test_extract_empty_returns_empty_comment() -> None:
    parser = LabOrderParser()
    proposal = parser.extract("")
    assert proposal is not None
    assert proposal.data["comment"] == ""


def test_build() -> None:
    parser = LabOrderParser()
    with patch("hyperscribe.scribe.commands.lab_order.LabOrderCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(
            {
                "lab_partner": "partner-uuid",
                "tests_order_codes": ["CBC", "BMP"],
                "diagnosis_codes": ["E11.9"],
                "fasting_required": True,
                "comment": "CBC with differential",
            },
            "note-uuid",
            "cmd-uuid",
        )

    mock_cmd.assert_called_once_with(
        lab_partner="partner-uuid",
        tests_order_codes=["CBC", "BMP"],
        diagnosis_codes=["E11.9"],
        fasting_required=True,
        comment="CBC with differential",
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_empty() -> None:
    parser = LabOrderParser()
    with patch("hyperscribe.scribe.commands.lab_order.LabOrderCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({}, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        lab_partner=None,
        tests_order_codes=[],
        diagnosis_codes=[],
        fasting_required=False,
        comment=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )
