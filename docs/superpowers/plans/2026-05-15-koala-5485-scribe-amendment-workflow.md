# Scribe-Tab Amendment Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the note author add new commands to a finalized Scribe tab via a "Make changes" affordance, without allowing edits to already-committed commands.

**Architecture:** Mostly frontend. One small backend field (`was_finalized` on `ScribeSummary`) gives the frontend a "this scribe has been finalized at least once" signal that survives reloads and distinguishes amending from drafting. UI gains a status pill at the top of the Scribe tab; per-command rows already accept a `readOnly` prop in most places (we just need to OR it with `c.already_documented` in the few sites that don't). The existing Approve flow handles re-finalization since `commands.filter(c => !c.already_documented ...)` is the existing insertable selector — we just need to stamp `already_documented: true` after Approve (a latent bug in today's flow that this work fixes).

**Tech Stack:** Python 3.12, Django 5.2, `canvas_sdk`, pytest, Preact 10 + htm (vanilla JS, no test framework, no build step), CSS.

**Spec:** `docs/superpowers/specs/2026-05-15-koala-5485-scribe-amendment-workflow-design.md`.

---

## File Structure

**Backend (`hyperscribe/`):**
- `models/scribe.py` — add `was_finalized` field on `ScribeSummary`.
- `scribe/api/session_view.py` — latch `was_finalized=True` in `_save_summary` when `approved=True`; surface in `/summary` GET response.

**Frontend (`hyperscribe/scribe/static/`):**
- `summary.js` — read `was_finalized` on load; stamp `already_documented: true` on commands post-Approve; render new status pill; add `handleMakeChanges` handler; pass `readOnly={readOnly || c.already_documented}` where missing in render sites.
- `soap-group.js` — add `|| entry.command.already_documented` to the `readOnly` prop pass-through sites that don't have it (audit identified ~12 sites missing the check vs. 5 that have it).
- `recommended-group.js` — hide Add Now buttons when in amending mode.
- `styles.css` — `.summary-status-pill` + variants; `.command-locked` modifier.

**Tests (`tests/hyperscribe/scribe/`):**
- `api/test_session_view.py` — extend existing save-summary tests for the `was_finalized` latch; extend get-summary test for the field on the response.

---

## Conventions for this plan

- The repo's pre-commit hook runs `ruff format .` repo-wide on every commit and occasionally pulls in unrelated formatter drift in 8–11 files. **Include the drift in each commit** — do not use `SKIP=ruff-format` or `--no-verify`. Memory: this is intentional so future rebases stay clean.
- The `uv.lock` file gets a metadata migration the first time `uv run` fires in a session. Stage it alongside.
- **Never commit attribution to Claude.** No `Co-Authored-By: Claude` trailer, no "🤖 Generated with…" footer, no `claude` in branch names. Memory.
- All work happens on the existing branch `nuno/scribe-amendment-workflow` (already created from `feat/canvas-scribe`).

---

## Task 1: Add `was_finalized` field to `ScribeSummary` model

**Files:**
- Modify: `hyperscribe/models/scribe.py`

- [ ] **Step 1: Add the field**

In `ScribeSummary` class, alongside `approved`, add:

```python
class ScribeSummary(CustomModel):
    """Stores the generated summary, commands, and recommendations for a note."""

    note: Any = OneToOneField(
        NoteProxy,
        to_field="dbid",
        on_delete=DO_NOTHING,
        related_name="%(app_label)s__summary",
        primary_key=True,
    )
    note_data: Any = JSONField(default=dict)
    commands: Any = JSONField(default=list)
    recommendations: Any = JSONField(default=list)
    unmatched_conditions: Any = JSONField(default=list)
    diagnosis_suggestions: Any = JSONField(default=dict)
    approved: Any = BooleanField(default=False)
    was_finalized: Any = BooleanField(default=False)
    selected_template_name: Any = TextField(default="")
    mode: Any = TextField(default="")
    raw_response: Any = JSONField(default=dict)
    updated_at: Any = DateTimeField(auto_now=True)
```

- [ ] **Step 2: Run the full test suite to confirm no break**

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && uv run pytest tests/hyperscribe/scribe/ -x`
Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
cd ~/Work/Glazed/Canvas/canvas-hyperscribe
git add hyperscribe/models/scribe.py
git commit -m "feat: add was_finalized field to ScribeSummary

One-way latch for the Scribe-tab amendment workflow. Flips True the
first time a scribe is approved; distinct from the live approved
toggle so the frontend can render the amendment pill on reload.

KOALA-5485"
```

If pre-commit pulls in drift, `git add` the drifted files and re-commit per the conventions section. Same body.

---

## Task 2: `_save_summary` latches `was_finalized=True` on `approved=True`

**Files:**
- Modify: `hyperscribe/scribe/api/session_view.py:197-213` (the `_save_summary` helper)
- Test: `tests/hyperscribe/scribe/api/test_session_view.py`

