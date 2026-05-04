import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const ICON_X = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></svg>`;
const ICON_CHECK = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 10 18 20 6"/></svg>`;
const ICON_INFO = html`<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill="currentColor"/><circle cx="12" cy="7.5" r="1.4" fill="#fff"/><rect x="10.7" y="10.6" width="2.6" height="8" rx="1.3" fill="#fff"/></svg>`;
// Filled-circle clock — same family as ICON_INFO. White minute hand at 12,
// hour hand at ~4. Reads as "time / history" without the rewind-arrow
// connotation of ↻ that previously confused users.
const ICON_HISTORY = html`<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill="currentColor"/><circle cx="12" cy="12" r="1.2" fill="#fff"/><line x1="12" y1="12" x2="12" y2="6.8" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/><line x1="12" y1="12" x2="15.2" y2="13.4" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/></svg>`;

function renderBoldMarkers(text) {
  if (!text || !text.includes('**')) return text;
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map(part => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return html`<strong class="positive-finding">${part.slice(2, -2)}</strong>`;
    }
    return part;
  });
}

function getEncounterChanges(sections) {
  return sections.filter(s => s.updated && s.template_text && s.template_text !== s.text);
}

function stripBoldMarkers(text) {
  return (text || '').replace(/\*\*/g, '');
}

function ReconciliationTrigger({ count, open, onToggle }) {
  if (count <= 0) return null;
  const label = open ? 'Hide AI generated changes' : 'Show AI generated changes';
  return html`
    <button
      type="button"
      class="history-reconciliation-trigger${open ? ' open' : ''}"
      title=${label}
      aria-label=${label}
      aria-expanded=${open ? 'true' : 'false'}
      onClick=${(e) => { e.stopPropagation(); onToggle(); }}
    >${ICON_INFO}</button>
  `;
}

function PriorVisitTrigger({ priorSection, open, onToggle }) {
  if (!priorSection || !priorSection.sections || priorSection.sections.length === 0) return null;
  const label = open ? 'Hide previous documentation' : 'View previous documentation';
  return html`
    <button
      type="button"
      class="history-prior-trigger${open ? ' open' : ''}"
      title=${label}
      aria-label=${label}
      aria-expanded=${open ? 'true' : 'false'}
      onClick=${(e) => { e.stopPropagation(); onToggle(); }}
    >${ICON_HISTORY}</button>
  `;
}

function sectionHasChange(s) {
  return !!(s && s.updated && s.template_text && s.template_text !== s.text);
}

function formatPriorDate(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch (_) {
    return '';
  }
}

function buildPriorByTitle(priorSection) {
  if (!priorSection || !Array.isArray(priorSection.sections)) return null;
  const map = new Map();
  for (const s of priorSection.sections) {
    if (s && s.title) {
      const key = s.title.trim().toLowerCase();
      if (!map.has(key)) map.set(key, (s.text || '').trim());
    }
  }
  return map;
}

