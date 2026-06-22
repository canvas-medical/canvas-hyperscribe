from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.refer import ReferParser


def test_extract_returns_none() -> None:
    parser = ReferParser()
    assert parser.extract("refer to cardiology") is None


def _complete_refer_data() -> dict:
    return {
        "service_provider": {"last_name": "(TBD)", "specialty": "Cardiology"},
        "clinical_question": "Assistance with Ongoing Management",
        "notes_to_specialist": "Please evaluate",
        "diagnosis_codes": ["I10"],
    }


def test_validate_passes_when_complete() -> None:
    assert ReferParser().validate(_complete_refer_data()) == []


def test_validate_requires_all_four_sign_fields() -> None:
    errors = ReferParser().validate({})
    assert "Referral recipient is required" in errors
    assert "Clinical question is required" in errors
    assert "Notes to specialist is required" in errors
    assert "At least one indication is required" in errors


def test_validate_flags_missing_recipient() -> None:
    data = _complete_refer_data()
    data["service_provider"] = None
    errors = ReferParser().validate(data)
    assert errors == ["Referral recipient is required"]


def test_validate_flags_missing_indication() -> None:
    data = _complete_refer_data()
    data["diagnosis_codes"] = []
    errors = ReferParser().validate(data)
    assert errors == ["At least one indication is required"]


def test_build_routine_priority() -> None:
    parser = ReferParser()
    data = {"comment": "Follow up", "priority": "Routine"}
    with patch("hyperscribe.scribe.commands.refer.ReferCommand") as mock_cmd:
        mock_cmd.Priority = MagicMock()
        mock_cmd.Priority.ROUTINE = "ROUTINE"
        mock_cmd.Priority.URGENT = "URGENT"
        mock_cmd.ClinicalQuestion = MagicMock()
        mock_cmd.ClinicalQuestion.__iter__ = MagicMock(return_value=iter([]))
        mock_cmd.return_value = MagicMock()
        with patch("hyperscribe.scribe.commands.refer.CLINICAL_QUESTION_MAP", {}):
            parser.build(data, "note-uuid", "cmd-uuid")

    call_kwargs = mock_cmd.call_args.kwargs
    assert call_kwargs["comment"] == "Follow up"
    assert call_kwargs["priority"] == "ROUTINE"
    assert call_kwargs["note_uuid"] == "note-uuid"


def test_build_urgent_priority() -> None:
    parser = ReferParser()
    data = {"comment": "Urgent referral", "priority": "Urgent"}
    with patch("hyperscribe.scribe.commands.refer.ReferCommand") as mock_cmd:
        mock_cmd.Priority = MagicMock()
        mock_cmd.Priority.ROUTINE = "ROUTINE"
        mock_cmd.Priority.URGENT = "URGENT"
        mock_cmd.ClinicalQuestion = MagicMock()
        mock_cmd.ClinicalQuestion.__iter__ = MagicMock(return_value=iter([]))
        mock_cmd.return_value = MagicMock()
        with patch("hyperscribe.scribe.commands.refer.CLINICAL_QUESTION_MAP", {}):
            parser.build(data, "note-uuid", "cmd-uuid")

    assert mock_cmd.call_args.kwargs["priority"] == "URGENT"


def test_build_no_priority() -> None:
    parser = ReferParser()
    data = {"comment": "Consult"}
    with patch("hyperscribe.scribe.commands.refer.ReferCommand") as mock_cmd:
        mock_cmd.Priority = MagicMock()
        mock_cmd.ClinicalQuestion = MagicMock()
        mock_cmd.ClinicalQuestion.__iter__ = MagicMock(return_value=iter([]))
        mock_cmd.return_value = MagicMock()
        with patch("hyperscribe.scribe.commands.refer.CLINICAL_QUESTION_MAP", {}):
            parser.build(data, "note-uuid", "cmd-uuid")

    assert mock_cmd.call_args.kwargs["priority"] is None


def test_build_clinical_question_mapping() -> None:
    parser = ReferParser()
    questions = [
        "Cognitive Assistance (Advice/Guidance)",
        "Assistance with Ongoing Management",
        "Specialized intervention",
        "Diagnostic Uncertainty",
    ]
    for q_value in questions:
        mock_enum = MagicMock()
        mock_enum.value = q_value
        data = {"clinical_question": q_value}
        with patch("hyperscribe.scribe.commands.refer.ReferCommand") as mock_cmd:
            mock_cmd.Priority = MagicMock()
            mock_cmd.ClinicalQuestion = MagicMock()
            mock_cmd.ClinicalQuestion.__iter__ = MagicMock(return_value=iter([]))
            mock_cmd.return_value = MagicMock()
            with patch("hyperscribe.scribe.commands.refer.CLINICAL_QUESTION_MAP", {q_value: mock_enum}):
                parser.build(data, "note-uuid", "cmd-uuid")

        assert mock_cmd.call_args.kwargs["clinical_question"] == mock_enum


