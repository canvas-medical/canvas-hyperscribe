import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function addDays(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().split('T')[0];
}

export function TaskRow({ command, commandIndex, onEdit, onToggle, assignees }) {
  const [editing, setEditing] = useState(!command.display);
  const [title, setTitle] = useState(command.data.title || '');
  const [dueDate, setDueDate] = useState(command.data.due_date || '');
  const [assignTo, setAssignTo] = useState(command.data.assign_to || null);
  const titleRef = useRef(null);

  useEffect(() => {
    if (editing && titleRef.current) {
      titleRef.current.focus();
    }
  }, [editing]);

  const handleSave = () => {
    if (!title.trim()) return;
    onEdit(commandIndex, {
      title: title.trim(),
      due_date: dueDate || null,
      assign_to: assignTo,
    });
    setEditing(false);
  };

  const handleCancel = () => {
    if (!command.display) {
      // New unsaved task — deselect it to effectively remove
      onToggle(commandIndex, false);
    }
    setTitle(command.data.title || '');
    setDueDate(command.data.due_date || '');
    setAssignTo(command.data.assign_to || null);
    setEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') handleCancel();
  };

  const handleAssigneeChange = (e) => {
    const val = e.target.value;
    if (!val) {
      setAssignTo(null);
      return;
    }
    const [type, id] = val.split(':');
    setAssignTo({ to: type, id: type === 'unassigned' ? undefined : id });
  };

  const assigneeValue = assignTo ? `${assignTo.to}:${assignTo.id || ''}` : '';

  const assigneeLabel = () => {
    if (!assignTo) return '';
    const match = (assignees || []).find(
      a => a.type === assignTo.to && String(a.id) === String(assignTo.id)
    );
    return match ? match.label : '';
  };

  if (editing) {
    return html`
      <div class="task-row editing" onKeyDown=${handleKeyDown}>
        <span class="command-type-badge badge-task">Task</span>
        <div class="task-form">
          <input
            ref=${titleRef}
            class="task-input task-title-input"
            type="text"
            value=${title}
            onInput=${(e) => setTitle(e.target.value)}
            placeholder="Add a task..."
          />
          <div class="task-due-date">
            <button
              type="button"
              class="task-quick-btn${dueDate === addDays(1) ? ' active' : ''}"
              onClick=${() => setDueDate(dueDate === addDays(1) ? '' : addDays(1))}
            >Tomorrow</button>
            <button
              type="button"
              class="task-quick-btn${dueDate === addDays(7) ? ' active' : ''}"
              onClick=${() => setDueDate(dueDate === addDays(7) ? '' : addDays(7))}
            >In a week</button>
            <input
              class="task-date-picker"
              type="date"
              value=${dueDate}
              onInput=${(e) => setDueDate(e.target.value)}
            />
          </div>
          <select class="task-select" value=${assigneeValue} onChange=${handleAssigneeChange}>
            <option value="">Unassigned</option>
            ${(assignees || []).some(a => a.type === 'team') && html`
              <optgroup label="Teams">
                ${(assignees || []).filter(a => a.type === 'team').map(a => html`
                  <option key=${`team:${a.id}`} value=${`team:${a.id}`}>${a.label}</option>
                `)}
              </optgroup>
            `}
            ${(assignees || []).some(a => a.type === 'staff') && html`
              <optgroup label="Staff">
                ${(assignees || []).filter(a => a.type === 'staff').map(a => html`
                  <option key=${`staff:${a.id}`} value=${`staff:${a.id}`}>${a.label}</option>
                `)}
              </optgroup>
            `}
          </select>
          <div class="command-row-actions">
            <button class="edit-btn" onClick=${handleSave} disabled=${!title.trim()}>Save</button>
            <button class="edit-btn" onClick=${handleCancel}>Cancel</button>
          </div>
        </div>
      </div>
    `;
  }

  const parts = [command.display];
  if (command.data.due_date) parts.push(`Due ${formatDate(command.data.due_date)}`);
  const aLabel = assigneeLabel();
  if (aLabel) parts.push(aLabel);

  return html`
    <div class="task-row${command.selected === false ? ' deselected' : ''}" onClick=${() => setEditing(true)}>
      <input
        type="checkbox"
        class="medication-checkbox"
        checked=${command.selected !== false}
        onClick=${(e) => { e.stopPropagation(); onToggle(commandIndex, e.target.checked); }}
      />
      <span class="command-type-badge badge-task">Task</span>
      <span class="command-row-text">${parts[0]}</span>
      ${command.data.due_date && html`<span class="task-meta-badge">${formatDate(command.data.due_date)}</span>`}
      ${aLabel && html`<span class="task-meta-badge">${aLabel}</span>`}
    </div>
  `;
}
