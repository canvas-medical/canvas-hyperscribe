import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';
import { CommandRow } from '/plugin-io/api/hyperscribe/scribe/static/command-row.js';
import { MedicationRow } from '/plugin-io/api/hyperscribe/scribe/static/medication-row.js';
import { VitalsRow } from '/plugin-io/api/hyperscribe/scribe/static/vitals-row.js';

const html = htm.bind(h);

const NARRATIVE_SECTIONS = new Set(['chief_complaint', 'history_of_present_illness', 'plan']);

export function SoapGroup({ title, sections, commandBySectionKey, onEditCommand, onToggleCommand }) {
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
      </div>
    </div>
  `;
}