- [ ] **Step 1: Write the failing tests**

Find the helper `_heal_summary_row` (around line 270 in `test_session_view.py`) and the existing `test_save_summary_success` test (around line 271, before the `test_get_summary_heals_blank_mode_from_start_ai`). Append two new tests after the existing `test_save_summary_*` block:

```python
@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
def test_save_summary_latches_was_finalized_on_approve(
    mock_summary: MagicMock, mock_note: MagicMock
) -> None:
    """First save with approved=True sets was_finalized=True via the defaults
    passed to update_or_create. Subsequent saves with approved=False keep
    was_finalized=True implicitly because the field is omitted from defaults."""
    mock_note.objects.values_list.return_value.get.return_value = 42

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({
        "note_id": "42",
        "note": {},
        "commands": [],
        "approved": True,
    }))
    view.post_save_summary()

    mock_summary.objects.update_or_create.assert_called_once()
    _, kwargs = mock_summary.objects.update_or_create.call_args
    assert kwargs["note_id"] == 42
    assert kwargs["defaults"]["approved"] is True
    assert kwargs["defaults"]["was_finalized"] is True


@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
def test_save_summary_does_not_set_was_finalized_when_unapproved(
    mock_summary: MagicMock, mock_note: MagicMock
) -> None:
    """Save with approved=False must NOT include was_finalized in defaults,
    so the existing column value (potentially True from a prior approval)
    is preserved by update_or_create."""
    mock_note.objects.values_list.return_value.get.return_value = 42

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({
        "note_id": "42",
        "note": {},
        "commands": [],
        "approved": False,
    }))
    view.post_save_summary()

    mock_summary.objects.update_or_create.assert_called_once()
    _, kwargs = mock_summary.objects.update_or_create.call_args
    assert "was_finalized" not in kwargs["defaults"]
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && uv run pytest tests/hyperscribe/scribe/api/test_session_view.py::test_save_summary_latches_was_finalized_on_approve tests/hyperscribe/scribe/api/test_session_view.py::test_save_summary_does_not_set_was_finalized_when_unapproved -v`
Expected: BOTH fail with KeyError or AssertionError because `was_finalized` isn't in defaults yet.

- [ ] **Step 3: Implement the latch in `_save_summary`**

In `hyperscribe/scribe/api/session_view.py`, find `_save_summary` (line 197). Replace it with:

```python
def _save_summary(note_id: str, payload: dict[str, Any]) -> None:
    note_dbid = Note.objects.values_list("dbid", flat=True).get(id=note_id)
    defaults: dict[str, Any] = {
        "note_data": payload.get("note") or {},
        "commands": payload.get("commands") or [],
        "approved": payload.get("approved", False),
        "recommendations": payload.get("recommendations") or [],
        "unmatched_conditions": payload.get("unmatched_conditions") or [],
        "diagnosis_suggestions": payload.get("diagnosis_suggestions") or {},
    }
    # One-way latch: was_finalized goes True the first time approved=True
    # is written and is never reset to False. Achieved by only putting it
    # in defaults when approved is True; update_or_create leaves the column
    # alone when the key isn't in defaults.
    if payload.get("approved"):
        defaults["was_finalized"] = True
    if "selected_template_name" in payload:
        defaults["selected_template_name"] = payload["selected_template_name"] or ""
    if "mode" in payload:
        defaults["mode"] = payload["mode"] or ""
    if "raw_response" in payload:
        defaults["raw_response"] = payload["raw_response"]
    ScribeSummary.objects.update_or_create(note_id=note_dbid, defaults=defaults)
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && uv run pytest tests/hyperscribe/scribe/api/test_session_view.py::test_save_summary_latches_was_finalized_on_approve tests/hyperscribe/scribe/api/test_session_view.py::test_save_summary_does_not_set_was_finalized_when_unapproved -v`
Expected: BOTH pass.

- [ ] **Step 5: Run the full session_view test suite to confirm no regressions**

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && uv run pytest tests/hyperscribe/scribe/api/test_session_view.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd ~/Work/Glazed/Canvas/canvas-hyperscribe
git add hyperscribe/scribe/api/session_view.py tests/hyperscribe/scribe/api/test_session_view.py
git commit -m "feat: latch was_finalized=True on first approved save

Server-side enforcement of the was_finalized one-way flag. The flag
flips True whenever /save-summary receives approved=True and stays True
on subsequent approved=False writes (update_or_create only touches keys
present in defaults, so omitting was_finalized preserves it).