export function HistoryReviewRow({ command, commandIndex, onEdit, readOnly, textareaRows, priorSection, onEditingChange }) {
  const sections = (command.data && command.data.sections) || [];
  const [editing, setEditing] = useState(false);
  const [reconciliationOpen, setReconciliationOpen] = useState(false);
  const [priorVisitOpen, setPriorVisitOpen] = useState(false);
  const priorByTitle = buildPriorByTitle(priorSection);
  const priorDateLabel = formatPriorDate(priorSection && priorSection.source_date);
  useEffect(() => {
    onEditingChange?.(commandIndex, editing);
    return () => onEditingChange?.(commandIndex, false);
  }, [editing, commandIndex]);
  const [drafts, setDrafts] = useState(sections.map(s => s.text || ''));
  const firstRef = useRef(null);

  useEffect(() => {
    if (editing && firstRef.current) {
      firstRef.current.focus({ preventScroll: true });
    }
  }, [editing]);

  useEffect(() => {
    setDrafts(sections.map(s => s.text || ''));
  }, [command.data]);

  const handleSave = () => {
    const updated = sections.map((s, i) => ({ ...s, text: drafts[i] || '' }));
    onEdit(commandIndex, { sections: updated });
    setEditing(false);
  };

  const handleCancel = () => {
    setDrafts(sections.map(s => s.text || ''));
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') handleCancel();
  };

  const encounterChanges = getEncounterChanges(sections);
  const hasChanges = encounterChanges.length > 0;

  // Edit mode: both AI-changes and prior-visit triggers are available so
  // providers can reference both signals while typing.
  if (editing && !readOnly) {
    const editReconciliationHeader = hasChanges ? html`
      <${ReconciliationTrigger}
        count=${encounterChanges.length}
        open=${reconciliationOpen}
        onToggle=${() => setReconciliationOpen(prev => !prev)}
      />
    ` : null;
    const editPriorHeader = (priorByTitle && priorByTitle.size > 0) ? html`
      <${PriorVisitTrigger}
        priorSection=${priorSection}
        open=${priorVisitOpen}
        onToggle=${() => setPriorVisitOpen(prev => !prev)}
      />
    ` : null;
    return html`
      <div class="history-review-row editing">
        ${editPriorHeader}
        ${editReconciliationHeader}
        ${sections.map((s, i) => {
          const showWas = reconciliationOpen && sectionHasChange(s);
          const priorText = priorVisitOpen && priorByTitle
            ? priorByTitle.get((s.title || '').trim().toLowerCase())
            : null;
          return html`
            <div class="history-subsection" key=${s.key}>
              <span class="history-subsection-title">${s.title}:</span>
              <textarea
                ref=${i === 0 ? firstRef : null}
                class="history-subsection-edit"
                rows="1"
                value=${drafts[i]}
                onInput=${(e) => {
                  const next = [...drafts];
                  next[i] = e.target.value;
                  setDrafts(next);
                }}
                onKeyDown=${handleKeyDown}
              />
              ${showWas && html`
                <div class="history-subsection-was">
                  <span class="history-subsection-was-label">was</span>
                  <span class="history-subsection-was-text">${stripBoldMarkers(s.template_text)}</span>
                </div>
              `}
              ${priorText && html`
                <div class="history-subsection-prior">
                  <span class="history-subsection-prior-label">${priorDateLabel || 'last visit'}</span>
                  <span class="history-subsection-prior-text">${priorText}</span>
                </div>
              `}
            </div>
          `;
        })}
        <div class="history-review-actions">
          <span class="history-review-hint">**asterisks** mark positive findings</span>
          <button type="button" class="form-btn form-btn-cancel" onClick=${handleCancel}>Cancel</button>
          <button type="button" class="form-btn form-btn-save" onClick=${handleSave}>Save</button>
        </div>
      </div>
    `;
  }

  // View mode: triggers (reconciliation + prior visit) are shown only here,
  // each only when relevant. Toggling reveals inline blocks beneath each
  // section so the current text is never duplicated in a separate panel.
  const reconciliationHeader = hasChanges ? html`
    <${ReconciliationTrigger}
      count=${encounterChanges.length}
      open=${reconciliationOpen}
      onToggle=${() => setReconciliationOpen(prev => !prev)}
    />
  ` : null;
  const priorHeader = (priorByTitle && priorByTitle.size > 0) ? html`
    <${PriorVisitTrigger}
      priorSection=${priorSection}
      open=${priorVisitOpen}
      onToggle=${() => setPriorVisitOpen(prev => !prev)}
    />
  ` : null;
  return html`
    <div
      class="history-review-row"
      onClick=${() => !readOnly && setEditing(true)}
    >
      ${priorHeader}
      ${reconciliationHeader}
      ${sections.map(s => {
        const showWas = reconciliationOpen && sectionHasChange(s);
        const priorText = priorVisitOpen && priorByTitle
          ? priorByTitle.get((s.title || '').trim().toLowerCase())
          : null;
        return html`
          <div class="history-subsection" key=${s.key}>
            <span class="history-subsection-title">${s.title}:</span>
            <span class="history-subsection-text">${renderBoldMarkers(s.text)}</span>
            ${showWas && html`
              <div class="history-subsection-was">
                <span class="history-subsection-was-label">was</span>
                <span class="history-subsection-was-text">${stripBoldMarkers(s.template_text)}</span>
              </div>
            `}
            ${priorText && html`
              <div class="history-subsection-prior">
                <span class="history-subsection-prior-label">${priorDateLabel || 'last visit'}</span>
                <span class="history-subsection-prior-text">${priorText}</span>
              </div>
            `}
          </div>
        `;
      })}
    </div>
  `;
}
