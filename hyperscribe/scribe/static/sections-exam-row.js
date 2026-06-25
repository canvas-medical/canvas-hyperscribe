import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

// Strip the reconciliation bold markers (**...**) — the redesign drops the
// normal/abnormal distinction, so positives render as plain text.
function stripMarkers(text) {
  if (!text) return '';
  return String(text).replace(/\*\*([^*]+)\*\*/g, '$1');
}

function slug(title) {
  return (title || '').toLowerCase().trim().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '') || 'system';
}

const TEMPLATE_FIELD = { physical_exam: 'pe_sections', ros: 'ros_sections', mental_status_exam: 'mse_sections' };
const LABEL = { physical_exam: 'physical exam', ros: 'review of systems', mental_status_exam: 'mental status exam' };
const TITLE_CASE = {
  physical_exam: 'Physical Exam',
  ros: 'Review of Systems',
  mental_status_exam: 'Mental Status Exam',
};

// Copy for the confirm popover shared by Template / Carry forward / Clear.
function confirmCopy(action, sectionKind, templates) {
  const what = TITLE_CASE[sectionKind] || 'Physical Exam';
  if (action.kind === 'clear') {
    return {
      title: `Clear ${what.toLowerCase()}?`,
      body: `This removes all systems and findings from the ${what}. You can add systems again, apply a template, or carry forward your last exam.`,
      go: 'Clear',
    };
  }
  if (action.kind === 'carry') {
    return {
      title: 'Carry forward last exam?',
      body: `This replaces the current ${what} with the one from your most recent prior note for this patient (the last note you were the provider on). Current findings will be discarded.`,
      go: 'Replace',
    };
  }
  // template
  const name = (templates[action.index] || {}).name || '';
  return {
    title: `Apply "${name}"?`,
    body: `This replaces the current ${what} with the "${name}" template. Current findings will be discarded.`,
    go: 'Apply',
  };
}