KOALA-5485"
```

Include any drift / lockfile changes pre-commit pulls in.

---

## Task 3: `/summary` GET surfaces `was_finalized`

**Files:**
- Modify: `hyperscribe/scribe/api/session_view.py` (the `get_summary` route around line 480-545)
- Test: `tests/hyperscribe/scribe/api/test_session_view.py`

- [ ] **Step 1: Identify the response builder**

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && grep -n '"approved":\s*summary' hyperscribe/scribe/api/session_view.py | head -5`
Expect to find the place where `get_summary` builds its `JSONResponse` body (look for the dict that includes `"approved": summary["approved"]` or similar). Note the line number.

- [ ] **Step 2: Add a failing test**

Append to `tests/hyperscribe/scribe/api/test_session_view.py` after the existing `test_get_summary_*` block:

```python
@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.ScribeAuditLog")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_surfaces_was_finalized(
    mock_note: MagicMock, mock_summary: MagicMock, mock_audit: MagicMock, mock_transcript: MagicMock
) -> None:
    """/summary GET response includes the was_finalized latch so the
    frontend can render the amendment pill on reload."""
    mock_note.objects.values_list.return_value.get.return_value = 42
    summary_row = _heal_summary_row(note_data={"sections": []})
    summary_row["was_finalized"] = True
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = summary_row
    mock_audit.objects.filter.return_value.values_list.return_value.first.return_value = []

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    body = json.loads(result[0].content)
    assert body["was_finalized"] is True
```

Also extend `_heal_summary_row` (around line 263) to include the new field by default:

```python
def _heal_summary_row(
    note_data: dict | None = None, commands: list | None = None, mode: str | None = None
) -> dict:
    return {
        "note_data": note_data or {},
        "commands": commands or [],
        "approved": False,
        "was_finalized": False,
        "recommendations": [],
        "unmatched_conditions": [],
        "diagnosis_suggestions": {},
        "selected_template_name": "",
        "mode": mode if mode is not None else "",
    }
```

- [ ] **Step 3: Run the test and verify it fails**

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && uv run pytest tests/hyperscribe/scribe/api/test_session_view.py::test_get_summary_surfaces_was_finalized -v`
Expected: FAIL with `KeyError: 'was_finalized'` (response body doesn't have the field yet).

- [ ] **Step 4: Add the field to the get_summary response and the values() query**

In `hyperscribe/scribe/api/session_view.py`, find the `get_summary` route. Two changes:

a. The `ScribeSummary.objects.filter(...).values(...)` call needs `"was_finalized"` added to the field list it selects.

b. The response dict (the `JSONResponse({...}, ...)` near the end of `get_summary`) needs `"was_finalized": summary.get("was_finalized", False)` added.

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && grep -n '\.values(' hyperscribe/scribe/api/session_view.py | head -5` to find the exact call site, then edit both lines to add `was_finalized`.

- [ ] **Step 5: Run the test and verify it passes**

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && uv run pytest tests/hyperscribe/scribe/api/test_session_view.py::test_get_summary_surfaces_was_finalized -v`
Expected: PASS.

- [ ] **Step 6: Run the full session_view tests to confirm no regressions**

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && uv run pytest tests/hyperscribe/scribe/api/test_session_view.py -v`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add hyperscribe/scribe/api/session_view.py tests/hyperscribe/scribe/api/test_session_view.py
git commit -m "feat: surface was_finalized in /summary response

Frontend reads this on reload to decide between drafting and amending
state. Updates the values() select and the response body.

KOALA-5485"
```

---

## Task 4: Pass `was_finalized` into the Scribe React component on initial render

**Files:**
- Modify: `hyperscribe/scribe/static/summary.js`
- Modify: `hyperscribe/scribe/static/app.js` (passes initialData / props into Scribe)
- Modify: Server-side template renderer if any (check what renders the iframe)

- [ ] **Step 1: Confirm the prop pipeline**

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && grep -n 'approved' hyperscribe/scribe/static/app.js | head -5`

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && grep -n 'initialData\|initSummary' hyperscribe/scribe/static/summary.js | head -10`

The `initialData` flows from `app.js` into `Scribe`. `initSummary = initialData?.summary ?? null`. The summary object should naturally include `was_finalized` once the backend returns it (Task 3). No prop pipeline change needed if Scribe reads from `initialData.summary`.

- [ ] **Step 2: Add was_finalized state to the Scribe component**

In `hyperscribe/scribe/static/summary.js`, find the `approved` useState (around line 214):

```javascript
const [approved, setApproved] = useState(initSummary?.approved ?? false);
```

Right after it, add:

```javascript
const [wasFinalized, setWasFinalized] = useState(initSummary?.was_finalized ?? false);
```

- [ ] **Step 3: Hydrate wasFinalized when /summary loads from cache**

In the `loadOrGenerate` useEffect (around line 321 in summary.js), find the cached state restoration block. Find where `cached.approved` is handled (around line 333) and add right after:

```javascript
if (cached.was_finalized) {
  setWasFinalized(true);
}
```

- [ ] **Step 4: Reinstall the plugin and verify the prop reaches React state**

```bash
canvas install ~/Work/Glazed/Canvas/canvas-hyperscribe/hyperscribe/ --host http://localhost:8000
```

In the browser DevTools console (Scribe iframe), check that `was_finalized` flows through:

```javascript
const win = document.querySelector('iframe[title="Application Frame"]').contentWindow;
await fetch('/plugin-io/api/hyperscribe/scribe-session/summary?note_id=YOUR_NOTE_UUID', {credentials: 'include'}).then(r => r.json()).then(j => j.was_finalized);
```

Replace `YOUR_NOTE_UUID` with the iframe's note id. Expected: `false` for a non-yet-approved note. No JS errors in the console.

- [ ] **Step 5: Commit**

```bash
git add hyperscribe/scribe/static/summary.js
git commit -m "feat: read was_finalized from cache into Scribe React state

