import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';
import { CommandRow } from '/plugin-io/api/hyperscribe/scribe/static/command-row.js';
import { AllergyRow } from '/plugin-io/api/hyperscribe/scribe/static/allergy-row.js';
import { MedicationRow } from '/plugin-io/api/hyperscribe/scribe/static/medication-row.js';
import { VitalsRow } from '/plugin-io/api/hyperscribe/scribe/static/vitals-row.js';
import { TaskRow } from '/plugin-io/api/hyperscribe/scribe/static/task-row.js';
import { OrderRow } from '/plugin-io/api/hyperscribe/scribe/static/order-row.js';
import { HistoryReviewRow } from '/plugin-io/api/hyperscribe/scribe/static/history-review-row.js';

const html = htm.bind(h);

const NARRATIVE_SECTIONS = new Set(['chief_complaint', 'history_of_present_illness', 'plan', 'assessment_and_plan']);
const PLAN_SECTIONS = new Set(['plan', 'assessment_and_plan']);
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
  allergy: { label: 'Allergy', color: 'allergy' },
  history_review: { label: 'History Review', color: 'history_review' },
  chart_review: { label: 'Chart Review', color: 'chart_review' },
};

// Map group title → review command section key + label
const REVIEW_COMMANDS = {
  HISTORY: { sectionKey: '_history_review', label: 'History Review', color: 'history_review' },
  OBJECTIVE: { sectionKey: '_chart_review', label: 'Chart Review', color: 'chart_review' },
};

function getCoveredKeys(commandBySectionKey) {
  const covered = new Set();
  for (const { sectionKey } of Object.values(REVIEW_COMMANDS)) {
    const cmds = commandBySectionKey && commandBySectionKey[sectionKey];
    if (cmds && cmds.length > 0) {
      for (const sec of cmds[0].command.data.sections || []) {
        covered.add(sec.key);
      }
    }
  }
  return covered;
}

function renderConditionCodes(conditions) {
  if (!conditions || conditions.length === 0) return null;
  return html`
    <div class="icd-codes">
      ${conditions.map(c => {
        const codes = (c.coding || []).filter(code => code.code);
        if (codes.length === 0) return null;
        const name = c.display || codes[0].display || '';
        return codes.map(code => html`
          <div class="icd-condition" key=${code.code}>
            ${name && html`<span class="icd-condition-name">${name} — </span>`}<span class="icd-code-badge">${code.code}</span>
          </div>
        `);
      })}
    </div>
  `;
}

export function SoapGroup({ title, groupColor, sections, commandBySectionKey, onEditCommand, onDeleteCommand, adHocCommands, assignees, onAddTask, onAddOrder, onAddMedication, onAddAllergy, readOnly, sectionConditions, patientId, noteId, staffId, staffName }) {
  const coveredKeys = getCoveredKeys(commandBySectionKey);

  return html`
    <div class="summary-section">
      <div class="section-header">
        <span class="section-title">${title}</span>
      </div>
      <div class="section-body">
        ${(() => {
          const review = REVIEW_COMMANDS[title];
          if (!review) return null;
          const cmds = commandBySectionKey && commandBySectionKey[review.sectionKey];
          if (!cmds || cmds.length === 0) return null;
          const entry = cmds[0];
          return html`
            <div class="content-block has-badge content-block--${review.color}">
              <span class="content-block-badge badge-${review.color}">${review.label}</span>
              <${HistoryReviewRow}
                command=${entry.command}
                commandIndex=${entry.index}
                onEdit=${onEditCommand}
                readOnly=${readOnly}
              />
            </div>
          `;
        })()}
        ${sections.map(s => {
          const key = s.key.toLowerCase();
          if (coveredKeys.has(key)) return null;
          const cmds = commandBySectionKey && commandBySectionKey[key];
          const codes = sectionConditions && sectionConditions[key];

          if (cmds && NARRATIVE_SECTIONS.has(key)) {
            const entry = cmds[0];
            const badge = COMMAND_BADGE[entry.command.command_type] || { label: entry.command.command_type, color: 'rfv' };
            const showCodes = PLAN_SECTIONS.has(key);
            return html`
              <div class="subsection" key=${s.key}>
                <div class="subsection-title">${s.title}</div>
                <div class="content-block has-badge content-block--${badge.color}">
                  <span class="content-block-badge badge-${entry.command.command_type}">${badge.label}</span>
                  <${CommandRow}
                    command=${entry.command}
                    commandIndex=${entry.index}
                    onEdit=${onEditCommand}
                    readOnly=${readOnly}
                  />
                  ${showCodes && renderConditionCodes(codes)}
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
                    readOnly=${readOnly}
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
                      onDelete=${onDeleteCommand}
                      readOnly=${readOnly}
                    />
                  </div>
                `)}
              </div>
            `;
          }

          if (cmds && key === 'allergies') {
            return html`
              <div class="subsection" key=${s.key}>
                <div class="subsection-title">${s.title}</div>
                ${cmds.map(entry => html`
                  <div class="content-block content-block--allergy" key=${entry.index}>
                    <${AllergyRow}
                      command=${entry.command}
                      commandIndex=${entry.index}
                      onEdit=${onEditCommand}
                      onDelete=${onDeleteCommand}
                      readOnly=${readOnly}
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
          if (type === 'medication_statement') {
            return html`
              <div class="content-block content-block--medication" key=${entry.index}>
                <${MedicationRow}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onDelete=${onDeleteCommand}
                />
              </div>
            `;
          }
          if (type === 'allergy') {
            return html`
              <div class="content-block content-block--allergy" key=${entry.index}>
                <${AllergyRow}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onDelete=${onDeleteCommand}
                />
              </div>
            `;
          }
          if (type === 'task') {
            return html`
              <div class="content-block content-block--${badge.color}" key=${entry.index}>
                <${TaskRow}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onDelete=${onDeleteCommand}
                  assignees=${assignees}
                  readOnly=${readOnly}
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
                  onDelete=${onDeleteCommand}
                  readOnly=${readOnly}
                  patientId=${patientId}
                  noteId=${noteId}
                  staffId=${staffId}
                  staffName=${staffName}
                />
              </div>
            `;
          }
          return null;
        })}
        ${onAddMedication && html`
          <div class="ad-hoc-buttons">
            <button type="button" class="ad-hoc-btn" onClick=${onAddMedication}>+ Medication</button>
            <button type="button" class="ad-hoc-btn" onClick=${onAddAllergy}>+ Allergy</button>
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
