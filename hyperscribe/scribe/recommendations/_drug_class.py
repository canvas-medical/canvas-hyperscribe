"""Therapeutic-class gate for prescription-recommendation defaults.

Two recommendation behaviors must only fire for **chronic maintenance**
medications and be suppressed for everything else:

- suggesting a **non-zero refill count** for chronic maintenance meds — a single
  uniform default (``CHRONIC_REFILL_DEFAULT``), not a per-class number. Earlier
  Brigade Q4 medians varied by class (~3-5), but unexplained per-drug variation
  in a field the provider reviews adds confusion without proven benefit, so all
  chronic classes share one conservative default; acute/controlled stay at 0. And
- assuming a **30-day supply** to compute the dispense quantity when no duration
  was dictated (valid for a chronic once-daily med, dangerous over-supply for an
  acute antibiotic).

The authoritative source is FDB's per-NDC ``maintenance_drug_indicator`` + ETC
class (Q10), but that isn't exposed to the plugin yet. This module is the
**interim name-map shim** that classifies off the medication description — it
hits ~87.5% on Brigade and is seeded from the Q4 classes + the Q10d brand/generic
tail. It is intentionally biased toward **non-chronic**: ``chronic`` is the only
bucket that triggers the two behaviors, so misclassifying a chronic med as
acute/neither just falls back to the safe default (refills 0, no assumption),
while the reverse would over-supply. Match rules therefore run neither/acute
first and require precise stems for chronic.

When FDB class data reaches the plugin, swap ``classify`` to read the maintenance
flag + ETC group and keep the same bucket/refill contract.
"""

from __future__ import annotations

import re
from typing import NamedTuple

CHRONIC = "chronic"
ACUTE = "acute"
NEITHER = "neither"
UNKNOWN = "unknown"

# Single, uniform refill default for chronic maintenance meds (when the provider
# didn't state a count). Deliberately one number across all chronic classes:
# predictable, conservative (under-supply bias), and easy to communicate. The
# class table below still drives the chronic/acute gate and the 30-day quantity
# assumption — it just no longer varies the refill count per class.
CHRONIC_REFILL_DEFAULT = 3


class DrugClass(NamedTuple):
    bucket: str
    therapeutic_class: str
    refills: int  # CHRONIC_REFILL_DEFAULT for chronic classes; 0 otherwise


# Controlled substances — force refills to 0 regardless of therapeutic class.
# A belt-and-suspenders guard on top of the bucket logic (a controlled med should
# never get auto-suggested refills even if it reads as chronic, e.g. testosterone).
_CONTROLLED_RE = re.compile(
    r"\b("
    r"oxycodone|hydrocodone|hydromorphone|oxymorphone|morphine|codeine|tramadol|tapentadol|"
    r"fentanyl|methadone|buprenorphine|meperidine|percocet|norco|vicodin|dilaudid|oxycontin|"
    r"roxicodone|ultram|suboxone|subutex|"
    r"alprazolam|lorazepam|clonazepam|diazepam|temazepam|midazolam|triazolam|clorazepate|"
    r"xanax|ativan|klonopin|valium|restoril|halcion|"
    r"methylphenidate|amphetamine|lisdexamfetamine|dextroamphetamine|adderall|vyvanse|ritalin|concerta|"
    r"zolpidem|eszopiclone|zaleplon|ambien|lunesta|"
    r"phentermine|testosterone|pregabalin|lyrica|ketamine|modafinil|armodafinil"
    r")\b",
    re.IGNORECASE,
)