Mirrors the existing pattern for cached.approved. wasFinalized stays a
React state so the pill render can react to changes within the
session.

KOALA-5485"
```

---

## Task 5: Stamp `already_documented: true` on commands after Approve

**Files:**
- Modify: `hyperscribe/scribe/static/summary.js` (the post-Approve UUID stamping block, around lines 1290-1305)

This is a latent bug fix: today's full-Approve flow stamps `command_uuid` on inserted commands but NOT `already_documented`. Re-approving in amendment mode would otherwise double-insert.

- [ ] **Step 1: Find the post-Approve mapping block**

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && grep -n 'uuidMap\|attempted.map' hyperscribe/scribe/static/summary.js | head -5`

The block is around line 1293-1300. Look for `const uuidMap = new Map(data.attempted.map(...))` followed by `updatedCommands = commands.map(...)`.

- [ ] **Step 2: Modify the mapping to also stamp `already_documented: true`**

Replace this block:

```javascript
if (data.attempted && data.attempted.length > 0) {
  const uuidMap = new Map(data.attempted.map(a => [`${a.command_type}:${a.display}`, a.command_uuid]));
  updatedCommands = commands.map(cmd => {
    const key = `${cmd.command_type}:${(cmd.display || '').slice(0, 80)}`;
    const uuid = uuidMap.get(key);
    return uuid ? { ...cmd, command_uuid: uuid } : cmd;
  });
```

With:

```javascript
if (data.attempted && data.attempted.length > 0) {
  const uuidMap = new Map(data.attempted.map(a => [`${a.command_type}:${a.display}`, a.command_uuid]));
  updatedCommands = commands.map(cmd => {
    const key = `${cmd.command_type}:${(cmd.display || '').slice(0, 80)}`;
    const uuid = uuidMap.get(key);
    // Stamp already_documented=true alongside command_uuid so the existing
    // `insertable` filter naturally excludes these commands on re-Approve
    // during amendment. Today's flow only sets already_documented from the
    // Add Now path; the full-Approve path skipped it, which would have
    // caused double-insertion on re-Approve. (KOALA-5485)
    return uuid ? { ...cmd, command_uuid: uuid, already_documented: true } : cmd;
  });
```

- [ ] **Step 3: Reinstall and manually verify**

```bash
canvas install ~/Work/Glazed/Canvas/canvas-hyperscribe/hyperscribe/ --host http://localhost:8000
```

In a Larry-authored note on the test patient, run a manual scribe (add a Plan), click Approve. After the approve completes, in DevTools console:

```javascript
const win = document.querySelector('iframe[title="Application Frame"]').contentWindow;
await fetch('/plugin-io/api/hyperscribe/scribe-session/summary?note_id=' + new URL(win.location).searchParams.get('note_id'), {credentials: 'include'}).then(r => r.json()).then(j => j.commands.map(c => ({type: c.command_type, uuid: c.command_uuid, already_doc: c.already_documented})));
```

Expected: the just-inserted commands have BOTH `uuid` (truthy) and `already_documented: true`.

- [ ] **Step 4: Commit**

```bash
git add hyperscribe/scribe/static/summary.js
git commit -m "fix: stamp already_documented=true on commands after Approve

Latent bug: today's full-Approve flow stamps command_uuid on inserted
commands but not already_documented. Re-approving (impossible today
because canEdit gates it, but enabled by the amendment workflow)
would have double-inserted. Stamp both so the insertable filter
correctly excludes prior approvals.

KOALA-5485"
```

---

## Task 6: Wire the "Make changes" → amendment-mode flip

**Files:**
- Modify: `hyperscribe/scribe/static/summary.js`

- [ ] **Step 1: Add `handleMakeChanges` handler**

In `hyperscribe/scribe/static/summary.js`, after the `saveSummaryToCache` callback definition (~line 340, after the closing `}, [noteId, isAuthor, isNoteEditable]);` from KOALA-5475 work), add:

