# Charge Capture Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let providers, in the scribe "Accept & Sign" matrix, associate charges to diagnoses (diagnosis pointers), reorder diagnosis rank, and add CPT modifiers per charge — written deterministically onto `BillingLineItem`s with no event handlers — and keep it all working through the amendment flow.

**Architecture:** Charges stay `PerformCommand`s and ride the existing command/amendment pipeline. A new, sequenced `/enrich-charges` endpoint (called by the frontend right after `/insert-commands` succeeds) resolves diagnosis links to `Assessment` ids, finds each charge's auto-created `BillingLineItem` precisely by `command_id`, and emits `Update`/`Add`/`RemoveBillingLineItem` effects. Diagnosis rank = command-insertion order. No `POST_COMMIT` / `POST_ENTER_IN_ERROR` handlers (this is the deliberate departure from PR #257).

**Tech Stack:** Python 3.12, Canvas SDK, Django ORM models (read), SDK Effects (write), pytest + mypy. Frontend: Preact + `htm` via esm.sh (no build step, ES-module imports, no JS test runner).

**Design spec:** `docs/superpowers/specs/2026-06-05-charge-capture-design.md` (read it first).

---

## Conventions in this codebase (read before starting)

- **Effects are returned from SimpleAPI endpoints**, mixed into a `list[Union[Response, Effect]]`. See existing endpoints in `hyperscribe/scribe/api/session_view.py` (e.g. `post_save_summary`). They are NOT `.apply()`-ed inside a `BaseHandler.compute`; the SimpleAPI return list carries them.
- **Auth:** mutating endpoints call `_authorize_edit(note_uuid, self.request)` (returns a `JSONResponse` to short-circuit, or `None`). See `session_view.py:107`.
- **Audit:** call `audit_event(note_uuid, "EVENT_TYPE", {...structural keys only, never free-text PHI...})`. See `session_view.py:172`.
- **Tests:** unit-style, no DB. Patch SDK models with `unittest.mock.patch("module.path.ModelName")`. Endpoint tests build the view with the `_helper_instance()` pattern and set `view.request = SimpleNamespace(...)`. See `tests/hyperscribe/scribe/api/test_session_view_charges.py`.
- **Run a single test:** `uv run pytest tests/path::test_name -v`. **All tests:** `uv run pytest tests/`. **Types:** `uv run mypy --config-file=mypy.ini .`. **Coverage:** `uv run pytest tests/ --cov=. ` (repo bar ≈90%).
- **Commit cadence:** one commit per task (after its tests pass). End commit messages with the `Co-Authored-By` trailer used on this branch.

## File structure (created / modified)

**Backend — new (`hyperscribe/scribe/charges/`):**
- `hyperscribe/scribe/charges/__init__.py` — package marker.
- `hyperscribe/scribe/charges/validation.py` — shared validator (caps + ≥1-pointer rule). Pure functions.
- `hyperscribe/scribe/charges/enrichment.py` — resolver: assessment index, BLI lookup, modifier coding, effect building.

**Backend — modified:**
- `hyperscribe/scribe/api/session_view.py` — add `post_enrich_charges` (`@api.post("/enrich-charges")`).

**Backend — tests (new):**
- `tests/hyperscribe/scribe/charges/__init__.py`
- `tests/hyperscribe/scribe/charges/test_validation.py`
- `tests/hyperscribe/scribe/charges/test_enrichment.py`
- extend `tests/hyperscribe/scribe/api/test_session_view_charges.py`

**Frontend — new:**
- `hyperscribe/scribe/static/charge-matrix.js` — the matrix component.

**Frontend — modified:**
- `hyperscribe/scribe/static/soap-group.js` — render `ChargeMatrix` in the CHARGES section.
- `hyperscribe/scribe/static/summary.js` — matrix state, diagnosis ordering at insert, `/enrich-charges` call, sign-gating, amend locked rules.
- `hyperscribe/scribe/static/styles.css` (or the existing stylesheet the matrix lives near) — matrix tokens/styles.

> **Concern isolation:** validator (pointers/caps), modifier coding, rank ordering, and amend rules are kept as separable units so any one can be reverted without unwinding the others (spec §11).

---

## Task 1: Charge enrichment validator

**Files:**
- Create: `hyperscribe/scribe/charges/__init__.py`
- Create: `hyperscribe/scribe/charges/validation.py`
- Create: `tests/hyperscribe/scribe/charges/__init__.py`
- Test: `tests/hyperscribe/scribe/charges/test_validation.py`

- [ ] **Step 1: Create package markers**

```bash
mkdir -p hyperscribe/scribe/charges tests/hyperscribe/scribe/charges
printf '' > hyperscribe/scribe/charges/__init__.py
printf '' > tests/hyperscribe/scribe/charges/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `tests/hyperscribe/scribe/charges/test_validation.py`:

```python
from hyperscribe.scribe.charges.validation import (
    MAX_DIAGNOSIS_POINTERS,
    MAX_MODIFIERS,
    validate_charge_enrichment,
)


def _charge(command_uuid="c1", pointers=("M25.511",), modifiers=()):
    return {
        "command_uuid": command_uuid,
        "diagnosis_pointers": [{"command_uuid": f"d{i}", "icd10_code": p} for i, p in enumerate(pointers)],
        "modifiers": list(modifiers),
    }


def test_valid_charge_has_no_errors():
    assert validate_charge_enrichment([_charge()]) == []


def test_charge_with_zero_pointers_is_invalid():
    errors = validate_charge_enrichment([_charge(pointers=())])
    assert errors == [{"command_uuid": "c1", "errors": ["at_least_one_pointer"]}]


def test_charge_over_pointer_cap_is_invalid():
    pointers = tuple(f"A0{i}.0" for i in range(MAX_DIAGNOSIS_POINTERS + 1))
    errors = validate_charge_enrichment([_charge(pointers=pointers)])
    assert errors == [{"command_uuid": "c1", "errors": ["too_many_pointers"]}]


def test_charge_over_modifier_cap_is_invalid():
    modifiers = [str(n) for n in range(MAX_MODIFIERS + 1)]
    errors = validate_charge_enrichment([_charge(modifiers=modifiers)])
    assert errors == [{"command_uuid": "c1", "errors": ["too_many_modifiers"]}]


def test_multiple_violations_on_one_charge_are_all_reported():
    pointers = tuple(f"A0{i}.0" for i in range(MAX_DIAGNOSIS_POINTERS + 1))
    modifiers = [str(n) for n in range(MAX_MODIFIERS + 1)]
    errors = validate_charge_enrichment([_charge(pointers=pointers, modifiers=modifiers)])
    assert errors == [{"command_uuid": "c1", "errors": ["too_many_pointers", "too_many_modifiers"]}]


