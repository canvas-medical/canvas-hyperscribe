import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

export const MAX_POINTERS = 4;
export const MAX_MODIFIERS = 4;

// Common modifiers seeded into the picker. code -> description.
export const MODIFIER_SEED = [
  { code: 'GV', desc: 'Attending not employed by hospice' },
  { code: 'GW', desc: 'Unrelated to terminal condition' },
  { code: '25', desc: 'Significant, separate E/M same day' },
  { code: '33', desc: 'Preventive service' },
  { code: '59', desc: 'Distinct procedural service' },
  { code: '93', desc: 'Synchronous audio-only telemedicine' },
  { code: '95', desc: 'Synchronous audio/video telemedicine' },
];

// Pure helper — each charge must have >=1 diagnosis pointer to be signable.
// Exported so summary.js's sign-gating reuses the exact same rule.
export function canSignCharges(charges) {
  return (charges || []).every(c => (c.pointers || []).length >= 1);
}

// Searchable modifier picker (multi-select, cap 4, free 1-2 char codes).
export function ModifierPicker({ selected, onToggle, onClose }) {
  const [query, setQuery] = useState('');
  const atCap = (selected || []).length >= MAX_MODIFIERS;
  const q = query.trim().toLowerCase();
  const rows = MODIFIER_SEED.filter(m =>
    !q || m.code.toLowerCase().includes(q) || m.desc.toLowerCase().includes(q));
  const freeCode = query.trim().toUpperCase();
  const showFree = freeCode.length >= 1 && freeCode.length <= 2
    && !MODIFIER_SEED.some(m => m.code === freeCode);
  // Search on top; results scroll below it.
  return html`
    <div class="cm-popover" role="dialog">
      <input class="cm-popover-search" autofocus placeholder="Search modifier code or description"
        value=${query} onInput=${e => setQuery(e.target.value)} />
      <div class="cm-popover-list">
        ${rows.map(m => {
          const on = (selected || []).includes(m.code);
          return html`<button class="cm-popover-row${on ? ' on' : ''}" key=${m.code}
            disabled=${!on && atCap} onClick=${() => onToggle(m.code)}>
            <span class="cm-popover-code">${m.code}</span>
            <span class="cm-popover-desc">${m.desc}</span>
            ${on ? html`<span class="cm-popover-check">✓</span>` : null}
          </button>`;
        })}
        ${showFree ? html`<button class="cm-popover-row" key="__free__" disabled=${atCap}
          onClick=${() => onToggle(freeCode)}>
          <span class="cm-popover-code">${freeCode}</span>
          <span class="cm-popover-desc">Use code "${freeCode}"</span>
        </button>` : null}
      </div>
    </div>`;
}

// CPT/HCPCS search popover for adding a charge column. Queries /search-charges
// via the injected `searchCharges(query)` async fn.
export function ChargePicker({ searchCharges, suggested, onPick, onClose }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const onInput = async (e) => {
    const value = e.target.value;
    setQuery(value);
    const t = value.trim();
    if (t.length < 2 || !searchCharges) { setResults([]); return; }
    try {
      const r = await searchCharges(t);
      setResults(Array.isArray(r) ? r : []);
    } catch (_err) {
      setResults([]);
    }
  };
  // Search on top; below it: the visit template's suggested charges (until the
  // provider starts typing), then free-text search results.
  const q = query.trim();
  const sugg = suggested || [];
  return html`
    <div class="cm-popover cm-popover-wide" role="dialog">
      <input class="cm-popover-search" autofocus
        placeholder="Search CPT/HCPCS code or description"
        value=${query} onInput=${onInput} />
      <div class="cm-popover-list">
        ${q.length < 2 && sugg.length ? html`
          <div class="cm-popover-group">Suggested for this visit</div>
          ${sugg.map(s => html`<button class="cm-popover-row" key=${'sugg-' + s.cpt_code}
            onClick=${() => onPick(s.cpt_code, s.description || '')}>
            <span class="cm-popover-code">${s.cpt_code}</span>
            <span class="cm-popover-desc">${s.description || ''}</span>
          </button>`)}` : null}
        ${q.length >= 2 ? results.map(r => html`<button class="cm-popover-row" key=${r.cpt_code}
          onClick=${() => onPick(r.cpt_code, r.short_name || r.full_name || '')}>
          <span class="cm-popover-code">${r.cpt_code}</span>
          <span class="cm-popover-desc">${r.short_name || r.full_name || ''}</span>
        </button>`) : null}
        ${q.length >= 2 && results.length === 0
          ? html`<div class="cm-popover-empty">No matching charges</div>` : null}
        ${q.length < 2 && sugg.length === 0
          ? html`<div class="cm-popover-empty">Type to search CPT/HCPCS codes</div>` : null}
      </div>
    </div>`;
}

