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

export function DiagnoseRow({ command, commandIndex, onEdit, onDelete, readOnly, suggestions, onAccept }) {
  const data = command.data || {};
  const hasCode = !!data.icd10_code;

  const [editingCode, setEditingCode] = useState(!hasCode);
  const [editingText, setEditingText] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [assessment, setAssessment] = useState(data.today_assessment || '');
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    if (editingCode && inputRef.current) {
      inputRef.current.focus();
    }
  }, [editingCode]);

  useEffect(() => {
    if (editingText && textareaRef.current) {
      textareaRef.current.focus();
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
    const newData = {
      ...data,
      icd10_code: result.code,
      icd10_display: display,
      condition_header: display,
      _original_header: data._original_header || data.condition_header || '',
      accepted: true,
      rejected: false,
    };
    onEdit(commandIndex, newData, 'diagnose');
    setResults([]);
    setSearched(false);
    setQuery('');
    setEditingCode(false);
  };

  const handleClearCode = () => {
    if (readOnly) return;
    const originalHeader = command.data._original_header || data.condition_header || '';
    const newData = { ...data, icd10_code: null, icd10_display: '', condition_header: originalHeader, accepted: false, rejected: false };
    onEdit(commandIndex, newData, 'diagnose');
    setEditingCode(true);
    setQuery('');
  };

  const handleSaveAssessment = () => {
    const newData = { ...data, today_assessment: assessment };
    onEdit(commandIndex, newData, 'diagnose');
    setEditingText(false);
  };

  const handleCancelAssessment = () => {
    setAssessment(data.today_assessment || '');
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
          ${(data.today_assessment || '').split('\n').map((line, i) => html`
            <div key=${i} class="diagnose-body-line">${line}</div>
          `)}
          ${!data.today_assessment && html`
            <div class="diagnose-body-empty">No assessment text</div>
          `}
        </div>
      `}

      ${editingText && !readOnly && html`
        <div class="diagnose-edit-area">
          <textarea
            ref=${textareaRef}
            class="command-row-textarea"
            value=${assessment}
            onInput=${(e) => setAssessment(e.target.value)}
            onKeyDown=${handleTextKeyDown}
          />
          <div class="command-row-actions">
            <button type="button" class="rec-btn rec-btn-reject" onClick=${handleCancelAssessment} title="Cancel">${ICON_X}</button>
            <button type="button" class="rec-btn rec-btn-accept" onClick=${handleSaveAssessment} title="Save">${ICON_CHECK}</button>
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
