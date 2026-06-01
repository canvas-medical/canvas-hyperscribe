"""Problem-list-aware refinement of Nabla normalization output (KOALA-5603).

Nabla's ``/generate-normalized-data`` sometimes emits the unspecified parent
code within an ICD-10 family (e.g. ``E11.9`` for Type 2 diabetes without
complications) when the patient already has a more specific active condition
on file (e.g. ``E11.65`` Type 2 diabetes with hyperglycemia). The frontend's
diagnose -> assess belt requires an exact code match against the patient's
active conditions; the unspecified-parent code falls through that belt and
surfaces as a stand-alone diagnose suggestion that the provider must then
manually swap.

This module rewrites the unspecified-parent code on the Nabla side BEFORE
the frontend belt runs, so the belt's exact-match path becomes the success
path. The Nabla client and the frontend belt are deliberately untouched --
this is the narrowest hook point that fixes the bug.

PHI: callers must not log condition codes or display strings emitted by this
module beyond aggregate counts; the values are clinical data.
"""

from __future__ import annotations

from typing import NamedTuple

from hyperscribe.scribe.backend.models import CodingEntry, Condition


_ICD10_SYSTEM_TOKEN = "icd"


# NamedTuple instead of @dataclass: the plugin-runner sandbox can't evaluate
# the `@dataclass` decorator at module-load time because its module-loading
# strategy leaves ``cls.__module__`` outside ``sys.modules``, which trips
# dataclasses' internal ``_is_type`` check. NamedTuple from ``typing`` is
# safe (it's used elsewhere in this plugin — medication_detail, json_extract).
class ActivePatientCondition(NamedTuple):
    """A patient's active problem-list entry, narrowed to the fields we need
    for code-preference matching.

    :param condition_id: The patient-condition externally-exposable id. Not
        used by this module directly but threaded through so downstream
        callers (and tests) can correlate a rewrite with a specific entry.
    :param code: The ICD-10 code on the active problem list. May be either
        dotted (``"E11.65"``) or dotless (``"E1165"``); normalised on use.
        Empty string means "no ICD-10 coding" and disqualifies the entry
        from being used as a hint.
    :param display: The patient-condition display string. Used to populate
        the rewritten coding's display so the chart text matches the active
        problem-list entry rather than Nabla's parent display.
    :param system: The coding system that produced ``code`` (e.g. ``"ICD-10"``
        or ``"http://snomed.info/sct"``). Carried so the
        ``get_patient_conditions`` endpoint can serialize the same shape it
        always has; this module itself only uses entries whose code looks
        like ICD-10 (3-char family root match).
    """

    condition_id: str
    code: str
    display: str
    system: str = ""


def icd10_normalize(code: str) -> str:
    """Return the dotless, uppercase, whitespace-stripped form of an ICD-10
    code. We normalise consistently across both Nabla and patient sources so
    string comparisons don't trip on cosmetic differences (``e11.65`` vs
    ``E1165`` vs ``  E11.65 ``)."""
    return code.strip().replace(".", "").upper()


def _icd10_family_root(code: str) -> str:
    """Return the 3-character family root of a normalised ICD-10 code
    (``E1165`` -> ``E11``). The root is the canonical key for grouping codes
    that share a parent within the ICD-10 hierarchy."""
    return icd10_normalize(code)[:3]


def icd10_is_unspecified_parent_of(parent: str, child: str) -> bool:
    """Return ``True`` iff ``parent`` is an unspecified-parent of ``child``.

    Two parent shapes qualify as "unspecified":
      1. The bare 3-char root (``E11`` with no sub-classification at all).
      2. The 3-char root followed by ``9`` and optionally one more digit
         (``E11.9`` or ``E11.90``), which is the conventional ICD-10 bucket
         for "type 2 diabetes mellitus, without complications / unspecified".

    Ending in ``.89`` (e.g. ``Z99.89`` "other dependence") is NOT treated as
    unspecified -- it carries its own clinical meaning.

    "Of ``child``" requires ``child`` to be in the same family AND strictly
    more specific than ``parent`` -- otherwise nothing's gained by the
    rewrite. ``E11.9`` is NOT a parent of ``E11`` (would be a loss of
    specificity); ``E11.36`` is NOT a parent of ``E11.65`` (sibling codes).
    """
    p = icd10_normalize(parent)
    c = icd10_normalize(child)
    if not p or not c or p == c:
        return False
    if _icd10_family_root(p) != _icd10_family_root(c):
        return False
    if len(c) <= len(p):
        # Child is not strictly more specific -- don't claim parenthood.
        return False
    # Case 1: bare 3-char root (E11) -- parent of any longer code in family.
    if len(p) == 3:
        return True
    # Case 2: root + "9" optionally followed by another digit
    # ("E119" or "E1190" both qualify; "E1189" does NOT).
    tail = p[3:]
    if tail == "9":
        return True
    if len(tail) == 2 and tail[0] == "9" and tail[1].isdigit():
        return True
    return False


