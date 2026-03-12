import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

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
  const code = raw.trim().toUpperCase();
  return code.length > 3 ? code.slice(0, 3) + '.' + code.slice(3) : code;
}

export function DiagnoseRow({ command, commandIndex, onEdit, onDelete, readOnly, suggestions }) {
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
    const newData = {
      ...data,
      icd10_code: result.code,
      icd10_display: result.display || result.description || '',
    };
    const display = result.display || result.description || command.display;
    onEdit(commandIndex, newData, 'diagnose');
    setResults([]);
    setSearched(false);
    setQuery('');
    setEditingCode(false);
  };

  const handleClearCode = () => {
    if (readOnly) return;
    const newData = { ...data, icd10_code: null, icd10_display: '' };
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
        ${!hasCode && !editingCode && !readOnly && html`
          <button
            type="button"
            class="diagnose-search-btn"
            onClick=${() => setEditingCode(true)}
          >Add ICD-10</button>
        `}
        ${!readOnly && html`
          <button
            type="button"
            class="diagnose-delete-btn"
            onClick=${() => onDelete(commandIndex)}
            title="Remove condition"
          >\u00d7</button>
        `}
      </div>

      ${editingCode && !readOnly && html`
        <div class="diagnose-search-area">
          <input
            ref=${inputRef}
            type="text"
            class="diagnose-search-input"
            value=${query}
            onInput=${handleInput}
            onKeyDown=${handleKeyDown}
            placeholder="Search diagnosis..."
          />
          ${searching && html`<span class="diagnose-search-spinner">Searching...</span>`}
          ${results.length > 0 && html`
            <div class="diagnose-search-dropdown">
              ${results.map(r => html`
                <div
                  key=${r.code}
                  class="diagnose-search-result"
                  onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
                >
                  <span class="diagnose-result-display">${r.display || r.description}</span>
                  ${r.code && html`<span class="diagnose-result-code">${formatIcdCode(r.code)}</span>`}
                </div>
              `)}
            </div>
          `}
          ${!searching && searched && results.length === 0 && query.length >= 2 && html`
            <div class="diagnose-search-dropdown">
              <div class="diagnose-search-result search-no-results">No diagnoses found</div>
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
            class="diagnose-textarea"
            value=${assessment}
            onInput=${(e) => setAssessment(e.target.value)}
            onKeyDown=${handleTextKeyDown}
          />
          <div class="command-row-actions">
            <button class="edit-btn" onClick=${handleSaveAssessment}>Save</button>
            <button class="edit-btn" onClick=${handleCancelAssessment}>Cancel</button>
          </div>
        </div>
      `}

      ${!hasCode && !readOnly && suggestions && suggestions.length > 0 && html`
        <div class="diagnose-suggestions">
          <div class="diagnose-suggestions-label">Suggested codes</div>
          <div class="diagnose-suggestions-chips">
            ${suggestions.map(s => html`
              <button
                key=${s.code}
                type="button"
                class="ap-suggested-chip"
                onClick=${() => handleSelect({ code: s.code, display: s.display, formatted_code: s.formatted_code })}
                title=${s.display}
              >${s.formatted_code} ${s.display}</button>
            `)}
          </div>
        </div>
      `}
    </div>
  `;
}
