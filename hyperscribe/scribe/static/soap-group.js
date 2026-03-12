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
  ros: { label: 'ROS', color: 'ros' },
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

// Map group title → review command section key + label + position
const REVIEW_COMMANDS = {
  SUBJECTIVE: { sectionKey: '_ros', label: 'ROS', color: 'ros', position: 'after' },
  HISTORY: { sectionKey: '_history_review', label: 'History Review', color: 'history_review', position: 'before' },
  OBJECTIVE: { sectionKey: '_chart_review', label: 'Chart Review', color: 'chart_review', position: 'before' },
};

// Note section keys that are fully represented by a review command.
const REVIEW_SOURCE_KEYS = {
  '_ros': 'review_of_systems',
};

function getCoveredKeys(commandBySectionKey) {
  const covered = new Set();
  for (const { sectionKey } of Object.values(REVIEW_COMMANDS)) {
    const cmds = commandBySectionKey && commandBySectionKey[sectionKey];
    if (cmds && cmds.length > 0) {
      for (const sec of cmds[0].command.data.sections || []) {
        covered.add(sec.key);
      }
      // Also cover the original note section that was split into this review command.
      const sourceKey = REVIEW_SOURCE_KEYS[sectionKey];
      if (sourceKey) covered.add(sourceKey);
    }
  }
  return covered;
}

function parseAPBlocks(text) {
  if (!text) return [];
  const lines = text.split('\n');
  const blocks = [];
  let current = null;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed === '') {
      // Blank line — finalize current block if it exists.
      if (current) {
        blocks.push(current);
        current = null;
      }
      continue;
    }
    const isBullet = /^[-•*]/.test(trimmed);
    if (!isBullet && current === null) {
      // Non-bullet line without an active block → new problem header.
      current = { header: trimmed, body: [] };
    } else if (!isBullet && current && current.body.length === 0) {
      // Another non-bullet line before any bullets — append to header.
      current.header += '\n' + trimmed;
    } else if (current) {
      current.body.push(trimmed);
    } else {
      // Bullet without a preceding header — orphan block.
      current = { header: '', body: [trimmed] };
    }
  }
  if (current) blocks.push(current);
  return blocks;
}

function significantWords(text) {
  const stop = new Set(['a','an','the','of','and','or','with','without','in','on','for','to','by','is','are','was','were','not','no','possible','probable','likely','suspected']);
  return text.toLowerCase().replace(/[^a-z0-9\s]/g, '').split(/\s+/).filter(w => w.length > 1 && !stop.has(w));
}

function wordOverlap(a, b) {
  const setA = new Set(significantWords(a));
  const wordsB = significantWords(b);
  if (setA.size === 0 || wordsB.length === 0) return 0;
  const matches = wordsB.filter(w => setA.has(w)).length;
  return matches / Math.min(setA.size, wordsB.length);
}

function matchCondition(header, conditions) {
  if (!conditions || !header) return null;
  const norm = header.toLowerCase();

  // Pass 1: exact substring match (either direction).
  for (const c of conditions) {
    const display = (c.display || '').toLowerCase();
    if (display && (norm.includes(display) || display.includes(norm))) return c;
    for (const code of (c.coding || [])) {
      const cd = (code.display || '').toLowerCase();
      if (cd && (norm.includes(cd) || cd.includes(norm))) return c;
    }
  }

  // Pass 2: significant-word overlap (>= 50%).
  let best = null;
  let bestScore = 0;
  for (const c of conditions) {
    const display = c.display || '';
    const score = Math.max(
      wordOverlap(header, display),
      ...(c.coding || []).map(code => wordOverlap(header, code.display || ''))
    );
    if (score > bestScore) {
      bestScore = score;
      best = c;
    }
  }
  return bestScore >= 0.5 ? best : null;
}

function formatIcdCode(raw) {
  const code = raw.trim().toUpperCase();
  return code.length > 3 ? code.slice(0, 3) + '.' + code.slice(3) : code;
}

function getIcdCode(condition) {
  if (!condition) return null;
  for (const code of (condition.coding || [])) {
    if (code.code) return formatIcdCode(code.code);
  }
  return null;
}

function renderStructuredAssessment(text, conditions) {
  const blocks = parseAPBlocks(text);
  if (blocks.length === 0) return null;

  const matchedSet = new Set();
  const problemEls = blocks.map((block, i) => {
    const matched = matchCondition(block.header, conditions);
    if (matched) matchedSet.add(matched);
    const icd = getIcdCode(matched);
    return html`
      <div class="ap-problem" key=${i}>
        ${block.header && html`
          <div class="ap-problem-title">
            ${block.header}${icd && html`${' '}<span class="ap-icd-code">(${icd})</span>`}
          </div>
        `}
        ${block.body.length > 0 && html`
          <div class="ap-problem-body">${block.body.join('\n')}</div>
        `}
      </div>
    `;
  });

  // Show all ICD-10 codes at the bottom (including matched ones).
  const codesWithIcd = (conditions || []).filter(c => (c.coding || []).some(code => code.code));
  const codeEls = codesWithIcd.length > 0 && html`
    <div class="icd-codes">
      ${codesWithIcd.map(c => {
        const codes = (c.coding || []).filter(code => code.code);
        const name = c.display || (codes[0] && codes[0].display) || '';
        return codes.map(code => html`
          <div class="icd-condition" key=${code.code}>
            ${name && html`<span class="icd-condition-name">${name} — </span>`}<span class="icd-code-badge">${formatIcdCode(code.code)}</span>
          </div>
        `);
      })}
    </div>
  `;

  return html`<div>${problemEls}${codeEls}</div>`;
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
          if (!review || review.position !== 'before') return null;
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
            const isPlan = PLAN_SECTIONS.has(key);
            const hasStructured = isPlan && codes && codes.length > 0;
            return html`
              <div class="subsection" key=${s.key}>
                <div class="subsection-title">${s.title}</div>
                ${hasStructured
                  ? html`
                    <div class="content-block has-badge content-block--${badge.color}">
                      <span class="content-block-badge badge-${entry.command.command_type}">${badge.label}</span>
                      ${renderStructuredAssessment(s.text, codes)}
                    </div>
                  `
                  : html`
                    <div class="content-block has-badge content-block--${badge.color}">
                      <span class="content-block-badge badge-${entry.command.command_type}">${badge.label}</span>
                      <${CommandRow}
                        command=${entry.command}
                        commandIndex=${entry.index}
                        onEdit=${onEditCommand}
                        readOnly=${readOnly}
                      />
                    </div>
                  `
                }
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
        ${(() => {
          const review = REVIEW_COMMANDS[title];
          if (!review || review.position !== 'after') return null;
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
