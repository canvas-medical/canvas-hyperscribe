import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

export function HistoryReviewRow({ command, commandIndex, onEdit, onToggle }) {
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

  const handleToggle = (e) => {
    e.stopPropagation();
    if (onToggle) onToggle(commandIndex, e.target.checked);
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
        <div class="command-row-actions">
          <button class="edit-btn" onClick=${handleSave}>Save</button>
          <button class="edit-btn" onClick=${handleCancel}>Cancel</button>
        </div>
      </div>
    `;
  }

  return html`
    <div
      class="history-review-row${command.selected === false ? ' deselected' : ''}"
      onClick=${() => setEditing(true)}
    >
      ${onToggle && html`
        <input
          type="checkbox"
          class="command-checkbox"
          checked=${command.selected !== false}
          onClick=${handleToggle}
        />
      `}
      <div>
        ${sections.map((s, i) => html`
          <div key=${s.key}>
            ${i > 0 && html`<hr class="history-divider" />`}
            <div class="history-subsection">
              <div class="history-subsection-title">${s.title}</div>
              <div class="history-subsection-text">${s.text}</div>
            </div>
          </div>
        `)}
      </div>
    </div>
  `;
}
