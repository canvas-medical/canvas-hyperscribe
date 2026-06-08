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

const TEMPLATE_FIELD = { physical_exam: 'pe_sections', ros: 'ros_sections' };
const LABEL = { physical_exam: 'physical exam', ros: 'review of systems' };

function confirmCopy(kind, sectionKind) {
  const what = LABEL[sectionKind] === 'review of systems' ? 'Review of Systems' : 'Physical Exam';
  if (kind === 'clear') {
    return {
      title: `Clear ${what.toLowerCase()}?`,
      body: `This removes all systems and findings from the ${what}. You can add systems again, apply a template, or carry forward your last exam.`,
      go: 'Clear',
    };
  }
  return {
    title: 'Carry forward last exam?',
    body: `This replaces the current ${what} with the one from your most recent prior note for this patient (the last note you were the provider on). Current findings will be discarded.`,
    go: 'Replace',
  };
}

// Inline, compact editor for the Physical Exam / Review of Systems CustomCommands
// (schema_key physicalExam / reviewOfSystems). Replaces HistoryReviewRow for these
// two sections only; History Review / Chart Review still use HistoryReviewRow.
// All mutations funnel through onEdit(commandIndex, { sections }).
export function ExamSectionsRow({
  command, commandIndex, onEdit, readOnly, onEditingChange,
  sectionKind, templates = [], onCarryForward, onCombine,
}) {
  const sections = (command.data && command.data.sections) || [];
  const seed = () => sections.map(s => ({ key: s.key || slug(s.title), title: s.title || '', text: stripMarkers(s.text), _new: false }));

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(seed);
  const [confirm, setConfirm] = useState(null);     // { kind: 'carry'|'clear' }
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuSel, setMenuSel] = useState(-1);        // selected template index in the Template menu
  const [busy, setBusy] = useState(false);           // carry-forward loading
  const [merging, setMerging] = useState(false);     // AI-merge loading
  const listRef = useRef(null);
  const focusNew = useRef(false);

  useEffect(() => {
    onEditingChange && onEditingChange(commandIndex, editing);
    return () => onEditingChange && onEditingChange(commandIndex, false);
  }, [editing, commandIndex]);

  // Re-seed from the source when the command changes and we're not mid-edit.
  useEffect(() => {
    if (!editing) setDraft(seed());
  }, [command.data]);

  // Auto-size textareas whenever the edit list changes.
  useEffect(() => {
    if (!editing || !listRef.current) return;
    listRef.current.querySelectorAll('textarea').forEach(t => {
      t.style.height = 'auto';
      t.style.height = t.scrollHeight + 'px';
    });
  }, [editing, draft]);

  // Focus the most-recently added system's name input.
  useEffect(() => {
    if (focusNew.current && listRef.current) {
      const inputs = listRef.current.querySelectorAll('.exam-esys input');
      const last = inputs[inputs.length - 1];
      if (last) last.focus({ preventScroll: true });
      focusNew.current = false;
    }
  }, [draft.length]);

  // Close the template menu on any outside click.
  useEffect(() => {
    if (!menuOpen) return;
    const close = () => { setMenuOpen(false); setMenuSel(-1); };
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [menuOpen]);

  const enterEdit = () => { if (!readOnly) { setDraft(seed()); setEditing(true); } };

  // Map any [{key?,title,text}] into clean draft rows.
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

  // Template ▾ → Clear & Replace (deterministic) or AI Merge (LLM blend into current findings).
  const applyTemplate = async (mode) => {
    if (menuSel < 0) return;
    const tmpl = templates[menuSel];
    const templateSecs = (tmpl && tmpl[TEMPLATE_FIELD[sectionKind]]) || [];
    if (mode === 'replace') {
      setDraft(toRows(templateSecs));
      setMenuOpen(false); setMenuSel(-1);
      return;
    }
    // AI Merge — blend the template into the current card findings via the backend.
    setMerging(true);
    const current = draft
      .map(s => ({ key: s.key || slug(s.title), title: (s.title || '').trim(), text: (s.text || '').trim() }))
      .filter(s => s.title || s.text);
    let merged = null;
    try { merged = onCombine && (await onCombine(sectionKind, templateSecs, current)); } catch (e) { merged = null; }
    setMerging(false);
    // Silent no-op when the merge fails / returns nothing (no notice banner).
    if (Array.isArray(merged) && merged.length) setDraft(toRows(merged));
    setMenuOpen(false); setMenuSel(-1);
  };

  // Carry forward / Clear — confirmed single-click actions.
  const runConfirm = async () => {
    const kind = confirm;
    setConfirm(null);
    if (kind === 'clear') { setDraft([]); return; }
    if (kind === 'carry') {
      setBusy(true);
      let secs = [];
      try { secs = (onCarryForward && (await onCarryForward(sectionKind))) || []; } catch (e) { secs = []; }
      setBusy(false);
      // Silent no-op when there is no prior exam to carry forward.
      if (secs.length) setDraft(toRows(secs));
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
  // The `editing` class suppresses the app's .content-block:hover grey
  // (the wrapper uses :not(:has(.editing)) to gate that hover state).
  return html`
    <div class="exam-edit editing">
      <div class="exam-toolbar">
        <span class="exam-dropdown">
          <button type="button" class="exam-action-btn" onClick=${(e) => { e.stopPropagation(); setMenuOpen(o => { const n = !o; if (n) setMenuSel(-1); return n; }); }} title="Apply a configured visit template">
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
                    return html`<div class=${`exam-tmpl-row${i === menuSel ? ' sel' : ''}`} onClick=${() => setMenuSel(i)}>
                      <span class="exam-tmpl-radio"></span>
                      <span class="exam-tmpl-meta"><span class="exam-tmpl-name">${t.name}</span><span class="exam-tmpl-sub">${secs.length} system${secs.length === 1 ? '' : 's'}</span></span>
                    </div>`;
                  })}
                  <div class="exam-tmpl-divider"></div>
                  <div class="exam-tmpl-foot">
                    <button type="button" class="exam-foot-btn" disabled=${menuSel < 0} onClick=${() => applyTemplate('replace')}>⇄ Clear & Replace</button>
                    <button type="button" class="exam-foot-btn merge" disabled=${menuSel < 0 || merging} onClick=${() => applyTemplate('merge')}>✦ ${merging ? 'Merging…' : 'AI Merge'}</button>
                  </div>
                `}
            </div>
          `}
        </span>
        <button type="button" class="exam-action-btn" disabled=${busy} onClick=${() => setConfirm('carry')} title="Overwrite with your last documented exam">
          <span class="exam-ico">⤵</span> ${busy ? 'Loading…' : 'Carry forward'}
        </button>
        <button type="button" class="exam-action-btn" onClick=${() => setConfirm('clear')} title="Remove all systems and findings">
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
            ${(() => { const c = confirmCopy(confirm, sectionKind); return html`
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
