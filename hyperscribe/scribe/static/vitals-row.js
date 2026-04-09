import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
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

const BP_SITE_OPTIONS = [
  { value: 0, label: 'Sitting, Right Upper Arm', group: 'Sitting' },
  { value: 1, label: 'Sitting, Left Upper Arm', group: 'Sitting' },
  { value: 2, label: 'Sitting, Right Lower Arm', group: 'Sitting' },
  { value: 3, label: 'Sitting, Left Lower Arm', group: 'Sitting' },
  { value: 4, label: 'Standing, Right Upper Arm', group: 'Standing' },
  { value: 5, label: 'Standing, Left Upper Arm', group: 'Standing' },
  { value: 6, label: 'Standing, Right Lower Arm', group: 'Standing' },
  { value: 7, label: 'Standing, Left Lower Arm', group: 'Standing' },
  { value: 8, label: 'Supine, Right Upper Arm', group: 'Supine' },
  { value: 9, label: 'Supine, Left Upper Arm', group: 'Supine' },
  { value: 10, label: 'Supine, Right Lower Arm', group: 'Supine' },
  { value: 11, label: 'Supine, Left Lower Arm', group: 'Supine' },
];
const BP_SITE_GROUPS = ['Sitting', 'Standing', 'Supine'];

function bpSiteLabel(value) {
  const opt = BP_SITE_OPTIONS.find(o => o.value === Number(value));
  return opt ? opt.label : '';
}

export { bpSiteLabel };

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
  if (data.blood_pressure_position_and_site != null) {
    const label = bpSiteLabel(data.blood_pressure_position_and_site);
    if (label) parts.push(`Site: ${label}`);
  }
  if (data.note) parts.push(`Note: ${data.note}`);
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

export function VitalsRow({ command, commandIndex, onEdit, readOnly, onEditingChange }) {
  const hasData = Object.values(command.data || {}).some(v => v != null);
  const [editing, setEditing] = useState(!readOnly && !hasData);
  useEffect(() => {
    onEditingChange?.(commandIndex, editing);
    return () => onEditingChange?.(commandIndex, false);
  }, [editing, commandIndex]);
  const [draft, setDraft] = useState({ ...command.data });
  const [tempRaw, setTempRaw] = useState(command.data.body_temperature != null ? String(command.data.body_temperature) : '');
  const [bpSite, setBpSite] = useState(command.data.blood_pressure_position_and_site != null ? String(command.data.blood_pressure_position_and_site) : '');
  const [note, setNote] = useState(command.data.note || '');
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
    if (note.length > 150) newErrors.note = 'Max 150 characters';
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    delete data.blood_pressure_position_and_site;
    delete data.note;
    if (bpSite !== '') data.blood_pressure_position_and_site = parseInt(bpSite, 10);
    if (note.trim()) data.note = note.trim();
    onEdit(commandIndex, data);
    setEditing(false);
  };

  const handleCancel = () => {
    setDraft({ ...command.data });
    setErrors({});
    setTempRaw(command.data.body_temperature != null ? String(command.data.body_temperature) : '');
    setBpSite(command.data.blood_pressure_position_and_site != null ? String(command.data.blood_pressure_position_and_site) : '');
    setNote(command.data.note || '');
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') handleCancel();
  };

  if (editing && !readOnly) {
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
        <div class="vitals-extra-fields">
          <div class="history-form-field">
            <label class="history-form-label">BP Position & Site</label>
            <select class="history-form-input" value=${bpSite} onChange=${(e) => setBpSite(e.target.value)}>
              <option value="">None</option>
              ${BP_SITE_GROUPS.map(group => html`
                <optgroup label=${group} key=${group}>
                  ${BP_SITE_OPTIONS.filter(o => o.group === group).map(o => html`
                    <option key=${o.value} value=${o.value}>${o.label}</option>
                  `)}
                </optgroup>
              `)}
            </select>
          </div>
          <div class="history-form-field">
            <label class="history-form-label">Comment</label>
            <input
              type="text"
              class="history-form-input"
              maxLength=${150}
              value=${note}
              onInput=${(e) => setNote(e.target.value)}
              placeholder="Optional note (max 150 characters)"
            />
            <div class="char-counter${note.length > 130 ? note.length > 150 ? ' over-limit' : ' near-limit' : ''}">${note.length} / 150</div>
            ${errors.note && html`<span class="vitals-error">${errors.note}</span>`}
          </div>
        </div>
        <div class="command-row-actions">
          <button type="button" class="form-btn form-btn-cancel" onClick=${handleCancel}>Cancel</button>
          <button type="button" class="form-btn form-btn-save" onClick=${handleSave}>Save</button>
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
  if (command.data.blood_pressure_position_and_site != null) {
    const label = bpSiteLabel(command.data.blood_pressure_position_and_site);
    if (label) items.push(html`<span class="vitals-item" key="bp_site"><strong>Site</strong> ${label}</span>`);
  }
  if (command.data.note) {
    items.push(html`<span class="vitals-item" key="note"><strong>Note</strong> ${command.data.note}</span>`);
  }

  return html`
    <div class="vitals-row" onClick=${() => !readOnly && setEditing(true)}>
      ${items.length > 0
        ? html`<div class="vitals-values">${items}</div>`
        : html`<span class="vitals-placeholder">Tap to enter vitals</span>`
      }
    </div>
  `;
}
