import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const DEBOUNCE_MS = 300;

const ORDER_TABS = [
  { key: 'prescribe', label: 'Rx' },
  { key: 'lab_order', label: 'Lab' },
  { key: 'imaging_order', label: 'Imaging' },
];

const BADGE_LABELS = {
  prescribe: 'Rx',
  lab_order: 'Lab',
  imaging_order: 'Imaging',
};

function useDebounce(fn, delay) {
  const timer = useRef(null);
  return useCallback((...args) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => fn(...args), delay);
  }, [fn, delay]);
}

function buildDisplay(type, data) {
  if (type === 'prescribe') {
    const parts = [];
    if (data.medication_text) parts.push(data.medication_text);
    if (data.sig) parts.push(`Sig: ${data.sig}`);
    if (data.quantity_to_dispense) parts.push(`Qty: ${data.quantity_to_dispense}`);
    if (data.days_supply) parts.push(`${data.days_supply}d supply`);
    if (data.refills) parts.push(`${data.refills} refill${data.refills > 1 ? 's' : ''}`);
    return parts.join(' | ') || '';
  }
  if (type === 'lab_order') return data.comment || '';
  if (type === 'imaging_order') {
    const parts = [];
    if (data.comment) parts.push(data.comment);
    if (data.priority) parts.push(data.priority);
    return parts.join(' | ') || '';
  }
  return '';
}

