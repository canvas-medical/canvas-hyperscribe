import { h } from 'https://esm.sh/preact@10.25.4';
import { useState } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const ICON_X = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></svg>`;
const ICON_CHECK = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 10 18 20 6"/></svg>`;

const VITALS_FIELDS = [
  { key: 'blood_pressure_systole', pair: 'blood_pressure_diastole', pairMin: 20, pairMax: 180, label: 'BP', unit: 'mmHg', min: 30, max: 305 },
  { key: 'pulse', label: 'HR', unit: 'bpm', min: 30, max: 250 },
  { key: 'respiration_rate', label: 'RR', unit: '/min', min: 6, max: 60 },
  { key: 'oxygen_saturation', label: 'SpO2', unit: '%', min: 60, max: 100 },
  { key: 'body_temperature', label: 'Temp', unit: '°F', step: '0.1', min: 85, max: 107 },
  { key: 'height', label: 'Height', unit: 'in', min: 10, max: 108 },
  { key: 'weight_lbs', label: 'Weight', unit: 'lbs', min: 1, max: 1500 },
];

function formatVitalsDisplay(data) {
  const parts = [];
  VITALS_FIELDS.forEach(f => {
    if (f.pair) {
      const sys = data[f.key];
      const dia = data[f.pair];
      if (sys != null && dia != null) parts.push(`${f.label} ${sys}/${dia} ${f.unit}`);
    } else {
      const val = data[f.key];
      if (val != null) parts.push(`${f.label} ${val} ${f.unit}`);
    }
  });
  return parts.join(', ');
}

export { formatVitalsDisplay };

function validateField(key, value) {
  if (value == null || value === '') return null;
  const field = VITALS_FIELDS.find(f => f.key === key || f.pair === key);
  if (!field) return null;
  const isPair = field.pair === key;
  const min = isPair ? field.pairMin : field.min;
  const max = isPair ? field.pairMax : field.max;
  const num = typeof value === 'string' ? parseFloat(value.replace(',', '.')) : value;
  if (isNaN(num)) return 'Invalid number';
  if (min != null && num < min) return `Min ${min}`;
  if (max != null && num > max) return `Max ${max}`;
  return null;
}

export function VitalsRow({ command, commandIndex, onEdit, readOnly }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ ...command.data });
  const [tempRaw, setTempRaw] = useState(command.data.body_temperature != null ? String(command.data.body_temperature) : '');
  const [errors, setErrors] = useState({});

  const updateField = (key, raw) => {
    if (key === 'body_temperature') {
      setTempRaw(raw.replace(',', '.'));
      setErrors(prev => { const n = { ...prev }; delete n[key]; return n; });
      return;
    }
    setDraft(prev => {
      const next = { ...prev };
      if (raw === '') {
        delete next[key];
      } else {
        next[key] = parseInt(raw, 10);
      }
      return next;
    });
    setErrors(prev => { const n = { ...prev }; delete n[key]; return n; });
  };

  const handleSave = () => {
    const data = { ...draft };
    if (tempRaw === '') {
      delete data.body_temperature;
    } else {
      const val = parseFloat(tempRaw);
      if (!isNaN(val)) data.body_temperature = val;
    }

    // Validate all fields.
    const newErrors = {};
    for (const f of VITALS_FIELDS) {
      const val = f.key === 'body_temperature' ? tempRaw : data[f.key];
      const err = validateField(f.key, val);
      if (err) newErrors[f.key] = err;
      if (f.pair) {
        const pairVal = data[f.pair];
        const pairErr = validateField(f.pair, pairVal);
        if (pairErr) newErrors[f.pair] = pairErr;
      }
    }
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    onEdit(commandIndex, data);
    setEditing(false);
  };

  const handleCancel = () => {
    setDraft({ ...command.data });
    setErrors({});
    setTempRaw(command.data.body_temperature != null ? String(command.data.body_temperature) : '');
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') handleCancel();
  };

  if (editing) {
    return html`
      <div class="vitals-row editing" onKeyDown=${handleKeyDown}>
        <div class="vitals-edit-fields">
          ${VITALS_FIELDS.map(f => {
            if (f.pair) {
              const sysErr = errors[f.key];
              const diaErr = errors[f.pair];
              return html`
                <div class="vitals-edit-field vitals-edit-bp" key=${f.key}>
                  <span class="vitals-edit-label">${f.label}</span>
                  <div class="vitals-bp-inputs">
                    <input
                      type="number"
                      class="vitals-edit-input${sysErr ? ' vitals-input-error' : ''}"
                      value=${draft[f.key] ?? ''}
                      onInput=${(e) => updateField(f.key, e.target.value)}
                      placeholder=${f.min + '-' + f.max}
                    />
                    <span class="vitals-bp-slash">/</span>
                    <input
                      type="number"
                      class="vitals-edit-input${diaErr ? ' vitals-input-error' : ''}"
                      value=${draft[f.pair] ?? ''}
                      onInput=${(e) => updateField(f.pair, e.target.value)}
                      placeholder=${f.pairMin + '-' + f.pairMax}
                    />
                  </div>
                  <span class="vitals-edit-unit">${f.unit}</span>
                  ${(sysErr || diaErr) && html`<span class="vitals-error">${sysErr || diaErr}</span>`}
                </div>
              `;
            }
            const err = errors[f.key];
            return html`
              <div class="vitals-edit-field" key=${f.key}>
                <span class="vitals-edit-label">${f.label}</span>
                <input
                  type=${f.step ? 'text' : 'number'}
                  inputMode="decimal"
                  class="vitals-edit-input${err ? ' vitals-input-error' : ''}"
                  value=${f.step ? tempRaw : (draft[f.key] ?? '')}
                  onInput=${(e) => updateField(f.key, e.target.value)}
                  placeholder=${f.min + '-' + f.max}
                />
                <span class="vitals-edit-unit">${f.unit}</span>
                ${err && html`<span class="vitals-error">${err}</span>`}
              </div>
            `;
          })}
        </div>
        <div class="command-row-actions">
          <button type="button" class="rec-btn rec-btn-reject" onClick=${handleCancel} title="Cancel">${ICON_X}</button>
          <button type="button" class="rec-btn rec-btn-accept" onClick=${handleSave} title="Save">${ICON_CHECK}</button>
        </div>
      </div>
    `;
  }

  // View mode — compact list of present vitals.
  const items = [];
  VITALS_FIELDS.forEach(f => {
    if (f.pair) {
      const sys = command.data[f.key];
      const dia = command.data[f.pair];
      if (sys != null && dia != null) {
        items.push(html`<span class="vitals-item" key=${f.key}><strong>${f.label}</strong> ${sys}/${dia} ${f.unit}</span>`);
      }
    } else {
      const val = command.data[f.key];
      if (val != null) {
        items.push(html`<span class="vitals-item" key=${f.key}><strong>${f.label}</strong> ${val} ${f.unit}</span>`);
      }
    }
  });

  return html`
    <div class="vitals-row" onClick=${() => !readOnly && setEditing(true)}>
      ${items.length > 0
        ? html`<div class="vitals-values">${items}</div>`
        : html`<span class="vitals-placeholder">Tap to enter vitals</span>`
      }
    </div>
  `;
}