```javascript
const handleMakeChanges = useCallback(() => {
  if (!isAuthor || !isNoteEditable || !approved) return;
  logEvent('AMENDMENT_STARTED', {
    commands_at_start: commands.filter(c => c.already_documented).length,
  });
  setApproved(false);
  // Optimistically keep wasFinalized=true; it's a one-way latch server-side
  // already, but ensure the React state matches without waiting for the
  // /summary refetch.
  setWasFinalized(true);
}, [isAuthor, isNoteEditable, approved, commands]);
```

The `setApproved(false)` triggers the existing debounced `commandsSaveRef` useEffect (around line 427), which fires `saveSummaryToCache` with `approved: false` — persisting the amendment state.

- [ ] **Step 2: No render change yet**

This task only adds the handler. The pill (next task) wires the button to it. No manual UAT step here; the next task verifies end-to-end.

- [ ] **Step 3: Commit**

```bash
git add hyperscribe/scribe/static/summary.js
git commit -m "feat: add handleMakeChanges to flip Scribe into amending mode

Emits AMENDMENT_STARTED audit event with the count of already-
documented commands at the start. Flips approved to false (triggering
the existing autosave) and keeps wasFinalized true.

KOALA-5485"
```

---

## Task 7: CSS for the status pill and locked-command modifier

**Files:**
- Modify: `hyperscribe/scribe/static/styles.css`

- [ ] **Step 1: Add the rules**

Find the existing `.readonly-banner` rules in `styles.css` (around line 404). Below them (and below the `.readonly-banner--alert` rule from KOALA-5475), add:

```css
/* Status pill at the top of the Scribe tab. Sticky indicator of finalize
   state with an inline action button. Two variants: finalized (neutral
   green) and amending (amber, more urgent). */
.summary-status-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 24px;
  font-size: 13px;
  line-height: 1.4;
  border-bottom: 1px solid #e8e8ec;
}

.summary-status-pill-icon {
  flex-shrink: 0;
}

.summary-status-pill-text {
  flex: 1;
  font-weight: 500;
}

.summary-status-pill-btn {
  flex-shrink: 0;
  padding: 4px 12px;
  border-radius: 14px;
  border: 1px solid currentColor;
  background: transparent;
  color: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.summary-status-pill-btn:hover {
  background: rgba(0, 0, 0, 0.06);
}

.summary-status-pill--finalized {
  background: #ecf7ee;
  border-bottom-color: #cce6d0;
  color: #245d2a;
}

.summary-status-pill--amending {
  background: #fff4d6;
  border-bottom-color: #f5d683;
  color: #6b4a00;
}

/* Per-command lock treatment used in amending mode. Cards with
   already_documented=true get this on top of their existing styles
   to read as "already on the note". */
.command-locked {
  opacity: 0.6;
  filter: saturate(0.85);
  position: relative;
}

.command-locked .command-row-icon-lock {
  position: absolute;
  top: 8px;
  right: 8px;
  color: #6b7280;
}
```

- [ ] **Step 2: Verify CSS parses**

The plugin install + page reload will surface any syntax error. No standalone test for CSS in this repo.

- [ ] **Step 3: Commit**

```bash
git add hyperscribe/scribe/static/styles.css
git commit -m "feat: styles for Scribe amendment status pill and locked cards

.summary-status-pill / --finalized / --amending variants and a
.command-locked modifier for cards whose already_documented is true.

KOALA-5485"
```

---

## Task 8: Render the status pill

**Files:**
- Modify: `hyperscribe/scribe/static/summary.js`

- [ ] **Step 1: Add pill JSX above the existing read-only banners**

Find the JSX in `summary.js` that starts `return html\`` near line 1540 (the `<div class="summary-container">` block). The existing structure is:

```javascript
return html`
  <div class=${`summary-container...`}>
    ${sessionLost && html`<div class="readonly-banner readonly-banner--alert" ...>`}
    ${readOnlyReason === 'locked' && html`<div class="readonly-banner" ...>`}
    ${readOnlyReason === 'non_author' && html`<div class="readonly-banner" ...>`}
    ...
```

Insert the pill above `${sessionLost && ...}`:

```javascript
return html`
  <div class=${`summary-container${!canEdit && !approved ? ' summary-container--readonly' : ''}`}>
    ${isAuthor && isNoteEditable && wasFinalized && html`
      <div class=${`summary-status-pill summary-status-pill--${approved ? 'finalized' : 'amending'}`} role="status" aria-live="polite">
        <svg class="summary-status-pill-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          ${approved
            ? html`<polyline points="20 6 9 17 4 12"/>`
            : html`<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>`
          }
        </svg>
        <span class="summary-status-pill-text">
          ${approved ? 'Charting finalized' : 'Editing charting'}
        </span>
        ${approved && html`
          <button class="summary-status-pill-btn" onClick=${handleMakeChanges} disabled=${!canEdit && !approved}>
            Make changes
          </button>
        `}
      </div>
    `}
    ${sessionLost && html`
      ...
