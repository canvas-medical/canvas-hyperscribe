import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const ICON_X = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></svg>`;
const ICON_CHECK = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 10 18 20 6"/></svg>`;

const DATA_FIELD = {
  rfv: 'comment',
  hpi: 'narrative',
  plan: 'narrative',
  lab_results: 'narrative',
};

export function CommandRow({ command, commandIndex, onEdit, onDelete, readOnly, onEditingChange }) {
  const field = DATA_FIELD[command.command_type];
  const isNew = onDelete && !command.display;
  const [editing, setEditing] = useState(isNew);
  useEffect(() => {
    onEditingChange?.(commandIndex, editing);
    return () => onEditingChange?.(commandIndex, false);
  }, [editing, commandIndex]);
  const [value, setValue] = useState(field ? (command.data[field] || '') : '');
  const textareaRef = useRef(null);

  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus({ preventScroll: true });
    }
  }, [editing]);

  const handleSave = () => {
    onEdit(commandIndex, { ...command.data, [field]: value });
    setEditing(false);
  };

  const handleCancel = () => {
    if (isNew) {
      onDelete(commandIndex);
      return;
    }
    setValue(field ? (command.data[field] || '') : '');
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      handleCancel();
    }
  };

  if (editing && !readOnly) {
    return html`
      <div class="command-row editing">
        <textarea
          ref=${textareaRef}
          class="command-row-textarea"
          rows=${command.command_type === 'hpi' ? 10 : undefined}
          value=${value}
          onInput=${(e) => setValue(e.target.value)}
          onKeyDown=${handleKeyDown}
        />
        <div class="command-row-actions">
          <button type="button" class="form-btn form-btn-cancel" onClick=${handleCancel}>Cancel</button>
          <button type="button" class="form-btn form-btn-save" onClick=${handleSave}>Save</button>
        </div>
      </div>
    `;
  }

  return html`
    <div class="command-row" onClick=${() => !readOnly && setEditing(true)}>
      ${command.display
        ? html`<span class="command-row-text">${command.display}</span>`
        : !readOnly && html`<span class="command-row-placeholder">Tap to enter text</span>`
      }
    </div>
  `;
}
