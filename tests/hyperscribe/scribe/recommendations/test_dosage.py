from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import MagicMock

from canvas_sdk.clients.llms.structures import LlmResponse, LlmTokens

from hyperscribe.scribe.recommendations._dosage import (
    _dispense_form_class,
    _is_multistep_sig,
    derive_dispense_fields,
)
from hyperscribe.structures.medication_detail import MedicationDetail
from hyperscribe.structures.medication_detail_quantity import MedicationDetailQuantity


def _quantity(
    quantity: str = "9",
    ncpdp_code: str = "C48542",
    ncpdp_desc: str = "Tablet",
    clinical_desc: str = "Tablet",
    ndc: str = "12345678901",
) -> MedicationDetailQuantity:
    return MedicationDetailQuantity(
        quantity=quantity,
        representative_ndc=ndc,
        clinical_quantity_description=clinical_desc,
        ncpdp_quantity_qualifier_code=ncpdp_code,
        ncpdp_quantity_qualifier_description=ncpdp_desc,
    )


def _detail(
    quantities: list[MedicationDetailQuantity] | None = None,
    description: str = "Testmed 10 mg tablet",
) -> MedicationDetail:
    # Default description is deliberately class-UNKNOWN so form/quantity mechanics
    # tests aren't perturbed by the chronic gate; pass a real drug name to exercise
    # classification.
    return MedicationDetail(
        fdb_code="99999",
        description=description,
        quantities=quantities if quantities is not None else [_quantity()],
    )


def _client(response_data: dict | None = None, code: HTTPStatus = HTTPStatus.OK) -> MagicMock:
    client = MagicMock()
    if response_data is not None:
        client.request.return_value = LlmResponse(
            code=code,
            response=json.dumps(response_data),
            tokens=LlmTokens(prompt=10, generated=10),
        )
    return client


# --- deterministic dispense form -------------------------------------------------