# Ordered (pattern, therapeutic_class, bucket, refills). First match wins.
# Neither/acute run before chronic so an ambiguous match errs to the safe side.
_RULES: list[tuple[re.Pattern[str], str, str, int]] = [
    # --- neither / do-not-auto-fill (controlled, PRN/symptomatic, supplies, topicals, bowel) ---
    (_CONTROLLED_RE, "controlled", NEITHER, 0),
    (
        re.compile(
            r"\b(ondansetron|zofran|promethazine|phenergan|meclizine|scopolamine|"
            r"sumatriptan|rizatriptan|imitrex|\w*triptan|"
            r"albuterol|levalbuterol|ipratropium|proair|ventolin|proventil|"
            r"ibuprofen|motrin|advil|naproxen|aleve|ketorolac|diclofenac|meloxicam|celecoxib|indomethacin|"
            r"acetaminophen|tylenol|cyclobenzaprine|flexeril|methocarbamol|tizanidine|baclofen|"
            r"hydroxyzine|diphenhydramine|benadryl|cetirizine|zyrtec|loratadine|claritin|"
            r"fexofenadine|allegra|azelastine|"
            r"loperamide|dicyclomine|simethicone|famotidine|pepcid|ranitidine|phenazopyridine|pyridium|"
            r"artificial tears|refresh|systane|"
            r"nitroglycerin|epinephrine|naloxone|glucagon"
            r")\b",
            re.IGNORECASE,
        ),
        "symptomatic_prn",
        NEITHER,
        0,
    ),
    (
        re.compile(
            r"\b(vitamin|cholecalciferol|ergocalciferol|cyanocobalamin|folic|ferrous|"
            r"calcium|magnesium|potassium chloride|melatonin|biotin|fish oil|omega|probiotic|"
            r"ensure|boost|libre|dexcom|lancet|needle|syringe|alcohol (pad|swab)|glucose"
            r")\b",
            re.IGNORECASE,
        ),
        "supplement_supply",
        NEITHER,
        0,
    ),
    (
        re.compile(
            r"\b(calmoseptine|aquaphor|petrolatum|lidocaine|lidoderm|hydrocortisone|"
            r"triamcinolone|clobetasol|mupirocin|clotrimazole|polyethylene glycol|miralax|"
            r"docusate|senna|bisacodyl|lactulose|emollient)\b",
            re.IGNORECASE,
        ),
        "topical_bowel",
        NEITHER,
        0,
    ),
    # --- acute (finite course) -> refills 0 ---
    (
        re.compile(
            r"\b(amoxicillin|augmentin|ampicillin|\w*cillin|\w*cycline|\w*floxacin|"
            r"cephalexin|keflex|cefdinir|cefuroxime|cefpodoxime|cefadroxil|"
            r"azithromycin|zithromax|clarithromycin|erythromycin|clindamycin|metronidazole|flagyl|"
            r"nitrofurantoin|macrobid|sulfamethoxazole|trimethoprim|bactrim|cipro|levaquin|"
            r"linezolid|fosfomycin)\b",
            re.IGNORECASE,
        ),
        "antibiotic",
        ACUTE,
        0,
    ),
    (
        re.compile(
            r"\b(acyclovir|zovirax|valacyclovir|valtrex|famciclovir|valganciclovir|ganciclovir|"
            r"oseltamivir|tamiflu|baloxavir)\b",
            re.IGNORECASE,
        ),
        "antiviral",
        ACUTE,
        0,
    ),
    (
        re.compile(
            r"\b(fluconazole|diflucan|\w*conazole|terbinafine|lamisil|nystatin|nystop|griseofulvin)\b",
            re.IGNORECASE,
        ),
        "antifungal",
        ACUTE,
        0,
    ),
    (
        re.compile(
            r"\b(prednisone|deltasone|prednisolone|methylprednisolone|medrol|dexamethasone)\b",
            re.IGNORECASE,
        ),
        "oral_steroid",
        ACUTE,
        0,
    ),
    (re.compile(r"\b(permethrin|ivermectin)\b", re.IGNORECASE), "scabies", ACUTE, 0),
    # --- chronic maintenance (precise stems) -> non-zero refills + 30-day assumption ---
    (
        re.compile(
            r"\b(\w*sartan|\w+pril|\w*dipine|\w+olol|"
            r"hydrochlorothiazide|chlorthalidone|furosemide|spironolactone|indapamide|triamterene|"
            r"clonidine|hydralazine|doxazosin|terazosin|"
            r"norvasc|lopressor|toprol|cozaar|diovan|benicar|microzide|lasix|coreg|hyzaar|lotrel)\b",
            re.IGNORECASE,
        ),
        "antihypertensive",
        CHRONIC,
        CHRONIC_REFILL_DEFAULT,
    ),
    (
        re.compile(
            r"\b(\w*vastatin|ezetimibe|lipitor|crestor|zocor|pravachol|livalo|zetia)\b",
            re.IGNORECASE,
        ),
        "statin",
        CHRONIC,
        CHRONIC_REFILL_DEFAULT,
    ),
    (
        re.compile(
            r"\b(sertraline|fluoxetine|escitalopram|citalopram|paroxetine|fluvoxamine|"
            r"venlafaxine|desvenlafaxine|duloxetine|vilazodone|vortioxetine|"
            r"zoloft|prozac|lexapro|celexa|paxil|effexor|cymbalta|pristiq)\b",
            re.IGNORECASE,
        ),
        "ssri_snri",
        CHRONIC,
        CHRONIC_REFILL_DEFAULT,
    ),
    (
        re.compile(
            r"\b(metformin|glipizide|glimepiride|glyburide|gliclazide|\w*gliptin|\w*gliflozin|"
            r"pioglitazone|rosiglitazone|repaglinide|nateglinide|acarbose|"
            r"semaglutide|dulaglutide|liraglutide|tirzepatide|exenatide|"
            r"glucophage|januvia|jardiance|farxiga|invokana|ozempic|wegovy|rybelsus|trulicity|"
            r"victoza|mounjaro|zepbound|actos)\b",
            re.IGNORECASE,
        ),
        "oral_antidiabetic",
        CHRONIC,
        CHRONIC_REFILL_DEFAULT,
    ),
    (
        re.compile(
            r"\b(\w*prazole|levothyroxine|synthroid|levoxyl|liothyronine|gabapentin|"
            r"warfarin|apixaban|eliquis|rivaroxaban|xarelto|dabigatran|pradaxa|edoxaban|clopidogrel|plavix|"
            r"quetiapine|risperidone|aripiprazole|olanzapine|lamotrigine|"
            r"tamsulosin|flomax|finasteride|proscar|propecia|dutasteride|oxybutynin|mirabegron|vibegron|"
            r"solifenacin|vesicare|tolterodine|detrol|"
            r"allopurinol|zyloprim|febuxostat|uloric|colchicine|alendronate|fosamax|risedronate|methenamine|"
            r"montelukast|singulair|donepezil|aricept|memantine|namenda|midodrine|estradiol|"
            r"latanoprost|xalatan|dorzolamide|timolol|brimonidine|"
            r"prilosec|nexium|protonix|dexilant|myrbetriq|gemtesa)\b",
            re.IGNORECASE,
        ),
        "chronic_other",
        CHRONIC,
        CHRONIC_REFILL_DEFAULT,
    ),
]


def classify(description: str | None) -> DrugClass:
    """Classify a medication description into a therapeutic bucket + refill default."""
    text = (description or "").lower()
    if not text.strip():
        return DrugClass(UNKNOWN, "unknown", 0)
    for pattern, therapeutic_class, bucket, refills in _RULES:
        if pattern.search(text):
            return DrugClass(bucket, therapeutic_class, refills)
    return DrugClass(UNKNOWN, "unknown", 0)


def is_controlled(description: str | None) -> bool:
    """True if the medication is a controlled substance (refills must stay 0)."""
    return bool(_CONTROLLED_RE.search((description or "").lower()))
