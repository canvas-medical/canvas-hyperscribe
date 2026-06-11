# Scribe UI harness

A high-fidelity design harness for the Canvas Scribe (hyperscribe) UI. It boots
the **real** Preact components from `hyperscribe/scribe/static/` in a plain
browser — no Canvas, no backend, no LLM, no microphone — by stubbing the three
IO seams that tie the UI to the live plugin.

Because it renders the shipping `styles.css` and the shipping `*.js`, what you
see is pixel-identical to production, and **editing the CSS or a component here
edits the real plugin file**. The harness adds nothing to `hyperscribe/`; all
mock/fixture code lives under `mockups/`.

## Status

- **Phase 1 (spike): complete.** Real `<Scribe>` boots and renders with zero
  page errors. Validated headless via Playwright.
- **Phase 2 (fixture library): complete.** `fixtures/commands.js` has a factory
  for every command type; `fixtures/scenarios.js` composes them into named
  states — recording phase (nothing-selected start, AI recording, AI paused,
  generate) and review phase (every-command kitchen sink, manual mode,
  recommendations, amending, read-only). The kitchen sink renders all ~25 command types — narratives,
  ROS/PE review sections, history entries, vitals, meds/allergies, removals,
  diagnose/assess, task, all six order types, questionnaire, and the charge
  matrix — with zero page errors.
- **Phase 3 (component gallery): complete.** The **Component gallery** view
  (`fixtures/gallery.js` + `gallery.css`) mounts every real row component in
  isolation, showing its states side by side (view / editing / deselected /
  read-only / locked / missing-field). All 11 components × their states render
  with zero page errors. Cards are live — click one to enter its real edit mode.
- **Phase 4 (guided flow): complete.** The **Guided flow** view (`fixtures/flow.js`)
  walks the end-to-end journey as a stepper above the live surface. Two flows:
  **AI Scribe** (start → recording → paused → generate → review → amend) and
  **Manual** (start → manual charting). Each step mounts a real scenario; the
  surface stays live (e.g. Generate Summary works on the generate step). Verified
  headlessly across all steps with zero page errors.
- **Phase 5 (polish): complete.** Search/list endpoint response shapes corrected
  so every dropdown populates (they read `data.results` / `data.conditions` /
  `data.tests` etc.); 9 missing search endpoints added. Gallery cards fixed at the
  standard 720px Scribe viewport width so components render at true size and don't
  resize. A committed headless fidelity gate (`verify/`) asserts all of the above.

The build is complete. Run `verify/` (below) any time to confirm the harness
still renders the real components faithfully.

### Fixture authoring notes

- **section_key drives placement.** "Card" command types (task, orders,
  questionnaire, history entries, stop/remove/resolve removals) render only from
  a group's *ad-hoc bucket* — `_ad_hoc` (A&P), `_objective_ad_hoc`,
  `_history_ad_hoc`, `_subjective_ad_hoc`, `_charges_ad_hoc` — not their narrative
  section_key. ROS uses `_ros`. AI-generated narratives/structured commands
  (rfv, hpi, vitals, medication_statement, allergy, diagnose/assess) use their
  real section_key.
- **Amending** pre-loads already-documented commands (with `command_uuid`). Since
  `syncNoteCommands` drops local UUIDs absent from `/note-commands`, those
  scenarios also expose a `noteCommands` array that the harness feeds to the mock.

## Run it

From the **repo root** (the import map and stylesheet links resolve relative to
the repo layout):

```sh
python3 -m http.server 8000
```

Then open <http://localhost:8000/mockups/scribe-harness/>.

> Must be served over HTTP, not opened as a `file://` URL — ES module import maps
> and relative module resolution require an HTTP origin. Requires network access
> to `esm.sh` (Preact + htm load from there, same as production).

## How it works

| File | Role |
| --- | --- |
| `index.html` | Harness shell + nav rail. The **import map** remaps `/plugin-io/api/hyperscribe/scribe/static/` → the real files on disk, so the components' absolute cross-imports load unmodified. Mounts `<Scribe>` with a fixture config. |
| `mock-io.js` | Stubs the Canvas↔iframe seams: a fake `MessagePort` (`window.__canvasPort`) and an inert `WebSocket` for the note-state socket. Classic script → runs before any module. |
| `mock-fetch.js` | Intercepts `window.fetch` for the single data base `/plugin-io/api/hyperscribe/scribe-session/*` and returns fixtures for every endpoint. Tunables on `window.__MOCK` (`latencyMs`, `failNext`, `log`). |
| `mock-recording-hook.js` | Stubs `recording-hook.js` (the mic + transcription-WebSocket seam) via an import-map override, so the **real** recording UI renders without a microphone. Drives `status` from `window.__MOCK.recording`; control callbacks (Start/Pause/Resume/Finish) transition state live. |
| `fixtures/` | `commands.js` (per-type factories), `scenarios.js` (named states), `gallery.js` (component gallery), `flow.js` (guided walkthroughs). `initialData` short-circuits the initial `/summary` fetch, so a fixture renders directly. |
| `gallery.css` | Chrome for the gallery only (namespaced `gallery-*`; never touches the product styles). |
| `verify/` | Headless fidelity gate (Playwright + installed Chrome). |

## Views (rail)

- **Guided flow** — clickable end-to-end walkthrough (AI Scribe / Manual).
- **Component gallery** — every row component in isolation, one card per state, each at the 720px Scribe viewport width. Cards are live.
- **Header states** — the summary header (status pill · top bar · banners) tracked through all 10 workflow states. Each card is a live `<Scribe>` with the body hidden (`fixtures/header.js`). Recording vs paused is driven per-instance via `transcript.__recordingStatus`.
- **Scenarios** — 9 named states grouped Recording / States.

## Verify (repeatable fidelity check)

With the harness server running, from `mockups/scribe-harness/verify/`:

```sh
npm install   # first time — pulls playwright-core
npm run verify
```

It boots the harness in your installed Chrome and asserts: every scenario mounts
with zero page errors, every gallery card is 720px wide, the search dropdowns
populate, and no endpoint goes unrouted. Override target/browser with
`BASE_URL=… CHANNEL=…`.

## Mapping a change back to the plugin

- **Visual / CSS tweak** → edit `hyperscribe/scribe/static/styles.css` directly; refresh.
- **Component markup / behavior** → edit the relevant `hyperscribe/scribe/static/*.js`; refresh.
- **New mock data or state** → edit `mockups/scribe-harness/` only.

## Fidelity notes

- **Width.** The surface (and every gallery card) renders at 720px, the standard
  Scribe viewport. In Canvas the modal autosizes via `RESIZE` postMessage; 720px
  matches the typical width.
- **Search shapes.** `mock-fetch.js` mirrors the exact response wrapper each
  component reads (`{ results }`, `{ tests }`, `{ conditions }`, `{ medications }`,
  `{ allergies }`, `{ assignees }`, `{ lab_partners }`, `{ providers }`,
  `{ labels }`). A wrong wrapper makes a dropdown silently empty — `verify/` guards this.
- **esm.sh.** Preact + htm load from `esm.sh`, same as production; the harness
  needs network access to it.
