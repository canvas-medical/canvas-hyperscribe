import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';
import { CommandItem } from '/plugin-io/api/hyperscribe/scribe/static/command-item.js';

const html = htm.bind(h);

export function CommandsSection({ commands, onToggle, onEdit, onInsert, inserting, inserted }) {
  const selectedCount = commands.filter(c => c.selected).length;

  return html`
    <div class="commands-container">
      <div class="commands-header">
        <span class="commands-title">PROPOSED COMMANDS</span>
        <span class="commands-count">${selectedCount} of ${commands.length} selected</span>
      </div>
      <div class="commands-list">
        ${commands.map((cmd, i) => html`
          <${CommandItem}
            key=${i}
            command=${cmd}
            onToggle=${() => onToggle(i)}
            onEdit=${(data) => onEdit(i, data)}
          />
        `)}
      </div>
      ${!inserted && html`
        <button
          class="insert-btn"
          onClick=${onInsert}
          disabled=${inserting || selectedCount === 0}
        >
          ${inserting ? 'Inserting...' : `Insert ${selectedCount} Command${selectedCount !== 1 ? 's' : ''} into Note`}
        </button>
      `}
      ${inserted && html`
        <p class="insert-success">Commands inserted into note.</p>
      `}
    </div>
  `;
}
