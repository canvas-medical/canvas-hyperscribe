import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const ICON_X = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></svg>`;
const ICON_CHECK = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 10 18 20 6"/></svg>`;

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
    <div class="history-form-field" style="position: relative;">
      <label class="history-form-label">${label}</label>
      <input
        type="text"
        class="history-form-input"
        value=${query}
        onInput=${handleInput}
        placeholder=${placeholder}
      />
      ${searching && html`<span class="diag-search-spinner">Searching...</span>`}
      ${results.length > 0 && html`
        <div class="history-search-dropdown">
          ${results.map(r => html`
            <div
              key=${r.code}
              class="history-search-result"
              onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
            >${r.display}${r.code ? html` <span style="opacity:0.5">(${r.code})</span>` : ''}</div>
          `)}
        </div>
      `}
      ${!searching && searched && results.length === 0 && query.length >= 2 && html`
        <div class="history-search-dropdown">
          <div class="history-search-result search-no-results">No results found</div>
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
    <div class="history-form">
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
      <div class="history-form-field">
        <label class="history-form-label">Comment</label>
        <textarea
          class="history-form-textarea"
          rows="3"
          value=${comment}
          onInput=${(e) => setComment(e.target.value)}
          placeholder="Optional notes..."
        />
      </div>
      <div class="questionnaire-form-actions">
        <button type="button" class="form-btn form-btn-cancel" onClick=${onCancel}>Cancel</button>
        <button type="button" class="form-btn form-btn-save" onClick=${handleSave}>Save</button>
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
    <div class="history-form">
      <${SearchField}
        key="mh-condition"
        label="Condition"
        placeholder="Search medical history conditions..."
        endpoint="search-medical-history"
        initialDisplay=${condition}
        onSelect=${(r, display) => { setCondition(display); setConditionCode(r ? r.code : null); }}
      />
      <div class="history-form-dates">
        <div class="history-form-field">
          <label class="history-form-label">Start Date</label>
          <input class="history-form-input" type="date" value=${startDate} onInput=${(e) => setStartDate(e.target.value)} />
        </div>
        <div class="history-form-field">
          <label class="history-form-label">End Date</label>
          <input class="history-form-input" type="date" value=${endDate} onInput=${(e) => setEndDate(e.target.value)} />
        </div>
      </div>
      <div class="history-form-field">
        <label class="history-form-label">Comment</label>
        <textarea
          class="history-form-textarea"
          rows="3"
          value=${comment}
          onInput=${(e) => setComment(e.target.value)}
          placeholder="Optional notes..."
        />
      </div>
      <div class="questionnaire-form-actions">
        <button type="button" class="form-btn form-btn-cancel" onClick=${onCancel}>Cancel</button>
        <button type="button" class="form-btn form-btn-save" onClick=${handleSave}>Save</button>
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
    <div class="history-form">
      <${SearchField}
        key="sh-procedure"
        label="Procedure"
        placeholder="Search surgical procedures..."
        endpoint="search-surgical-history"
        initialDisplay=${procedure}
        onSelect=${(r, display) => { setProcedure(display); setProcedureCode(r ? r.code : null); }}
      />
      <div class="history-form-field">
        <label class="history-form-label">Date</label>
        <input class="history-form-input" type="date" value=${date} onInput=${(e) => setDate(e.target.value)} />
      </div>
      <div class="history-form-field">
        <label class="history-form-label">Comment</label>
        <textarea
          class="history-form-textarea"
          rows="3"
          value=${comment}
          onInput=${(e) => setComment(e.target.value)}
          placeholder="Optional notes..."
        />
      </div>
      <div class="questionnaire-form-actions">
        <button type="button" class="form-btn form-btn-cancel" onClick=${onCancel}>Cancel</button>
        <button type="button" class="form-btn form-btn-save" onClick=${handleSave}>Save</button>
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

  if (editing && !readOnly) {
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

  const d = command.data || {};
  const type = command.command_type;
  const name = type === 'familyHistory' ? d.condition_display
    : type === 'medicalHistory' ? d.past_medical_history
    : d.procedure_display;
  const details = [];
  if (type === 'familyHistory' && d.relative) details.push(d.relative);
  if (type === 'medicalHistory') {
    const dates = [d.approximate_start_date, d.approximate_end_date].filter(Boolean);
    if (dates.length) details.push(dates.join(' – '));
  }
  if (type === 'surgicalHistory' && d.approximate_date) details.push(d.approximate_date);
  const comment = type === 'familyHistory' ? d.note
    : type === 'medicalHistory' ? d.comments
    : d.comment;
  if (comment) details.push(comment);

  return html`
    <div class="history-entry-view" onClick=${() => !readOnly && setEditing(true)}>
      <div class="history-entry-content">
        <div class="history-entry-name">${name || '(empty)'}</div>
        ${details.length > 0 && html`<div class="history-entry-details">${details.join(' · ')}</div>`}
      </div>
    </div>
  `;
}
