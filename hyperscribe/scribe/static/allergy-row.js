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

export function AllergyRow({ command, commandIndex, onEdit, onDelete, readOnly }) {
  const [editing, setEditing] = useState(!command.display);
  const [query, setQuery] = useState(command.data.allergy_text || '');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [selectedConceptId, setSelectedConceptId] = useState(command.data.concept_id || null);
  const [selectedConceptIdType, setSelectedConceptIdType] = useState(command.data.concept_id_type || null);
  const [selectedDisplay, setSelectedDisplay] = useState(command.data.allergy_text || '');
  const [reaction, setReaction] = useState(command.data.reaction || '');
  const [severity, setSeverity] = useState(command.data.severity || '');
  const inputRef = useRef(null);
  const containerRef = useRef(null);

  const isStructured = !!command.data.concept_id;

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [editing]);

  // Close dropdown on outside click.
  useEffect(() => {
    if (!editing) return;
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setResults([]);
        setSearched(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [editing]);

  const doSearch = useCallback(async (q) => {
    if (!q || q.length < 2) {
      setResults([]);
      setSearched(false);
      return;
    }
    setSearching(true);
    try {
      const res = await fetch(
        `${API_BASE}/search-allergies?query=${encodeURIComponent(q)}`
      );
      const data = await res.json();
      setResults(data.results || []);
    } catch (err) {
      console.error('Allergy search failed:', err);
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
    setSelectedConceptId(null);
    setSelectedConceptIdType(null);
    setSelectedDisplay(val);
    debouncedSearch(val);
  };

  const handleSelect = (result) => {
    setSelectedConceptId(result.concept_id);
    setSelectedConceptIdType(result.concept_id_type);
    setSelectedDisplay(result.description);
    setQuery(result.description);
    setResults([]);
    setSearched(false);
  };

  const handleSave = () => {
    const newData = {
      ...command.data,
      allergy_text: selectedDisplay,
      concept_id: selectedConceptId,
      concept_id_type: selectedConceptIdType,
      reaction,
      severity: severity || null,
    };
    onEdit(commandIndex, newData);
    setEditing(false);
  };

  const handleCancel = () => {
    if (!command.display) {
      onDelete(commandIndex);
      return;
    }
    setQuery(command.data.allergy_text || '');
    setSelectedConceptId(command.data.concept_id || null);
    setSelectedConceptIdType(command.data.concept_id_type || null);
    setSelectedDisplay(command.data.allergy_text || '');
    setReaction(command.data.reaction || '');
    setSeverity(command.data.severity || '');
    setResults([]);
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    }
    if (e.key === 'Escape') {
      handleCancel();
    }
  };

  // Already documented — non-clickable, dimmed.
  if (command.already_documented) {
    const docDetails = [];
    if (command.data.reaction) docDetails.push(command.data.reaction);
    if (command.data.severity) docDetails.push(command.data.severity);
    return html`
      <div class="allergy-row documented">
        <div class="order-view">
          <div class="order-view-name">${command.display}</div>
          ${docDetails.length > 0 && html`<div class="order-view-sig">${docDetails.join(' · ')}</div>`}
        </div>
      </div>
    `;
  }

  // Edit mode with search.
  if (editing && !readOnly) {
    return html`
      <div class="allergy-row editing" ref=${containerRef}>
        <div class="history-form">
          <div class="history-form-field" style="position: relative;">
            <label class="history-form-label">Allergy</label>
            <input
              ref=${inputRef}
              type="text"
              class="history-form-input"
              value=${query}
              onInput=${handleInput}
              onKeyDown=${handleKeyDown}
              placeholder="Search allergies..."
            />
            ${searching && html`<span class="diag-search-spinner">Searching...</span>`}
            ${results.length > 0 && html`
              <div class="history-search-dropdown">
                ${results.map(r => html`
                  <div
                    key=${r.concept_id}
                    class="history-search-result"
                    onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
                  >
                    ${r.description}
                  </div>
                `)}
              </div>
            `}
            ${!searching && searched && results.length === 0 && query.length >= 2 && html`
              <div class="history-search-dropdown">
                <div class="history-search-result search-no-results">No allergies found</div>
              </div>
            `}
          </div>
          <div class="history-form-field">
            <label class="history-form-label">Reaction</label>
            <input
              type="text"
              class="history-form-input"
              value=${reaction}
              onInput=${(e) => setReaction(e.target.value)}
              onKeyDown=${handleKeyDown}
              placeholder="e.g. rash, hives"
            />
          </div>
          <div class="history-form-field">
            <label class="history-form-label">Severity</label>
            <div class="allergy-severity">
              ${['mild', 'moderate', 'severe'].map(s => html`
                <button
                  key=${s}
                  type="button"
                  class="allergy-severity-btn${severity === s ? ' active-' + s : ''}"
                  onClick=${() => setSeverity(severity === s ? '' : s)}
                >${s[0].toUpperCase() + s.slice(1)}</button>
              `)}
            </div>
          </div>
          <div class="questionnaire-form-actions">
            <button type="button" class="form-btn form-btn-cancel" onClick=${handleCancel}>Cancel</button>
            <button type="button" class="form-btn form-btn-save" onClick=${handleSave}>Save</button>
          </div>
        </div>
      </div>
    `;
  }

  // View mode.
  const details = [];
  if (command.data.reaction) details.push(command.data.reaction);
  if (command.data.severity) details.push(command.data.severity);

  return html`
    <div class="allergy-row"
         onClick=${() => !readOnly && setEditing(true)}>
      <div class="order-view">
        <div class="order-view-name">${command.display}</div>
        ${details.length > 0 && html`<div class="order-view-sig">${details.join(' · ')}</div>`}
      </div>
    </div>
  `;
}
