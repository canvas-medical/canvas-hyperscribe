import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';
import { MedicationRow } from '/plugin-io/api/hyperscribe/scribe/static/medication-row.js';
import { AllergyRow } from '/plugin-io/api/hyperscribe/scribe/static/allergy-row.js';

const html = htm.bind(h);

export function RecommendedGroup({ recommendations, onEditCommand, onDeleteCommand }) {
  if (!recommendations || recommendations.length === 0) return null;

  return html`
    <div class="summary-section">
      <div class="section-header">
        <span class="section-title">RECOMMENDED</span>
      </div>
      <div class="section-body">
        ${recommendations.map((cmd, index) => {
          if (cmd.command_type === 'medication_statement') {
            return html`
              <div class="content-block content-block--medication" key=${index}>
                <${MedicationRow}
                  command=${cmd}
                  commandIndex=${index}
                  onEdit=${onEditCommand}
                  onDelete=${onDeleteCommand}
                />
              </div>
            `;
          }
          if (cmd.command_type === 'allergy') {
            return html`
              <div class="content-block content-block--allergy" key=${index}>
                <${AllergyRow}
                  command=${cmd}
                  commandIndex=${index}
                  onEdit=${onEditCommand}
                  onDelete=${onDeleteCommand}
                />
              </div>
            `;
          }
          return null;
        })}
      </div>
    </div>
  `;
}
