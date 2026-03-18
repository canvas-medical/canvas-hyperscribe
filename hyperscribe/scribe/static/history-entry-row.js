import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const DEBOUNCE_MS = 300;

function SearchField({ label, placeholder, endpoint, onSelect, initialDisplay }) {
  const [query, setQuery] = useState(initialDisplay || '');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const timer = useRef(null);

  const doSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setResults([]); setSearched(false); return; }
    setSearching(true);
    try {
      const res = await fetch(`${API_BASE}/${endpoint}?query=${encodeURIComponent(q)}`);
      const json = await res.json();
      setResults(json.results || []);
    } catch (err) {
      console.error(`Search failed (${endpoint}):`, err);
      setResults([]);
    } finally {
      setSearching(false);
      setSearched(true);
    }
  }, [endpoint]);

  const handleInput = (e) => {
    const val = e.target.value;
    setQuery(val);
    onSelect(null, val);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => doSearch(val), DEBOUNCE_MS);
  };

  const handleSelect = (r) => {
    setQuery(r.display);
    setResults([]);
    setSearched(false);
    onSelect(r, r.display);
  };

  return html`
    <div style="position: relative;">
      <div class="labeled-field">
        <span class="labeled-field-label">${label}</span>
        <input
          type="text"
          class="labeled-field-input"
          value=${query}
          onInput=${handleInput}
          placeholder=${placeholder}
        />
      </div>
      ${searching && html`<span class="diag-search-spinner">Searching...</span>`}
      ${results.length > 0 && html`
        <div class="diag-search-dropdown">
          ${results.map(r => html`
            <div
              key=${r.code}
              class="diag-search-result"
              onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
            >${r.display}${r.code ? html` <span style="opacity:0.5">(${r.code})</span>` : ''}</div>
          `)}
        </div>
      `}
      ${!searching && searched && results.length === 0 && query.length >= 2 && html`
        <div class="diag-search-dropdown">
          <div class="diag-search-result search-no-results">No results found</div>
        </div>
      `}
    </div>
  `;
}

function FamilyHistoryForm({ command, commandIndex, onEdit, onDelete, onCancel, isNew }) {
  const [condition, setCondition] = useState(command.data.condition_display || '');
  const [conditionCode, setConditionCode] = useState(command.data.condition_code || null);
  const [relative, setRelative] = useState(command.data.relative || '');
  const [relativeCode, setRelativeCode] = useState(command.data.relative_code || null);
  const [comment, setComment] = useState(command.data.note || '');

  const handleSave = () => {
    if (!condition.trim()) return;
    onEdit(commandIndex, {
      condition_code: conditionCode,
      condition_display: condition,
      relative: relative || null,
      relative_code: relativeCode,
      note: comment || null,
    }, 'familyHistory');
  };

  return html`
    <div class="order-rx-form">
      <div class="subsection-title">Family Hx</div>
      <${SearchField}
        key="fh-condition"
        label="Condition"
        placeholder="Search family history conditions..."
        endpoint="search-family-history"
        initialDisplay=${condition}
        onSelect=${(r, display) => { setCondition(display); setConditionCode(r ? r.code : null); }}
      />
      <${SearchField}
        key="fh-relative"
        label="Relative"
        placeholder="Search family relation..."
        endpoint="search-family-relation"
        initialDisplay=${relative}
        onSelect=${(r, display) => { setRelative(display); setRelativeCode(r ? r.code : null); }}
      />
      <div class="labeled-field">
        <span class="labeled-field-label">Comment</span>
        <textarea
          class="labeled-field-input"
          rows="4"
          value=${comment}
          onInput=${(e) => setComment(e.target.value)}
        />
      </div>
      <div class="command-row-actions">
        <button class="edit-btn" onClick=${handleSave}>Save</button>
        <button class="edit-btn" onClick=${onCancel}>Cancel</button>
        <button class="delete-btn" onClick=${() => onDelete(commandIndex)}>Delete</button>
      </div>
    </div>
  `;
}