def test_each_invalid_charge_reported_separately():
    errors = validate_charge_enrichment([_charge("a", pointers=()), _charge("b")])
    assert errors == [{"command_uuid": "a", "errors": ["at_least_one_pointer"]}]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/hyperscribe/scribe/charges/test_validation.py -v`
Expected: FAIL — `ModuleNotFoundError: hyperscribe.scribe.charges.validation`.

- [ ] **Step 4: Write the implementation**

Create `hyperscribe/scribe/charges/validation.py`:

```python
"""Shared validation for charge enrichment (diagnosis pointers + modifiers).

This is the single source of truth used by BOTH the frontend (to gate the
"Accept and sign" button) and the ``/enrich-charges`` write path (to reject
invalid payloads defensively). The caps come from CMS-1500 box 24E (≤4
diagnosis pointers per service line) and the 4-modifier line limit.
"""

from __future__ import annotations

from typing import Any

MAX_DIAGNOSIS_POINTERS = 4
MAX_MODIFIERS = 4


def validate_charge_enrichment(charges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a list of ``{command_uuid, errors:[...]}`` for charges that
    violate a rule. An empty list means every charge is valid.

    Rules (order of error codes is stable for test/UI consumption):
      * ``at_least_one_pointer`` — a charge must point to ≥1 diagnosis.
      * ``too_many_pointers``    — ≤ ``MAX_DIAGNOSIS_POINTERS`` pointers.
      * ``too_many_modifiers``   — ≤ ``MAX_MODIFIERS`` modifiers.
    """
    failures: list[dict[str, Any]] = []
    for charge in charges:
        errors: list[str] = []
        pointers = charge.get("diagnosis_pointers") or []
        modifiers = charge.get("modifiers") or []
        if len(pointers) < 1:
            errors.append("at_least_one_pointer")
        if len(pointers) > MAX_DIAGNOSIS_POINTERS:
            errors.append("too_many_pointers")
        if len(modifiers) > MAX_MODIFIERS:
            errors.append("too_many_modifiers")
        if errors:
            failures.append({"command_uuid": charge.get("command_uuid", ""), "errors": errors})
    return failures
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/hyperscribe/scribe/charges/test_validation.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Type-check and commit**

```bash
uv run mypy --config-file=mypy.ini hyperscribe/scribe/charges/validation.py
git add hyperscribe/scribe/charges/__init__.py hyperscribe/scribe/charges/validation.py \
        tests/hyperscribe/scribe/charges/__init__.py tests/hyperscribe/scribe/charges/test_validation.py
git commit -m "$(cat <<'EOF'
feat(charges): shared validator for diagnosis-pointer + modifier caps

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Assessment index (icd10 → assessment ids)

**Files:**
- Create: `hyperscribe/scribe/charges/enrichment.py`
- Test: `tests/hyperscribe/scribe/charges/test_enrichment.py`

This task builds only the assessment-resolution helper; effect building comes in Task 3.

- [ ] **Step 1: Write the failing tests**

Create `tests/hyperscribe/scribe/charges/test_enrichment.py`:

```python
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
    mock_assessment.objects.filter.assert_called_once_with(note=note, entered_in_error__isnull=True)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hyperscribe/scribe/charges/test_enrichment.py -v`
Expected: FAIL — `ImportError` (module/functions don't exist).

- [ ] **Step 3: Write the implementation**

Create `hyperscribe/scribe/charges/enrichment.py`:

```python
"""Deterministic charge enrichment: resolve diagnosis pointers + modifiers
onto the BillingLineItem each PerformCommand creates.

No event handlers. This runs synchronously from the ``/enrich-charges``
endpoint AFTER charges have committed, so every Assessment and BillingLineItem
already exists when we resolve. See design spec §3-§5.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from canvas_sdk.effects import Effect
from canvas_sdk.effects.billing_line_item import (
    RemoveBillingLineItem,
    UpdateBillingLineItem,
)
from canvas_sdk.v1.data.assessment import Assessment
from canvas_sdk.v1.data.billing import BillingLineItem, BillingLineItemStatus
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.note import Note
from logger import log

# The Coding system CMS modifiers are expressed under. Matches the Canvas SDK
# billing-line-item effect docs example. VERIFY ON INSTANCE (spec §9.3) before
# relying on this exact string.
CPT_MODIFIER_SYSTEM = "http://www.ama-assn.org/go/cpt"


def _normalize_icd10(code: str | None) -> str:
    return (code or "").strip().replace(".", "").upper()


def build_assessment_index(note: Any) -> dict[str, list[str]]:
    """Map normalized ICD-10 code -> [Assessment.id, ...] for the note.

    Excludes entered-in-error assessments. The default Assessment manager
    already filters ``deleted=False`` (AuditedModel). ``prefetch_related`` on
    ``condition__codings`` collapses the per-assessment coding reads to avoid
    an N+1.
    """
    index: dict[str, list[str]] = defaultdict(list)
    assessments = Assessment.objects.filter(
        note=note, entered_in_error__isnull=True
    ).prefetch_related("condition__codings")
    for assessment in assessments:
        condition = assessment.condition
        if condition is None:
            continue
        for coding in condition.codings.all():
            index[_normalize_icd10(coding.code)].append(str(assessment.id))
    return dict(index)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/hyperscribe/scribe/charges/test_enrichment.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Type-check and commit**

```bash
uv run mypy --config-file=mypy.ini hyperscribe/scribe/charges/enrichment.py
git add hyperscribe/scribe/charges/enrichment.py tests/hyperscribe/scribe/charges/test_enrichment.py
git commit -m "$(cat <<'EOF'
feat(charges): assessment index for diagnosis-pointer resolution

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Enrichment effect builder

**Files:**
- Modify: `hyperscribe/scribe/charges/enrichment.py`
- Test: `tests/hyperscribe/scribe/charges/test_enrichment.py`

Builds the function that turns a validated payload into `Update`/`Remove` effects, resolving pointers via the Task 2 index and locating each charge's BLI by `command_id`.

- [ ] **Step 1: Add the failing tests**

Append to `tests/hyperscribe/scribe/charges/test_enrichment.py`:

```python
from hyperscribe.scribe.charges.enrichment import (
    CPT_MODIFIER_SYSTEM,
    build_charge_enrichment_effects,
)


def _patch_note(mock_note, dbid=7):
    mock_note.objects.get.return_value = SimpleNamespace(dbid=dbid)


@patch("hyperscribe.scribe.charges.enrichment.UpdateBillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
@patch("hyperscribe.scribe.charges.enrichment.build_assessment_index")
@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_update_effect_built_for_charge_with_pointer_and_modifier(
    mock_note, mock_index, mock_command, mock_bli, mock_update
):
    _patch_note(mock_note)
    mock_index.return_value = {"M25511": ["aid-1"]}
    mock_command.objects.get.return_value = SimpleNamespace(dbid=42)
    bli = SimpleNamespace(id="bli-1")
    bli_qs = MagicMock()
    bli_qs.first.return_value = bli
    mock_bli.objects.filter.return_value = bli_qs
    mock_update.return_value = SimpleNamespace(apply=lambda: "UPDATE_EFFECT")

    charges = [{
        "command_uuid": "perform-1",
        "diagnosis_pointers": [{"command_uuid": "d0", "icd10_code": "M25.511"}],
        "modifiers": ["25"],
    }]
    effects, enriched, errors = build_charge_enrichment_effects(charges, [], "note-uuid")

    assert effects == ["UPDATE_EFFECT"]
    assert errors == []
    assert enriched == [{"command_uuid": "perform-1", "billing_line_item_id": "bli-1",
                         "assessment_ids": ["aid-1"], "modifiers": ["25"]}]
    mock_update.assert_called_once_with(
        billing_line_item_id="bli-1",
        assessment_ids=["aid-1"],
        modifiers=[{"code": "25", "system": CPT_MODIFIER_SYSTEM}],
    )
    mock_bli.objects.filter.assert_called_once_with(
        note=mock_note.objects.get.return_value, command_id=42,
        status=mock_bli_status_active(mock_bli),
    )


def mock_bli_status_active(mock_bli):
    # BillingLineItemStatus.ACTIVE is itself patched-through; resolve the real value.
    from canvas_sdk.v1.data.billing import BillingLineItemStatus
    return BillingLineItemStatus.ACTIVE


@patch("hyperscribe.scribe.charges.enrichment.UpdateBillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
@patch("hyperscribe.scribe.charges.enrichment.build_assessment_index")
@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_missing_bli_records_error_and_no_effect(
    mock_note, mock_index, mock_command, mock_bli, mock_update
):
    _patch_note(mock_note)
    mock_index.return_value = {"M25511": ["aid-1"]}
    mock_command.objects.get.return_value = SimpleNamespace(dbid=42)
    bli_qs = MagicMock()
    bli_qs.first.return_value = None
    mock_bli.objects.filter.return_value = bli_qs

    charges = [{
        "command_uuid": "perform-1",
        "diagnosis_pointers": [{"command_uuid": "d0", "icd10_code": "M25.511"}],
        "modifiers": [],
    }]
    effects, enriched, errors = build_charge_enrichment_effects(charges, [], "note-uuid")

    assert effects == []
    assert enriched == []
    assert errors == [{"command_uuid": "perform-1", "reason": "billing_line_item_not_found"}]
    mock_update.assert_not_called()


@patch("hyperscribe.scribe.charges.enrichment.RemoveBillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.BillingLineItem")
@patch("hyperscribe.scribe.charges.enrichment.Command")
@patch("hyperscribe.scribe.charges.enrichment.build_assessment_index")
@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_removed_charge_emits_remove_effect(
    mock_note, mock_index, mock_command, mock_bli, mock_remove
):
    _patch_note(mock_note)
    mock_index.return_value = {}
    mock_command.objects.get.return_value = SimpleNamespace(dbid=99)
    bli = SimpleNamespace(id="bli-9")
    bli_qs = MagicMock()
    bli_qs.first.return_value = bli
    mock_bli.objects.filter.return_value = bli_qs
    mock_remove.return_value = SimpleNamespace(apply=lambda: "REMOVE_EFFECT")

    effects, enriched, errors = build_charge_enrichment_effects([], ["perform-removed"], "note-uuid")

    assert effects == ["REMOVE_EFFECT"]
    assert enriched == []
    assert errors == []
    mock_remove.assert_called_once_with(billing_line_item_id="bli-9")


@patch("hyperscribe.scribe.charges.enrichment.Note")
def test_unknown_note_returns_error(mock_note):
    mock_note.DoesNotExist = Exception
    mock_note.objects.get.side_effect = mock_note.DoesNotExist
    effects, enriched, errors = build_charge_enrichment_effects([], [], "bad-uuid")
    assert effects == []
    assert enriched == []
    assert errors == [{"command_uuid": "", "reason": "note_not_found"}]
```

> Note: `test_update_effect_built...` asserts the `BillingLineItem.objects.filter` kwargs via a small helper that resolves the real `BillingLineItemStatus.ACTIVE`; keep `BillingLineItemStatus` imported from the real module in the implementation (do not patch it) so the enum value is stable.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hyperscribe/scribe/charges/test_enrichment.py -v -k "effect or removed or missing or unknown_note"`
Expected: FAIL — `ImportError: cannot import name 'build_charge_enrichment_effects'`.

- [ ] **Step 3: Implement the effect builder**

Append to `hyperscribe/scribe/charges/enrichment.py`:

```python
def _resolve_assessment_ids(
    pointers: list[dict[str, Any]], index: dict[str, list[str]]
) -> list[str]:
    """Resolve a charge's diagnosis pointers to Assessment ids via the code
    index. De-duplicates while preserving order. When an ICD code maps to more
    than one assessment (rare: two assessments of the same condition on one
    note), all matches are included and a warning is logged — there is no
    direct Command->Assessment FK to disambiguate further (spec §5)."""
    resolved: list[str] = []
    for pointer in pointers:
        code = _normalize_icd10(pointer.get("icd10_code"))
        matches = index.get(code, [])
        if len(matches) > 1:
            log.warning("enrich_charges: ambiguous icd10 %s maps to %d assessments", code, len(matches))
        for assessment_id in matches:
            if assessment_id not in resolved:
                resolved.append(assessment_id)
    return resolved


def _find_billing_line_item(note: Any, command_uuid: str) -> Any | None:
    """Find the ACTIVE BillingLineItem the given PerformCommand created.

    Matched by ``command_id`` (== Command.dbid) + note + active status. This is
    the precise lookup; the loose ``cpt + note`` match used by PR #257 is
    ambiguous when two charges share a CPT. Returns None if the command or BLI
    can't be found."""
    try:
        command = Command.objects.get(id=command_uuid)
    except Command.DoesNotExist:
        return None
    return (
        BillingLineItem.objects.filter(
            note=note, command_id=command.dbid, status=BillingLineItemStatus.ACTIVE
        ).first()
    )


def build_charge_enrichment_effects(
    charges: list[dict[str, Any]],
    removed_command_uuids: list[str],
    note_uuid: str,
) -> tuple[list[Effect], list[dict[str, Any]], list[dict[str, Any]]]:
    """Build BillingLineItem effects for charge enrichment.

    ``charges`` is the desired enriched state for surviving charges; each is
    ``{command_uuid, diagnosis_pointers:[{command_uuid, icd10_code}], modifiers:[code]}``.
    ``removed_command_uuids`` are PerformCommand uuids whose BLI should be
    removed (amendment charge removal).

    Returns ``(effects, enriched, errors)``. ``enriched`` records what was
    written (for audit/UI); ``errors`` records charges whose BLI couldn't be
    located. Assumes ``charges`` already passed :func:`validate_charge_enrichment`.
    """
    try:
        note = Note.objects.get(id=note_uuid)
    except Note.DoesNotExist:
        return [], [], [{"command_uuid": "", "reason": "note_not_found"}]

    index = build_assessment_index(note)
    effects: list[Effect] = []
    enriched: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for charge in charges:
        command_uuid = charge.get("command_uuid", "")
        bli = _find_billing_line_item(note, command_uuid)
        if bli is None:
            errors.append({"command_uuid": command_uuid, "reason": "billing_line_item_not_found"})
            continue
        assessment_ids = _resolve_assessment_ids(charge.get("diagnosis_pointers") or [], index)
        modifier_codes = [str(m) for m in (charge.get("modifiers") or [])]
        modifiers = [{"code": code, "system": CPT_MODIFIER_SYSTEM} for code in modifier_codes]
        effects.append(
            UpdateBillingLineItem(
                billing_line_item_id=str(bli.id),
                assessment_ids=assessment_ids,
                modifiers=modifiers,
            ).apply()
        )
        enriched.append({
            "command_uuid": command_uuid,
            "billing_line_item_id": str(bli.id),
            "assessment_ids": assessment_ids,
            "modifiers": modifier_codes,
        })

    for command_uuid in removed_command_uuids:
        bli = _find_billing_line_item(note, command_uuid)
        if bli is None:
            continue
        effects.append(RemoveBillingLineItem(billing_line_item_id=str(bli.id)).apply())

    return effects, enriched, errors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/hyperscribe/scribe/charges/test_enrichment.py -v`
Expected: PASS (all enrichment tests).

- [ ] **Step 5: Type-check and commit**

```bash
uv run mypy --config-file=mypy.ini hyperscribe/scribe/charges/enrichment.py
git add hyperscribe/scribe/charges/enrichment.py tests/hyperscribe/scribe/charges/test_enrichment.py
git commit -m "$(cat <<'EOF'
feat(charges): build Update/Remove BillingLineItem effects from enrichment payload

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `/enrich-charges` endpoint

**Files:**
- Modify: `hyperscribe/scribe/api/session_view.py`
- Test: `tests/hyperscribe/scribe/api/test_session_view_charges.py`

- [ ] **Step 1: Add the failing endpoint tests**

Append to `tests/hyperscribe/scribe/api/test_session_view_charges.py`:

```python
from canvas_sdk.effects import Effect


def _post_instance(body: dict, staff_id="staff-key-abc") -> ScribeSessionView:
    view = _helper_instance(staff_id)
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": staff_id},
        query_params={},
        body=json.dumps(body).encode(),
    )
    return view


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_charge_enrichment_effects")
def test_enrich_charges_happy_path(mock_build, mock_audit, mock_auth):
    effect = Effect(type=Effect.EffectType.LOG, payload="x") if hasattr(Effect, "EffectType") else MagicMock(spec=Effect)
    mock_build.return_value = ([effect], [{"command_uuid": "c1", "billing_line_item_id": "b1",
                                          "assessment_ids": ["a1"], "modifiers": ["25"]}], [])
    view = _post_instance({
        "note_uuid": "note-1",
        "charges": [{"command_uuid": "c1",
                     "diagnosis_pointers": [{"command_uuid": "d1", "icd10_code": "M25.511"}],
                     "modifiers": ["25"]}],
    })
    result = view.post_enrich_charges()

    # Effects precede the JSONResponse in the return list.
    assert result[0] is effect
    body = json.loads(result[-1].content)
    assert body["enriched"][0]["billing_line_item_id"] == "b1"
    assert body["errors"] == []
    mock_audit.assert_called_once()


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_enrich_charges_rejects_charge_without_pointer(mock_auth):
    view = _post_instance({
        "note_uuid": "note-1",
        "charges": [{"command_uuid": "c1", "diagnosis_pointers": [], "modifiers": []}],
    })
    result = view.post_enrich_charges()
    assert result[0].status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    body = json.loads(result[0].content)
    assert body["errors"] == [{"command_uuid": "c1", "errors": ["at_least_one_pointer"]}]


def test_enrich_charges_requires_auth():
    # No _authorize_edit patch: real auth runs and short-circuits on missing note.
    view = _post_instance({"note_uuid": "", "charges": []})
    result = view.post_enrich_charges()
    assert result[0].status_code == HTTPStatus.BAD_REQUEST


def test_enrich_charges_invalid_json():
    view = _helper_instance()
    view.request = SimpleNamespace(headers={"canvas-logged-in-user-id": "x"}, query_params={}, body=b"not json")
    result = view.post_enrich_charges()
    assert result[0].status_code == HTTPStatus.BAD_REQUEST
```

> If constructing a bare `Effect` in the happy-path test is awkward with the installed SDK version, replace `effect` with `MagicMock(spec=Effect)` and assert `result[0] is effect` only.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hyperscribe/scribe/api/test_session_view_charges.py -v -k enrich`
Expected: FAIL — `AttributeError: 'ScribeSessionView' object has no attribute 'post_enrich_charges'`.

- [ ] **Step 3: Wire the import**

In `hyperscribe/scribe/api/session_view.py`, add to the existing import block (near the other `hyperscribe.scribe...` imports, after the `from hyperscribe.scribe.commands.builder import (...)` block):

```python
from hyperscribe.scribe.charges.enrichment import build_charge_enrichment_effects
from hyperscribe.scribe.charges.validation import validate_charge_enrichment
```

- [ ] **Step 4: Add the endpoint method**

Add this method to the `ScribeSessionView` class, next to the other amend endpoints (e.g. just after `post_delete_existing_commands`). Match the surrounding indentation/style:

```python
    @api.post("/enrich-charges")
    def post_enrich_charges(self) -> list[Union[Response, Effect]]:
        """Write diagnosis pointers + modifiers onto each charge's BillingLineItem.

        Called by the frontend AFTER /insert-commands has committed the charge
        PerformCommands (so their BLIs exist). Deterministic, no event handlers.
        ``removed_charges`` carries PerformCommand uuids whose BLI should be
        removed (amendment charge removal).
        """
        try:
            payload = json.loads(self.request.body or b"{}")
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return [JSONResponse({"error": f"Invalid JSON: {exc}"}, status_code=HTTPStatus.BAD_REQUEST)]

        note_uuid = payload.get("note_uuid", "")
        auth = _authorize_edit(note_uuid, self.request)
        if auth is not None:
            return [auth]

        charges = payload.get("charges", []) or []
        removed = payload.get("removed_charges", []) or []

        validation_errors = validate_charge_enrichment(charges)
        if validation_errors:
            audit_event(note_uuid, "ENRICH_CHARGES_VALIDATION_FAILED", {"count": len(validation_errors)})
            return [JSONResponse({"errors": validation_errors}, status_code=HTTPStatus.UNPROCESSABLE_ENTITY)]

        effects, enriched, errors = build_charge_enrichment_effects(charges, removed, note_uuid)
        audit_event(
            note_uuid,
            "ENRICH_CHARGES",
            {"enriched": len(enriched), "removed": len(removed), "errors": len(errors)},
        )
        return [*effects, JSONResponse({"enriched": enriched, "errors": errors}, status_code=HTTPStatus.OK)]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/hyperscribe/scribe/api/test_session_view_charges.py -v`
Expected: PASS (existing search-charges tests + 4 new enrich tests).

- [ ] **Step 6: Type-check and commit**

```bash
uv run mypy --config-file=mypy.ini hyperscribe/scribe/api/session_view.py
git add hyperscribe/scribe/api/session_view.py tests/hyperscribe/scribe/api/test_session_view_charges.py
git commit -m "$(cat <<'EOF'
feat(charges): /enrich-charges endpoint (auth + validate + emit BLI effects)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Backend gate — full suite + types green

**Files:** none (verification task).

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/`
Expected: PASS, no regressions. If anything fails, fix before proceeding — do not move to frontend on a red suite.

- [ ] **Step 2: Type-check the whole project**

Run: `uv run mypy --config-file=mypy.ini .`
Expected: 0 errors.

- [ ] **Step 3: Coverage check on new modules**

Run: `uv run pytest tests/hyperscribe/scribe/charges tests/hyperscribe/scribe/api/test_session_view_charges.py --cov=hyperscribe.scribe.charges --cov=hyperscribe.scribe.api.session_view --cov-report=term-missing`
Expected: `hyperscribe/scribe/charges/*` ≥ 90%. Add tests for any uncovered branch (e.g. ambiguous-code warning path, `Command.DoesNotExist` in `_find_billing_line_item`) and re-run.

- [ ] **Step 4: Commit any added coverage tests**

```bash
git add -A && git commit -m "$(cat <<'EOF'
test(charges): cover remaining enrichment branches

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `charge-matrix.js` component

**Files:**
- Create: `hyperscribe/scribe/static/charge-matrix.js`

No JS test runner exists; this task is implementation + a manual render checklist (verified in Task 9). Build the component to the data contract below; the design handoff (`design_handoff_charges_matrix`) is the visual spec.

**Data contract (props):**
```
ChargeMatrix({
  diagnoses,        // [{ command_uuid, code, label, locked }]  array order = rank (1-based by index)
  charges,          // [{ command_uuid, cpt, description, modifiers:[code], pointers:[diagnosis command_uuid] }]
  isAmending,       // bool — when true, locked diagnoses can't be dragged; a divider separates net-new
  onTogglePointer,  // (chargeUuidOrIndex, diagnosisUuid) => void
  onReorderDiagnoses, // (nextOrderedCommandUuids) => void
  onAddModifier, onRemoveModifier, // (chargeRef, code) => void
  onAddCharge,      // () => void  (opens CPT search)
  onRemoveCharge,   // (chargeRef) => void
})
```

- [ ] **Step 1: Create the component**

Create `hyperscribe/scribe/static/charge-matrix.js`:

```javascript
import { html } from '/plugin-io/api/hyperscribe/scribe/static/preact-deps.js';

// NOTE: match the import style used by the sibling components (soap-group.js,
// charge-row.js). If those import { html } from a shared deps module, reuse it;
// otherwise import htm/preact from esm.sh exactly as charge-row.js does. Verify
// the first line of charge-row.js and copy its import convention verbatim.

export const MAX_POINTERS = 4;
export const MAX_MODIFIERS = 4;

// Common modifiers seeded into the picker (spec §6 / handoff). code -> description.
export const MODIFIER_SEED = [
  { code: '25', desc: 'Significant, separately identifiable E/M service' },
  { code: '59', desc: 'Distinct procedural service' },
  { code: '95', desc: 'Synchronous telemedicine service' },
  { code: 'LT', desc: 'Left side' },
  { code: 'RT', desc: 'Right side' },
  { code: '76', desc: 'Repeat procedure by same physician' },
];

// Pure helper: each charge must have >=1 pointer to be signable. Exported for
// reuse by summary.js's sign-gating so the rule lives in one place.
export function chargeValidity(charges) {
  return charges.map(c => ({
    command_uuid: c.command_uuid,
    pointerCount: (c.pointers || []).length,
    valid: (c.pointers || []).length >= 1,
  }));
}
export function canSignCharges(charges) {
  return charges.every(c => (c.pointers || []).length >= 1);
}

export function ChargeMatrix({
  diagnoses, charges, isAmending,
  onTogglePointer, onReorderDiagnoses,
  onAddModifier, onRemoveModifier, onAddCharge, onRemoveCharge,
}) {
  const lockedCount = isAmending ? diagnoses.filter(d => d.locked).length : 0;

  const headerCells = charges.map(charge => html`
    <div class="cm-col-header">
      <div class="cm-cpt">${charge.cpt}</div>
      <div class="cm-modifiers">
        ${(charge.modifiers || []).map(code => html`
          <span class="cm-modchip" onClick=${() => onRemoveModifier(charge.command_uuid, code)}>
            ${code}<span class="cm-modchip-x">×</span>
          </span>`)}
        ${(charge.modifiers || []).length < MAX_MODIFIERS
          ? html`<button class="cm-modadd" onClick=${() => onAddModifier(charge.command_uuid)}>+ Modifier</button>`
          : null}
      </div>
    </div>`);

  const renderDxRow = (dx, idx) => {
    const draggable = !(isAmending && dx.locked);
    const rank = idx + 1;
    return html`
      <div class="cm-row${dx.locked ? ' cm-row-locked' : ''}"
           draggable=${draggable}
           onDragStart=${e => draggable && e.dataTransfer.setData('text/dx', dx.command_uuid)}
           onDragOver=${e => draggable && e.preventDefault()}
           onDrop=${e => handleDrop(e, idx)}>
        <span class="cm-grip">${draggable
          ? html`<span class="cm-grip-dots" title="Drag to reorder rank">⠿</span>`
          : html`<span class="cm-lock" title="Order locked — already on the signed claim">🔒</span>`}</span>
        <span class="cm-rank${dx.locked ? ' cm-rank-muted' : ''}">${rank}</span>
        <span class="cm-dxcode">${dx.code}</span>
        <span class="cm-dxlabel">${dx.label}</span>
        ${charges.map(charge => {
          const on = (charge.pointers || []).includes(dx.command_uuid);
          const atCap = !on && (charge.pointers || []).length >= MAX_POINTERS;
          return html`<span class="cm-cell${on ? ' cm-cell-on' : ''}">
            <input type="checkbox" checked=${on} disabled=${atCap}
              title=${atCap ? `Max ${MAX_POINTERS} diagnosis pointers` : ''}
              onChange=${() => onTogglePointer(charge.command_uuid, dx.command_uuid)} />
          </span>`;
        })}
      </div>`;
  };

  // Drag-drop reorder, constrained: a net-new row may only land at/after the
  // locked boundary; locked rows never move.
  function handleDrop(e, targetIdx) {
    const draggedUuid = e.dataTransfer.getData('text/dx');
    if (!draggedUuid) return;
    const from = diagnoses.findIndex(d => d.command_uuid === draggedUuid);
    if (from < 0) return;
    let to = targetIdx;
    if (isAmending && to < lockedCount) to = lockedCount; // can't cross into the locked group
    const next = diagnoses.map(d => d.command_uuid);
    next.splice(to, 0, next.splice(from, 1)[0]);
    onReorderDiagnoses(next);
  }

  const footerCells = charges.map(charge => {
    const n = (charge.pointers || []).length;
    return html`<span class="cm-pill${n === 0 ? ' cm-pill-error' : ''}">${n} / ${MAX_POINTERS} ✓</span>`;
  });

  const lockedRows = [], newRows = [];
  diagnoses.forEach((dx, idx) => {
    (isAmending && dx.locked ? lockedRows : newRows).push(renderDxRow(dx, idx));
  });

  return html`
    <div class="cm-matrix" style=${`--cm-charge-cols:${charges.length}`}>
      <div class="cm-header-row">
        <div class="cm-corner"></div>
        ${headerCells}
        <button class="cm-addcol" title="Add charge" onClick=${onAddCharge}>+</button>
      </div>
      ${isAmending && lockedRows.length
        ? html`<div class="cm-group-label">ON THE SIGNED CLAIM</div>${lockedRows}
               <div class="cm-divider">added in this amendment</div>`
        : null}
      ${newRows}
      <div class="cm-footer-row"><div class="cm-corner"></div>${footerCells}</div>
    </div>`;
}
```

- [ ] **Step 1b: Add the modifier picker**

The header's `+ Modifier` button must open a searchable, multi-select picker capped at `MAX_MODIFIERS`, seeded with `MODIFIER_SEED` and allowing a free-typed code. Add to `charge-matrix.js`:

```javascript
export function ModifierPicker({ selected, onToggle, onClose }) {
  // `selected` = array of currently-applied modifier codes for this charge.
  // Controlled search via a closure variable is fine; this is a small popover.
  const atCap = (selected || []).length >= MAX_MODIFIERS;
  return html`
    <div class="cm-modpicker" role="dialog">
      <input class="cm-modpicker-search" placeholder="Search modifier code or description"
        onInput=${e => onSearch(e.target.value)} />
      <div class="cm-modpicker-list">
        ${MODIFIER_SEED.map(m => {
          const on = (selected || []).includes(m.code);
          const disabled = !on && atCap;
          return html`<button class="cm-modpicker-row${on ? ' on' : ''}" disabled=${disabled}
            onClick=${() => onToggle(m.code)}>
            <span class="cm-modpicker-code">${m.code}</span>
            <span class="cm-modpicker-desc">${m.desc}</span>
            ${on ? html`<span class="cm-modpicker-check">✓</span>` : null}
          </button>`;
        })}
      </div>
      <button class="cm-modpicker-done" onClick=${onClose}>Done</button>
    </div>`;
  // `onSearch` filters the rendered rows by code/desc substring — implement with
  // a useState in the picker (import useState alongside html) to track the query
  // and filter MODIFIER_SEED plus surface a "use '<query>'" free-entry row when
  // the query is a 2-char code not in the seed list.
}
```

In `ChargeMatrix`, track which charge's picker is open with a `useState` (`const [modPickerFor, setModPickerFor] = useState(null)`), have the `+ Modifier` button call `setModPickerFor(charge.command_uuid)`, and render `<${ModifierPicker} selected=${charge.modifiers} onToggle=${code => (charge.modifiers.includes(code) ? onRemoveModifier(charge.command_uuid, code) : onAddModifier(charge.command_uuid, code))} onClose=${() => setModPickerFor(null)} />` anchored under that column header when `modPickerFor === charge.command_uuid`. Import `useState` from the same module as `html`.

- [ ] **Step 2: Reconcile imports with the sibling components**

Open `hyperscribe/scribe/static/charge-row.js` and copy its exact `import` line(s) for `html`/preact into the top of `charge-matrix.js`, replacing the placeholder `preact-deps.js` import. The matrix must use the same module source as its siblings.

- [ ] **Step 3: Manual smoke check**

There is no JS unit runner. Confirm the file parses by loading the scribe tab in a browser later (Task 9). For now, sanity-check there are no syntax errors:

Run: `node --check hyperscribe/scribe/static/charge-matrix.js`
Expected: no output (exit 0). (If `node` isn't available, skip — Task 9 catches it in-browser.)

- [ ] **Step 4: Commit**

```bash
git add hyperscribe/scribe/static/charge-matrix.js
git commit -m "$(cat <<'EOF'
feat(charges): ChargeMatrix component (pointers, modifiers, rank, locked rows)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Render the matrix in the CHARGES section

**Files:**
- Modify: `hyperscribe/scribe/static/soap-group.js`

- [ ] **Step 1: Import the component**

At the top of `hyperscribe/scribe/static/soap-group.js`, alongside the existing `import { ChargeRow } ...` line (around line 2), add:

```javascript
import { ChargeMatrix } from '/plugin-io/api/hyperscribe/scribe/static/charge-matrix.js';
```

- [ ] **Step 2: Replace the CHARGES checklist render with the matrix**

In the CHARGES section render block (around `soap-group.js:1534-1625`), replace the `<div class="charge-checklist">…</div>` + pending-rows render with a `ChargeMatrix` render. The `SoapGroup` already receives the props needed; map them:

```javascript
// CHARGES section — matrix render. `diagnoses` and `charges` are derived in
// summary.js and passed down via props (see Task 8). `onToggleChargePointer`,
// `onReorderDiagnoses`, `onAddChargeModifier`, `onRemoveChargeModifier`,
// `onAddCharge`, `onRemoveChargeByUuid`, and `isAmending` are passed from summary.js.
html`<${ChargeMatrix}
  diagnoses=${chargeMatrixDiagnoses}
  charges=${chargeMatrixCharges}
  isAmending=${isAmending}
  onTogglePointer=${onToggleChargePointer}
  onReorderDiagnoses=${onReorderDiagnoses}
  onAddModifier=${onAddChargeModifier}
  onRemoveModifier=${onRemoveChargeModifier}
  onAddCharge=${onAddCharge}
  onRemoveCharge=${onRemoveChargeByUuid}
/>`
```

Keep the existing CHARGES section heading/wrapper. Remove the now-unused `charge-checklist` / pending `ChargeRow` markup for the perform section (the matrix supersedes it). Leave `ChargeRow` import in place only if still used elsewhere; otherwise remove the import to keep mypy/lint-equivalent cleanliness (JS: just remove the dead import line).

- [ ] **Step 3: Thread the new props through `SoapGroup`'s signature**

Add the new prop names (`chargeMatrixDiagnoses`, `chargeMatrixCharges`, `isAmending`, `onToggleChargePointer`, `onReorderDiagnoses`, `onAddChargeModifier`, `onRemoveChargeModifier`, `onAddCharge`, `onRemoveChargeByUuid`) to the `SoapGroup` destructured props at its definition. Default the arrays to `[]` so non-charges groups render unaffected.

- [ ] **Step 4: Syntax check + commit**

Run: `node --check hyperscribe/scribe/static/soap-group.js` (skip if no node)

```bash
git add hyperscribe/scribe/static/soap-group.js
git commit -m "$(cat <<'EOF'
feat(charges): render ChargeMatrix in the CHARGES section

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Matrix state + `/enrich-charges` wiring in `summary.js`

**Files:**
- Modify: `hyperscribe/scribe/static/summary.js`

This is the integration task. It (a) derives the matrix `diagnoses`/`charges` view-models from `commands[]`, (b) orders diagnosis commands by matrix rank at insert time, (c) calls `/enrich-charges` after `/insert-commands` succeeds, (d) gates "Accept and sign" on `canSignCharges`, and (e) enforces the amend locked/net-new rule.

- [ ] **Step 1: Import the shared helpers**

At the top of `summary.js`, add:

```javascript
import { canSignCharges } from '/plugin-io/api/hyperscribe/scribe/static/charge-matrix.js';
```

- [ ] **Step 2: Derive matrix view-models from `commands`**

Where `commands` state is available (near the other derived values, after `const [commands, setCommands] = useState(...)` at ~line 414), add memoized derivations:

```javascript
// Diagnosis rows = diagnose/assess commands, in commands[] order (= rank).
// `locked` = already on the signed claim (already_documented || command_uuid).
const chargeMatrixDiagnoses = useMemo(() => commands
  .filter(c => (c.command_type === 'diagnose' || c.command_type === 'assess')
    && (c.data?.icd10_code || c.data?.code))
  .map(c => ({
    command_uuid: c.command_uuid || c._localId,
    code: c.data?.icd10_code || c.data?.code || '',
    label: c.data?.label || c.display || '',
    locked: Boolean(c.already_documented || c.command_uuid),
  })), [commands]);

// Charge columns = perform commands. `pointers` and `modifiers` live on the
// command's data (frontend-only fields until /enrich-charges writes them).
const chargeMatrixCharges = useMemo(() => commands
  .filter(c => c.command_type === 'perform' && c.data?.cpt_code)
  .map(c => ({
    command_uuid: c.command_uuid || c._localId,
    cpt: c.data.cpt_code,
    description: c.data.description || '',
    modifiers: c.data._modifiers || [],
    pointers: c.data._pointers || [],
  })), [commands]);
```

> If `useMemo` isn't already imported from preact/hooks in this file, add it to the existing hooks import. Also ensure each command gets a stable `_localId` when created (set it in the charge/diagnosis add handlers if not already present) so matrix identity survives before a `command_uuid` exists.

- [ ] **Step 3: Pointer/modifier/reorder handlers (mutate `commands`)**

Add handlers (near the existing `handleAddCharge`/`handleEdit` handlers, ~line 1484):

```javascript
const matrixRef = (uuid) => (c) => (c.command_uuid || c._localId) === uuid;

const onToggleChargePointer = (chargeUuid, dxUuid) => setCommands(prev => prev.map(c => {
  if (!matrixRef(chargeUuid)(c)) return c;
  const cur = c.data._pointers || [];
  const has = cur.includes(dxUuid);
  if (!has && cur.length >= 4) return c; // cap
  return { ...c, data: { ...c.data, _pointers: has ? cur.filter(u => u !== dxUuid) : [...cur, dxUuid] } };
}));

const onAddChargeModifier = (chargeUuid, code) => setCommands(prev => prev.map(c => {
  if (!matrixRef(chargeUuid)(c)) return c;
  const cur = c.data._modifiers || [];
  if (cur.includes(code) || cur.length >= 4) return c;
  return { ...c, data: { ...c.data, _modifiers: [...cur, code] } };
}));

const onRemoveChargeModifier = (chargeUuid, code) => setCommands(prev => prev.map(c =>
  matrixRef(chargeUuid)(c)
    ? { ...c, data: { ...c.data, _modifiers: (c.data._modifiers || []).filter(m => m !== code) } }
    : c));

// Reorder: reorder the diagnose/assess slice of commands[] to the new order,
// leaving non-diagnosis commands in place. Locked rows keep their relative
// position (the matrix already prevents dragging them, but enforce here too).
const onReorderDiagnoses = (nextUuids) => setCommands(prev => {
  const idOf = c => c.command_uuid || c._localId;
  const isDx = c => (c.command_type === 'diagnose' || c.command_type === 'assess');
  const dxByA = new Map(prev.filter(isDx).map(c => [idOf(c), c]));
  const reordered = nextUuids.map(u => dxByA.get(u)).filter(Boolean);
  let i = 0;
  return prev.map(c => isDx(c) ? reordered[i++] : c);
});
```

- [ ] **Step 4: Order diagnosis commands by rank at insert**

In the insert pipeline (`handleInsert`, before building the `/insert-commands` payload at ~line 1944), ensure diagnosis commands are inserted in matrix order. Since Step 3's `onReorderDiagnoses` already mutates `commands[]` order, the existing insertion (which preserves `commands` order) yields the correct rank — **no extra sort needed**, but add a guard comment so a future refactor doesn't re-sort and break rank:

```javascript
// Diagnosis rank is the commands[] order of diagnose/assess rows. Do NOT
// re-sort the insertable batch in a way that reorders diagnoses, or claim
// ClaimDiagnosisCode.rank will diverge from the matrix. (spec §2)
```

- [ ] **Step 5: Call `/enrich-charges` after `/insert-commands` succeeds**

In `handleInsert`, immediately after the `/insert-commands` response is parsed and commands are re-stamped with their new `command_uuid`s (~line 1949, before `/verify-commands` at ~line 2068), add the enrichment call. Build the payload from the now-UUID-stamped commands:

```javascript
// Enrich charges: write diagnosis pointers + modifiers onto each charge's
// BillingLineItem. Runs AFTER insert so the perform commands (and thus their
// BLIs) exist. Pointers are sent as {command_uuid, icd10_code} resolved from
// the diagnosis rows; the backend maps icd10 -> Assessment id.
const dxCodeByRef = new Map(chargeMatrixDiagnoses.map(d => [d.command_uuid, d.code]));
const enrichCharges = workingCommands
  .filter(c => c.command_type === 'perform' && c.data?.cpt_code && (c.command_uuid))
  .map(c => ({
    command_uuid: c.command_uuid,
    diagnosis_pointers: (c.data._pointers || []).map(u => ({
      command_uuid: u,
      icd10_code: dxCodeByRef.get(u) || '',
    })).filter(p => p.icd10_code),
    modifiers: c.data._modifiers || [],
  }));
const removedCharges = (amendDeletes || [])
  .filter(c => c.command_type === 'perform' && c.command_uuid)
  .map(c => c.command_uuid);

if (enrichCharges.length || removedCharges.length) {
  const enrichRes = await fetch(`${API_BASE}/enrich-charges`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note_uuid: noteId, charges: enrichCharges, removed_charges: removedCharges }),
  });
  const enrichData = await enrichRes.json();
  if (enrichRes.status === 422) {
    // Validation blocked the write — surface and stop the pipeline before sign.
    setChargeErrors(enrichData.errors || []);
    return;
  }
  if (enrichData.errors && enrichData.errors.length) {
    console.warn('enrich-charges partial errors', enrichData.errors);
  }
}
```

> `workingCommands` is the locally-stamped command list already used in this function; reuse whatever variable holds the post-insert, UUID-stamped commands. `setChargeErrors` is a new state setter — add `const [chargeErrors, setChargeErrors] = useState([]);` near the other `useState`s.

- [ ] **Step 6: Gate "Accept and sign" on charge validity**

Find where the approve/sign button's `disabled` is computed (the primary CTA). Add `canSignCharges(chargeMatrixCharges)` to the disabled condition, and render the reason when blocked:

```javascript
const chargesSignable = canSignCharges(chargeMatrixCharges);
// ...in the button: disabled=${... || !chargesSignable}
// ...reason text when blocked:
${!chargesSignable ? html`<div class="cm-sign-error">Every charge needs at least one diagnosis pointer to sign.</div>` : null}
```

- [ ] **Step 7: Pass matrix props + isAmending down to `SoapGroup`**

Where `SoapGroup` is rendered for the CHARGES group, pass the derived view-models and handlers:

```javascript
chargeMatrixDiagnoses=${chargeMatrixDiagnoses}
chargeMatrixCharges=${chargeMatrixCharges}
isAmending=${wasFinalized && !approved}
onToggleChargePointer=${onToggleChargePointer}
onReorderDiagnoses=${onReorderDiagnoses}
onAddChargeModifier=${onAddChargeModifier}
onRemoveChargeModifier=${onRemoveChargeModifier}
onAddCharge=${handleAddCharge}
onRemoveChargeByUuid=${onRemoveChargeByUuid}
```

> `wasFinalized && !approved` is the existing amend-mode predicate in this file — reuse the exact expression already used elsewhere (search for `wasFinalized`). `onRemoveChargeByUuid` should route to the existing charge-removal handler (`handleRemoveChargeByCpt` / delete path) keyed by the matrix ref; adapt the existing remover to accept a uuid/ref.

- [ ] **Step 8: Syntax check + commit**

Run: `node --check hyperscribe/scribe/static/summary.js` (skip if no node)

```bash
git add hyperscribe/scribe/static/summary.js
git commit -m "$(cat <<'EOF'
feat(charges): matrix state, rank ordering, /enrich-charges wiring, sign gate

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Matrix styles

