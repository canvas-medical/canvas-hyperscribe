import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

// Toolbar icons for the template-merge button. Inline SVG rather than a unicode glyph
// so the stroke weight and baseline do not drift with the system font. Both are built on
// a 24x24 box: the merge arrows converge on a filled head, and the refresh arc is centred
// on 12,12 at r=8.5 with its head on the travel tangent so it reads counter-clockwise.
const SVG_ATTRS = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  'stroke-width': '1.8',
  'stroke-linecap': 'round',
  'stroke-linejoin': 'round',
  'aria-hidden': 'true',
};

const mergeIcon = () => html`
  <svg ...${SVG_ATTRS}>
    <path d="M2.5 5.5H7l5.5 6.5H16.5" />
    <path d="M2.5 18.5H7l5.5-6.5" />
    <polygon points="16.5,10.2 16.5,13.8 20,12" fill="currentColor" stroke="none" />
  </svg>
`;

const refreshIcon = () => html`
  <svg ...${SVG_ATTRS}>
    <path d="M3.5 12A8.5 8.5 0 1 0 5.99 5.99" />
    <polygon points="3.87,8.11 5.55,3.43 8.55,6.43" fill="currentColor" stroke="none" />
  </svg>
`;

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

const MERGE_LABEL = { apply: 'Merge template defaults', undo: 'Undo merge', redo: 'Redo merge' };
const MERGE_TITLE = {
  apply: "Blend the visit template's defaults into what this visit documented",
  undo: 'Keep only what this visit documented',
  redo: 'Bring back the merged version, template findings included',
};

