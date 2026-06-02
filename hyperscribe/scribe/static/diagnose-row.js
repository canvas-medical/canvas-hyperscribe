import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const ICON_X = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></svg>`;
const ICON_CHECK = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 10 18 20 6"/></svg>`;

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
  // KOALA_5635_BACKGROUND_GATE — gate the editable Background section on
  // ``data.condition_id``. The id is stamped server-side by
  // ``split_plan_into_diagnoses`` when this proposal's icd10_code matches an
  // an active condition on the patient. That's also the predicate
  // ``handleInsert`` uses to flip this row from diagnose → assess at insert
  // time; rendering Background only when the flip is on the table keeps the
  // UI honest about which proposals carry a per-(patient, condition)
  // background. Without a condition_id there is no scope for carry-forward
  // and the field would be free-text that the home-app assess command
  // wouldn't persist anyway.
  const hasConditionId = !!data.condition_id;

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
  // fetch can't clobber in-progress typing. The state is intentionally NOT
  // gated on ``hasConditionId`` so the hook order stays stable across
  // renders (React rule of hooks).
  const [background, setBackground] = useState(data.background || '');
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const textareaRef = useRef(null);
  const backgroundRef = useRef(null);

  // KOALA_5635_BACKGROUND_TEXTAREA — sync local ``background`` from data
  // when the row isn't being edited. Mirrors AssessNarrative; needed
  // because useState initializes once and the carry-forward fetch may
  // resolve AFTER first render.
  useEffect(() => {
    if (!editingText) {
      setBackground(data.background || '');
    }
  }, [data.background, editingText]);

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

  // Close dropdown on outside click.
  useEffect(() => {
    if (!editingCode) return;
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setResults([]);
        setSearched(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [editingCode]);

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
    setResults([]);
    setSearched(false);
    setQuery('');
    setEditingCode(false);
  };

  const handleClearCode = () => {
    if (readOnly) return;
    const originalHeader = command.data._original_header || data.condition_header || '';
    // KOALA_5635_CLEAR_ON_ICD_CHANGE — same reasoning as handleSelect:
    // clearing the ICD also clears the (now-orphaned) condition_id and
    // background. If the user picks a new code, the carry-forward will
    // re-resolve from /generate-summary; if they pick the same code, the
    // re-pick path also re-resolves. Preserving here would let the old
    // condition_id leak into the next handleSelect spread.
    const newData = {
      ...data,
      icd10_code: null,
      icd10_display: '',
      condition_header: originalHeader,
      accepted: false,
      rejected: false,
      condition_id: '',  // explicit clear; never preserve across ICD clear
      background: '',    // explicit clear; never preserve across ICD clear
    };
    onEdit(commandIndex, newData, 'diagnose');
    setBackground('');
    setEditingCode(true);
    setQuery('');
  };

  const handleSaveAssessment = () => {
    // KOALA_5635_BACKGROUND_TEXTAREA — when condition_id is present we also
    // persist ``background`` through the spread; for non-condition rows we
    // still spread ``data`` so any pre-existing ``background`` field on the
    // proposal (set by an upstream carry-forward) round-trips untouched.
    const newData = { ...data, today_assessment: assessment, accepted: true, rejected: false };
    if (hasConditionId) {
      newData.background = background;
    }
    onEdit(commandIndex, newData, 'diagnose');
    setEditingText(false);
  };

  const handleCancelAssessment = () => {
    setAssessment(data.today_assessment || '');
    setBackground(data.background || '');
    setEditingText(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      if (editingCode && hasCode) {
        setEditingCode(false);
        setResults([]);
        setQuery('');
      }
    }
  };

  const handleTextKeyDown = (e) => {
    if (e.key === 'Escape') {
      handleCancelAssessment();
    }
  };

  const conditionHeader = data.condition_header || command.display;
  const formattedCode = hasCode ? formatIcdCode(data.icd10_code) : null;
  const title = hasCode
    ? html`<span class="diagnose-icd-prefix${readOnly ? '' : ' clickable'}" onClick=${() => !readOnly && handleClearCode()} title=${readOnly ? formattedCode : 'Click to change diagnosis'}>${formattedCode}</span> ${data.icd10_display || conditionHeader}`
    : conditionHeader;

  return html`
    <div class="diagnose-row" ref=${containerRef}>
      <div class="diagnose-row-header">
        <span class="diagnose-row-title">${title}</span>
      </div>

      ${editingCode && !readOnly && html`
        <div class="history-form-field" style="position: relative;">
          <input
            ref=${inputRef}
            type="text"
            class="history-form-input"
            value=${query}
            onInput=${handleInput}
            onKeyDown=${handleKeyDown}
            placeholder="Search diagnosis..."
          />
          ${searching && html`<span class="diag-search-spinner">Searching...</span>`}
          ${results.length > 0 && html`
            <div class="history-search-dropdown">
              ${results.map(r => html`
                <div
                  key=${r.code}
                  class="history-search-result"
                  onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
                >
                  ${r.code && html`<strong>${formatIcdCode(r.code)}</strong>`}${' '}${r.display || r.description}
                </div>
              `)}
            </div>
          `}
          ${!searching && searched && results.length === 0 && query.length >= 2 && html`
            <div class="history-search-dropdown">
              <div class="history-search-result search-no-results">No diagnoses found</div>
            </div>
          `}
        </div>
      `}

      ${!editingText && html`
        <div
          class="diagnose-row-body${readOnly ? '' : ' editable'}"
          onClick=${() => !readOnly && setEditingText(true)}
        >
          ${/* KOALA_5635_BACKGROUND_TEXTAREA — read-only Background block,
              shown only when condition_id is stamped. Mirrors AssessNarrative
              (soap-group.js) so a future merge can reconcile shape if rec-
              diagnose is consolidated into the assess UI. */ ''}
          ${hasConditionId && (data.background || '').length > 0 && html`
            <div class="diagnose-body-label">Background</div>
            ${(data.background || '').split('\n').map((line, i) => html`
              <div key=${'b' + i} class="diagnose-body-line">${line}</div>
            `)}
            ${(data.background || '').length > 2048 && html`
              <div class="char-counter over-limit">${data.background.length} / 2048 — text must be shortened before approving</div>
            `}
          `}
          ${hasConditionId && (data.background || '').length > 0 && html`
            <div class="diagnose-body-label">Today's assessment</div>
          `}
          ${(data.today_assessment || '').split('\n').map((line, i) => html`
            <div key=${i} class="diagnose-body-line">${line}</div>
          `)}
          ${!data.today_assessment && !(hasConditionId && (data.background || '').length > 0) && html`
            <div class="diagnose-body-empty">No assessment text</div>
          `}
          ${(data.today_assessment || '').length > 2048 && html`
            <div class="char-counter over-limit">${data.today_assessment.length} / 2048 — text must be shortened before approving</div>
          `}
        </div>
      `}

      ${editingText && !readOnly && html`
        <div class="diagnose-edit-area">
          ${/* KOALA_5635_BACKGROUND_TEXTAREA — editable Background textarea,
              shown only when condition_id is stamped. Above the today's
              assessment textarea to match AssessNarrative ordering. */ ''}
          ${hasConditionId && html`
            <div class="diagnose-body-label">Background</div>
            <textarea
              ref=${backgroundRef}
              class="command-row-textarea"
              maxLength=${2048}
              value=${background}
              onInput=${(e) => setBackground(e.target.value)}
              onKeyDown=${handleTextKeyDown}
            />
            <div class="char-counter${background.length > 1900 ? background.length > 2048 ? ' over-limit' : ' near-limit' : ''}">${background.length} / 2048</div>
            <div class="diagnose-body-label">Today's assessment</div>
          `}
          <textarea
            ref=${textareaRef}
            class="command-row-textarea"
            maxLength=${2048}
            value=${assessment}
            onInput=${(e) => setAssessment(e.target.value)}
            onKeyDown=${handleTextKeyDown}
          />
          <div class="char-counter${assessment.length > 1900 ? assessment.length > 2048 ? ' over-limit' : ' near-limit' : ''}">${assessment.length} / 2048</div>
          <div class="command-row-actions">
            <button type="button" class="form-btn form-btn-cancel" onClick=${handleCancelAssessment}>Cancel</button>
            <button type="button" class="form-btn form-btn-save" disabled=${assessment.length > 2048 || (hasConditionId && background.length > 2048)} onClick=${handleSaveAssessment}>Save</button>
          </div>
        </div>
      `}

      ${!hasCode && !readOnly && suggestions && suggestions.length > 0 && html`
        <div class="diagnose-suggestions">
          <div class="history-form-label">Suggested codes</div>
          <div class="diagnose-suggestions-list">
            ${suggestions.map(s => html`
              <button
                key=${s.code}
                type="button"
                class="diagnose-suggestion-btn"
                onClick=${() => handleSelect({ code: s.code, display: s.display, formatted_code: s.formatted_code })}
              >
                <strong>${s.formatted_code}</strong>${' '}${s.display}
              </button>
            `)}
          </div>
        </div>
      `}
    </div>
  `;
}
