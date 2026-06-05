# Charge Capture Enhancements for Canvas Scribe — Design

**Date:** 2026-06-05
**Branch:** `feat/charge-capture` (based on `feat/canvas-scribe`)
**Status:** Approved design — ready for implementation planning

## 1. Goal

Give providers, inside the scribe "Accept & Sign" experience, the ability to:

1. **Associate charges to diagnoses** — link each charge (CPT/HCPCS) to one or more diagnoses (ICD-10) via a matrix of checkboxes ("diagnosis pointers").
2. **Reorder diagnosis codes** — drag diagnosis rows to set their rank on the claim.
3. **Add modifiers to charges** — up to 4 CPT modifiers per charge, entered in the charge column header.
4. **Add/remove charges** — add a charge column; remove a charge.

The work must integrate cleanly with the existing scribe amendment ("Make Changes") workflow and introduce as little defect risk as possible. It deliberately replaces the approach taken in PR #257, which bundled six unrelated areas and relied on event-driven reconciliation that proved fragile.

### Explicitly out of scope
- **Units** on charges (intentionally cut for simplicity; Canvas defaults `units` to 1).
- LLM/AI extraction of modifiers or diagnosis links. The CPT is still proposed by the scribe as today; **units/modifiers/diagnosis-links are manual provider entry only**. No new LLM prompt work, no new evals.
- Per-mutation amendment confirm dialogs (the design handoff proposed these; explicitly disregarded).
- Staged/multi-PR delivery (the handoff proposed 4 PRs; we ship one focused PR but keep each write path independently revertable).

## 2. Background: current state and the decisive SDK constraint

### Current state on `feat/canvas-scribe`
- Charges are `PerformCommand`s carrying only `cpt_code` + `notes`, rendered in the CHARGES section by `charge-row.js`. The CPT is selected by an LLM from `ChargeDescriptionMaster`.
- `Diagnose`/`Assess` commands exist but are **not** linked to charges.
- A mature amendment workflow already exists: routes (direct-edit / void-recreate / custom-command-routed), an `EDITABLE_AMEND_SECTIONS` allowlist, and endpoints `/insert-commands`, `/edit-existing-commands`, `/delete-existing-commands`, `/insert-metadata`, `/verify-commands`, `/sign-note` in `hyperscribe/scribe/api/session_view.py`, with effects built in `hyperscribe/scribe/commands/builder.py`.
- Nothing yet writes units/modifiers/diagnosis-pointers, and there is no diagnosis-rank control or charges matrix.

### The decisive constraint (verified against the installed Canvas SDK)
- **`PerformCommand` cannot carry units, modifiers, or diagnosis pointers** — it only has `cpt_code` and `notes`.
- All three live on the **`BillingLineItem`** (the note-footer line the home-app auto-creates when a `PerformCommand` commits):
  - `BillingLineItem.assessment_ids` — "diagnosis pointers" → `Assessment` ids.
  - `BillingLineItem.modifiers` — list of `Coding`.
  - `BillingLineItem.units` — integer (we leave at default 1).
- The SDK exposes effects to write these: `AddBillingLineItem(note_id, cpt, units, assessment_ids, modifiers)`, `UpdateBillingLineItem(billing_line_item_id, cpt?, units?, assessment_ids?, modifiers?)` (only sets the fields provided), and `RemoveBillingLineItem(billing_line_item_id)`.
- A `BillingLineItem` records `command_type` and `command_id`, so it can be matched **precisely** back to the `PerformCommand` that created it (better than matching loosely on `cpt + note`, which is ambiguous when two charges share a CPT).
- **Diagnosis rank:** `ClaimDiagnosisCode.rank` exists and orders the claim's diagnoses, but there is **no SDK effect to set it**. Rank is derived by the home-app from the **order in which diagnosis commands are inserted into the note** (confirmed: this is how PR #257 achieves rank today). `ClaimEffect` covers only labels/queue/comments/payments/metadata/banners/providers — not rank.

## 3. Architecture (Approach A: deterministic in-pipeline enrichment)

Charges remain `PerformCommand`s and continue to ride the existing command and amendment plumbing. Enrichment (modifiers + diagnosis pointers) is written by a **deterministic, sequenced step with no event handlers**. This is the core decision that distinguishes this work from PR #257's `ClaimLinkSync` (POST_COMMIT) and `PerformBillingLineItemRemoval` (POST_ENTER_IN_ERROR) handlers.

### UI → Canvas mapping

| Matrix element | Canvas write |
|---|---|
| Diagnosis row (rank-numbered, draggable) | a `Diagnose`/`Assess` command → produces a `Note` `Assessment`; **row order = command-insertion order = `ClaimDiagnosisCode.rank`** |
| Charge column (`+` adds one) | a `PerformCommand` (CPT only); home-app auto-creates its `BillingLineItem` on commit |
| Cell checkbox (diagnosis ↔ charge) | adds that row's `Assessment` id to the charge's `BillingLineItem.assessment_ids` |
| Column `+ Modifier` / chip | appends/edits a `Coding` (CPT system) in `BillingLineItem.modifiers` |
| Column footer `n / 4 ✓` | derived display of linked-pointer count |

