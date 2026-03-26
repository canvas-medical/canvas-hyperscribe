import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const ICON_X = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></svg>`;
const ICON_CHECK = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 10 18 20 6"/></svg>`;

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

function DiffToggle({ templateText, currentText }) {
  const [open, setOpen] = useState(false);
  if (!templateText || templateText === currentText) return null;
  return html`
    <span
      class="reconciliation-badge updated"
      onClick=${(e) => { e.stopPropagation(); setOpen(prev => !prev); }}
    >
      Updated from encounter ${open ? '▾' : '▸'}
    </span>
    ${open && html`
      <div class="reconciliation-diff" onClick=${(e) => e.stopPropagation()}>
        <div class="reconciliation-diff-label">Template default:</div>
        <div class="reconciliation-diff-text">${templateText}</div>
      </div>
    `}
  `;
}

export function HistoryReviewRow({ command, commandIndex, onEdit, readOnly }) {
  const sections = (command.data && command.data.sections) || [];
  const [editing, setEditing] = useState(false);
  const [drafts, setDrafts] = useState(sections.map(s => s.text || ''));
  const firstRef = useRef(null);

  useEffect(() => {
    if (editing && firstRef.current) {
      firstRef.current.focus();
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

  if (editing) {
    return html`
      <div class="history-review-row editing">
        ${sections.map((s, i) => html`
          <div class="history-subsection" key=${s.key}>
            <div class="history-subsection-title">${s.title}</div>
            <textarea
              ref=${i === 0 ? firstRef : null}
              class="command-row-textarea"
              value=${drafts[i]}
              onInput=${(e) => {
                const next = [...drafts];
                next[i] = e.target.value;
                setDrafts(next);
              }}
              onKeyDown=${handleKeyDown}
            />
          </div>
        `)}
        <div class="questionnaire-form-actions">
          <button type="button" class="form-btn form-btn-cancel" onClick=${handleCancel}>Cancel</button>
          <button type="button" class="form-btn form-btn-save" onClick=${handleSave}>Save</button>
        </div>
      </div>
    `;
  }

  return html`
    <div
      class="history-review-row"
      onClick=${() => !readOnly && setEditing(true)}
    >
      <div>
        ${sections.map((s, i) => html`
          <div key=${s.key}>
            ${i > 0 && html`<hr class="history-divider" />`}
            <div class="history-subsection">
              <div class="history-subsection-header">
                <div class="history-subsection-title">${s.title}</div>
                ${s.updated && html`<${DiffToggle} templateText=${s.template_text} currentText=${s.text} />`}
              </div>
              <div class="history-subsection-text">${renderBoldMarkers(s.text)}</div>
            </div>
          </div>
        `)}
      </div>
    </div>
  `;
}