def test_build_with_service_provider() -> None:
    parser = ReferParser()
    data = {
        "service_provider": {
            "first_name": "Jane",
            "last_name": "Smith",
            "specialty": "Cardiology",
            "practice_name": "Heart Clinic",
            "business_fax": "555-0100",
            "business_phone": "555-0101",
            "business_address": "123 Main St",
        }
    }
    with patch("hyperscribe.scribe.commands.refer.ReferCommand") as mock_cmd:
        mock_cmd.Priority = MagicMock()
        mock_cmd.ClinicalQuestion = MagicMock()
        mock_cmd.ClinicalQuestion.__iter__ = MagicMock(return_value=iter([]))
        mock_cmd.return_value = MagicMock()
        with patch("hyperscribe.scribe.commands.refer.CLINICAL_QUESTION_MAP", {}):
            with patch("hyperscribe.scribe.commands.refer.ServiceProvider") as mock_sp:
                mock_sp.return_value = "sp-obj"
                parser.build(data, "note-uuid", "cmd-uuid")

    mock_sp.assert_called_once_with(
        first_name="Jane",
        last_name="Smith",
        specialty="Cardiology",
        practice_name="Heart Clinic",
        business_fax="555-0100",
        business_phone="555-0101",
        business_address="123 Main St",
    )
    assert mock_cmd.call_args.kwargs["service_provider"] == "sp-obj"


def test_build_with_diagnosis_codes() -> None:
    parser = ReferParser()
    data = {"diagnosis_codes": ["E11.9", "I10"]}
    with patch("hyperscribe.scribe.commands.refer.ReferCommand") as mock_cmd:
        mock_cmd.Priority = MagicMock()
        mock_cmd.ClinicalQuestion = MagicMock()
        mock_cmd.ClinicalQuestion.__iter__ = MagicMock(return_value=iter([]))
        mock_cmd.return_value = MagicMock()
        with patch("hyperscribe.scribe.commands.refer.CLINICAL_QUESTION_MAP", {}):
            parser.build(data, "note-uuid", "cmd-uuid")

    assert mock_cmd.call_args.kwargs["diagnosis_codes"] == ["E11.9", "I10"]


def test_build_empty_data() -> None:
    parser = ReferParser()
    with patch("hyperscribe.scribe.commands.refer.ReferCommand") as mock_cmd:
        mock_cmd.Priority = MagicMock()
        mock_cmd.ClinicalQuestion = MagicMock()
        mock_cmd.ClinicalQuestion.__iter__ = MagicMock(return_value=iter([]))
        mock_cmd.return_value = MagicMock()
        with patch("hyperscribe.scribe.commands.refer.CLINICAL_QUESTION_MAP", {}):
            parser.build({}, "note-uuid", "cmd-uuid")

    call_kwargs = mock_cmd.call_args.kwargs
    assert call_kwargs["comment"] is None
    assert call_kwargs["priority"] is None
    assert call_kwargs["clinical_question"] is None
    assert call_kwargs["diagnosis_codes"] == []
    assert call_kwargs["service_provider"] is None
    assert call_kwargs["notes_to_specialist"] is None


def test_build_notes_and_comment() -> None:
    parser = ReferParser()
    data = {
        "notes_to_specialist": "Patient has complex history",
        "comment": "Internal note about referral",
    }
    with patch("hyperscribe.scribe.commands.refer.ReferCommand") as mock_cmd:
        mock_cmd.Priority = MagicMock()
        mock_cmd.ClinicalQuestion = MagicMock()
        mock_cmd.ClinicalQuestion.__iter__ = MagicMock(return_value=iter([]))
        mock_cmd.return_value = MagicMock()
        with patch("hyperscribe.scribe.commands.refer.CLINICAL_QUESTION_MAP", {}):
            parser.build(data, "note-uuid", "cmd-uuid")

    call_kwargs = mock_cmd.call_args.kwargs
    assert call_kwargs["notes_to_specialist"] == "Patient has complex history"
    assert call_kwargs["comment"] == "Internal note about referral"
