import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);

const ICON_X = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></svg>`;
const ICON_CHECK = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 10 18 20 6"/></svg>`;
const AI_SPARKLE = html`<span class="rec-ai-sparkle" aria-hidden="true"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.3l1.72 5.72c.18.6.66 1.08 1.26 1.26L20.7 11l-5.72 1.72c-.6.18-1.08.66-1.26 1.26L12 19.7l-1.72-5.72c-.18-.6-.66-1.08-1.26-1.26L3.3 11l5.72-1.72c.6-.18 1.08-.66 1.26-1.26z"/></svg></span>`;

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';

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

export function TaskRow({ command, commandIndex, onEdit, onDelete, assignees, readOnly, onEditingChange, aiPending }) {
  const [editing, setEditing] = useState(!command.display);
  useEffect(() => {
    onEditingChange?.(commandIndex, editing);
    return () => onEditingChange?.(commandIndex, false);
  }, [editing, commandIndex]);
  const [title, setTitle] = useState(command.data.title || '');
  const [dueDate, setDueDate] = useState(command.data.due_date || '');
  const [assignTo, setAssignTo] = useState(command.data.assign_to || null);
  const [selectedLabels, setSelectedLabels] = useState(command.data.labels || []);
  const [comment, setComment] = useState(command.data.comment || '');
  const [availableLabels, setAvailableLabels] = useState([]);
  const titleRef = useRef(null);

  useEffect(() => {
    if (editing && titleRef.current) {
      titleRef.current.focus({ preventScroll: true });
    }
  }, [editing]);

  useEffect(() => {
    if (!editing || availableLabels.length > 0) return;
    fetch(`${API_BASE}/task-labels`)
      .then(r => r.json())
      .then(d => setAvailableLabels(d.labels || []))
      .catch(() => {});
  }, [editing]);

  const handleSave = () => {
    if (!title.trim()) return;
    onEdit(commandIndex, {
      title: title.trim(),
      due_date: dueDate || null,
      assign_to: assignTo,
      labels: selectedLabels.length > 0 ? selectedLabels : null,
      comment: comment.trim() || null,
    });
    setEditing(false);
  };

  const handleCancel = () => {
    if (!command.display) {
      onDelete(commandIndex);
      return;
    }
    setTitle(command.data.title || '');
    setDueDate(command.data.due_date || '');
    setAssignTo(command.data.assign_to || null);
    setSelectedLabels(command.data.labels || []);
    setComment(command.data.comment || '');
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

  const toggleLabel = (name) => {
    setSelectedLabels(prev =>
      prev.includes(name) ? prev.filter(l => l !== name) : [...prev, name]
    );
  };

  const assigneeValue = assignTo ? `${assignTo.to}:${assignTo.id || ''}` : '';

  const assigneeLabel = () => {
    if (!assignTo) return '';
    const match = (assignees || []).find(
      a => a.type === assignTo.to && String(a.id) === String(assignTo.id)
    );
    return match ? match.label : '';
  };

  if (editing && !readOnly) {
    return html`
      <div class="task-row editing" onKeyDown=${handleKeyDown}>
        <div class="history-form">
          <div class="history-form-field">
            <label class="history-form-label">Task</label>
            <input
              ref=${titleRef}
              class="history-form-input"
              type="text"
              value=${title}
              onInput=${(e) => setTitle(e.target.value)}
              placeholder="Add a task..."
            />
          </div>
          <div class="history-form-field">
            <label class="history-form-label">Due Date</label>
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
          </div>
          <div class="history-form-field">
            <label class="history-form-label">Assign to</label>
            <select class="history-form-input" value=${assigneeValue} onChange=${handleAssigneeChange}>
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
          </div>
          ${availableLabels.length > 0 && html`
            <div class="history-form-field">
              <label class="history-form-label">Labels</label>
              <div class="task-labels">
                ${availableLabels.map(l => html`
                  <button
                    key=${l.name}
                    type="button"
                    class="task-label-btn${selectedLabels.includes(l.name) ? ' active' : ''}"
                    onClick=${() => toggleLabel(l.name)}
                  >${l.name}</button>
                `)}
              </div>
            </div>
          `}
          <div class="history-form-field">
            <label class="history-form-label">Comment</label>
            <textarea
              class="history-form-input"
              rows="2"
              value=${comment}
              onInput=${(e) => setComment(e.target.value)}
              placeholder="Optional comment..."
            />
          </div>
          <div class="questionnaire-form-actions">
            <button type="button" class="form-btn form-btn-cancel" onClick=${handleCancel}>Cancel</button>
            <button type="button" class="form-btn form-btn-save" onClick=${handleSave}>Save</button>
          </div>
        </div>
      </div>
    `;
  }

  const details = [];
  if (command.data.due_date) details.push(`Due ${formatDate(command.data.due_date)}`);
  const aLabel = assigneeLabel();
  if (aLabel) details.push(aLabel);
  if (command.data.labels && command.data.labels.length) details.push(command.data.labels.join(', '));
  if (command.data.comment) details.push(`Comment: ${command.data.comment}`);

  return html`
    <div class="task-row" onClick=${() => !readOnly && setEditing(true)}>
      <div class="order-view">
        <span class="command-type-label">Task</span>
        <div class="order-view-name">${command.display}${aiPending ? AI_SPARKLE : ''}</div>
        ${details.length > 0 && html`<div class="order-view-details">${details.join(' · ')}</div>`}
      </div>
    </div>
  `;
}