// Inline, compact editor for the Physical Exam / Review of Systems CustomCommands
// (schema_key physicalExam / reviewOfSystems). Replaces HistoryReviewRow for these
// two sections only; History Review / Chart Review still use HistoryReviewRow.
// All mutations funnel through onEdit(commandIndex, { sections }).
export function ExamSectionsRow({
  command, commandIndex, onEdit, readOnly, onEditingChange,
  sectionKind, templates = [], onCarryForward,
}) {
  const sections = (command.data && command.data.sections) || [];
  const seed = () => sections.map(s => ({ key: s.key || slug(s.title), title: s.title || '', text: stripMarkers(s.text), _new: false }));

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(seed);
  const [confirm, setConfirm] = useState(null);     // { kind: 'carry'|'clear'|'template', index? }
  const [menuOpen, setMenuOpen] = useState(false);
  const [busy, setBusy] = useState(false);           // carry-forward loading
  const listRef = useRef(null);
  const focusNew = useRef(false);

  useEffect(() => {
    onEditingChange && onEditingChange(commandIndex, editing);
    return () => onEditingChange && onEditingChange(commandIndex, false);
  }, [editing, commandIndex]);

  useEffect(() => {
    if (!editing) setDraft(seed());
  }, [command.data]);

  useEffect(() => {
    if (!editing || !listRef.current) return;
    listRef.current.querySelectorAll('textarea').forEach(t => {
      t.style.height = 'auto';
      t.style.height = t.scrollHeight + 'px';
    });
  }, [editing, draft]);

  useEffect(() => {
    if (focusNew.current && listRef.current) {
      const inputs = listRef.current.querySelectorAll('.exam-esys input');
      const last = inputs[inputs.length - 1];
      if (last) last.focus({ preventScroll: true });
      focusNew.current = false;
    }
  }, [draft.length]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = () => setMenuOpen(false);
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [menuOpen]);

  const enterEdit = () => { if (!readOnly) { setDraft(seed()); setEditing(true); } };

  const toRows = (secs) => secs.map(s => ({ key: s.key || slug(s.title), title: s.title || '', text: stripMarkers(s.text), _new: false }));

  const persist = (rows) => {
    const cleaned = rows
      .map(s => ({ key: s.key || slug(s.title), title: (s.title || '').trim(), text: (s.text || '').trim() }))
      .filter(s => s.title || s.text);
    onEdit(commandIndex, { sections: cleaned });
  };

  const handleSave = () => { persist(draft); setEditing(false); };
  const handleCancel = () => { setDraft(seed()); setEditing(false); };

  const updateText = (i, val) => setDraft(d => d.map((s, j) => (j === i ? { ...s, text: val } : s)));
  const updateTitle = (i, val) => setDraft(d => d.map((s, j) => (j === i ? { ...s, title: val } : s)));
  const removeRow = (i) => setDraft(d => d.filter((_, j) => j !== i));
  const addSystem = () => { focusNew.current = true; setDraft(d => [...d, { key: '', title: '', text: '', _new: true }]); };

  // Template / Carry forward / Clear — all confirmed via the same popover.
  const runConfirm = async () => {
    const action = confirm;
    setConfirm(null);
    if (!action) return;
    if (action.kind === 'clear') { setDraft([]); return; }
    if (action.kind === 'template') {
      const tmpl = templates[action.index];
      const secs = (tmpl && tmpl[TEMPLATE_FIELD[sectionKind]]) || [];
      setDraft(toRows(secs));
      return;
    }
    if (action.kind === 'carry') {
      setBusy(true);
      let secs = [];
      try { secs = (onCarryForward && (await onCarryForward(sectionKind))) || []; } catch (e) { secs = []; }
      setBusy(false);
      if (secs.length) setDraft(toRows(secs));  // silent no-op when no prior exam
    }
  };

  // ── DISPLAY ──
  if (!editing) {
    return html`
      <div class=${`exam-rows${readOnly ? '' : ' exam-clickable'}`} onClick=${enterEdit}>
        ${sections.length === 0
          ? html`<div class="exam-empty">No ${LABEL[sectionKind]} documented.${readOnly ? '' : ' Click to add.'}</div>`
          : sections.map((s, i) => html`
            <div class="exam-row" key=${s.key || i}>
              <div class="exam-sys">${s.title}</div>
              <div class="exam-find">${stripMarkers(s.text)}</div>
            </div>
          `)}
      </div>
    `;
  }

  // ── EDIT ──
  // The `editing` class suppresses the app's .content-block:hover grey.
  return html`
    <div class="exam-edit editing">
      <div class="exam-toolbar">
        <span class="exam-dropdown">
          <button type="button" class="exam-action-btn" onClick=${(e) => { e.stopPropagation(); setMenuOpen(o => !o); }} title="Apply a configured visit template">
            <span class="exam-ico">⊞</span> Template <span class="exam-ico">▾</span>
          </button>
          ${menuOpen && html`
            <div class="exam-menu" onClick=${(e) => e.stopPropagation()}>
              ${templates.length === 0
                ? html`<div class="exam-menu-empty">No visit templates configured.</div>`
                : html`
                  <div class="exam-menu-head">Apply a visit template</div>
                  ${templates.map((t, i) => {
                    const secs = (t[TEMPLATE_FIELD[sectionKind]] || []);
                    return html`<button type="button" class="exam-menu-item" onClick=${() => { setMenuOpen(false); setConfirm({ kind: 'template', index: i }); }}>
                      ${t.name}<small>${secs.length} system${secs.length === 1 ? '' : 's'}</small>
                    </button>`;
                  })}
                `}
            </div>
          `}
        </span>
        <button type="button" class="exam-action-btn" disabled=${busy} onClick=${() => setConfirm({ kind: 'carry' })} title="Overwrite with your last documented exam">
          <span class="exam-ico">⤵</span> ${busy ? 'Loading…' : 'Carry forward'}
        </button>
        <button type="button" class="exam-action-btn" onClick=${() => setConfirm({ kind: 'clear' })} title="Remove all systems and findings">
          <span class="exam-ico">⊘</span> Clear
        </button>
      </div>

      <div class="exam-list" ref=${listRef}>
        ${draft.map((s, i) => html`
          <div class="exam-erow" key=${i}>
            <div class="exam-esys">
              ${s._new
                ? html`<input type="text" placeholder="System name" value=${s.title} onInput=${(e) => updateTitle(i, e.target.value)} />`
                : html`<span class="exam-elabel">${s.title}</span>`}
            </div>
            <div class="exam-efind">
              <textarea rows="1" value=${s.text} onInput=${(e) => updateText(i, e.target.value)}></textarea>
            </div>
            <div class="exam-controls">
              <button type="button" class="exam-remove" title="Remove system" onClick=${() => removeRow(i)}>×</button>
            </div>
          </div>
        `)}
      </div>

      <div class="exam-add">
        <button type="button" class="exam-add-btn" onClick=${addSystem}>+ Add system</button>
      </div>

      <div class="exam-actions">
        <button type="button" class="form-btn form-btn-cancel" onClick=${handleCancel}>Cancel</button>
        <button type="button" class="form-btn form-btn-save" onClick=${handleSave}>Save</button>
      </div>

      ${confirm && html`
        <div class="exam-confirm-overlay" onClick=${() => setConfirm(null)}>
          <div class="exam-confirm" onClick=${(e) => e.stopPropagation()}>
            ${(() => { const c = confirmCopy(confirm, sectionKind, templates); return html`
              <h3>${c.title}</h3>
              <p>${c.body}</p>
              <div class="exam-confirm-actions">
                <button type="button" class="form-btn form-btn-cancel" onClick=${() => setConfirm(null)}>Cancel</button>
                <button type="button" class="form-btn exam-confirm-go" onClick=${runConfirm}>${c.go}</button>
              </div>
            `; })()}
          </div>
        </div>
      `}
    </div>
  `;
}