```

(Keep the rest of the existing JSX after this point untouched.)

- [ ] **Step 2: Reinstall, reload, and manually verify**

```bash
canvas install ~/Work/Glazed/Canvas/canvas-hyperscribe/hyperscribe/ --host http://localhost:8000
```

Reload the patient page. On a Larry-authored Scribe iframe that **has been previously approved**, the pill should render at the top with `✓ Charting finalized` and a "Make changes" button.

If no such note exists, run a manual scribe + approve in a fresh note first. Then reload to see the pill.

Click "Make changes". The pill should flip to `✏️ Editing charting` (no right-side button). The bottom Approve button area should reappear.

In DevTools console:

```javascript
const win = document.querySelector('iframe[title="Application Frame"]').contentWindow;
await fetch('/plugin-io/api/hyperscribe/scribe-session/summary?note_id=' + new URL(win.location).searchParams.get('note_id'), {credentials: 'include'}).then(r => r.json()).then(j => ({approved: j.approved, was_finalized: j.was_finalized}));
```

Expected after "Make changes" click + ~500ms debounce: `{approved: false, was_finalized: true}`.

- [ ] **Step 3: Commit**

```bash
git add hyperscribe/scribe/static/summary.js
git commit -m "feat: render Scribe amendment status pill

Top-of-tab pill that surfaces 'Charting finalized' with a Make changes
button, or 'Editing charting' during amendment. Gated on
isAuthor && isNoteEditable && wasFinalized so it only appears for the
note author when the scribe has been finalized at least once and the
note itself isn't locked.

KOALA-5485"
```

---

## Task 9: Lock already-documented commands in amending mode (per-row `readOnly`)

**Files:**
- Modify: `hyperscribe/scribe/static/soap-group.js`

The pattern `readOnly={readOnly || entry.command.already_documented}` already exists in 5 sites (lines 683, 857, 881, 908, 937, 1020 — verified by the spec-time grep). Mirror it in the sites that currently use plain `readOnly=${readOnly}` where the row corresponds to an editable command.

- [ ] **Step 1: Audit the sites that lack the already_documented check**

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && grep -n 'readOnly=\${readOnly}\|readOnly=\${readOnly ||' hyperscribe/scribe/static/soap-group.js`

The output lists every `readOnly=` site. The fix targets sites that pass `readOnly=${readOnly}` to row components whose command can be already_documented. Specifically: lines 606, 651, 732, 761, 773, 805, 829, 980, 999, 1046, 1087, 1110, 1142.

Open each line in context (5-10 lines of surroundings) and decide:

- If the wrapping render is iterating over `commands` (or has `entry.command` in scope), change `readOnly=${readOnly}` to `readOnly=${readOnly || entry.command.already_documented}`.
- If the render is for a section header / non-command / no `entry.command` accessor, leave it.

Apply the change at each applicable site. The change is mechanical: `readOnly=${readOnly}` → `readOnly=${readOnly || entry.command.already_documented}` (and add `|| isRejected` where the existing pattern includes it).

- [ ] **Step 2: Reinstall, reload, and manually verify**

```bash
canvas install ~/Work/Glazed/Canvas/canvas-hyperscribe/hyperscribe/ --host http://localhost:8000
```

On a finalized Scribe (from Task 8 setup), click "Make changes" to enter amending mode. **Expected:** the existing committed commands (Plans, Vitals, Assess, etc.) render with their inputs as plain text and no per-card edit affordances. The `+ Plan`, `+ Vitals`, etc. buttons remain enabled.

Click `+ Plan`, type something, save the card. **Expected:** the new Plan is fully editable. The previously-committed commands remain locked.

- [ ] **Step 3: Commit**

```bash
git add hyperscribe/scribe/static/soap-group.js
git commit -m "feat: lock already-documented commands during amendment

Mirrors the existing readOnly||already_documented pattern at the
remaining render sites in soap-group.js so amended scribes don't let
the provider edit commands that are already part of the signed note.

KOALA-5485"
```

---

## Task 10: Add `.command-locked` modifier + lock icon to documented cards

**Files:**
- Modify: `hyperscribe/scribe/static/soap-group.js` (or wherever the row container is rendered — likely the same line ranges as Task 9)

- [ ] **Step 1: Add the modifier to documented row wrappers**