No new database tables. The only state beyond the commands themselves is the enrichment pushed onto the BLI.

### New backend surface
- A single new endpoint, **`/enrich-charges`** (working name), in `hyperscribe/scribe/api/session_view.py`, author-authorized like the other edit endpoints (`_authorize_edit`).
- A **charge-enrichment resolver** module that, given the per-charge payload, resolves diagnosis links to `Assessment` ids, finds each charge's BLI by `command_type`+`command_id`, and returns `UpdateBillingLineItem` / `AddBillingLineItem` / `RemoveBillingLineItem` effects.
- A **shared validator** (used by both the UI and the write path) enforcing the caps in §6.

## 4. Request pipeline

### First approval (extends the existing insert → verify → sign sequence)
1. **Insert diagnosis commands first**, in matrix-row order. Row order *is* the rank — the frontend orders the `commands[]` diagnosis slice to match the matrix before calling `/insert-commands`.
2. **Insert charge `PerformCommand`s** (originate + commit). The home-app creates one `BillingLineItem` per committed charge.
3. **`/enrich-charges`**: for each charge, resolve its linked diagnosis rows → `Assessment` ids, locate its BLI by `command_id`, and emit `UpdateBillingLineItem(assessment_ids=…, modifiers=…)`.
4. **Sign.**

Because step 3 runs as a separate request *after* step 2's effects have been applied, every `Assessment` and every `BillingLineItem` already exists when enrichment resolves — eliminating the ordering races that an event handler must guard against.

### Amendment ("Make Changes")
Charge edits ride the existing amendment plumbing; no extra confirm UI. Rules:
- **Existing diagnosis rows: rank-locked.** Drag disabled. Their command-insertion order (hence rank) is not disturbed.
- **Net-new diagnosis rows: reorderable among themselves**, inserted after the existing ones → appended ranks.
- **Existing charge enrichment edits** (toggle pointer, add/remove modifier): **in-place `UpdateBillingLineItem`** by `command_id`. No void/recreate — `UpdateBillingLineItem` only writes the fields provided.
- **Remove an existing charge:** `PerformCommand` enter-in-error **plus an explicit `RemoveBillingLineItem`** for its BLI (deterministic; we do not rely on an implicit cascade).
- **Add a charge in amend:** originate + commit via the existing amend-insert route → then enrich.
- Pipeline order in amend stays **deletes → inserts → enrich/edits**, so any net-new diagnosis exists before a charge points at it.

## 5. Assessment-link resolution (the one inherent fragility, contained)

There is **no direct `Command → Assessment` foreign key** in the SDK (`Assessment` links to `Condition`, not to the originating command). Resolving "this diagnosis row → which `Assessment` id" therefore must join through the condition/coding — the same join PR #257 used.

