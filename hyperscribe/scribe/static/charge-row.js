import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const DEBOUNCE_MS = 300;

export function ChargeRow({ command, commandIndex, onEdit, onDelete, readOnly }) {
  const data = command.data || {};
  const hasCpt = !!data.cpt_code;
  const [editing, setEditing] = useState(!hasCpt);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const timer = useRef(null);

  const doSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setResults([]); setSearched(false); return; }
    setSearching(true);
    try {
      const res = await fetch(`${API_BASE}/search-charges?query=${encodeURIComponent(q)}`);
      const json = await res.json();
      setResults(json.results || []);
    } catch (err) {
      console.error('Charge search failed:', err);
      setResults([]);
    } finally {
      setSearching(false);
      setSearched(true);
    }
  }, []);

  const handleInput = (e) => {
    const val = e.target.value;
    setQuery(val);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => doSearch(val), DEBOUNCE_MS);
  };

  const handleSelect = (r) => {
    onEdit(commandIndex, {
      ...data,
      cpt_code: r.cpt_code,
      description: r.short_name || r.full_name || '',
      notes: data.notes || '',
    });
    setQuery('');
    setResults([]);
    setSearched(false);
    setEditing(false);
  };

  const handleRemove = (e) => {
    e.stopPropagation();
    onDelete(commandIndex);
  };

  // Search mode: new charge with no CPT code yet.
  if (!hasCpt || editing) {
    return html`
      <div class="charge-row editing">
        <div class="charge-search-area">
          <input
            type="text"
            class="charge-search-input"
            value=${query}
            onInput=${handleInput}
            placeholder="Search CPT code or description..."
            autoFocus
          />
          ${searching && html`<span class="charge-search-spinner">Searching...</span>`}
          ${results.length > 0 && html`
            <div class="charge-search-dropdown">
              ${results.map(r => html`
                <div
                  key=${r.cpt_code}
                  class="charge-search-result"
                  onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
                >
                  <span class="charge-result-code">${r.cpt_code}</span>
                  <span class="charge-result-name">${r.short_name || r.full_name}</span>
                </div>
              `)}
            </div>
          `}
          ${!searching && searched && results.length === 0 && query.length >= 2 && html`
            <div class="charge-search-dropdown">
              <div class="charge-search-result search-no-results">No charges found</div>
            </div>
          `}
        </div>
        <div class="charge-row-actions">
          ${hasCpt && html`<button type="button" class="edit-btn" onClick=${() => setEditing(false)}>Cancel</button>`}
          <button type="button" class="delete-btn" onClick=${handleRemove} title="Remove charge">x</button>
        </div>
      </div>
    `;
  }

  // View mode: shows CPT code + description.
  return html`
    <div class="charge-row${readOnly ? ' read-only' : ''}" onClick=${() => !readOnly && setEditing(true)}>
      <div class="charge-row-display">
        <span class="charge-cpt-code">${data.cpt_code}</span>
        <span class="charge-description">${data.description || ''}</span>
      </div>
      ${!readOnly && html`
        <div class="charge-row-actions">
          <button type="button" class="delete-btn" onClick=${handleRemove} title="Remove charge">x</button>
        </div>
      `}
    </div>
  `;
}