This task is purely visual — `.command-locked` styling (from Task 7) needs to be applied to the row container `<div>` (or equivalent) when the row corresponds to an `already_documented` command. The grep from Task 9 found the `<CommandRow>`-style invocations; the container wrapping each row is usually a `<div class="soap-card" ...>` or similar.

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && grep -n 'soap-card\|command-card\|class="command-row"\|class=\${\`' hyperscribe/scribe/static/soap-group.js | head -20`

For each row container that wraps an editable command, add `${entry.command.already_documented ? ' command-locked' : ''}` to the class list. E.g.:

```javascript
<div class=${`soap-card${entry.command.already_documented ? ' command-locked' : ''}`}>
```

Inside the same wrapper, conditionally render a lock icon:

```javascript
${entry.command.already_documented && html`
  <svg class="command-row-icon-lock" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
  </svg>
`}
```

- [ ] **Step 2: Reinstall and verify**

```bash
canvas install ~/Work/Glazed/Canvas/canvas-hyperscribe/hyperscribe/ --host http://localhost:8000
```

Reload. In amending mode, already-documented cards should have a muted, slightly desaturated appearance with a lock icon in the corner. Newly-added cards should look normal.

- [ ] **Step 3: Commit**

```bash
git add hyperscribe/scribe/static/soap-group.js
git commit -m "feat: visual lock treatment for already-documented cards

Apply .command-locked modifier and a lock icon to rows whose command
is already_documented. Pairs with the readOnly gating so the locked
state reads both visually and behaviorally.

KOALA-5485"
```

---

## Task 11: Hide "Add Now" recommendations during amendment

**Files:**
- Modify: `hyperscribe/scribe/static/recommended-group.js`

- [ ] **Step 1: Locate the Add Now button render and the props**

Run: `cd ~/Work/Glazed/Canvas/canvas-hyperscribe && grep -n 'Add Now\|onAddNow\|add-now\|_added_now' hyperscribe/scribe/static/recommended-group.js | head -10`

The Add Now button is rendered when the rec is accepted but not yet added. We need to also gate it on "not in amending mode."

- [ ] **Step 2: Pass `isAmending` down from summary.js**

In `hyperscribe/scribe/static/summary.js`, find where `RecommendedGroup` (or similar) is invoked. Add an `isAmending=${!approved && wasFinalized}` prop.

- [ ] **Step 3: In `recommended-group.js`, gate the Add Now button on `!isAmending`**

Find the `Add Now` button's JSX. Wrap or modify so it only renders when `!isAmending`. Example:

```javascript
${!isAmending && html`
  <button class="add-now-btn" onClick=${...}>Add Now</button>
`}
```

- [ ] **Step 4: Reinstall and verify**

```bash
canvas install ~/Work/Glazed/Canvas/canvas-hyperscribe/hyperscribe/ --host http://localhost:8000
```

Reload. In drafting / finalized states, Add Now buttons render normally on accepted recommendations. In amending state, they don't render.

- [ ] **Step 5: Commit**

```bash
git add hyperscribe/scribe/static/summary.js hyperscribe/scribe/static/recommended-group.js
git commit -m "feat: hide recommendation Add Now buttons during amendment

Recommendations come from the original AI generation pass; we don't
re-run AI during amendment so re-surfacing the recs' Add Now buttons
feels stale. Provider can still add equivalent commands via the
section + buttons.

KOALA-5485"
```

---

## Task 12: End-to-end manual UAT

**Files:** none.

- [ ] **Step 1: Reinstall the plugin**

```bash
canvas install ~/Work/Glazed/Canvas/canvas-hyperscribe/hyperscribe/ --host http://localhost:8000
```

- [ ] **Step 2: Run the UAT plan from the spec**

Walk every numbered case in the spec's "Testing & verification → Manual UAT plan" section against localhost:

1. **State transitions**: Drafting → Finalized → Amending → Finalized (with new command), Amending → Finalized (empty re-approval).
2. **Per-command locking in amending mode**: existing cards locked, new cards editable, `+` buttons work, recs panel shows no Add Now.
3. **Authorization**: non-author view, locked-note view.
4. **Reload / re-mount mid-amendment**: state restores.
5. **Regression**: initial scribe approve flow, drafting flow, sign-then-lock flow (KOALA-5475 banner suppression still works).

Document any deviations and either fix inline (new task at end of plan) or file as a follow-up.

- [ ] **Step 3: Smoke test the end-to-end Brigade workflow**

Per the spec:
- Create a Larry-authored Office visit on the test patient.
- Run a scribe (Manual mode), add a Plan, Approve.
- Pill appears `✓ Charting finalized`.
- Click "Make changes". Pill flips to `✏️ Editing charting`. Add a second Plan. Approve. Verify both Plans on the note via the home-app note view (`http://localhost:8000/note/<note-uuid>`).
- Sign the note via home-app footer. Pill disappears. The existing "Click Amend in note footer" banner is what shows.
- Click home-app Amend. Note unlocks. Pill returns with "Make changes".

- [ ] **Step 4: If anything fails, file inline or follow-up**

If a step fails, capture the actual vs expected, fix on the same branch as new tasks, re-run UAT. If a step reveals an unrelated bug, file a follow-up ticket and continue.

---

## Task 13: Push and open PR

**Files:** none.

- [ ] **Step 1: Sanity check the branch state**