def test_type_to_dispense_is_deterministic_encoded_value() -> None:
    client = _client()
    out = derive_dispense_fields(
        _detail(),
        stated_sig="Take 1 tablet daily",
        stated_days_supply=None,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    # Encoded as ndc|qty|code so order-row.js pre-selects the dropdown option.
    assert out["type_to_dispense"] == "12345678901|9|C48542"
    assert out["type_to_dispense_label"] == "Tablet"
    # No days supply -> cannot derive quantity, must not call the model.
    client.request.assert_not_called()
    assert "quantity_to_dispense" not in out


def test_label_falls_back_to_ncpdp_description() -> None:
    detail = _detail([_quantity(clinical_desc="", ncpdp_desc="Milliliter")])
    out = derive_dispense_fields(
        detail,
        stated_sig=None,
        stated_days_supply=None,
        stated_quantity=None,
        stated_refills=None,
        client=_client(),
    )
    assert out["type_to_dispense_label"] == "Milliliter"


def test_no_dispense_form_when_unresolved() -> None:
    out = derive_dispense_fields(
        None,
        stated_sig="Take 1 daily",
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=_client(),
    )
    assert "type_to_dispense" not in out
    assert "quantity_to_dispense" not in out


# --- refills ---------------------------------------------------------------------


def test_refills_default_to_zero() -> None:
    out = derive_dispense_fields(
        _detail(),
        stated_sig=None,
        stated_days_supply=None,
        stated_quantity=None,
        stated_refills=None,
        client=_client(),
    )
    assert out["refills"] == 0


def test_stated_refills_passed_through() -> None:
    out = derive_dispense_fields(
        _detail(),
        stated_sig=None,
        stated_days_supply=None,
        stated_quantity=None,
        stated_refills=3,
        client=_client(),
    )
    assert out["refills"] == 3


# --- stated quantity pass-through ------------------------------------------------


def test_stated_quantity_passed_through_without_llm() -> None:
    client = _client()
    out = derive_dispense_fields(
        _detail(),
        stated_sig="Take 1 tablet daily",
        stated_days_supply=30,
        stated_quantity="30",
        stated_refills=None,
        client=client,
    )
    assert out["quantity_to_dispense"] == "30"
    client.request.assert_not_called()


def test_stated_quantity_normalizes_trailing_zeros() -> None:
    out = derive_dispense_fields(
        _detail(),
        stated_sig="Take 1 daily",
        stated_days_supply=30,
        stated_quantity="30.00",
        stated_refills=None,
        client=_client(),
    )
    assert out["quantity_to_dispense"] == "30"


def test_invalid_stated_quantity_falls_back_to_derivation() -> None:
    client = _client({"derivable": True, "unitsPerDose": 1, "dosesPerDay": 1, "quantityToDispense": 30})
    out = derive_dispense_fields(
        _detail(),
        stated_sig="Take 1 tablet daily",
        stated_days_supply=30,
        stated_quantity="not-a-number",
        stated_refills=None,
        client=client,
    )
    assert out["quantity_to_dispense"] == "30"
    client.request.assert_called_once()


# --- derivation guardrails -------------------------------------------------------


def test_derives_discrete_quantity_as_integer() -> None:
    client = _client(
        {"derivable": True, "unitsPerDose": 1, "dosesPerDay": 2, "quantityToDispense": 60, "discrete": True}
    )
    out = derive_dispense_fields(
        _detail(),
        stated_sig="Take 1 tablet twice daily",
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert out["quantity_to_dispense"] == "60"


def test_derives_continuous_quantity_as_decimal() -> None:
    detail = _detail([_quantity(ncpdp_code="C28254", ncpdp_desc="Milliliter", clinical_desc="Milliliter")])
    client = _client(
        {"derivable": True, "unitsPerDose": 5, "dosesPerDay": 3, "quantityToDispense": 150, "discrete": False}
    )
    out = derive_dispense_fields(
        detail,
        stated_sig="Take 5 mL three times daily",
        stated_days_supply=10,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert out["quantity_to_dispense"] == "150"


def test_not_derivable_leaves_quantity_blank() -> None:
    client = _client({"derivable": False})
    out = derive_dispense_fields(
        _detail(),
        stated_sig="Take as directed",
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out


def test_cross_check_mismatch_leaves_quantity_blank() -> None:
    # Model reports 1x daily (=> arithmetic 30) but claims 90 to dispense: a
    # >20% internal contradiction, so we distrust it and leave the field blank.
    client = _client({"derivable": True, "unitsPerDose": 1, "dosesPerDay": 1, "quantityToDispense": 90})
    out = derive_dispense_fields(
        _detail(),
        stated_sig="Take 1 tablet daily",
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out


def test_implausible_quantity_dropped() -> None:
    client = _client({"derivable": True, "unitsPerDose": 200, "dosesPerDay": 1, "quantityToDispense": 6000})
    out = derive_dispense_fields(
        _detail(),
        stated_sig="Take 200 tablets daily",
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out


def test_no_sig_skips_derivation() -> None:
    client = _client()
    out = derive_dispense_fields(
        _detail(),
        stated_sig=None,
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out
    client.request.assert_not_called()


def test_placeholder_sig_skips_derivation() -> None:
    client = _client()
    out = derive_dispense_fields(
        _detail(),
        stated_sig="<UNKNOWN>",
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out
    client.request.assert_not_called()


def test_llm_error_leaves_quantity_blank() -> None:
    client = _client({"derivable": True, "unitsPerDose": 1, "dosesPerDay": 1}, code=HTTPStatus.INTERNAL_SERVER_ERROR)
    out = derive_dispense_fields(
        _detail(),
        stated_sig="Take 1 daily",
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out


def test_llm_exception_leaves_quantity_blank() -> None:
    client = MagicMock()
    client.request.side_effect = Exception("boom")
    out = derive_dispense_fields(
        _detail(),
        stated_sig="Take 1 daily",
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out


def test_malformed_response_leaves_quantity_blank() -> None:
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.OK, response="not json", tokens=LlmTokens(prompt=1, generated=1)
    )
    out = derive_dispense_fields(
        _detail(),
        stated_sig="Take 1 daily",
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out


def test_zero_frequency_leaves_quantity_blank() -> None:
    client = _client({"derivable": True, "unitsPerDose": 0, "dosesPerDay": 1, "quantityToDispense": 0})
    out = derive_dispense_fields(
        _detail(),
        stated_sig="Take 1 daily",
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out


# --- Wave 1: dispense-form classification ----------------------------------------


def test_form_class_buckets() -> None:
    assert _dispense_form_class(_quantity(clinical_desc="30 gram tube", ncpdp_desc="Gram")) == "container"
    assert _dispense_form_class(_quantity(clinical_desc="100 mL bottle", ncpdp_desc="Milliliter")) == "container"
    assert _dispense_form_class(_quantity(clinical_desc="albuterol inhaler", ncpdp_desc="Gram")) == "container"
    assert _dispense_form_class(_quantity(clinical_desc="6 tablet blister pack", ncpdp_desc="Tablet")) == "container"
    assert _dispense_form_class(_quantity(clinical_desc="0.5 mL syringe", ncpdp_desc="Milliliter")) == "injectable"
    assert _dispense_form_class(_quantity(clinical_desc="insulin pen", ncpdp_desc="Milliliter")) == "injectable"
    assert _dispense_form_class(_quantity(clinical_desc="tablet", ncpdp_desc="Tablet")) == "countable"
    assert _dispense_form_class(_quantity(clinical_desc="Milliliter", ncpdp_desc="Milliliter")) == "volume_mass"


def test_pen_token_not_matched_inside_word() -> None:
    # "suspension" contains the letters "pen" — must not classify as injectable.
    assert _dispense_form_class(_quantity(clinical_desc="oral suspension", ncpdp_desc="Milliliter")) != "injectable"


def test_container_form_dispenses_one_without_llm() -> None:
    client = _client()
    detail = _detail([_quantity(clinical_desc="30 gram tube", ncpdp_desc="Gram")])
    out = derive_dispense_fields(
        detail,
        stated_sig="apply a thin layer twice daily",
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert out["quantity_to_dispense"] == "1"
    client.request.assert_not_called()


def test_ml_bottle_is_container_qty_one() -> None:
    detail = _detail([_quantity(clinical_desc="100 mL bottle", ncpdp_desc="Milliliter", ncpdp_code="C28254")])
    out = derive_dispense_fields(
        detail,
        stated_sig="take 10 mL twice daily",
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=_client(),
    )
    assert out["quantity_to_dispense"] == "1"


def test_injectable_leaves_quantity_blank() -> None:
    client = _client()
    detail = _detail([_quantity(clinical_desc="0.5 mL syringe", ncpdp_desc="Milliliter", ncpdp_code="C28254")])
    out = derive_dispense_fields(
        detail,
        stated_sig="inject 0.5 mL subcutaneously once weekly",
        stated_days_supply=28,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out
    client.request.assert_not_called()


def test_multistep_sig_leaves_quantity_blank() -> None:
    client = _client()
    out = derive_dispense_fields(
        _detail(),
        stated_sig="take 2 tablets on day 1, then 1 tablet daily on days 2-5",
        stated_days_supply=5,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out
    client.request.assert_not_called()


def test_dose_range_sig_leaves_quantity_blank() -> None:
    client = _client()
    out = derive_dispense_fields(
        _detail(),
        stated_sig="take 1-2 tablets twice daily",
        stated_days_supply=30,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out
    client.request.assert_not_called()


def test_is_multistep_sig_direct() -> None:
    assert _is_multistep_sig("take 2 tablets then 1 daily")
    assert _is_multistep_sig("1-2 tablets daily")
    assert _is_multistep_sig("apply on days 2-5")
    assert not _is_multistep_sig("take 1 tablet twice daily")
    assert not _is_multistep_sig("take 10 mL by mouth twice daily for 10 days")


# --- Wave 2: chronic gate (refills + 30-day assumption) --------------------------


def test_chronic_no_days_assumes_30_and_computes() -> None:
    client = _client({"derivable": True, "unitsPerDose": 1, "dosesPerDay": 1, "quantityToDispense": 30})
    out = derive_dispense_fields(
        _detail(description="lisinopril 10 mg tablet"),
        stated_sig="1 tablet by mouth once daily",
        stated_days_supply=None,  # no duration dictated -> assume 30
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert out["quantity_to_dispense"] == "30"
    assert out["refills"] == 5  # antihypertensive default
    # The assumption feeds the quantity math but is NOT written to days_supply.
    assert "days_supply" not in out
    client.request.assert_called_once()


def test_acute_no_days_stays_blank() -> None:
    client = _client()
    out = derive_dispense_fields(
        _detail(description="amoxicillin 500 mg capsule"),
        stated_sig="1 capsule by mouth three times daily",
        stated_days_supply=None,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out  # no assumption for acute
    assert out["refills"] == 0
    client.request.assert_not_called()


def test_chronic_refill_defaults_by_class() -> None:
    cases = [
        ("lisinopril 10 mg tablet", 5),
        ("atorvastatin 20 mg tablet", 4),
        ("sertraline 50 mg tablet", 4),
        ("metformin 500 mg tablet", 3),
        ("omeprazole 20 mg capsule", 3),
    ]
    for description, expected in cases:
        out = derive_dispense_fields(
            _detail(description=description),
            stated_sig="1 by mouth once daily",
            stated_days_supply=90,
            stated_quantity="90",  # stated quantity -> isolates the refill default
            stated_refills=None,
            client=_client(),
        )
        assert out["refills"] == expected, description


def test_controlled_substance_forces_zero_refills() -> None:
    out = derive_dispense_fields(
        _detail(description="alprazolam 1 mg tablet"),
        stated_sig="1 tablet twice daily",
        stated_days_supply=30,
        stated_quantity="60",
        stated_refills=None,
        client=_client(),
    )
    assert out["refills"] == 0


def test_unknown_class_no_days_stays_blank() -> None:
    client = _client()
    out = derive_dispense_fields(
        _detail(description="mysterydrug 5 mg tablet"),
        stated_sig="1 tablet once daily",
        stated_days_supply=None,
        stated_quantity=None,
        stated_refills=None,
        client=client,
    )
    assert "quantity_to_dispense" not in out
    assert out["refills"] == 0
    client.request.assert_not_called()


def test_stated_refills_override_chronic_default() -> None:
    out = derive_dispense_fields(
        _detail(description="lisinopril 10 mg tablet"),
        stated_sig="1 tablet once daily",
        stated_days_supply=90,
        stated_quantity="90",
        stated_refills=2,
        client=_client(),
    )
    assert out["refills"] == 2
