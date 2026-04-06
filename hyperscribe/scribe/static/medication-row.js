import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const ICON_X = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></svg>`;
const ICON_CHECK = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 10 18 20 6"/></svg>`;

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const DEBOUNCE_MS = 300;
const FDB_SYSTEM = 'http://www.fdbhealth.com/';

/** True when fdb_code is a resolved Coding dict (not UNSTRUCTURED, not null). */
function isFdbStructured(fdb) {
  return fdb != null && typeof fdb === 'object' && fdb.system !== 'UNSTRUCTURED';
}

function useDebounce(fn, delay) {
  const timer = useRef(null);
  return useCallback((...args) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => fn(...args), delay);
  }, [fn, delay]);
}

export function MedicationRow({ command, commandIndex, onEdit, onDelete, readOnly, alertFacilityEnabled }) {
  const [editing, setEditing] = useState(!command.display);
  const [query, setQuery] = useState(command.data.medication_text || '');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [selectedFdb, setSelectedFdb] = useState(
    isFdbStructured(command.data.fdb_code) ? command.data.fdb_code : null
  );
  const [selectedDisplay, setSelectedDisplay] = useState(command.data.medication_text || '');
  const [sig, setSig] = useState(command.data.sig || '');
  const [alertFacility, setAlertFacility] = useState(!!command.data.alert_facility);
  const inputRef = useRef(null);
  const containerRef = useRef(null);

  const isStructured = isFdbStructured(command.data.fdb_code);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus({ preventScroll: true });
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
        `${API_BASE}/search-medications?query=${encodeURIComponent(q)}`
      );
      const data = await res.json();
      setResults(data.results || []);
    } catch (err) {
      console.error('Medication search failed:', err);
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
    setSelectedFdb(null);
    setSelectedDisplay(val);
    debouncedSearch(val);
  };

  const handleSelect = (result) => {
    setSelectedFdb({ system: FDB_SYSTEM, code: result.fdb_code, display: result.description });
    setSelectedDisplay(result.description);
    setQuery(result.description);
    setResults([]);
    setSearched(false);
  };

  const handleSave = () => {
    const newData = { ...command.data, medication_text: selectedDisplay, sig, alert_facility: alertFacility };
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
    setSelectedFdb(isFdbStructured(command.data.fdb_code) ? command.data.fdb_code : null);
    setSelectedDisplay(command.data.medication_text || '');
    setSig(command.data.sig || '');
    setAlertFacility(!!command.data.alert_facility);
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
        <div class="order-view">
          <div class="order-view-name">${command.display}</div>
          ${command.data.sig && html`<div class="order-view-sig">${command.data.sig}</div>`}
        </div>
      </div>
    `;
  }

  // Edit mode with search.
  if (editing && !readOnly) {
    return html`
      <div class="medication-row editing" ref=${containerRef}>
        <div class="history-form">
          <div class="history-form-field" style="position: relative;">
            <label class="history-form-label">Medication</label>
            <input
              ref=${inputRef}
              type="text"
              class="history-form-input"
              value=${query}
              onInput=${handleInput}
              onKeyDown=${handleKeyDown}
              placeholder="Search medications..."
            />
            ${searching && html`<span class="diag-search-spinner">Searching...</span>`}
            ${results.length > 0 && html`
              <div class="history-search-dropdown">
                ${results.map(r => html`
                  <div
                    key=${r.fdb_code}
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
                <div class="history-search-result search-no-results">No medications found</div>
              </div>
            `}
          </div>
          <div class="history-form-field">
            <label class="history-form-label">Sig</label>
            <input
              type="text"
              class="history-form-input"
              value=${sig}
              onInput=${(e) => setSig(e.target.value)}
              onKeyDown=${handleKeyDown}
              placeholder="e.g. Take 1 tablet daily"
            />
          </div>
          ${alertFacilityEnabled && html`
          <div class="history-form-field">
            <label class="alert-facility-toggle" onClick=${() => setAlertFacility(prev => !prev)}>
              <div class="toggle-switch${alertFacility ? ' on' : ''}">
                <div class="toggle-knob" />
              </div>
              Alert Facility
            </label>
          </div>
          `}
          <div class="questionnaire-form-actions">
            <button type="button" class="form-btn form-btn-cancel" onClick=${handleCancel}>Cancel</button>
            <button type="button" class="form-btn form-btn-save" onClick=${handleSave}>Save</button>
          </div>
        </div>
      </div>
    `;
  }

  // View mode.
  return html`
    <div class="medication-row"
         onClick=${() => !readOnly && setEditing(true)}>
      <div class="order-view">
        <div class="order-view-name">${command.display}</div>
        ${command.data.sig && html`<div class="order-view-sig">${command.data.sig}</div>`}
        ${alertFacilityEnabled && command.data.alert_facility && html`<span class="badge badge-alert">Alert Facility</span>`}
      </div>
    </div>
  `;
}
