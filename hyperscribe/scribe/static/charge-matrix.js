import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

export const MAX_POINTERS = 4;
export const MAX_MODIFIERS = 4;
// Soft cap on a charge comment — warns past it, never blocks typing/saving.
// The underlying perform.notes field is an unconstrained string; this is a UX
// guideline so the popover stays sane, not a hard limit.
export const MAX_COMMENT = 500;

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

// Pure helper — charges that this plugin has managed (hasPointerData) must have
// >=1 diagnosis pointer. Pre-plugin historical charges (no _pointers key in data,
// hasPointerData:false) are grandfathered so they never block signing on old notes.
// Exported so summary.js's sign-gating reuses the exact same rule.
export function canSignCharges(charges) {
  return (charges || []).every(c => !c.hasPointerData || (c.pointers || []).length >= 1);
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

// Free-text comment editor for a charge — the saved text lands as the perform
// command's `notes`. Soft cap (warns past MAX_COMMENT, never blocks). Save with
// empty text clears the comment (handled by the caller).
export function CommentEditor({ value, onSave, onCancel }) {
  const [text, setText] = useState(value || '');
  const over = text.length > MAX_COMMENT;
  return html`
    <div class="cm-popover cm-popover-comment" role="dialog">
      <textarea class="cm-comment-ta" autofocus placeholder="Add a comment for this charge…"
        value=${text} onInput=${e => setText(e.target.value)}></textarea>
      <div class="cm-comment-foot">
        <span class="cm-comment-count${over ? ' over' : ''}">${text.length} / ${MAX_COMMENT}</span>
        <div class="cm-comment-actions">
          <button class="cm-comment-btn cm-comment-btn-ghost" onClick=${onCancel}>Cancel</button>
          <button class="cm-comment-btn cm-comment-btn-primary" onClick=${() => onSave(text.trim())}>Save</button>
        </div>
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
  onSetComment, onClearComment,
}) {
  // Single popover state so only one popover is ever open.
  // { kind: 'mod', id } | { kind: 'commentEdit', id } | { kind: 'commentRead', id }
  // | { kind: 'charge' } | null
  const [popover, setPopover] = useState(null);

  // Close the open popover (modifier picker / CPT search) on an outside click
  // or Escape — so the provider doesn't have to use Cancel/Done. Clicks on a
  // popover or its trigger are ignored so opening/toggling still works.
  useEffect(() => {
    if (!popover) return undefined;
    const onPointerDown = (e) => {
      const t = e.target;
      if (t && t.closest && (t.closest('.cm-popover') || t.closest('.cm-modadd') || t.closest('.cm-add-btn')
          || t.closest('.cm-noteadd') || t.closest('.cm-notechip'))) return;
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
  // Diagnoses present but no charges yet (and the note is editable): show a
  // ghost charge column nudging the provider to add a charge to bill the visit.
  // It replaces the orphaned "+" add column 1-for-1, so colSpan is unchanged.
  const showGhostCharge = !readOnly && chs.length === 0 && dxs.length > 0;

  function handleDrop(e, targetIdx) {
    e.preventDefault();
    const draggedUuid = e.dataTransfer.getData('text/dx');
    if (!draggedUuid) return;
    const from = dxs.findIndex(d => d.command_uuid === draggedUuid);
    if (from < 0) return;
    let to = targetIdx;
    if (isAmending && to < lockedCount) to = lockedCount; // can't cross into the locked group
    const next = dxs.map(d => d.command_uuid);
    // Drop-above-target semantics (the indicator is a top-border on the target row).
    // For a forward drag (from < to), the inner splice(from,1) removes the dragged
    // item first, shifting the target down one slot, so we insert at `to - 1` to land
    // above it. Backward drags (from >= to) are unaffected.
    const insertAt = from < to ? to - 1 : to;
    next.splice(insertAt, 0, next.splice(from, 1)[0]);
    onReorderDiagnoses(next);
  }

  const headerCells = chs.map(charge => {
    const mods = charge.modifiers || [];
    const open = popover && popover.kind === 'mod' && popover.id === charge.command_uuid;
    const comment = charge.comment || '';
    const cmtEdit = popover && popover.kind === 'commentEdit' && popover.id === charge.command_uuid;
    const cmtRead = popover && popover.kind === 'commentRead' && popover.id === charge.command_uuid;
    // Editable whenever the matrix is. Editing a comment on a charge already on
    // the signed claim is handled in summary.js by entering the old charge in
    // error and re-entering a clone with the new comment (with explicit BLI
    // cleanup so /enrich-charges stays unambiguous).
    const commentEditable = !readOnly;
    return html`
      <th class="cm-charge-head" key=${charge.command_uuid}>
        <div class="cm-cpt-row">
          <span class="cm-cpt">${charge.cpt}</span>
          ${!readOnly ? html`<button class="cm-colremove" title="Remove charge"
            onClick=${() => onRemoveCharge(charge.command_uuid)}>×</button>` : null}
        </div>
        <div class="cm-affordances">
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
          ${comment
            ? html`<span class="cm-notechip" title="View comment"
                onClick=${() => setPopover(cmtRead ? null : { kind: 'commentRead', id: charge.command_uuid })}>
                <svg class="cm-notechip-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                <span class="cm-notechip-label">${comment}</span>
              </span>`
            : (commentEditable
                ? html`<button class="cm-noteadd"
                    onClick=${() => setPopover(cmtEdit ? null : { kind: 'commentEdit', id: charge.command_uuid })}>+ Comment</button>`
                : null)}
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
        ${cmtEdit && commentEditable ? html`<${CommentEditor} value=${comment}
            onSave=${text => {
              if (text) onSetComment(charge.command_uuid, text);
              else onClearComment(charge.command_uuid);
              setPopover(null);
            }}
            onCancel=${() => setPopover(null)} />` : null}
        ${cmtRead ? html`
          <div class="cm-popover cm-popover-comment" role="dialog">
            <div class="cm-comment-read">${comment}</div>
            ${commentEditable
              ? html`<div class="cm-comment-foot">
                  <span></span>
                  <div class="cm-comment-actions">
                    <button class="cm-comment-btn cm-comment-btn-danger"
                      onClick=${() => { onClearComment(charge.command_uuid); setPopover(null); }}>Remove</button>
                    <button class="cm-comment-btn cm-comment-btn-ghost"
                      onClick=${() => setPopover({ kind: 'commentEdit', id: charge.command_uuid })}>Edit</button>
                  </div>
                </div>`
              : html`<div class="cm-comment-meta">Read-only — note finalized.</div>`}
          </div>` : null}
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
                ? html`<span class="cm-lock" title="Order locked — already on the signed claim"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></span>`
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
        ${showGhostCharge
          ? html`<td class="cm-ghost-cell"><span class="cm-ghost-check"></span></td>`
          : html`<td class="cm-add-cell"></td>`}
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
  // The CPT search popover (with the visit template's suggestions). Reused by
  // both the header "+" and the empty-state "Add charge" button.
  const chargePicker = chargeOpen
    ? html`<${ChargePicker} searchCharges=${searchCharges} suggested=${suggestedAvailable}
        onPick=${(cpt, desc) => { onAddCharge(cpt, desc); setPopover(null); }}
        onClose=${() => setPopover(null)} />`
    : null;

  // Fully-empty state (no diagnoses and no charges): a friendly panel instead
  // of an empty table shell with an orphaned "+".
  if (dxs.length === 0 && chs.length === 0) {
    return html`
      <div class="cm-wrap">
        <div class="cm-empty-panel">
          <div class="cm-empty-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 3h16v18l-3-2-2 2-2-2-2 2-2-2-3 2z"/><path d="M8 8h8M8 12h8"/></svg>
          </div>
          <div class="cm-empty-title">No charges yet</div>
          <div class="cm-empty-hint">Add a condition above, then a charge here.</div>
          ${!readOnly ? html`<div class="cm-empty-add">
            <button class="cm-empty-btn" onClick=${() => setPopover(chargeOpen ? null : { kind: 'charge' })}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>
              Add charge
            </button>
            ${chargePicker}
          </div>` : null}
        </div>
      </div>`;
  }

  return html`
    <div class="cm-wrap">
      <table class="cm-table">
        <thead>
          <tr>
            <th class="cm-dx-head"></th>
            ${headerCells}
            ${showGhostCharge
              ? html`<th class="cm-ghost-head">
                  <button class="cm-empty-btn" onClick=${() => setPopover(chargeOpen ? null : { kind: 'charge' })}>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>
                    Add charge
                  </button>
                  ${chargePicker}
                </th>`
              : html`<th class="cm-add-head">
                  ${!readOnly ? html`
                    <button class="cm-add-btn" title="Add charge"
                      onClick=${() => setPopover(chargeOpen ? null : { kind: 'charge' })}>+</button>
                    ${chargePicker}` : null}
                </th>`}
          </tr>
        </thead>
        <tbody>${dxs.length === 0
          ? html`<tr><td class="cm-empty" colSpan=${colSpan}>Add a condition above to link this charge.</td></tr>`
          : bodyRows}</tbody>
        ${chs.length > 0 ? html`
          <tfoot>
            <tr>
              <td class="cm-foot-dx"></td>
              ${chs.map(charge => {
                const n = (charge.pointers || []).length;
                const legacy = !charge.hasPointerData && n === 0;
                return html`<td class="cm-foot-cell" key=${charge.command_uuid}>
                  <span class="cm-pill${legacy ? ' cm-pill-muted' : n === 0 ? ' cm-pill-error' : ''}">
                    ${legacy ? '—' : `${n} / ${MAX_POINTERS}`}
                  </span>
                </td>`;
              })}
              <td></td>
            </tr>
          </tfoot>` : null}
      </table>
    </div>`;
}
