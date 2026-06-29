import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const ICON_PENCIL = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>`;
const ICON_SEARCH = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="20" y1="20" x2="16.65" y2="16.65"/></svg>`;

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const DEBOUNCE_MS = 300;

function useDebounce(fn, delay) {
  const timer = useRef(null);
  return useCallback((...args) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => fn(...args), delay);
  }, [fn, delay]);
}

function formatIcdCode(raw) {
  if (!raw) return '';
  const code = raw.replace(/\./g, '').trim().toUpperCase();
  return code.length > 3 ? code.slice(0, 3) + '.' + code.slice(3) : code;
}

export function DiagnoseRow({ command, commandIndex, onEdit, onDelete, readOnly, suggestions, onAccept, onEditingChange }) {
  const data = command.data || {};
  const hasCode = !!data.icd10_code;
  // KOALA_5635_BACKGROUND_ALWAYS_RENDER — Background is available on EVERY
  // diagnose-row card, regardless of whether the proposal matched an active
  // patient condition. Round-2 gated this on ``data.condition_id``; Kevin's
  // UAT explicitly rejected that gate: the field must be available for ALL
  // condition cards in ALL situations — new diagnosis, matched assess, AI
  // rec, user-initiated, prior-background-empty-or-not, and after an ICD
  // change.
  //
  // The UI polish layered on top (Kevin, condition-card-UI work): the
  // Background SECTION is only shown when there's something to show —
  //   * collapsed/read view: render the Background block only when
  //     ``data.background`` is non-empty (no label/help/counter noise on an
  //     empty card);
  //   * edit view: when there's no preexisting background, show a "+ Add
  //     background" pill (the refer-card .refer-add-pill disclosure pattern)
  //     instead of an empty field; clicking it reveals the textarea.
  // The data path is unchanged: ``DiagnoseCommand`` carries ``background``,
  // so it round-trips through both the diagnose and assess persistence paths.
  //
  // The KOALA_5635_CLEAR_ON_ICD_CHANGE behavior (handleSelect /
  // handleClearCode) is STILL in force — the text content is explicitly
  // cleared on an ICD change. That's the Council-blessed clinical-data-
  // integrity safeguard against cross-attaching one condition's background
  // text onto a different condition's Assessment row in the chart.

  // editingCode drives the "change an already-assigned code" picker AND
  // (preserved from the original) flags a no-code row as actively editing its
  // code so summary.js's unsaved-edits footer treats a freshly-loaded
  // unmatched-diagnosis card as in-progress. It initializes to ``!hasCode``.
  // The Change picker render is gated on ``hasCode && editingCode``; the
  // no-code picker renders off ``!hasCode`` (always shown until a code is set).
  const [editingCode, setEditingCode] = useState(!hasCode);
  const [editingText, setEditingText] = useState(false);
  useEffect(() => {
    onEditingChange?.(`${commandIndex}:code`, editingCode);
    return () => onEditingChange?.(`${commandIndex}:code`, false);
  }, [editingCode, commandIndex]);
  useEffect(() => {
    onEditingChange?.(`${commandIndex}:text`, editingText);
    return () => onEditingChange?.(`${commandIndex}:text`, false);
  }, [editingText, commandIndex]);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [assessment, setAssessment] = useState(data.today_assessment || '');
  // KOALA_5635_BACKGROUND_TEXTAREA — local state mirrors AssessNarrative's
  // pattern (soap-group.js): seed from ``data.background``, sync on
  // external prop change ONLY when not editing so a late carry-forward
  // fetch can't clobber in-progress typing.
  const [background, setBackground] = useState(data.background || '');
  // Whether the Background field is shown in edit mode. True when there's
  // preexisting background; the "+ Add background" pill flips it on otherwise.
  const [showBackground, setShowBackground] = useState((data.background || '').length > 0);
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const textareaRef = useRef(null);
  const backgroundRef = useRef(null);
  // Only auto-focus the background textarea when the user explicitly clicks
  // "+ Add background" — not when it shows because background already exists
  // (the assessment textarea owns focus on entering edit mode).
  const addedBgRef = useRef(false);

  // KOALA_5635_BACKGROUND_TEXTAREA — sync local ``background`` from data
  // when the row isn't being edited. Mirrors AssessNarrative; needed
  // because useState initializes once and the carry-forward fetch may
  // resolve AFTER first render.
  useEffect(() => {
    if (!editingText) {
      setBackground(data.background || '');
      setShowBackground((data.background || '').length > 0);
    }
  }, [data.background, editingText]);

  // Focus the picker search input when it opens (no-code on mount, or "Change").
  useEffect(() => {
    if (editingCode && inputRef.current) {
      inputRef.current.focus({ preventScroll: true });
    }
  }, [editingCode]);

  useEffect(() => {
    if (editingText && textareaRef.current) {
      textareaRef.current.focus({ preventScroll: true });
    }
  }, [editingText]);

  useEffect(() => {
    if (showBackground && addedBgRef.current && backgroundRef.current) {
      backgroundRef.current.focus({ preventScroll: true });
      addedBgRef.current = false;
    }
  }, [showBackground]);

  // Outside click clears any stale search query/results so the picker reverts
  // to its recommendations. For an already-coded card the "Change" picker also
  // closes; the no-code picker stays open (it's the persistent UI for an
  // incomplete row and must not be dismissed).
  useEffect(() => {
    if (!editingCode) return;
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setResults([]);
        setSearched(false);
        setSearching(false);
        setQuery('');
        if (hasCode) setEditingCode(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [editingCode, hasCode]);

  const doSearch = useCallback(async (q) => {
    if (!q || q.length < 2) {
      setResults([]);
      setSearched(false);
      return;
    }
    setSearching(true);
    try {
      const res = await fetch(
        `${API_BASE}/search-diagnoses?query=${encodeURIComponent(q)}`
      );
      const json = await res.json();
      setResults(json.results || []);
    } catch (err) {
      console.error('Diagnosis search failed:', err);
      setResults([]);
    } finally {
      setSearching(false);
      setSearched(true);
    }
  }, []);

  const debouncedSearch = useDebounce(doSearch, DEBOUNCE_MS);

  const handleInput = (e) => {
    const val = e.target.value;
    setQuery(val);
    debouncedSearch(val);
  };

  const handleSelect = (result) => {
    const display = result.display || result.description || '';
    // KOALA_5635_CLEAR_ON_ICD_CHANGE — when the ICD changes, the stamped
    // condition_id is for the OLD code's matched patient condition.
    // Carrying it forward would cause handleInsert's diagnose→assess flip
    // (summary.js) to write background text scoped to the OLD condition
    // against the NEW condition's Assessment row — a clinical-data-integrity
    // cross-attachment. The spread still runs first (so unrelated proposal
    // fields like _original_header / accepted survive) but condition_id and
    // background are EXPLICITLY cleared AFTER it. The user can re-derive
    // background via the next /generate-summary if they want it back; the
    // alternative (silent cross-attachment) is worse than this small UX cost.
    const newData = {
      ...data,
      icd10_code: result.code,
      icd10_display: display,
      condition_header: display,
      _original_header: data._original_header || data.condition_header || '',
      accepted: true,
      rejected: false,
      condition_id: '',  // explicit clear; never preserve across ICD change
      background: '',    // explicit clear; never preserve across ICD change
    };
    onEdit(commandIndex, newData, 'diagnose');
    // KOALA_5635_CLEAR_ON_ICD_CHANGE — also mirror the clear into local
    // ``background`` state so the textarea / read-only block reflects the
    // cleared value without waiting for the prop-sync useEffect to run
    // (avoids a render flash where stale background flickers visible).
    setBackground('');
    setShowBackground(false);
    setResults([]);
    setSearched(false);
    setSearching(false);
    setQuery('');
    setEditingCode(false);
  };

  const handleClearCode = () => {
    if (readOnly) return;
    // "Change" enters code-edit mode WITHOUT clearing icd10_code / accepted.
    // Clearing them here would drop this diagnosis out of
    // chargeMatrixDiagnoses mid-edit, and the pointer-prune effect in summary.js
    // would then permanently strip this diagnosis's _localId from every charge's
    // _pointers — silently wiping charge links before the replacement is picked.
    // handleSelect overwrites the code atomically and STILL clears condition_id /
    // background (the KOALA_5635 cross-attachment guard), so the diagnosis never
    // leaves the matrix and charge links survive an in-place ICD change. If the
    // user abandons the edit (Escape), the original code is intact.
    setEditingCode(true);
    setQuery('');
    setResults([]);
    setSearched(false);
    setSearching(false);
  };

  const handleAddBackground = () => {
    addedBgRef.current = true;
    setShowBackground(true);
  };

  const handleSaveAssessment = () => {
    // KOALA_5635_BACKGROUND_ALWAYS_RENDER — persist ``background`` on EVERY
    // save, not only when ``condition_id`` is stamped. DiagnoseCommand
    // accepts background, so unmatched-ICD rows persist it cleanly through
    // the diagnose path. A round-tripped save that silently drops what the
    // user typed would be exactly the UX trap the UAT was pushing back on.
    const newData = {
      ...data,
      today_assessment: assessment,
      background: background,
      accepted: true,
      rejected: false,
    };
    onEdit(commandIndex, newData, 'diagnose');
    setEditingText(false);
  };

  const handleCancelAssessment = () => {
    setAssessment(data.today_assessment || '');
    setBackground(data.background || '');
    setShowBackground((data.background || '').length > 0);
    setEditingText(false);
  };

  const handleKeyDown = (e) => {
    // Escape closes the "Change" picker on an already-coded card (restoring the
    // original code). On a no-code row the picker is the persistent UI, so
    // Escape is a no-op there.
    if (e.key === 'Escape' && editingCode && hasCode) {
      setEditingCode(false);
      setResults([]);
      setQuery('');
    }
  };

  const handleTextKeyDown = (e) => {
    if (e.key === 'Escape') {
      handleCancelAssessment();
    }
  };

  const conditionHeader = data.condition_header || command.display;
  const formattedCode = hasCode ? formatIcdCode(data.icd10_code) : null;
  // Name leads, the ICD code trails it as a quiet gray identifier (matches the
  // name's size/weight, color-differentiated only). Changing the code is done
  // via the header "Change" affordance, not by clicking the code.
  const title = hasCode
    ? html`${data.icd10_display || conditionHeader}<span class="diagnose-icd-code">${formattedCode}</span>`
    : conditionHeader;

  const recCodes = suggestions || [];

  // Integrated picker — search input on top, then live results (while typing)
  // or the recommended codes (when the query is empty). Shared by the no-code
  // state and the "Change diagnosis" flow.
  const pickerPanel = (placeholder) => html`
    <div class="diagnose-picker">
      <div class="diagnose-picker-search">
        ${ICON_SEARCH}
        <input
          ref=${inputRef}
          type="text"
          value=${query}
          onInput=${handleInput}
          onKeyDown=${handleKeyDown}
          placeholder=${placeholder}
        />
      </div>
      ${results.length > 0
        ? html`
          <div class="diagnose-picker-list">
            ${results.map((r, i) => html`
              <div
                key=${r.code || ('r' + i)}
                class="diagnose-picker-row"
                onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
              >
                <span class="diagnose-picker-code">${formatIcdCode(r.code)}</span>
                <span class="diagnose-picker-name">${r.display || r.description}</span>
              </div>
            `)}
          </div>
        `
        : (query.length < 2 && recCodes.length > 0)
        ? html`
          <div class="diagnose-picker-label">Recommended</div>
          <div class="diagnose-picker-list">
            ${recCodes.map(s => html`
              <div
                key=${s.code}
                class="diagnose-picker-row"
                onMouseDown=${(e) => { e.preventDefault(); handleSelect({ code: s.code, display: s.display, formatted_code: s.formatted_code }); }}
              >
                <span class="diagnose-picker-code">${s.formatted_code}</span>
                <span class="diagnose-picker-name">${s.display}</span>
              </div>
            `)}
          </div>
        `
        : searching
        ? html`<div class="diagnose-picker-empty">Searching…</div>`
        : (searched && query.length >= 2)
        ? html`<div class="diagnose-picker-empty">No diagnoses found</div>`
        : null}
    </div>
  `;

  return html`
    <div class="diagnose-row" ref=${containerRef}>
      <div class="diagnose-row-header">
        <span class="diagnose-row-title">${title}</span>
        ${hasCode && !readOnly && html`
          <button type="button" class="diagnose-change-btn" onClick=${handleClearCode} title="Change diagnosis">${ICON_PENCIL} Change</button>
        `}
      </div>

      ${/* "Change diagnosis" picker (already-coded card). */ ''}
      ${hasCode && editingCode && !readOnly && pickerPanel('Search for a different code…')}

      ${/* No-diagnosis-code state: the integrated picker is the persistent UI. */ ''}
      ${!hasCode && !readOnly && pickerPanel('Search a diagnosis code, or pick a recommendation below…')}

      ${!editingText && html`
        <div
          class="diagnose-row-body${readOnly ? '' : ' editable'}"
          onClick=${() => !readOnly && setEditingText(true)}
        >
          ${/* Collapsed view: Background block only when there's text to show.
              No help line, no char counter — over-limit is surfaced as a
              warning pill in the actions column (soap-group.js). */ ''}
          ${(data.background || '').length > 0 && html`
            <div class="diagnose-body-label">Background</div>
            ${(data.background || '').split('\n').map((line, i) => html`
              <div key=${'b' + i} class="diagnose-body-line">${line}</div>
            `)}
          `}
          <div class="diagnose-body-label">Today's assessment</div>
          ${(data.today_assessment || '').length > 0
            ? (data.today_assessment || '').split('\n').map((line, i) => html`
                <div key=${i} class="diagnose-body-line">${line}</div>
              `)
            : html`<div class="diagnose-body-empty">No assessment text</div>`}
        </div>
      `}

      ${editingText && !readOnly && html`
        <div class="diagnose-edit-area editing">
          ${showBackground
            ? html`
              <div class="diagnose-field">
                <div class="diagnose-body-label">Background</div>
                <textarea
                  ref=${backgroundRef}
                  class="command-row-textarea"
                  rows=${2}
                  maxLength=${2048}
                  value=${background}
                  onInput=${(e) => setBackground(e.target.value)}
                  onKeyDown=${handleTextKeyDown}
                />
                <div class="diagnose-bg-footer">
                  <span class="diagnose-bg-help">Carries forward to future notes</span>
                  <span class="char-counter${background.length > 1900 ? background.length > 2048 ? ' over-limit' : ' near-limit' : ''}"><span class="cc-num">${background.length}</span> / 2048</span>
                </div>
              </div>
            `
            : html`
              <div class="refer-disclosures">
                <button type="button" class="refer-add-pill" onClick=${handleAddBackground}>+ Add background</button>
              </div>
            `}
          <div class="diagnose-field">
            <div class="diagnose-body-label">Today's assessment</div>
            <textarea
              ref=${textareaRef}
              class="command-row-textarea"
              rows=${5}
              maxLength=${2048}
              value=${assessment}
              onInput=${(e) => setAssessment(e.target.value)}
              onKeyDown=${handleTextKeyDown}
            />
            <div class="char-counter${assessment.length > 1900 ? assessment.length > 2048 ? ' over-limit' : ' near-limit' : ''}"><span class="cc-num">${assessment.length}</span> / 2048</div>
          </div>
          <div class="command-row-actions">
            <button type="button" class="form-btn form-btn-cancel" onClick=${handleCancelAssessment}>Cancel</button>
            <button type="button" class="form-btn form-btn-save" disabled=${assessment.length > 2048 || background.length > 2048} onClick=${handleSaveAssessment}>Save</button>
          </div>
        </div>
      `}
    </div>
  `;
}
