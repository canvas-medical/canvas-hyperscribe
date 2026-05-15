# Scribe-tab amendment workflow

**Ticket:** [KOALA-5485](https://canvasmedical.atlassian.net/browse/KOALA-5485)
**Parent epic:** KOALA-4370 (Canvas Scribe for Brigade)
**Status:** Design approved · 2026-05-15

---

## Context

After a provider finalizes the Scribe tab (`approved = true`), the tab becomes read-only. Today, even when the underlying note is later re-opened via the home-app's "Amend" button (note enters the `UNLOCKED` state, `isNoteEditable=true`), the Scribe tab stays locked because `canEdit = isAuthor && isNoteEditable && !approved` — the `!approved` term wins. The provider can amend the rest of the note but cannot add new orders, vitals, conditions, or CPT codes via the Scribe tab.

Per the ticket, the note author should be able to amend the Scribe tab in that situation. The amendment workflow adds new commands only — existing committed commands stay locked because they are already part of the signed/committed note record.

## Goals

- Provider can return to the Scribe tab after finalizing it and add new commands (orders, additional HPI/Vitals/Conditions/CPT, etc.).
- Already-committed commands stay locked — they remain part of the note's prior signed record and cannot be edited in place.
- Workflow respects the existing note-level lock state: if the note itself is locked (`isNoteEditable=false`), the provider must amend the note via the home-app's existing Amend button first.

## Non-goals

- Editing pre-existing committed commands. New commands only.
- Removing or invalidating pre-existing commands.
- Re-running the AI generation pipeline against new audio during amendment.
- Server-side architectural changes to authentication (save-summary keeps using `StaffSessionAuthMixin`).

---

## Design

### State machine

Four user-facing states for the Scribe tab, driven by `isAuthor`, `isNoteEditable` (from the home-app via WebSocket `NOTE_STATE_CHANGED`), and `approved` (from the plugin's own React state and `ScribeSummary` cache).

| Note (`isNoteEditable`) | Scribe (`approved`) | UI state | Status pill (top of tab) | Bottom action area |
|---|---|---|---|---|
| Editable | False | **Drafting** (current pre-approve) | hidden | "Accept and sign" |
| Editable | True | **Finalized** | `✓ Charting finalized · [Make changes]` | hidden |
| Editable | True → False (via "Make changes") | **Amending** | `✏️ Editing charting · click Approve when ready` | "Accept and sign" reappears |
| Locked | True | **Finalized & note locked** | hidden | hidden; existing "Click Amend in the note footer" banner shows |
| Locked | False | (rare — note locked before scribe approval) | hidden | hidden; existing locked banner |

The status pill is gated on `isAuthor && isNoteEditable && (approved || amending)`. Non-author viewers and locked-note states never show the pill — they continue to surface the existing read-only banners they already do.

### Transitions

- **Drafting → Finalized**: existing Approve flow runs unchanged. Sets `approved=true`, stamps `command_uuid` and `already_documented=true` on each inserted command. Pill appears.
- **Finalized → Amending**: provider clicks "Make changes" on the pill. `setApproved(false)`. The existing debounced `saveSummaryToCache` fires with `approved=false`, persisting the state in `ScribeSummary`. `canEdit` becomes true (because `!approved`).
- **Amending → Finalized**: provider clicks Approve. The existing approve flow runs `commands.filter(c => !c.already_documented ...)` so only newly-added commands hit `/insert-commands`. New commands receive `command_uuid` and `already_documented=true`. `setApproved(true)`. Pill returns to `✓ Charting finalized`.

There is no explicit Cancel — empty re-approval (clicking Approve immediately after "Make changes" with no new commands added) is the de-facto back-out path. `/insert-commands` accepts an empty `commands` list and returns `inserted: 0`.

### UI treatment

**Status pill** (new component, top of `.summary-container`):

- New CSS classes: `.summary-status-pill`, `.summary-status-pill--finalized`, `.summary-status-pill--amending`.
- Layout: `[icon] [text on left] [spacer] [button on right]`.
- Finalized variant: green/neutral background, `✓ Charting finalized` text, "Make changes" chip button on the right.
- Amending variant: amber background, `✏️ Editing charting` text, no right-side button (user uses the bottom Approve to exit).
- Renders above the existing read-only banners. Only one of {status pill, read-only banner} can show at a time because they are gated on different conditions.

**Per-command locking in amending mode:**

- The discriminator is `c.already_documented === true` — same flag the approve flow already uses to filter the insertable set.
- Apply a `.command-locked` modifier on each card whose `already_documented` is true:
  - Muted treatment (`opacity: 0.6` or similar saturation reduction).
  - Lock icon in the card's top-right.
  - Inputs render as plain text; per-card action buttons (Delete / Edit individual fields) are hidden.
- New commands the user adds during amendment render fully editable.

**Section + buttons:**

- `+ Plan`, `+ Vitals`, `+ Order`, `+ Charge`, `+ HPI` (etc.) remain enabled in amending mode. They create new commands with `already_documented: false` — these get inserted on the next Approve.

**Recommendations panel:**

- Existing recommendations from the original generation remain visible in the panel.
- Their "Add Now" buttons are hidden during amendment — the recs were derived from the original transcript, are now stale, and we don't re-run AI during amendment.
- The provider can still add equivalent commands via the section `+` buttons if they want similar content.

**Bottom Approve area:**

- In drafting and amending, identical: the existing "Accept and sign" / confirm-state / verification-result UI.
- The verification banner from the original approval remains visible during amending, giving the provider context for what's already been documented.

### Data flow

```
[Finalized state]
  approved = true
  commands = [...all with already_documented=true]
  recommendations = [...accepted/rejected from original generation]

  User clicks "Make changes"
  ─────────────────────────────────
  setApproved(false)
  → triggers existing commandsSaveRef useEffect (debounced 500ms)
    → saveSummaryToCache(noteData, commands, false, ...)
      → POST /save-summary with approved: false
      → ScribeSummary.approved = false

[Amending state]
  approved = false
  isNoteEditable = true
  canEdit = true (because !approved)
  Per-command editability: c.already_documented ? read-only : editable

  User adds a new Plan ("Follow up in 2 weeks")
  ─────────────────────────────────
  commands = [...existing, {command_type: 'plan', already_documented: false, ...}]
  Debounced autosave: POST /save-summary { approved: false, commands: [...all] }

  User clicks Approve
  ─────────────────────────────────
  insertable = commands.filter(c => !c.already_documented ...)  // existing logic
  → only the new Plan is in the list
  POST /insert-commands with [{command_type: 'plan', ...}]
  → originate + commit effects fire on home-app side
  → new Plan gets command_uuid stamped onto local state
  saveSummaryToCache(noteData, updatedCommands, true, ...)
  → ScribeSummary.approved = true again, with updated commands array

[Finalized state]
  approved = true
  commands = [...original docs, new Plan with command_uuid]
```

### Server-side changes

**None.** This is a frontend-only change.

- `/save-summary` already accepts arbitrary `approved` values via `bool(data.get("approved", False))`.
- `/insert-commands` already only processes the commands sent in the request body; the frontend filters by `already_documented` before sending.
- `_authorize_edit` already enforces the right gates: note must exist, must be editable, user must be the provider.
- `ScribeSummary` model has no schema changes — `commands` is `JSONField`, `approved` is `BooleanField`.

### Audit logging

- Add new client-side audit event when "Make changes" is clicked:
  ```js
  logEvent('AMENDMENT_STARTED', { commands_at_start: <count of already_documented> });
  ```
- Existing `COMMANDS_SENDING` / `APPROVE_COMPLETE` events fire as today on the re-approve.
- The existing server-side `audit_event(note_uuid, "INSERT_COMMANDS", ...)` continues to fire.
- The audit log timeline reads cleanly: `INSERT_COMMANDS → AMENDMENT_STARTED → COMMANDS_SENDING → INSERT_COMMANDS`.

### Reload / re-mount

The cache (`ScribeSummary`) is the source of truth across reloads.

- Reload mid-amendment: cache returns `approved: false, commands: [...]`. Component restores into amending state. Pill renders as `✏️ Editing charting`. Already-documented commands lock, new commands stay editable.
- Reload mid-amendment with no new commands added: same behavior — user is still in amendment mode until they click Approve.

---

## File-level implementation notes

Frontend only. Expect changes in:

- `hyperscribe/scribe/static/summary.js`
  - Drop the `!approved` term from `canEdit` (or replace with a per-command guard tied to `already_documented`).
  - Add a "Make changes" handler that flips `setApproved(false)` and emits the new `AMENDMENT_STARTED` audit event.
  - Render the new status pill at the top of `.summary-container`, gated on the conditions above.
  - Pass an `isLocked` (or equivalent) prop into per-command row components based on `c.already_documented`.
- `hyperscribe/scribe/static/styles.css`
  - `.summary-status-pill`, `.summary-status-pill--finalized`, `.summary-status-pill--amending` rules.
  - `.command-locked` modifier (muted styling, lock icon positioning).
- Per-command row files (e.g. `hyperscribe/scribe/static/command-row.js`, `vitals-row.js`, `prescription-row.js`, `order-row.js`, `medication-row.js`, etc.)
  - Accept the `isLocked` (or equivalent) prop.
  - When locked, render as plain text and hide per-card edit/delete affordances.
- `hyperscribe/scribe/static/recommended-group.js`
  - Hide "Add Now" buttons when in amending mode.

No changes to:
- `hyperscribe/scribe/api/session_view.py`
- `hyperscribe/scribe/commands/*`
- `hyperscribe/models/scribe.py`
- Any tests.

---

## Testing & verification

Backend: zero code changes, zero new tests.

Frontend: no JS test framework available in `canvas-hyperscribe` — verification is manual UAT, drivable via Playwright + DevTools.

**Manual UAT plan:**

1. **State transitions**
   - Drafting → Finalized: standard approve flow. Pill appears with `✓ Charting finalized · [Make changes]`.
   - Finalized → Amending: click "Make changes". Pill flips to `✏️ Editing charting`; `approved=false` lands in the cache (verify via subsequent `/summary` GET); bottom Approve button reappears.
   - Amending → Finalized with new command: add a Plan with narrative, click Approve. `/insert-commands` request body contains only the new Plan. Pill returns to finalized.
   - Amending → Finalized with empty re-approval: click "Make changes", immediately click Approve. `/insert-commands` body is empty, response is `inserted: 0`, pill flips back.

2. **Per-command locking in amending mode**
   - Already-documented commands render with the `.command-locked` style and lock icon.
   - Their input fields render as plain text.
   - Per-card delete/edit affordances are hidden.
   - New commands added during amendment are fully editable.
   - `+ Plan`, `+ Vitals`, `+ Order`, `+ Charge` etc. all work.
   - Recommendations panel renders without "Add Now" buttons.

3. **Authorization**
   - Non-author viewer: pill never appears; existing read-only banner is the only treatment.
   - Note locked (signed): pill never appears; existing "Click Amend in the note footer" banner is the only treatment.
   - Author + note editable + finalized: pill appears with "Make changes".

4. **Reload / re-mount**
   - Reload mid-amendment: pill renders correctly, locked commands lock, new commands persist.
   - Reload mid-amendment with no new commands added: same — still in amending state.

5. **Regression**
   - Initial scribe approve flow still works end-to-end.
   - Non-amendment editing flows (drafting state) unchanged.
   - Note-state transitions (sign → lock) still cleanly stop autosaves (KOALA-5475).

**End-to-end smoke before merge:**

- Create a Larry-authored Office visit on the existing test patient.
- Run a scribe (Manual mode), add a Plan, Approve. Pill appears.
- Click "Make changes". Add a second Plan. Approve. Verify both Plans are on the note via the home-app note view.
- Sign the note. Verify pill disappears; existing "Click Amend in the note footer" banner is what shows.
- Click home-app Amend. Verify note becomes editable again, pill reappears with "Make changes".

---

## Out of scope (worth filing as follow-ups)

- Editing previously-committed commands in place. Per the ticket, out of scope.
- Removing previously-committed commands during amendment. Out of scope.
- Distinguishing "amendment-added" commands from "original-approve-added" commands in the post-finalized view (e.g. a different visual indicator). Out of scope; the underlying note's audit log already records the timestamps.
- Re-running the AI pipeline against new audio during amendment. Out of scope.
- Architectural change to drop `StaffSessionAuthMixin` from save-summary (see KOALA-5475 design notes). Independent change.
