import { h } from 'https://esm.sh/preact@10.25.4';
import { useState } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const VITALS_FIELDS = [
  { key: 'blood_pressure_systole', pair: 'blood_pressure_diastole', label: 'BP', unit: 'mmHg' },
  { key: 'pulse', label: 'HR', unit: 'bpm' },
  { key: 'respiration_rate', label: 'RR', unit: '/min' },
  { key: 'oxygen_saturation', label: 'SpO2', unit: '%' },
  { key: 'body_temperature', label: 'Temp', unit: '°F', step: '0.1' },
  { key: 'height', label: 'Height', unit: 'in' },
  { key: 'weight_lbs', label: 'Weight', unit: 'lbs' },
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

export function VitalsRow({ command, commandIndex, onEdit }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ ...command.data });

  const updateField = (key, raw) => {
    setDraft(prev => {
      const next = { ...prev };
      if (raw === '') {
        delete next[key];
      } else {
        next[key] = key === 'body_temperature' ? parseFloat(raw) : parseInt(raw, 10);
      }
      return next;
    });
  };

  const handleSave = () => {
    onEdit(commandIndex, draft);
    setEditing(false);
  };

  const handleCancel = () => {
    setDraft({ ...command.data });
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') handleCancel();
  };

  if (editing) {
    return html`
      <div class="vitals-row editing" onKeyDown=${handleKeyDown}>
        <span class="command-type-badge badge-vitals">Vitals</span>
        <div class="vitals-grid">
          ${VITALS_FIELDS.map(f => {
            if (f.pair) {
              return html`
                <div class="vitals-field vitals-bp" key=${f.key}>
                  <label class="vitals-label">${f.label}</label>
                  <div class="vitals-bp-inputs">
                    <input
                      type="number"
                      class="vitals-input"
                      value=${draft[f.key] ?? ''}
                      onInput=${(e) => updateField(f.key, e.target.value)}
                      placeholder="sys"
                    />
                    <span class="vitals-bp-slash">/</span>
                    <input
                      type="number"
                      class="vitals-input"
                      value=${draft[f.pair] ?? ''}
                      onInput=${(e) => updateField(f.pair, e.target.value)}
                      placeholder="dia"
                    />
                  </div>
                  <span class="vitals-unit">${f.unit}</span>
                </div>
              `;
            }
            return html`
              <div class="vitals-field" key=${f.key}>
                <label class="vitals-label">${f.label}</label>
                <input
                  type="number"
                  step=${f.step || '1'}
                  class="vitals-input"
                  value=${draft[f.key] ?? ''}
                  onInput=${(e) => updateField(f.key, e.target.value)}
                />
                <span class="vitals-unit">${f.unit}</span>
              </div>
            `;
          })}
        </div>
        <div class="command-row-actions">
          <button class="edit-btn" onClick=${handleSave}>Save</button>
          <button class="edit-btn" onClick=${handleCancel}>Cancel</button>
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
    <div class="vitals-row" onClick=${() => setEditing(true)}>
      <div class="vitals-values">${items}</div>
    </div>
  `;
}
