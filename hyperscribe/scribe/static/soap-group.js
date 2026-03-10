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

const COMMAND_BADGE = {
  rfv: { label: 'RFV', color: 'rfv' },
  hpi: { label: 'HPI', color: 'hpi' },
  plan: { label: 'Plan', color: 'plan_cmd' },
  vitals: { label: 'Vitals', color: 'vitals' },
  medication_statement: { label: 'Med', color: 'medication' },
  task: { label: 'Task', color: 'task' },
  prescribe: { label: 'Rx', color: 'prescribe' },
  lab_order: { label: 'Lab', color: 'lab_order' },
  imaging_order: { label: 'Imaging', color: 'imaging_order' },
};

export function SoapGroup({ title, groupColor, sections, commandBySectionKey, onEditCommand, onToggleCommand, adHocCommands, assignees, onAddTask, onAddOrder }) {
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
            const badge = COMMAND_BADGE[entry.command.command_type] || { label: entry.command.command_type, color: 'rfv' };
            return html`
              <div class="subsection" key=${s.key}>
                <div class="subsection-title">${s.title}</div>
                <div class="content-block has-badge content-block--${badge.color}">
                  <span class="content-block-badge badge-${entry.command.command_type}">${badge.label}</span>
                  <${CommandRow}
                    command=${entry.command}
                    commandIndex=${entry.index}
                    onEdit=${onEditCommand}
                    onToggle=${onToggleCommand}
                  />
                </div>
              </div>
            `;
          }

          if (cmds && key === 'vitals') {
            const entry = cmds[0];
            return html`
              <div class="subsection" key=${s.key}>
                <div class="subsection-title">${s.title}</div>
                <div class="content-block has-badge content-block--vitals">
                  <span class="content-block-badge badge-vitals">Vitals</span>
                  <${VitalsRow}
                    command=${entry.command}
                    commandIndex=${entry.index}
                    onEdit=${onEditCommand}
                    onToggle=${onToggleCommand}
                  />
                </div>
              </div>
            `;
          }

          if (cmds && key === 'current_medications') {
            return html`
              <div class="subsection" key=${s.key}>
                <div class="subsection-title">${s.title}</div>
                ${cmds.map(entry => html`
                  <div class="content-block content-block--medication" key=${entry.index}>
                    <${MedicationRow}
                      command=${entry.command}
                      commandIndex=${entry.index}
                      onEdit=${onEditCommand}
                      onToggle=${onToggleCommand}
                    />
                  </div>
                `)}
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
        ${adHocCommands && adHocCommands.map(entry => {
          const type = entry.command.command_type;
          const badge = COMMAND_BADGE[type] || { label: type, color: 'task' };
          if (type === 'task') {
            return html`
              <div class="content-block content-block--${badge.color}" key=${entry.index}>
                <${TaskRow}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onToggle=${onToggleCommand}
                  assignees=${assignees}
                />
              </div>
            `;
          }
          if (ORDER_TYPES.has(type)) {
            return html`
              <div class="content-block content-block--${badge.color}" key=${entry.index}>
                <${OrderRow}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onToggle=${onToggleCommand}
                />
              </div>
            `;
          }
          return null;
        })}
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