```bash
cd ~/Work/Glazed/Canvas/canvas-hyperscribe
git status -uno
git log --oneline -20
```

Expected: clean working tree; branch has the spec commits and the implementation commits.

- [ ] **Step 2: Push**

```bash
git push -u origin nuno/scribe-amendment-workflow
```

- [ ] **Step 3: Open the PR via `gh pr create`**

```bash
gh pr create --base feat/canvas-scribe --head nuno/scribe-amendment-workflow \
  --title "Scribe: amendment workflow — add new commands after finalize" \
  --body "$(cat <<'EOF'
[KOALA-5485](https://canvasmedical.atlassian.net/browse/KOALA-5485)

## Summary

Adds an amendment workflow to the Scribe tab so the note author can add new commands (orders, additional HPI/Vitals/Conditions/CPT) after finalizing the scribe — without allowing edits to commands that are already part of the signed note.

UI: a new status pill at the top of the Scribe tab. In finalized state it reads `✓ Charting finalized` with a "Make changes" button; clicking flips the tab into amending mode (pill: `✏️ Editing charting`, bottom Approve area returns). Already-committed commands are visually locked and behaviorally read-only; new commands the provider adds are fully editable. Re-clicking Approve inserts only the new commands (the existing `commands.filter(c => !c.already_documented)` selector handles this once we stamp `already_documented=true` after the first Approve — a latent bug this PR fixes).

Backend: one small field added to `ScribeSummary` — `was_finalized: BooleanField(default=False)` — as a one-way latch. Set to True whenever `/save-summary` receives `approved=True`; never reset. Lets the frontend distinguish "drafting" from "amending" on reload (both have `approved=false` but only amending has `was_finalized=true`).

## Files changed

**Backend (small):**
- `hyperscribe/models/scribe.py` — `was_finalized` field.
- `hyperscribe/scribe/api/session_view.py` — latch in `_save_summary`, surface in `/summary` GET.
- `tests/hyperscribe/scribe/api/test_session_view.py` — three new tests for the latch and the response field.

**Frontend (the bulk of the change):**
- `hyperscribe/scribe/static/summary.js` — read `was_finalized`, stamp `already_documented` after Approve, render the pill, `handleMakeChanges` handler, pass `isAmending` into recommendations.
- `hyperscribe/scribe/static/soap-group.js` — `readOnly || entry.command.already_documented` at the render sites that didn't already have the pattern; `.command-locked` modifier + lock icon on documented cards.
- `hyperscribe/scribe/static/recommended-group.js` — hide Add Now in amending mode.
- `hyperscribe/scribe/static/styles.css` — `.summary-status-pill` variants and `.command-locked` modifier.

## Test plan

- [x] `uv run pytest tests/hyperscribe/scribe/` — backend tests pass, including new `was_finalized` latch and response tests.
- [x] Manual UAT against local Canvas via Playwright + DevTools:
  - State transitions: Drafting → Finalized → Amending → Finalized (with and without new commands).
  - Per-command locking: existing cards locked + lock icon, new cards editable, recommendations' Add Now hidden during amendment.
  - Authorization: non-author and locked-note paths unchanged.
  - Reload mid-amendment: state restores via `was_finalized` from /summary.
  - Regression: drafting and finalized paths unchanged; KOALA-5475 banner suppression intact.
- [x] End-to-end smoke: create note → scribe → Approve → amend → Approve → sign → Amend → amend again.

## Out of scope (filed as follow-ups)

- Editing existing committed commands in place (per ticket: out of scope).
- Removing committed commands during amendment.
- Distinguishing amendment-added from original-approve-added commands in the post-finalized view (audit log already records timestamps).
- Re-running the AI pipeline against new audio during amendment.

## Spec

`docs/superpowers/specs/2026-05-15-koala-5485-scribe-amendment-workflow-design.md`
EOF
)"
```

The PR URL is returned on success. Done.

---

## Self-review notes

1. **Spec coverage**:
   - State machine → Tasks 4–8 cover read/render. ✅
   - UI treatment (pill + locked cards) → Tasks 7, 8, 10, 11. ✅
   - Data flow → Tasks 1–6. ✅
   - Server-side changes (was_finalized) → Tasks 1–3. ✅
   - File-level implementation notes match the file lists above. ✅
   - Testing & verification → Task 12. ✅

2. **Placeholder scan**: no TBDs, no "implement later", every code step has explicit code or a precise command. Some Task 9 / 10 / 11 steps reference grep results because the exact line targets are mechanical follow-throughs — these are concrete enough to execute.

3. **Type / name consistency**:
   - `wasFinalized` (React state, camelCase) ↔ `was_finalized` (cache JSON key, snake_case, matches Python field name). Consistent within each layer.
   - `handleMakeChanges` referenced in Task 6 (definition) and Task 8 (onClick). ✅
   - `isAmending` derived as `!approved && wasFinalized`. Used in Task 11. ✅
