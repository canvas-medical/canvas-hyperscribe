import { h } from 'https://esm.sh/preact@10.25.4';
import { useState } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

export const MAX_POINTERS = 4;
export const MAX_MODIFIERS = 4;

// Common modifiers seeded into the picker. code -> description.
export const MODIFIER_SEED = [
  { code: '25', desc: 'Significant, separately identifiable E/M service' },
  { code: '59', desc: 'Distinct procedural service' },
  { code: '95', desc: 'Synchronous telemedicine service' },
  { code: 'LT', desc: 'Left side' },
  { code: 'RT', desc: 'Right side' },
  { code: '76', desc: 'Repeat procedure by same physician' },
];

// Pure helpers — each charge must have >=1 pointer to be signable. Exported so
// summary.js's sign-gating reuses the exact same rule (single source of truth).
export function canSignCharges(charges) {
  return (charges || []).every(c => (c.pointers || []).length >= 1);
}

export function ModifierPicker({ selected, onToggle, onClose }) {
  const [query, setQuery] = useState('');
  const atCap = (selected || []).length >= MAX_MODIFIERS;
  const q = query.trim().toLowerCase();
  const rows = MODIFIER_SEED.filter(m =>
    !q || m.code.toLowerCase().includes(q) || m.desc.toLowerCase().includes(q));
  const freeCode = query.trim().toUpperCase();
  const showFree = freeCode.length >= 1 && freeCode.length <= 2
    && !MODIFIER_SEED.some(m => m.code === freeCode);
  return html`
    <div class="cm-modpicker" role="dialog">
      <input class="cm-modpicker-search" placeholder="Search modifier code or description"
        value=${query} onInput=${e => setQuery(e.target.value)} />
      <div class="cm-modpicker-list">
        ${rows.map(m => {
          const on = (selected || []).includes(m.code);
          const disabled = !on && atCap;
          return html`<button class="cm-modpicker-row${on ? ' on' : ''}" key=${m.code} disabled=${disabled}
            onClick=${() => onToggle(m.code)}>
            <span class="cm-modpicker-code">${m.code}</span>
            <span class="cm-modpicker-desc">${m.desc}</span>
            ${on ? html`<span class="cm-modpicker-check">✓</span>` : null}
          </button>`;
        })}
        ${showFree ? html`<button class="cm-modpicker-row" key="__free__" disabled=${atCap}
          onClick=${() => onToggle(freeCode)}>
          <span class="cm-modpicker-code">${freeCode}</span>
          <span class="cm-modpicker-desc">Use code "${freeCode}"</span>
        </button>` : null}
      </div>
      <button class="cm-modpicker-done" onClick=${onClose}>Done</button>
    </div>`;
}

export function ChargeMatrix({
  diagnoses, charges, isAmending,
  onTogglePointer, onReorderDiagnoses,
  onAddModifier, onRemoveModifier, onAddCharge, onRemoveCharge,
}) {
  const [modPickerFor, setModPickerFor] = useState(null);
  const dxs = diagnoses || [];
  const chs = charges || [];
  const lockedCount = isAmending ? dxs.filter(d => d.locked).length : 0;

  function handleDrop(e, targetIdx) {
    const draggedUuid = e.dataTransfer.getData('text/dx');
    if (!draggedUuid) return;
    const from = dxs.findIndex(d => d.command_uuid === draggedUuid);
    if (from < 0) return;
    let to = targetIdx;
    if (isAmending && to < lockedCount) to = lockedCount; // can't cross into the locked group
    const next = dxs.map(d => d.command_uuid);
    next.splice(to, 0, next.splice(from, 1)[0]);
    onReorderDiagnoses(next);
  }

  const headerCells = chs.map(charge => html`
    <div class="cm-col-header" key=${charge.command_uuid}>
      <div class="cm-cpt-row">
        <span class="cm-cpt">${charge.cpt}</span>
        <button class="cm-colremove" title="Remove charge"
          onClick=${() => onRemoveCharge(charge.command_uuid)}>×</button>
      </div>
      <div class="cm-modifiers">
        ${(charge.modifiers || []).map(code => html`
          <span class="cm-modchip" onClick=${() => onRemoveModifier(charge.command_uuid, code)}>
            ${code}<span class="cm-modchip-x">×</span>
          </span>`)}
        ${(charge.modifiers || []).length < MAX_MODIFIERS
          ? html`<button class="cm-modadd" onClick=${() => setModPickerFor(charge.command_uuid)}>+ Modifier</button>`
          : null}
        ${modPickerFor === charge.command_uuid
          ? html`<${ModifierPicker} selected=${charge.modifiers || []}
              onToggle=${code => ((charge.modifiers || []).includes(code)
                ? onRemoveModifier(charge.command_uuid, code)
                : onAddModifier(charge.command_uuid, code))}
              onClose=${() => setModPickerFor(null)} />`
          : null}
      </div>
    </div>`);

  const renderDxRow = (dx, idx) => {
    const draggable = !(isAmending && dx.locked);
    const rank = idx + 1;
    return html`
      <div class="cm-row${dx.locked ? ' cm-row-locked' : ''}" key=${dx.command_uuid}
           draggable=${draggable}
           onDragStart=${e => draggable && e.dataTransfer.setData('text/dx', dx.command_uuid)}
           onDragOver=${e => draggable && e.preventDefault()}
           onDrop=${e => handleDrop(e, idx)}>
        <span class="cm-grip">${draggable
          ? html`<span class="cm-grip-dots" title="Drag to reorder rank">⠿</span>`
          : html`<span class="cm-lock" title="Order locked — already on the signed claim">🔒</span>`}</span>
        <span class="cm-rank${dx.locked ? ' cm-rank-muted' : ''}">${rank}</span>
        <span class="cm-dxcode">${dx.code}</span>
        <span class="cm-dxlabel">${dx.label}</span>
        ${chs.map(charge => {
          const on = (charge.pointers || []).includes(dx.command_uuid);
          const atCap = !on && (charge.pointers || []).length >= MAX_POINTERS;
          return html`<span class="cm-cell${on ? ' cm-cell-on' : ''}" key=${charge.command_uuid}>
            <input type="checkbox" checked=${on} disabled=${atCap}
              title=${atCap ? `Max ${MAX_POINTERS} diagnosis pointers` : ''}
              aria-label=${`Link ${charge.cpt} to ${dx.code}`}
              onChange=${() => onTogglePointer(charge.command_uuid, dx.command_uuid)} />
          </span>`;
        })}
      </div>`;
  };

  const footerCells = chs.map(charge => {
    const n = (charge.pointers || []).length;
    return html`<span class="cm-pill${n === 0 ? ' cm-pill-error' : ''}" key=${charge.command_uuid}>${n} / ${MAX_POINTERS} ${n === 0 ? '✗' : '✓'}</span>`;
  });

  const lockedRows = [], newRows = [];
  dxs.forEach((dx, idx) => {
    (isAmending && dx.locked ? lockedRows : newRows).push(renderDxRow(dx, idx));
  });

  return html`
    <div class="cm-matrix" style=${`--cm-charge-cols:${chs.length}`}>
      <div class="cm-header-row">
        <div class="cm-corner"></div>
        ${headerCells}
        <button class="cm-addcol" title="Add charge" onClick=${onAddCharge}>+</button>
      </div>
      ${isAmending && lockedRows.length
        ? html`<div class="cm-group-label">ON THE SIGNED CLAIM</div>${lockedRows}
               <div class="cm-divider">added in this amendment</div>`
        : null}
      ${newRows}
      <div class="cm-footer-row"><div class="cm-corner"></div>${footerCells}</div>
    </div>`;
}
