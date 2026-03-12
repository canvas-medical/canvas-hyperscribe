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
    return html`
      <div class="allergy-row documented">
        <span class="command-type-badge badge-allergy">Allergy</span>
        <span class="allergy-row-text">${command.display}</span>
        <span class="allergy-documented-badge">Already in chart</span>
      </div>
    `;
  }

  // Edit mode with search.
  if (editing) {
    return html`
      <div class="allergy-row editing" ref=${containerRef}>
        <span class="command-type-badge badge-allergy">Allergy</span>
        <div class="allergy-search-wrapper">
          <input
            ref=${inputRef}
            type="text"
            class="allergy-row-input"
            value=${query}
            onInput=${handleInput}
            onKeyDown=${handleKeyDown}
            placeholder="Search allergies..."
          />
          ${searching && html`<span class="allergy-search-spinner">Searching...</span>`}
          ${results.length > 0 && html`
            <div class="allergy-search-dropdown">
              ${results.map(r => html`
                <div
                  key=${r.concept_id}
                  class="allergy-search-result"
                  onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
                >
                  ${r.description}
                </div>
              `)}
            </div>
          `}
          ${!searching && searched && results.length === 0 && query.length >= 2 && html`
            <div class="allergy-search-dropdown">
              <div class="allergy-search-result search-no-results">No allergies found</div>
            </div>
          `}
        </div>
        ${selectedConceptId && html`
          <span class="allergy-structured-badge">Coded</span>
        `}
        <input
          type="text"
          class="allergy-row-input"
          value=${reaction}
          onInput=${(e) => setReaction(e.target.value)}
          onKeyDown=${handleKeyDown}
          placeholder="Reaction (e.g. rash, hives)"
        />
        <div class="allergy-severity">
          ${['mild', 'moderate', 'severe'].map(s => html`
            <button
              key=${s}
              type="button"
              class="task-quick-btn${severity === s ? ' active' : ''}"
              onClick=${() => setSeverity(severity === s ? '' : s)}
            >${s[0].toUpperCase() + s.slice(1)}</button>
          `)}
        </div>
        <div class="command-row-actions">
          <button class="edit-btn" onClick=${handleSave}>Save</button>
          <button class="edit-btn" onClick=${handleCancel}>Cancel</button>
          <button class="delete-btn" onClick=${() => onDelete(commandIndex)}>Delete</button>
        </div>
      </div>
    `;
  }

  // View mode.
  return html`
    <div class="allergy-row"
         onClick=${() => !readOnly && setEditing(true)}>
      <span class="command-type-badge badge-allergy">Allergy</span>
      <span class="allergy-row-text">${command.display}</span>
      ${command.data.reaction && html`<span class="allergy-reaction-text">${command.data.reaction}</span>`}
      ${command.data.severity && html`<span class="allergy-severity-badge severity-${command.data.severity}">${command.data.severity}</span>`}
      ${isStructured
        ? html`<span class="allergy-structured-badge">Coded</span>`
        : html`<span class="allergy-unstructured-badge">Unstructured</span>`
      }
    </div>
  `;
}
