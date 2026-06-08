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

export function HistoryReviewRow({ command, commandIndex, onEdit, readOnly, textareaRows, onEditingChange }) {
  const sections = (command.data && command.data.sections) || [];
  const [editing, setEditing] = useState(false);
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

  if (editing && !readOnly) {
    return html`
      <div class="history-review-row editing">
        ${sections.map((s, i) => html`
          <div class="history-subsection" key=${s.key}>
            <div class="history-subsection-title">${s.title}</div>
            <textarea
              ref=${i === 0 ? firstRef : null}
              class="command-row-textarea"
              rows=${textareaRows || undefined}
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
              </div>
              <div class="history-subsection-text">${renderBoldMarkers(s.text)}</div>
            </div>
          </div>
        `)}
      </div>
    </div>
  `;
}
