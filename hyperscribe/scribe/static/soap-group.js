import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';
import { CommandRow } from '/plugin-io/api/hyperscribe/scribe/static/command-row.js';
import { MedicationRow } from '/plugin-io/api/hyperscribe/scribe/static/medication-row.js';
import { VitalsRow } from '/plugin-io/api/hyperscribe/scribe/static/vitals-row.js';
import { TaskRow } from '/plugin-io/api/hyperscribe/scribe/static/task-row.js';
import { OrderRow } from '/plugin-io/api/hyperscribe/scribe/static/order-row.js';

const html = htm.bind(h);

const NARRATIVE_SECTIONS = new Set(['chief_complaint', 'history_of_present_illness', 'plan']);
const ORDER_TYPES = new Set(['prescribe', 'lab_order', 'imaging_order']);

export function SoapGroup({ title, sections, commandBySectionKey, onEditCommand, onToggleCommand, adHocCommands, assignees, onAddTask, onAddOrder }) {
  return html`
    <div class="summary-section">
      <div class="section-header">
        <span class="section-title">${title}</span>
      </div>
      <div class="section-body">
        ${sections.map(s => {
          const key = s.key.toLowerCase();
          const cmds = commandBySectionKey && commandBySectionKey[key];
          if (cmds && NARRATIVE_SECTIONS.has(key)) {
            const entry = cmds[0];
            return html`<${CommandRow}
              key=${key}
              command=${entry.command}
              commandIndex=${entry.index}
              onEdit=${onEditCommand}
            />`;
          }
          if (cmds && key === 'vitals') {
            const entry = cmds[0];
            return html`<${VitalsRow}
              key=${key}
              command=${entry.command}
              commandIndex=${entry.index}
              onEdit=${onEditCommand}
            />`;
          }
          if (cmds && key === 'current_medications') {
            return html`
              <div class="subsection" key=${s.key}>
                <div class="subsection-title">${s.title}</div>
                ${cmds.map(entry => html`<${MedicationRow}
                  key=${entry.index}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onToggle=${onToggleCommand}
                />`)}
              </div>
            `;
          }
          return html`
            <div class="subsection" key=${s.key}>
              <div class="subsection-title">${s.title}</div>
              <p class="section-text">${s.text}</p>
            </div>
          `;
        })}
        ${adHocCommands && adHocCommands.length > 0 && html`
          <div class="subsection">
            ${adHocCommands.map(entry => {
              if (entry.command.command_type === 'task') {
                return html`<${TaskRow}
                  key=${entry.index}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onToggle=${onToggleCommand}
                  assignees=${assignees}
                />`;
              }
              if (ORDER_TYPES.has(entry.command.command_type)) {
                return html`<${OrderRow}
                  key=${entry.index}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onToggle=${onToggleCommand}
                />`;
              }
              return null;
            })}
          </div>
        `}
        ${onAddTask && html`
          <div class="ad-hoc-buttons">
            <button type="button" class="ad-hoc-btn" onClick=${onAddTask}>+ Task</button>
            <button type="button" class="ad-hoc-btn" onClick=${onAddOrder}>+ Order</button>
          </div>
        `}
      </div>
    </div>
  `;
}