export function ChargeMatrix({
  diagnoses, charges, isAmending, readOnly, searchCharges, suggested,
  onTogglePointer, onReorderDiagnoses,
  onAddModifier, onRemoveModifier, onAddCharge, onRemoveCharge,
}) {
  // Single popover state so only one (modifier or charge-search) is ever open.
  // { kind: 'mod', id: <charge uuid> } | { kind: 'charge' } | null
  const [popover, setPopover] = useState(null);

  // Close the open popover (modifier picker / CPT search) on an outside click
  // or Escape — so the provider doesn't have to use Cancel/Done. Clicks on a
  // popover or its trigger are ignored so opening/toggling still works.
  useEffect(() => {
    if (!popover) return undefined;
    const onPointerDown = (e) => {
      const t = e.target;
      if (t && t.closest && (t.closest('.cm-popover') || t.closest('.cm-modadd') || t.closest('.cm-add-btn'))) return;
      setPopover(null);
    };
    const onKeyDown = (e) => { if (e.key === 'Escape') setPopover(null); };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [popover]);

  const dxs = diagnoses || [];
  const chs = charges || [];
  // Template-suggested charges, minus any CPT already on the matrix.
  const existingCpts = new Set(chs.map(c => c.cpt));
  const suggestedAvailable = (suggested || []).filter(s => !existingCpts.has(s.cpt_code));
  const lockedCount = isAmending ? dxs.filter(d => d.locked).length : 0;
  const colSpan = chs.length + 2; // diagnosis col + charge cols + add col

  function handleDrop(e, targetIdx) {
    e.preventDefault();
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

  const headerCells = chs.map(charge => {
    const mods = charge.modifiers || [];
    const open = popover && popover.kind === 'mod' && popover.id === charge.command_uuid;
    return html`
      <th class="cm-charge-head" key=${charge.command_uuid}>
        <div class="cm-cpt-row">
          <span class="cm-cpt">${charge.cpt}</span>
          ${!readOnly ? html`<button class="cm-colremove" title="Remove charge"
            onClick=${() => onRemoveCharge(charge.command_uuid)}>×</button>` : null}
        </div>
        <div class="cm-mods">
          ${mods.map(code => readOnly
            ? html`<span class="cm-modchip cm-modchip-static" key=${code}>${code}</span>`
            : html`<span class="cm-modchip" key=${code} title="Remove modifier"
                onClick=${() => onRemoveModifier(charge.command_uuid, code)}>
                ${code}<span class="cm-modchip-x">×</span>
              </span>`)}
          ${!readOnly && mods.length < MAX_MODIFIERS
            ? html`<button class="cm-modadd"
                onClick=${() => setPopover(open ? null : { kind: 'mod', id: charge.command_uuid })}>+ Modifier</button>`
            : null}
        </div>
        ${open && !readOnly ? html`<${ModifierPicker} selected=${mods}
            onToggle=${code => {
              if (mods.includes(code)) {
                onRemoveModifier(charge.command_uuid, code);
              } else {
                onAddModifier(charge.command_uuid, code);
                setPopover(null); // close once a modifier is selected
              }
            }}
            onClose=${() => setPopover(null)} />` : null}
      </th>`;
  });

  const renderDxRow = (dx, idx) => {
    const draggable = !readOnly && !(isAmending && dx.locked);
    const isDxDrag = e => e.dataTransfer && e.dataTransfer.types
      && Array.from(e.dataTransfer.types).includes('text/dx');
    return html`
      <tr class="cm-row${dx.locked ? ' cm-row-locked' : ''}" key=${dx.command_uuid}
          draggable=${draggable}
          onDragStart=${e => {
            if (!draggable) return;
            // Don't start a drag from a click on the checkbox / a button.
            if (e.target.closest && e.target.closest('input, button, select, textarea, a')) {
              e.preventDefault();
              return;
            }
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/dx', dx.command_uuid);
          }}
          onDragOver=${e => { if (isDxDrag(e)) { e.preventDefault(); e.currentTarget.classList.add('cm-drag-over'); } }}
          onDragLeave=${e => e.currentTarget.classList.remove('cm-drag-over')}
          onDrop=${e => { e.currentTarget.classList.remove('cm-drag-over'); handleDrop(e, idx); }}>
        <td class="cm-dx">
          <div class="cm-dx-inner">
            ${draggable
              ? html`<span class="cm-grip" title="Drag to reorder rank">⠿</span>`
              : (isAmending && dx.locked)
                ? html`<span class="cm-lock" title="Order locked — already on the signed claim">🔒</span>`
                : html`<span class="cm-grip-empty"></span>`}
            <span class="cm-rank${dx.locked ? ' cm-rank-muted' : ''}">${idx + 1}</span>
            <span class="cm-dxcode">${dx.code}</span>
            <span class="cm-dxlabel">${dx.label}</span>
          </div>
        </td>
        ${chs.map(charge => {
          const on = (charge.pointers || []).includes(dx.command_uuid);
          const atCap = !on && (charge.pointers || []).length >= MAX_POINTERS;
          return html`<td class="cm-cell${on ? ' on' : ''}" key=${charge.command_uuid}>
            <input type="checkbox" checked=${on} disabled=${readOnly || atCap}
              title=${atCap ? `Max ${MAX_POINTERS} diagnosis pointers` : ''}
              aria-label=${`Link ${charge.cpt} to ${dx.code}`}
              onChange=${() => onTogglePointer(charge.command_uuid, dx.command_uuid)} />
          </td>`;
        })}
        <td class="cm-add-cell"></td>
      </tr>`;
  };

  const bodyRows = [];
  if (isAmending && lockedCount > 0) {
    bodyRows.push(html`<tr class="cm-grouprow" key="__locked_label"><td colSpan=${colSpan}>On the signed claim</td></tr>`);
    dxs.forEach((dx, idx) => { if (dx.locked) bodyRows.push(renderDxRow(dx, idx)); });
    bodyRows.push(html`<tr class="cm-dividerrow" key="__new_label"><td colSpan=${colSpan}>Added in this amendment</td></tr>`);
    dxs.forEach((dx, idx) => { if (!dx.locked) bodyRows.push(renderDxRow(dx, idx)); });
  } else {
    dxs.forEach((dx, idx) => bodyRows.push(renderDxRow(dx, idx)));
  }

  const chargeOpen = popover && popover.kind === 'charge';

  return html`
    <div class="cm-wrap">
      <table class="cm-table">
        <thead>
          <tr>
            <th class="cm-dx-head"></th>
            ${headerCells}
            <th class="cm-add-head">
              ${!readOnly ? html`
                <button class="cm-add-btn" title="Add charge"
                  onClick=${() => setPopover(chargeOpen ? null : { kind: 'charge' })}>+</button>
                ${chargeOpen ? html`<${ChargePicker} searchCharges=${searchCharges} suggested=${suggestedAvailable}
                    onPick=${(cpt, desc) => { onAddCharge(cpt, desc); setPopover(null); }}
                    onClose=${() => setPopover(null)} />` : null}` : null}
            </th>
          </tr>
        </thead>
        <tbody>${dxs.length === 0
          ? html`<tr><td class="cm-empty" colSpan=${colSpan}>Add a diagnosis in the Plan, then link it to a charge here.</td></tr>`
          : bodyRows}</tbody>
        ${chs.length > 0 ? html`
          <tfoot>
            <tr>
              <td class="cm-foot-dx"></td>
              ${chs.map(charge => {
                const n = (charge.pointers || []).length;
                return html`<td class="cm-foot-cell" key=${charge.command_uuid}>
                  <span class="cm-pill${n === 0 ? ' cm-pill-error' : ''}">${n} / ${MAX_POINTERS} ${n === 0 ? '✗' : '✓'}</span>
                </td>`;
              })}
              <td></td>
            </tr>
          </tfoot>` : null}
      </table>
    </div>`;
}
