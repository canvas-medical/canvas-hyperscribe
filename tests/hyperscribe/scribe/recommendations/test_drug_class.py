from __future__ import annotations

import pytest

from hyperscribe.scribe.recommendations._drug_class import (
    ACUTE,
    CHRONIC,
    NEITHER,
    UNKNOWN,
    classify,
    is_controlled,
)


@pytest.mark.parametrize(
    "description, bucket, refills",
    [
        # chronic maintenance -> non-zero refill default (Q4)
        ("lisinopril 10 mg tablet", CHRONIC, 5),
        ("losartan 50 mg tablet", CHRONIC, 5),
        ("amlodipine 5 mg tablet", CHRONIC, 5),
        ("metoprolol succinate 25 mg tablet", CHRONIC, 5),
        ("hydrochlorothiazide 25 mg tablet", CHRONIC, 5),
        ("atorvastatin 20 mg tablet", CHRONIC, 4),
        ("rosuvastatin 10 mg tablet", CHRONIC, 4),
        ("sertraline 50 mg tablet", CHRONIC, 4),
        ("duloxetine 30 mg capsule", CHRONIC, 4),
        ("metformin 500 mg tablet", CHRONIC, 3),
        ("empagliflozin 10 mg tablet", CHRONIC, 3),
        ("sitagliptin 100 mg tablet", CHRONIC, 3),
        ("omeprazole 20 mg capsule", CHRONIC, 3),
        ("levothyroxine 75 mcg tablet", CHRONIC, 3),
        ("gabapentin 300 mg capsule", CHRONIC, 3),
        ("apixaban 5 mg tablet", CHRONIC, 3),
        ("tamsulosin 0.4 mg capsule", CHRONIC, 3),
        # acute -> 0
        ("amoxicillin 500 mg capsule", ACUTE, 0),
        ("azithromycin 250 mg tablet", ACUTE, 0),
        ("cephalexin 500 mg capsule", ACUTE, 0),
        ("ciprofloxacin 500 mg tablet", ACUTE, 0),
        ("doxycycline 100 mg capsule", ACUTE, 0),
        ("valacyclovir 1 gm tablet", ACUTE, 0),
        ("fluconazole 150 mg tablet", ACUTE, 0),
        ("prednisone 10 mg tablet", ACUTE, 0),
        # neither / do-not-auto-fill
        ("oxycodone 5 mg tablet", NEITHER, 0),
        ("alprazolam 0.5 mg tablet", NEITHER, 0),
        ("lisdexamfetamine 30 mg capsule", NEITHER, 0),
        ("ondansetron 4 mg tablet", NEITHER, 0),
        ("albuterol HFA inhaler", NEITHER, 0),
        ("ibuprofen 600 mg tablet", NEITHER, 0),
        ("cholecalciferol 2000 unit tablet", NEITHER, 0),
        ("calmoseptine ointment", NEITHER, 0),
        # unknown
        ("mysterydrug 5 mg tablet", UNKNOWN, 0),
        ("", UNKNOWN, 0),
    ],
)
def test_classify(description: str, bucket: str, refills: int) -> None:
    result = classify(description)
    assert result.bucket == bucket, f"{description} -> {result}"
    assert result.refills == refills, f"{description} -> {result}"


@pytest.mark.parametrize(
    "description, bucket, refills",
    [
        # brand names the generic list would miss (Q10d tail)
        ("norvasc 5 mg tablet", CHRONIC, 5),
        ("lipitor 40 mg tablet", CHRONIC, 4),
        ("crestor 10 mg tablet", CHRONIC, 4),
        ("zoloft 50 mg tablet", CHRONIC, 4),
        ("cymbalta 30 mg capsule", CHRONIC, 4),
        ("jardiance 10 mg tablet", CHRONIC, 3),
        ("ozempic 1 mg pen", CHRONIC, 3),
        ("synthroid 75 mcg tablet", CHRONIC, 3),
        ("eliquis 5 mg tablet", CHRONIC, 3),
        ("myrbetriq 25 mg tablet", CHRONIC, 3),
        ("zithromax 250 mg tablet", ACUTE, 0),
        ("diflucan 150 mg tablet", ACUTE, 0),
        ("zofran 4 mg tablet", NEITHER, 0),
        ("xanax 0.5 mg tablet", NEITHER, 0),
        ("ambien 10 mg tablet", NEITHER, 0),
    ],
)
def test_classify_brands(description: str, bucket: str, refills: int) -> None:
    result = classify(description)
    assert result.bucket == bucket, f"{description} -> {result}"
    assert result.refills == refills, f"{description} -> {result}"


def test_nystatin_is_not_a_statin() -> None:
    # "nystatin" contains "statin" — must not classify as a chronic statin.
    result = classify("nystatin oral suspension")
    assert result.bucket != CHRONIC


def test_is_controlled() -> None:
    assert is_controlled("oxycodone 5 mg tablet")
    assert is_controlled("alprazolam 0.5 mg tablet")
    assert is_controlled("lisdexamfetamine 30 mg capsule")
    assert is_controlled("pregabalin 75 mg capsule")
    assert not is_controlled("lisinopril 10 mg tablet")
    assert not is_controlled("amoxicillin 500 mg capsule")
