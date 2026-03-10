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

export function MedicationRow({ command, commandIndex, onEdit, onDelete }) {
  const [editing, setEditing] = useState(!command.display);
  const [query, setQuery] = useState(command.data.medication_text || '');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selectedFdb, setSelectedFdb] = useState(
    typeof command.data.fdb_code === 'string' ? command.data.fdb_code : null
  );
  const [selectedDisplay, setSelectedDisplay] = useState(command.data.medication_text || '');
  const [sig, setSig] = useState(command.data.sig || '');
  const inputRef = useRef(null);
  const containerRef = useRef(null);

  const isStructured = typeof command.data.fdb_code === 'string';

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
      return;
    }
    setSearching(true);
    try {
      const res = await fetch(
        `${API_BASE}/search-medications?query=${encodeURIComponent(q)}`
      );
      const data = await res.json();
      setResults(data.results || []);
    } catch (err) {
      console.error('Medication search failed:', err);
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  const debouncedSearch = useDebounce(doSearch, DEBOUNCE_MS);

  const handleInput = (e) => {
    const val = e.target.value;
    setQuery(val);
    setSelectedFdb(null);
    setSelectedDisplay(val);
    debouncedSearch(val);
  };

  const handleSelect = (result) => {
    setSelectedFdb(result.fdb_code);
    setSelectedDisplay(result.description);
    setQuery(result.description);
    setResults([]);
  };

  const handleSave = () => {
    const newData = { ...command.data, medication_text: selectedDisplay, sig };
    if (selectedFdb) {
      newData.fdb_code = selectedFdb;
    } else {
      newData.fdb_code = { system: 'UNSTRUCTURED', code: selectedDisplay, display: selectedDisplay };
    }
    onEdit(commandIndex, newData);
    setEditing(false);
  };

  const handleCancel = () => {
    if (!command.display) {
      onDelete(commandIndex);
      return;
    }
    setQuery(command.data.medication_text || '');
    setSelectedFdb(typeof command.data.fdb_code === 'string' ? command.data.fdb_code : null);
    setSelectedDisplay(command.data.medication_text || '');
    setSig(command.data.sig || '');
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
      <div class="medication-row documented">
        <span class="command-type-badge badge-medication">Med</span>
        <span class="medication-row-text">${command.display}</span>
        <span class="medication-documented-badge">Already in chart</span>
      </div>
    `;
  }

  // Edit mode with search.
  if (editing) {
    return html`
      <div class="medication-row editing" ref=${containerRef}>
        <span class="command-type-badge badge-medication">Med</span>
        <div class="medication-search-wrapper">
          <input
            ref=${inputRef}
            type="text"
            class="medication-row-input"
            value=${query}
            onInput=${handleInput}
            onKeyDown=${handleKeyDown}
            placeholder="Search medications..."
          />
          ${searching && html`<span class="medication-search-spinner">Searching...</span>`}
          ${results.length > 0 && html`
            <div class="medication-search-dropdown">
              ${results.map(r => html`
                <div
                  key=${r.fdb_code}
                  class="medication-search-result"
                  onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
                >
                  ${r.description}
                </div>
              `)}
            </div>
          `}
        </div>
        ${selectedFdb && html`
          <span class="medication-structured-badge">FDB: ${selectedFdb}</span>
        `}
        <input
          type="text"
          class="medication-row-input"
          value=${sig}
          onInput=${(e) => setSig(e.target.value)}
          onKeyDown=${handleKeyDown}
          placeholder="Sig (e.g. Take 1 tablet daily)"
        />
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
    <div class="medication-row"
         onClick=${() => setEditing(true)}>
      <span class="command-type-badge badge-medication">Med</span>
      <span class="medication-row-text">${command.display}</span>
      ${command.data.sig && html`<span class="medication-sig-text">${command.data.sig}</span>`}
      ${isStructured
        ? html`<span class="medication-structured-badge">FDB: ${command.data.fdb_code}</span>`
        : html`<span class="medication-unstructured-badge">Unstructured</span>`
      }
    </div>
  `;
}