**Files:**
- Modify: the scribe stylesheet (find it: `grep -rl "charge-checklist\|charge-check-item" hyperscribe/scribe/static/ hyperscribe/scribe/templates/`). Add styles there (or create `hyperscribe/scribe/static/charge-matrix.css` and link it in `index.html` next to the existing stylesheet link).

- [ ] **Step 1: Locate the stylesheet**

Run: `grep -rln "charge-checklist\|--navy\|charge-check" hyperscribe/scribe/static hyperscribe/scribe/templates`
Use the file that holds the existing scribe styles. If styles are inline in `index.html`, add a `<style>`/`<link>` accordingly.

- [ ] **Step 2: Add matrix styles using the handoff tokens**

Add CSS implementing the grid + chips + checkboxes + pills using the exact tokens from `design_handoff_charges_matrix/README.md` §"Design tokens". Minimum classes to style: `.cm-matrix` (CSS grid `minmax(0,1fr) repeat(var(--cm-charge-cols),230px) 96px`), `.cm-header-row`, `.cm-col-header`, `.cm-cpt` (mono/navy), `.cm-modchip`/`.cm-modadd`, `.cm-row`/`.cm-row-locked`, `.cm-grip`/`.cm-lock`, `.cm-rank`/`.cm-rank-muted`, `.cm-dxcode` (green chip), `.cm-cell`/`.cm-cell-on` (green wash), checkbox on/off/disabled, `.cm-pill`/`.cm-pill-error` (red `0/4`), `.cm-group-label`, `.cm-divider`, `.cm-addcol`, `.cm-sign-error`, and the modifier picker (`.cm-modpicker`, `.cm-modpicker-search`, `.cm-modpicker-list`, `.cm-modpicker-row`/`.on`, `.cm-modpicker-code`, `.cm-modpicker-desc`, `.cm-modpicker-check`, `.cm-modpicker-done`).

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(charges): matrix styles per design handoff tokens

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Instance verification (UAT) — close the spec §9 unknowns