export function OrderRow({ command, commandIndex, onEdit, onDelete }) {
  const isNew = !command.display;
  const [editing, setEditing] = useState(isNew);
  const [activeTab, setActiveTab] = useState(command.command_type || 'prescribe');

  // Rx state
  const [medQuery, setMedQuery] = useState(command.data.medication_text || '');
  const [medResults, setMedResults] = useState([]);
  const [medSearching, setMedSearching] = useState(false);
  const [selectedFdb, setSelectedFdb] = useState(command.data.fdb_code || null);
  const [selectedMedDisplay, setSelectedMedDisplay] = useState(command.data.medication_text || '');
  const [sig, setSig] = useState(command.data.sig || '');
  const [daysSupply, setDaysSupply] = useState(command.data.days_supply || '');
  const [quantity, setQuantity] = useState(command.data.quantity_to_dispense || '');
  const [refills, setRefills] = useState(command.data.refills || '');
  const [substitutions, setSubstitutions] = useState(command.data.substitutions !== 'not_allowed');
  const [noteToPharmacist, setNoteToPharmacist] = useState(command.data.note_to_pharmacist || '');

  // Lab state
  const [labComment, setLabComment] = useState(command.data.comment || '');

  // Imaging state
  const [imagingComment, setImagingComment] = useState(command.data.comment || '');
  const [imagingPriority, setImagingPriority] = useState(command.data.priority || 'Routine');

  const medInputRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (editing && activeTab === 'prescribe' && medInputRef.current) {
      medInputRef.current.focus();
    }
  }, [editing, activeTab]);

  // Close dropdown on outside click.
  useEffect(() => {
    if (!editing) return;
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setMedResults([]);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [editing]);

  const doMedSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setMedResults([]); return; }
    setMedSearching(true);
    try {
      const res = await fetch(`${API_BASE}/search-medications?query=${encodeURIComponent(q)}`);
      const data = await res.json();
      setMedResults(data.results || []);
    } catch (err) {
      setMedResults([]);
    } finally {
      setMedSearching(false);
    }
  }, []);

  const debouncedMedSearch = useDebounce(doMedSearch, DEBOUNCE_MS);

  const handleMedInput = (e) => {
    const val = e.target.value;
    setMedQuery(val);
    setSelectedFdb(null);
    setSelectedMedDisplay(val);
    debouncedMedSearch(val);
  };

  const handleMedSelect = (result) => {
    setSelectedFdb(result.fdb_code);
    setSelectedMedDisplay(result.description);
    setMedQuery(result.description);
    setMedResults([]);
  };

  const handleSave = () => {
    let data = {};
    if (activeTab === 'prescribe') {
      if (!selectedMedDisplay.trim()) return;
      data = {
        fdb_code: selectedFdb || null,
        medication_text: selectedMedDisplay,
        sig,
        days_supply: daysSupply ? Number(daysSupply) : null,
        quantity_to_dispense: quantity ? Number(quantity) : null,
        refills: refills ? Number(refills) : null,
        substitutions: substitutions ? 'allowed' : 'not_allowed',
        note_to_pharmacist: noteToPharmacist || null,
      };
    } else if (activeTab === 'lab_order') {
      data = { comment: labComment };
    } else if (activeTab === 'imaging_order') {
      data = { comment: imagingComment, priority: imagingPriority };
    }
    onEdit(commandIndex, data, activeTab);
    setEditing(false);
  };

  const handleCancel = () => {
    if (isNew) {
      onDelete(commandIndex);
      return;
    }
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') handleCancel();
  };

  if (editing) {
    return html`
      <div class="order-row editing" ref=${containerRef} onKeyDown=${handleKeyDown}>
        <div class="order-layout">
          <div class="order-tabs">
            ${ORDER_TABS.map(tab => html`
              <button
                key=${tab.key}
                type="button"
                class="order-tab${activeTab === tab.key ? ' active' : ''}"
                onClick=${() => setActiveTab(tab.key)}
              >${tab.label}</button>
            `)}
          </div>
          <div class="order-form">
            ${activeTab === 'prescribe' && html`
              <div class="order-rx-form">
                <div class="medication-search-wrapper">
                  <input
                    ref=${medInputRef}
                    type="text"
                    class="order-input"
                    value=${medQuery}
                    onInput=${handleMedInput}
                    placeholder="Search medications..."
                  />
                  ${medSearching && html`<span class="medication-search-spinner">Searching...</span>`}
                  ${medResults.length > 0 && html`
                    <div class="medication-search-dropdown">
                      ${medResults.map(r => html`
                        <div
                          key=${r.fdb_code}
                          class="medication-search-result"
                          onMouseDown=${(e) => { e.preventDefault(); handleMedSelect(r); }}
                        >${r.description}</div>
                      `)}
                    </div>
                  `}
                </div>
                ${selectedFdb && html`<span class="medication-structured-badge">FDB: ${selectedFdb}</span>`}
                <div class="order-rx-row">
                  <div class="labeled-field">
                    <span class="labeled-field-label">Qty</span>
                    <input class="labeled-field-input labeled-field-narrow" type="number" value=${quantity} onInput=${(e) => setQuantity(e.target.value)} min="0" />
                  </div>
                  <div class="labeled-field">
                    <span class="labeled-field-label">Days</span>
                    <input class="labeled-field-input labeled-field-narrow" type="number" value=${daysSupply} onInput=${(e) => setDaysSupply(e.target.value)} min="0" />
                  </div>
                  <div class="labeled-field">
                    <span class="labeled-field-label">Refills</span>
                    <input class="labeled-field-input labeled-field-narrow" type="number" value=${refills} onInput=${(e) => setRefills(e.target.value)} min="0" />
                  </div>
                  <label class="order-checkbox-label">
                    <input type="checkbox" checked=${substitutions} onChange=${(e) => setSubstitutions(e.target.checked)} />
                    Sub
                  </label>
                </div>
                <div class="order-rx-row">
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Sig</span>
                    <input class="labeled-field-input" type="text" value=${sig} onInput=${(e) => setSig(e.target.value)} />
                  </div>
                  <div class="labeled-field" style="flex:1">
                    <span class="labeled-field-label">Note to Pharmacist</span>
                    <input class="labeled-field-input" type="text" value=${noteToPharmacist} onInput=${(e) => setNoteToPharmacist(e.target.value)} />
                  </div>
                </div>
              </div>
            `}
            ${activeTab === 'lab_order' && html`
              <textarea
                class="order-textarea"
                value=${labComment}
                onInput=${(e) => setLabComment(e.target.value)}
                placeholder="Lab order details..."
              />
            `}
            ${activeTab === 'imaging_order' && html`
              <div class="order-imaging-form">
                <textarea
                  class="order-textarea"
                  value=${imagingComment}
                  onInput=${(e) => setImagingComment(e.target.value)}
                  placeholder="Imaging order details..."
                />
                <div class="order-priority">
                  <button type="button" class="task-quick-btn${imagingPriority === 'Routine' ? ' active' : ''}" onClick=${() => setImagingPriority('Routine')}>Routine</button>
                  <button type="button" class="task-quick-btn${imagingPriority === 'Urgent' ? ' active' : ''}" onClick=${() => setImagingPriority('Urgent')}>Urgent</button>
                </div>
              </div>
            `}
            <div class="command-row-actions">
              <button class="edit-btn" onClick=${handleSave}>Save</button>
              <button class="edit-btn" onClick=${handleCancel}>Cancel</button>
              <button class="delete-btn" onClick=${() => onDelete(commandIndex)}>Delete</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // View mode.
  const badgeLabel = BADGE_LABELS[command.command_type] || 'Order';
  return html`
    <div class="order-row" onClick=${() => setEditing(true)}>
      <span class="command-type-badge badge-${command.command_type}">${badgeLabel}</span>
      <span class="command-row-text">${command.display}</span>
    </div>
  `;
}