// Copy for the confirm popover shared by Template / Carry forward / merge / Clear.
function confirmCopy(action, sectionKind, templates, mergeTemplateName) {
  const what = TITLE_CASE[sectionKind] || 'Physical Exam';
  if (action.kind === 'merge') {
    if (action.mode === 'apply') {
      const named = mergeTemplateName ? `the "${mergeTemplateName}" template` : 'the visit template';
      return {
        title: 'Merge template defaults?',
        body: `This blends ${named} into the ${what.toLowerCase()} you have now. Systems this visit never addressed will carry the template's wording. It takes a few seconds, and you can undo it afterward.`,
        go: 'Merge',
      };
    }
    if (action.mode === 'redo') {
      return {
        title: 'Redo the merge?',
        body: `This puts back the merged ${what.toLowerCase()}, including the findings that came from the visit template. Any edits you have made since undoing it will be discarded.`,
        go: 'Redo',
      };
    }
    const n = action.count || 0;
    return {
      title: 'Undo the merge?',
      body: `This removes the ${n} finding${n === 1 ? '' : 's'} that came from the visit template and keeps only what this visit documented. You can redo it afterward.`,
      go: 'Undo',
    };
  }
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
  onMergeTemplate, mergeKinds = [], mergeTemplate = null,
}) {
  const sections = (command.data && command.data.sections) || [];
  // `_seedText` is what the row held when the editor opened. persist() compares against
  // it to decide whether a row is still the template's or has become the provider's.
  const seed = () => sections.map(s => ({
    key: s.key || slug(s.title),
    title: s.title || '',
    text: stripMarkers(s.text),
    updated: s.updated,
    template_text: s.template_text,
    clauses: s.clauses,
    _seedText: stripMarkers(s.text),
    _new: false,
  }));

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(seed);
  const [confirm, setConfirm] = useState(null);     // { kind: 'carry'|'clear'|'template'|'merge', index?, mode? }
  const [menuOpen, setMenuOpen] = useState(false);
  // null | 'merge' | 'carry'. A tag rather than a boolean so the in-flight chip can
  // name the right action, without a second flag that could drift out of sync with this
  // one. Every read is a truthiness check, so `disabled=${busy}` is unchanged.
  const [busy, setBusy] = useState(null);
  const [removed, setRemoved] = useState(!!(command.data && command.data.template_removed));
  const [mergeError, setMergeError] = useState(null);
  // A fresh merge's restore points live here until Save writes them onto command.data,
  // so persist() has something to carry through and the button can flip to Undo first.
  const [mergeRefs, setMergeRefs] = useState(null);
  // Bumped on every request and on Save/Cancel. A response whose sequence is stale lost
  // its race and must not write into a draft that has moved on. The merge takes seconds,
  // so this is a real window rather than a theoretical one.
  const reqSeq = useRef(0);

  // The merge button is a drafting aid, so it stops once the command is on the chart
  // (`already_documented` is the finalized signal).
  //
  // Three states, and only the first costs a server call. Once a merge has landed, its
  // two restore points are on the card and undo/redo are local array swaps:
  //   no refs           -> "Merge template defaults"  (LLM call)
  //   refs, showing merged -> "Undo merge"            (instant)
  //   refs, showing pre-merge -> "Redo merge"         (instant)
  // Because it turns into Undo the moment a merge lands, a provider cannot merge twice
  // and compound template wording into an already-merged card.
  //
  // `updated` / `template_text` still ride along on each section even though nothing
  // renders them any more. They drive the count in the confirm popover and the
  // TEMPLATE_DEFAULTS_SIGNED audit event.
  const mergeSrc = mergeRefs || command.data || {};
  const hasMergeRefs = Array.isArray(mergeSrc.encounter_sections);
  const mergeScaffold = (mergeTemplate && mergeTemplate[TEMPLATE_FIELD[sectionKind]]) || [];
  const mergeState = !hasMergeRefs ? 'apply' : (removed ? 'redo' : 'undo');
  // An already-merged card keeps its undo even if the secret or the template changed
  // underneath it, otherwise the provider would be stuck with wording they cannot revert.
  const showMerge =
    !command.already_documented &&
    (hasMergeRefs || (mergeKinds.includes(sectionKind) && mergeScaffold.length > 0));
  // Clause-level, not row-level. A row marked updated=true can still carry unearned
  // template wording inside it: on one measured note the physical exam had zero
  // template-sourced ROWS but six template-sourced CLAUSES. Falls back to the row count
  // for summaries saved before clauses existed.
  const templateCount = draft.reduce((total, s) => {
    if (Array.isArray(s.clauses) && s.clauses.length > 0) {
      return total + s.clauses.filter(c => c.provenance === 'template').length;
    }
    return total + (s.updated === false && s.template_text ? 1 : 0);
  }, 0);
  const listRef = useRef(null);
  const focusNew = useRef(false);

  useEffect(() => {
    onEditingChange && onEditingChange(commandIndex, editing);
    return () => onEditingChange && onEditingChange(commandIndex, false);
  }, [editing, commandIndex]);

  useEffect(() => {
    if (!editing) {
      setDraft(seed());
      setRemoved(!!(command.data && command.data.template_removed));
      setMergeRefs(null);
      setMergeError(null);
    }
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

  // What the server and the chart both see: title and text, nothing else. The merge
  // request sends this so it blends into what the provider is actually looking at.
  const cleanRows = (rows) => rows
    .map(s => ({ key: s.key || slug(s.title), title: (s.title || '').trim(), text: (s.text || '').trim() }))
    .filter(s => s.title || s.text);

  // keepProvenance is on only for the merge button's undo and redo, which swap in
  // sections the server already stamped. Template apply and Carry forward bring in fresh
  // content that has no relationship to this note's merge, so they drop attribution.
  const toRows = (secs, keepProvenance = false) => secs.map(s => ({
    key: s.key || slug(s.title),
    title: s.title || '',
    text: stripMarkers(s.text),
    updated: keepProvenance ? s.updated : undefined,
    template_text: keepProvenance ? s.template_text : undefined,
    clauses: keepProvenance ? s.clauses : undefined,
    _seedText: stripMarkers(s.text),
    _new: false,
  }));

  const persist = (rows, removedFlag = removed) => {
    const cleaned = rows
      .map(s => {
        const row = { key: s.key || slug(s.title), title: (s.title || '').trim(), text: (s.text || '').trim() };
        // Attribution survives only on rows the provider left alone. Once they rewrite a
        // finding it is theirs, so the badge goes.
        if (s.template_text != null && (s.text || '') === (s._seedText || '')) {
          row.updated = !!s.updated;
          row.template_text = s.template_text;
        }
        // Clauses describe this exact text, so they only survive an untouched row.
        if (Array.isArray(s.clauses) && (s.text || '') === (s._seedText || '')) {
          row.clauses = s.clauses;
        }
        return row;
      })
      .filter(s => s.title || s.text);
    // handleEdit replaces command.data wholesale with whatever we pass, so the toggle's
    // restore points have to be carried through explicitly or the first Save wipes them.
    const data = { sections: cleaned };
    // A merge applied in this editing session has its refs in state, not on command.data.
    const src = mergeRefs || command.data || {};
    if (Array.isArray(src.encounter_sections)) {
      data.encounter_sections = src.encounter_sections;
      data.reconciled_sections = src.reconciled_sections || [];
      data.template_removed = removedFlag;
    }
    onEdit(commandIndex, data);
  };

  const handleSave = () => { reqSeq.current++; persist(draft); setEditing(false); };
  const handleCancel = () => {
    reqSeq.current++;
    setDraft(seed());
    setRemoved(!!(command.data && command.data.template_removed));
    setMergeRefs(null);
    setMergeError(null);
    setEditing(false);
  };

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
    if (action.kind === 'merge') {
      // Undo and redo are local swaps between the two restore points, so they are
      // instant and make no request. Undo drops template-only systems entirely and
      // returns blended rows to their pre-merge wording, because that is what
      // encounter_sections holds.
      if (action.mode !== 'apply') {
        const next = action.mode === 'redo'
          ? (mergeSrc.reconciled_sections || [])
          : (mergeSrc.encounter_sections || []);
        setRemoved(action.mode !== 'redo');
        setDraft(toRows(next, true));
        return;
      }
      // Apply is the one server call. Send the card as it stands so edits made before
      // the click are merged into rather than thrown away.
      const seq = ++reqSeq.current;
      setMergeError(null);
      setBusy('merge');
      let result = null;
      try {
        result = onMergeTemplate && (await onMergeTemplate(sectionKind, cleanRows(draft)));
      } catch (e) {
        result = null;
      }
      // Clear BEFORE the supersede check. Save and Cancel bump reqSeq, so returning first
      // left this set for good and reopening the card showed a fully disabled toolbar. A
      // second concurrent merge cannot reach here, because the button is disabled while the
      // tag is set and both Save and Cancel close the editor.
      setBusy(null);
      if (seq !== reqSeq.current) return;   // superseded: drop the result, the tag is clear
      if (!result || !result.ok) {
        setMergeError((result && result.message) || 'The merge could not run. Nothing was changed.');
        return;
      }
      setMergeRefs({
        encounter_sections: result.data.encounter_sections || [],
        reconciled_sections: result.data.reconciled_sections || [],
      });
      setRemoved(false);
      setDraft(toRows(result.data.sections || [], true));
      return;
    }
    if (action.kind === 'template') {
      const tmpl = templates[action.index];
      const secs = (tmpl && tmpl[TEMPLATE_FIELD[sectionKind]]) || [];
      setDraft(toRows(secs));
      return;
    }
    if (action.kind === 'carry') {
      setBusy('carry');
      let secs = [];
      try { secs = (onCarryForward && (await onCarryForward(sectionKind))) || []; } catch (e) { secs = []; }
      setBusy(null);
      if (secs.length) setDraft(toRows(secs));  // silent no-op when no prior exam
    }
  };

  // ── DISPLAY ──
  if (!editing) {
    return html`
      <div class=${`exam-rows${readOnly ? '' : ' exam-clickable'}`} onClick=${enterEdit}>
        ${sections.length === 0
          ? html`<div class="exam-empty">No ${LABEL[sectionKind]} documented.</div>`
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
          <button type="button" class="exam-action-btn" disabled=${busy} onClick=${(e) => { e.stopPropagation(); setMenuOpen(o => !o); }} title="Apply a configured visit template">
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
          <span class="exam-ico">⤵</span> ${busy === 'carry' ? 'Loading…' : 'Carry forward'}
        </button>
        <button type="button" class="exam-action-btn" disabled=${busy} onClick=${() => setConfirm({ kind: 'clear' })} title="Remove all systems and findings">
          <span class="exam-ico">⊘</span> Clear
        </button>
        ${showMerge && html`
          <button type="button" class="exam-action-btn" disabled=${busy}
            onClick=${() => setConfirm({ kind: 'merge', mode: mergeState, count: templateCount })}
            title=${MERGE_TITLE[mergeState]}>
            <span class="exam-ico">${mergeState === 'undo' ? refreshIcon() : mergeIcon()}</span> ${MERGE_LABEL[mergeState]}
          </button>
        `}
        ${busy === 'merge' && html`
          <span class="exam-status" role="status" aria-live="polite">
            <span class="exam-spin"></span> Merging template defaults
          </span>
        `}
      </div>

      ${mergeError && html`
        <div class="exam-merge-error" role="alert">
          ${mergeError}
          <button type="button" class="exam-merge-error-x" title="Dismiss" onClick=${() => setMergeError(null)}>×</button>
        </div>
      `}

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
        <button type="button" class="form-btn form-btn-cancel" disabled=${busy} onClick=${handleCancel}>Cancel</button>
        <button type="button" class="form-btn form-btn-save" disabled=${busy} onClick=${handleSave}>Save</button>
      </div>

      ${confirm && html`
        <div class="exam-confirm-overlay" onClick=${() => setConfirm(null)}>
          <div class="exam-confirm" onClick=${(e) => e.stopPropagation()}>
            ${(() => { const c = confirmCopy(confirm, sectionKind, templates, mergeTemplate && mergeTemplate.name); return html`
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