**Files:** none (manual verification on a Canvas playground instance, e.g. scribeqa-playground). Use the CPA tooling to deploy/inspect. This task confirms the three assumptions the design deliberately did NOT bake in.

- [ ] **Step 1: Deploy the plugin to a playground instance**

Use the CPA deploy flow (`cpa:deploy-uat` or the project's `canvas` CLI) to install the plugin on a test instance.

- [ ] **Step 2: Verify BLI lookup (spec §9.1)**

On a fresh note: add a charge via the matrix, complete first-approval (insert → enrich → sign). In the Django shell / SDK data inspector, confirm:
- a `BillingLineItem` exists for the note with `command_id == ` the perform `Command.dbid`, and
- its `assessments` / `modifiers` reflect what the matrix sent.
If `command_id` does NOT equal `Command.dbid`, adjust `_find_billing_line_item` (e.g. add a `command_type` filter or use the documented `cpt + note` fallback) and re-run Task 3 tests.

- [ ] **Step 3: Verify rank derivation (spec §9.2)**

Add ≥2 diagnoses, reorder them in the matrix, sign, then open the resulting claim. Confirm `ClaimDiagnosisCode.rank` matches the matrix row order. If not, capture the actual rank source and revisit the diagnosis-insert ordering in Task 8 Step 4.

- [ ] **Step 4: Verify modifier coding system (spec §9.3)**

Confirm the modifiers written to the BLI use the expected system and render correctly on the claim. If the system string differs, update `CPT_MODIFIER_SYSTEM` in `enrichment.py` and re-run Task 3 tests.

- [ ] **Step 5: Amendment walk-through**

"Make Changes" on the signed note. Confirm:
- already-approved diagnosis rows show the lock glyph under "ON THE SIGNED CLAIM" and can't be dragged; net-new diagnoses reorder among themselves below the divider;
- toggling a pointer / adding a modifier on an existing charge issues an in-place `UpdateBillingLineItem` (BLI id unchanged, no void/recreate of the perform);
- removing a charge EIE's the perform AND removes its BLI;
- re-sign succeeds and the corrected claim reflects the changes.

- [ ] **Step 6: Record results**

Note any deviations and the fixes applied. If any of Steps 2-4 forced a code change, ensure the corresponding unit tests were updated and the full suite + mypy are green again. Commit fixes.

---

## Final self-review checklist (run before opening the PR)

- [ ] `uv run pytest tests/` green; `uv run mypy --config-file=mypy.ini .` 0 errors.
- [ ] New `hyperscribe/scribe/charges/*` coverage ≥ 90%.
- [ ] No event handlers were added (no `PERFORM_COMMAND__POST_COMMIT` / `POST_ENTER_IN_ERROR` subscriptions) — enrichment is endpoint-driven only.
- [ ] Units are NOT modeled anywhere (out of scope).
- [ ] Validator is the single source of truth (frontend `canSignCharges` + backend `validate_charge_enrichment` agree on the ≥1-pointer rule).
- [ ] Amendment: existing diagnoses rank-locked; net-new reorderable; existing-charge enrichment via in-place `UpdateBillingLineItem`; charge removal via perform-EIE + `RemoveBillingLineItem`.
- [ ] Each of the four concerns (validator/pointers, modifiers, rank, amend) is an independently revertable unit (spec §11).
- [ ] Spec §9 instance verifications completed and any forced code changes have updated tests.
```
