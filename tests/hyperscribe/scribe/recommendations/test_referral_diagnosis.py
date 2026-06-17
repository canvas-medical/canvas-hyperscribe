from __future__ import annotations

from typing import Any

from hyperscribe.scribe.recommendations._referral_diagnosis import link_referral_diagnoses


def _refer(indication: str | None, diagnosis_codes: list[str] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"refer_to_display": "Cardiology", "indication": indication}
    if diagnosis_codes is not None:
        data["diagnosis_codes"] = diagnosis_codes
    return {"command_type": "refer", "display": "Cardiology", "data": data}


def _diagnose(header: str, code: str | None, display: str = "") -> dict[str, Any]:
    return {
        "command_type": "diagnose",
        "data": {"condition_header": header, "icd10_code": code, "icd10_display": display},
    }


def test_links_code_from_diagnose_command() -> None:
    recs = [_refer("Shoulder muscle spasm")]
    commands = [_diagnose("Shoulder muscle spasm:", "M62.838", "Other muscle spasm")]
    link_referral_diagnoses(recs, commands, [], {})
    assert recs[0]["data"]["diagnosis_codes"] == ["M62.838"]


def test_diagnose_command_takes_priority_over_suggestions() -> None:
    recs = [_refer("Hypertension")]
    commands = [_diagnose("Hypertension:", "I10")]
    suggestions = {"Hypertension:": [{"code": "I150", "formatted_code": "I15.0"}]}
    link_referral_diagnoses(recs, commands, [], suggestions)
    assert recs[0]["data"]["diagnosis_codes"] == ["I10"]


def test_falls_back_to_suggestions_when_diagnose_uncoded() -> None:
    recs = [_refer("Shoulder muscle spasm")]
    # diagnose command exists but has no code yet
    commands = [_diagnose("Shoulder muscle spasm:", None)]
    suggestions = {"Shoulder muscle spasm:": [{"code": "M6281", "formatted_code": "M62.81"}]}
    link_referral_diagnoses(recs, commands, [], suggestions)
    assert recs[0]["data"]["diagnosis_codes"] == ["M62.81"]


def test_falls_back_to_unmatched_conditions() -> None:
    recs = [_refer("Asthma")]
    unmatched = [
        {
            "coding": [{"system": "icd10", "code": "J45.909", "display": "Unspecified asthma, uncomplicated"}],
            "corresponding_note_problem": "Asthma",
        }
    ]
    link_referral_diagnoses(recs, commands=[], unmatched_conditions=unmatched, diagnosis_suggestions={})
    assert recs[0]["data"]["diagnosis_codes"] == ["J45.909"]


def test_containment_match() -> None:
    # indication is a substring of the note's problem header (minor wording drift)
    recs = [_refer("muscle spasm")]
    commands = [_diagnose("Shoulder muscle spasm:", "M62.838")]
    link_referral_diagnoses(recs, commands, [], {})
    assert recs[0]["data"]["diagnosis_codes"] == ["M62.838"]


def test_partial_word_overlap_does_not_match() -> None:
    # conservative: "shoulder spasm" is NOT a substring of "shoulder muscle spasm",
    # so no code is linked (avoids guessing a wrong indication)
    recs = [_refer("shoulder spasm")]
    commands = [_diagnose("Shoulder muscle spasm:", "M62.838")]
    link_referral_diagnoses(recs, commands, [], {})
    assert "diagnosis_codes" not in recs[0]["data"]


def test_no_match_leaves_codes_absent() -> None:
    recs = [_refer("Cardiology consult")]
    commands = [_diagnose("Diabetes:", "E11.9")]
    link_referral_diagnoses(recs, commands, [], {})
    assert "diagnosis_codes" not in recs[0]["data"]


def test_no_indication_is_skipped() -> None:
    recs = [_refer(None)]
    commands = [_diagnose("Hypertension:", "I10")]
    link_referral_diagnoses(recs, commands, [], {})
    assert "diagnosis_codes" not in recs[0]["data"]


def test_existing_codes_preserved() -> None:
    recs = [_refer("Hypertension", diagnosis_codes=["I11.9"])]
    commands = [_diagnose("Hypertension:", "I10")]
    link_referral_diagnoses(recs, commands, [], {})
    # not overwritten
    assert recs[0]["data"]["diagnosis_codes"] == ["I11.9"]


def test_non_refer_proposals_untouched() -> None:
    med = {"command_type": "medication_statement", "data": {"indication": "Hypertension"}}
    recs = [med]
    commands = [_diagnose("Hypertension:", "I10")]
    link_referral_diagnoses(recs, commands, [], {})
    assert "diagnosis_codes" not in med["data"]