The risk reduction is *where and when* the join happens:
- **Once, synchronously, at enrich time**, when every assessment for the note already exists — inside a single, unit-tested resolver — instead of reactively inside a `POST_COMMIT` handler racing command creation.
- Pointer state is keyed by **diagnosis row identity (the diagnosis command's `command_uuid`)**, not by raw ICD code or row index, so repeated ICD codes and reordering don't corrupt links.
- The resolver disambiguates when a note has multiple assessments for the same condition, and is covered by explicit tests for that case.
- Assessment queries use `prefetch_related` to avoid N+1 and exclude `entered_in_error` rows.

## 6. Validation rules (shared validator, UI + write path)
- **≥1 diagnosis pointer per charge** before "Accept and sign" is enabled. A charge with 0 pointers shows an inline error and its footer pill renders red `0 / 4`; the sign button is disabled with a reason ("Resolve N issue(s) to sign").
- **≤4 diagnosis pointers per charge** (CMS-1500 box 24E). The 4th check disables remaining unchecked boxes in that column; footer pill shows `4 / 4`.
- **≤4 modifiers per charge** (CMS cap). The `+ Modifier` affordance hides at 4.
- Modifiers are standard CPT modifier codes entered via a searchable picker (code + description), stored as `Coding` with the CPT system. Seed/common list: `25, 59, 95, LT, RT, 76`.

The same validator function is the single source of truth, called by the frontend (to gate the button) and by `/enrich-charges` (to reject invalid writes defensively).

## 7. Frontend

A new charges-matrix component replaces the flat charge list in the CHARGES section (rows = diagnoses, columns = charges), recreated inside the Canvas codebase using its component library and the exact tokens/layout from the design handoff (`design_handoff_charges_matrix`). The handoff HTML/JSX is a visual+behavioral reference, not a dependency.

**Per-claim UI state:**
- `diagnoses: [{ command_uuid, code, label, rank, locked }]` — array order = rank; `locked` true for already-entered diagnoses during amendment.
- `charges: [{ command_uuid?, cpt, description, modifiers: string[] /* ≤4 */, pointers: command_uuid[] /* ≤4, diagnosis row ids */ }]`.
- Derived: per-charge pointer count, per-charge validity (≥1 pointer), global "can sign".
- Reorder mutates the `diagnoses` array (and, for unlocked rows only, the underlying `commands[]` order); **pointers follow the diagnosis identity, not the row position**.

Interaction patterns (drag-to-reorder, checkbox cells) may borrow from PR #257 where sound, but the component is built clean. The design agent owns visual polish; this spec owns the data contract behind it.

### Amendment: locked-rank affordance
During an amendment, the matrix shows two diagnosis groups, using primitives the handoff already provides (`Lock` glyph in `primitives.jsx`; the `showGrips` toggle that swaps the 6-dot grip for a blank gutter in `dirs-matrix.jsx`):

```
ON THE SIGNED CLAIM
 🔒 1  M25511  Pain in right shoulder      (locked rank, no grip, muted rank chip)
 🔒 2  K219    GERD w/o esophagitis
── added in this amendment ──────────
 ⠿ 3  J029    Acute pharyngitis            (grip shown, draggable)
 ⠿ 4  R51     Headache
```

- **Locked rows** (`locked: true`): the `Lock` glyph replaces the drag grip, rank chip rendered muted; row is not draggable.
- A **labeled divider** ("added in this amendment") separates the locked group (top, ranks 1..k) from the net-new group (bottom, ranks k+1..n).
- **Drag is constrained to below the divider:** a net-new row can only be dropped within the net-new group; it cannot move above the last locked row. The drop zone/boundary is highlighted during drag.
- Outside amendment (first approval) every row shows the grip and is freely reorderable; the divider and lock glyphs do not appear.

## 8. Testing strategy
- **Resolver unit tests:** `command_uuid` → `Assessment` id mapping; duplicate-condition disambiguation; modifier `Coding` construction; BLI lookup by `command_id`; exclusion of `entered_in_error` assessments.
- **Endpoint tests** for `/enrich-charges`: auth (author-only), happy path, invalid payloads, validator rejections.
- **Validator tests:** ≥1-pointer gate, 4-pointer cap, 4-modifier cap.
- **Pipeline/amendment tests:** first-approval ordering (diagnoses → charges → enrich); existing-diagnosis drag locked; net-new reorder; existing-charge in-place `UpdateBillingLineItem`; charge removal emits `RemoveBillingLineItem`; amend order deletes → inserts → enrich.
- **Frontend state-reducer tests:** rank derivation from order, pointers-follow-diagnosis on reorder, cap enforcement, can-sign derivation.
- Meets the repo bar: `uv run mypy --config-file=mypy.ini .` clean and `uv run pytest tests/` at the project's coverage threshold (~90%). Use the `cpa:testing` skill during implementation.

## 9. Items to verify on a live instance before finalizing (do not assume)
1. **BLI queryable post-commit:** confirm the `BillingLineItem` created for a committed `PerformCommand` is queryable on the follow-up `/enrich-charges` request, and findable by `command_type`+`command_id`.
2. **Rank derivation:** confirm `ClaimDiagnosisCode.rank` follows diagnosis command-insertion order end-to-end (claim reflects matrix order).
3. **Modifier coding shape:** confirm the exact `Coding` system/value the BLI expects for CPT modifiers.

These are explicit verification steps (via CPA UAT on a playground instance), not design assumptions — directly addressing how PR #257 drifted by building on unverified behavior.

## 10. Risks and mitigations
| Risk | Mitigation |
|---|---|
| Assessment-link join ambiguity (no command→assessment FK) | single tested resolver, keyed by diagnosis `command_uuid`, run when all assessments exist; duplicate-condition tests |
| BLI not present when enrichment runs | enrichment is a separate request after commit; verify item §9.1; defensive handling if a BLI is missing |
| Rank assumption wrong | verify item §9.2 before relying on it; rank already works this way in #257 |
| Amendment mutating an already-claimed line | scoped rules in §4; existing dx rank locked; in-place update only for charge enrichment |
| Scope creep (the #257 failure mode) | one focused PR; units and AI-extraction explicitly out; each write path independently revertable |

## 11. Concern isolation (independently revertable write paths)
Even though delivered as one PR, the four concerns are kept separable so any one can be reverted without unwinding the others:
- **Modifiers** — column-header picker + modifier portion of the enrichment write.
- **Diagnosis pointers + cap** — cell checkboxes + `assessment_ids` portion of the enrichment write + shared validator.
- **Rank reorder** — diagnosis-row drag + `commands[]` ordering at insert.
- **Amendment behavior** — the `isAmending` rules in §4.