def _find_specific_active_match(
    nabla_code: str,
    active_conditions: list[ActivePatientCondition],
) -> ActivePatientCondition | None:
    """Return the first active condition that Nabla's ``nabla_code`` is the
    unspecified-parent of, or ``None`` when no such hint applies.

    First-match-wins is documented in the test suite -- the caller does not
    need to sort the active list; we accept whatever order the queryset
    produced (typically ``-onset_date`` from ``get_patient_conditions``)."""
    for active in active_conditions:
        if not active.code:
            continue
        if icd10_is_unspecified_parent_of(nabla_code, active.code):
            return active
    return None


def _rewrite_icd10_coding(
    coding: CodingEntry,
    active_match: ActivePatientCondition,
) -> CodingEntry:
    """Return a NEW ``CodingEntry`` with the active match's code and display.

    The system field is preserved as-is so downstream code that filters by
    ``"ICD-10"`` keeps working. The display is rewritten so the chart text
    matches the active problem-list entry rather than Nabla's parent label."""
    return CodingEntry(
        system=coding.system,
        code=active_match.code,
        display=active_match.display or coding.display,
    )


def prefer_patient_specific_codes(
    nabla_conditions: list[Condition],
    active_conditions: list[ActivePatientCondition],
) -> list[Condition]:
    """Rewrite ICD-10 codings on ``nabla_conditions`` to prefer the patient's
    more specific active problem-list code when Nabla emitted an unspecified
    parent.

    Pure function: input lists and ``Condition`` / ``CodingEntry`` instances
    are not mutated. The returned list contains fresh ``Condition`` objects
    when any coding is rewritten; identity-stable entries are reused when no
    rewrite applies.

    :param nabla_conditions: ``NormalizedData.conditions`` from Nabla.
    :param active_conditions: The patient's active problem-list entries,
        narrowed to ``ActivePatientCondition``. Pass an empty list when the
        patient has no problem list -- the function returns input unchanged.
    """
    if not active_conditions or not nabla_conditions:
        return nabla_conditions

    out: list[Condition] = []
    for condition in nabla_conditions:
        new_coding: list[CodingEntry] = []
        rewritten = False
        for coding in condition.coding:
            if _ICD10_SYSTEM_TOKEN in (coding.system or "").lower():
                active_match = _find_specific_active_match(coding.code, active_conditions)
                if active_match is not None:
                    new_coding.append(_rewrite_icd10_coding(coding, active_match))
                    rewritten = True
                    continue
            new_coding.append(coding)
        if rewritten:
            out.append(_to_view(condition)._replace(coding=new_coding).to_condition())
        else:
            out.append(condition)
    return out


# ---------------------------------------------------------------------------
# Internal: ``Condition`` is a hand-written class (not a dataclass), so to
# stay pure we copy fields explicitly via this small helper rather than
# mutating in-place. Keeping the helper private avoids leaking the
# bookkeeping detail into the module's public surface. NamedTuple instead
# of dataclass for plugin-sandbox compatibility (see ActivePatientCondition).
# ---------------------------------------------------------------------------


class _ConditionView(NamedTuple):
    display: str
    clinical_status: str
    coding: list[CodingEntry]
    corresponding_note_problem: str | None

    def to_condition(self) -> Condition:
        return Condition(
            display=self.display,
            clinical_status=self.clinical_status,
            coding=self.coding,
            corresponding_note_problem=self.corresponding_note_problem,
        )


def _to_view(condition: Condition) -> _ConditionView:
    return _ConditionView(
        display=condition.display,
        clinical_status=condition.clinical_status,
        coding=list(condition.coding),
        corresponding_note_problem=condition.corresponding_note_problem,
    )
