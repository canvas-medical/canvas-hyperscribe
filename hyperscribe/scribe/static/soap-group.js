import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';
import { CommandRow } from '/plugin-io/api/hyperscribe/scribe/static/command-row.js';
import { VitalsRow } from '/plugin-io/api/hyperscribe/scribe/static/vitals-row.js';

const html = htm.bind(h);

const NARRATIVE_SECTIONS = new Set(['chief_complaint', 'history_of_present_illness', 'plan']);

export function SoapGroup({ title, sections, commandBySectionKey, onEditCommand }) {
  return html`
    <div class="summary-section">
      <div class="section-header">
        <span class="section-title">${title}</span>
      </div>
      <div class="section-body">
        ${sections.map(s => {
          const key = s.key.toLowerCase();
          const cmd = commandBySectionKey && commandBySectionKey[key];
          if (cmd && NARRATIVE_SECTIONS.has(key)) {
            return html`<${CommandRow}
              key=${key}
              command=${cmd.command}
              commandIndex=${cmd.index}
              onEdit=${onEditCommand}
            />`;
          }
          if (cmd && key === 'vitals') {
            return html`<${VitalsRow}
              key=${key}
              command=${cmd.command}
              commandIndex=${cmd.index}
              onEdit=${onEditCommand}
            />`;
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