function MedicalHistoryForm({ command, commandIndex, onEdit, onDelete, onCancel, isNew }) {
  const [condition, setCondition] = useState(command.data.past_medical_history || '');
  const [conditionCode, setConditionCode] = useState(command.data.condition_code || null);
  const [startDate, setStartDate] = useState(command.data.approximate_start_date || '');
  const [endDate, setEndDate] = useState(command.data.approximate_end_date || '');
  const [comment, setComment] = useState(command.data.comments || '');

  const handleSave = () => {
    if (!condition.trim()) return;
    onEdit(commandIndex, {
      past_medical_history: condition,
      condition_code: conditionCode,
      approximate_start_date: startDate || null,
      approximate_end_date: endDate || null,
      comments: comment || null,
    }, 'medicalHistory');
  };

  return html`
    <div class="order-rx-form">
      <div class="subsection-title">Medical Hx</div>
      <${SearchField}
        key="mh-condition"
        label="Condition"
        placeholder="Search medical history conditions..."
        endpoint="search-medical-history"
        initialDisplay=${condition}
        onSelect=${(r, display) => { setCondition(display); setConditionCode(r ? r.code : null); }}
      />
      <div class="order-rx-row">
        <div class="labeled-field" style="flex:1">
          <span class="labeled-field-label">Start Date</span>
          <input class="labeled-field-input" type="date" value=${startDate} onInput=${(e) => setStartDate(e.target.value)} />
        </div>
        <div class="labeled-field" style="flex:1">
          <span class="labeled-field-label">End Date</span>
          <input class="labeled-field-input" type="date" value=${endDate} onInput=${(e) => setEndDate(e.target.value)} />
        </div>
      </div>
      <div class="labeled-field">
        <span class="labeled-field-label">Comment</span>
        <textarea
          class="labeled-field-input"
          rows="4"
          value=${comment}
          onInput=${(e) => setComment(e.target.value)}
        />
      </div>
      <div class="command-row-actions">
        <button class="edit-btn" onClick=${handleSave}>Save</button>
        <button class="edit-btn" onClick=${onCancel}>Cancel</button>
        <button class="delete-btn" onClick=${() => onDelete(commandIndex)}>Delete</button>
      </div>
    </div>
  `;
}

function SurgicalHistoryForm({ command, commandIndex, onEdit, onDelete, onCancel, isNew }) {
  const [procedure, setProcedure] = useState(command.data.procedure_display || '');
  const [procedureCode, setProcedureCode] = useState(command.data.procedure_code || null);
  const [date, setDate] = useState(command.data.approximate_date || '');
  const [comment, setComment] = useState(command.data.comment || '');

  const handleSave = () => {
    if (!procedure.trim()) return;
    onEdit(commandIndex, {
      procedure_code: procedureCode,
      procedure_display: procedure,
      approximate_date: date || null,
      comment: comment || null,
    }, 'surgicalHistory');
  };

  return html`
    <div class="order-rx-form">
      <div class="subsection-title">Surgical Hx</div>
      <${SearchField}
        key="sh-procedure"
        label="Procedure"
        placeholder="Search surgical procedures..."
        endpoint="search-surgical-history"
        initialDisplay=${procedure}
        onSelect=${(r, display) => { setProcedure(display); setProcedureCode(r ? r.code : null); }}
      />
      <div class="labeled-field">
        <span class="labeled-field-label">Date</span>
        <input class="labeled-field-input" type="date" value=${date} onInput=${(e) => setDate(e.target.value)} />
      </div>
      <div class="labeled-field">
        <span class="labeled-field-label">Comment</span>
        <textarea
          class="labeled-field-input"
          rows="4"
          value=${comment}
          onInput=${(e) => setComment(e.target.value)}
        />
      </div>
      <div class="command-row-actions">
        <button class="edit-btn" onClick=${handleSave}>Save</button>
        <button class="edit-btn" onClick=${onCancel}>Cancel</button>
        <button class="delete-btn" onClick=${() => onDelete(commandIndex)}>Delete</button>
      </div>
    </div>
  `;
}

const FORM_COMPONENTS = {
  familyHistory: FamilyHistoryForm,
  medicalHistory: MedicalHistoryForm,
  surgicalHistory: SurgicalHistoryForm,
};

const BADGE_LABELS = {
  familyHistory: 'Family Hx',
  medicalHistory: 'Medical Hx',
  surgicalHistory: 'Surgical Hx',
};

export function HistoryEntryRow({ command, commandIndex, onEdit, onDelete, readOnly }) {
  const isNew = !command.display;
  const [editing, setEditing] = useState(isNew);

  const handleCancel = () => {
    if (isNew) {
      onDelete(commandIndex);
      return;
    }
    setEditing(false);
  };

  const handleEdit = (index, data, type) => {
    onEdit(index, data, type);
    setEditing(false);
  };

  if (editing) {
    const FormComponent = FORM_COMPONENTS[command.command_type];
    if (!FormComponent) return null;
    return html`
      <div class="order-row editing" onKeyDown=${(e) => e.key === 'Escape' && handleCancel()}>
        <${FormComponent}
          command=${command}
          commandIndex=${commandIndex}
          onEdit=${handleEdit}
          onDelete=${onDelete}
          onCancel=${handleCancel}
          isNew=${isNew}
        />
      </div>
    `;
  }

  const badge = BADGE_LABELS[command.command_type] || 'History';

  return html`
    <div>
      <div class="order-row" onClick=${() => !readOnly && setEditing(true)}>
        <div class="subsection-title">${badge}</div>
        <span class="command-row-text">${command.display || '(empty)'}</span>
      </div>
    </div>
  `;
}
