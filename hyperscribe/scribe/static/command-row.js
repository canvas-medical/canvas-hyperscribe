import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const TYPE_LABELS = {
  rfv: 'RFV',
  hpi: 'HPI',
  plan: 'Plan',
};

const DATA_FIELD = {
  rfv: 'comment',
  hpi: 'narrative',
  plan: 'narrative',
};

export function CommandRow({ command, commandIndex, onEdit }) {
  const field = DATA_FIELD[command.command_type];
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(field ? (command.data[field] || '') : '');
  const textareaRef = useRef(null);

  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [editing]);

  const handleSave = () => {
    onEdit(commandIndex, { ...command.data, [field]: value });
    setEditing(false);
  };

  const handleCancel = () => {
    setValue(field ? (command.data[field] || '') : '');
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      handleCancel();
    }
  };

  if (editing) {
    return html`
      <div class="command-row editing">
        <span class="command-type-badge badge-${command.command_type}">
          ${TYPE_LABELS[command.command_type] || command.command_type}
        </span>
        <textarea
          ref=${textareaRef}
          class="command-row-textarea"
          value=${value}
          onInput=${(e) => setValue(e.target.value)}
          onKeyDown=${handleKeyDown}
        />
        <div class="command-row-actions">
          <button class="edit-btn" onClick=${handleSave}>Save</button>
          <button class="edit-btn" onClick=${handleCancel}>Cancel</button>
        </div>
      </div>
    `;
  }

  return html`
    <div class="command-row" onClick=${() => setEditing(true)}>
      <span class="command-type-badge badge-${command.command_type}">
        ${TYPE_LABELS[command.command_type] || command.command_type}
      </span>
      <span class="command-row-text">${command.display}</span>
    </div>
  `;
}
