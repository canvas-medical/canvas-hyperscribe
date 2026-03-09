import { h } from 'https://esm.sh/preact@10.25.4';
import { useState } from 'https://esm.sh/preact@10.25.4/hooks';
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

export function CommandItem({ command, onToggle, onEdit }) {
  const [editing, setEditing] = useState(false);
  const field = DATA_FIELD[command.command_type] || 'narrative';
  const [value, setValue] = useState(command.data[field] || '');

  const handleSave = () => {
    onEdit({ ...command.data, [field]: value });
    setEditing(false);
  };

  const handleCancel = () => {
    setValue(command.data[field] || '');
    setEditing(false);
  };

  return html`
    <div class="command-item ${command.selected ? '' : 'deselected'}">
      <label class="command-checkbox">
        <input type="checkbox" checked=${command.selected} onChange=${onToggle} />
      </label>
      <div class="command-content">
        <div class="command-header-row">
          <span class="command-type-badge badge-${command.command_type}">
            ${TYPE_LABELS[command.command_type] || command.command_type}
          </span>
          ${!editing && html`
            <button class="edit-btn" onClick=${() => setEditing(true)}>Edit</button>
          `}
        </div>
        ${editing
          ? html`
            <textarea
              class="command-textarea"
              value=${value}
              onInput=${(e) => setValue(e.target.value)}
            />
            <div class="command-edit-actions">
              <button class="edit-btn" onClick=${handleSave}>Save</button>
              <button class="edit-btn" onClick=${handleCancel}>Cancel</button>
            </div>
          `
          : html`<p class="command-display">${command.display}</p>`
        }
      </div>
    </div>
  `;
}
