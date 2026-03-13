import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useRef, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { CommandRow } from '/plugin-io/api/hyperscribe/scribe/static/command-row.js';
import { AllergyRow } from '/plugin-io/api/hyperscribe/scribe/static/allergy-row.js';
import { MedicationRow } from '/plugin-io/api/hyperscribe/scribe/static/medication-row.js';
import { VitalsRow } from '/plugin-io/api/hyperscribe/scribe/static/vitals-row.js';
import { TaskRow } from '/plugin-io/api/hyperscribe/scribe/static/task-row.js';
import { OrderRow } from '/plugin-io/api/hyperscribe/scribe/static/order-row.js';
import { HistoryReviewRow } from '/plugin-io/api/hyperscribe/scribe/static/history-review-row.js';
import { DiagnoseRow } from '/plugin-io/api/hyperscribe/scribe/static/diagnose-row.js';

const html = htm.bind(h);

const NARRATIVE_SECTIONS = new Set(['chief_complaint', 'history_of_present_illness', 'plan', 'assessment_and_plan']);
const PLAN_SECTIONS = new Set(['plan', 'assessment_and_plan']);
const ORDER_TYPES = new Set(['prescribe', 'lab_order', 'imaging_order']);

const COMMAND_BADGE = {
  rfv: { label: 'RFV', color: 'rfv' },
  hpi: { label: 'HPI', color: 'hpi' },
  ros: { label: 'ROS', color: 'ros' },
  plan: { label: 'Plan', color: 'plan_cmd' },
  diagnose: { label: 'Dx', color: 'diagnose' },
  assess: { label: 'Assess', color: 'assess' },
  vitals: { label: 'Vitals', color: 'vitals' },
  medication_statement: { label: 'Med', color: 'medication' },
  task: { label: 'Task', color: 'task' },
  prescribe: { label: 'Rx', color: 'prescribe' },
  lab_order: { label: 'Lab', color: 'lab_order' },
  imaging_order: { label: 'Imaging', color: 'imaging_order' },
  allergy: { label: 'Allergy', color: 'allergy' },
  physical_exam: { label: 'PE', color: 'physical_exam' },
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

export function parseAPBlocks(text) {
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

export function matchCondition(header, conditions) {
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


const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const DEBOUNCE_MS = 300;

function AddConditionSearch({ onAdd }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const timer = useRef(null);
  const containerRef = useRef(null);

  const doSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setResults([]); setSearched(false); return; }
    setSearching(true);
    try {
      const res = await fetch(`${API_BASE}/search-diagnoses?query=${encodeURIComponent(q)}`);
      const json = await res.json();
      setResults(json.results || []);
    } catch (err) {
      console.error('Add condition search failed:', err);
      setResults([]);
    } finally {
      setSearching(false);
      setSearched(true);
    }
  }, []);

  const handleInput = (e) => {
    const val = e.target.value;
    setQuery(val);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => doSearch(val), DEBOUNCE_MS);
  };

  const handleSelect = (r) => {
    onAdd(r.code, r.display);
    setQuery('');
    setResults([]);
    setSearched(false);
    setOpen(false);
  };

  if (!open) {
    return html`<button type="button" class="ad-hoc-btn" onClick=${() => setOpen(true)}>+ Add Condition</button>`;
  }

  return html`
    <div class="ap-add-condition-area" ref=${containerRef}>
      <input
        type="text"
        class="diagnose-search-input"
        value=${query}
        onInput=${handleInput}
        placeholder="Search ICD-10 diagnosis..."
        autoFocus
      />
      ${searching && html`<span class="diagnose-search-spinner">Searching...</span>`}
      ${results.length > 0 && html`
        <div class="diagnose-search-dropdown">
          ${results.map(r => html`
            <div
              key=${r.code}
              class="diagnose-search-result"
              onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
            >
              <span class="diagnose-result-display">${r.display}</span>
              ${r.formatted_code && html`<span class="diagnose-result-code">${r.formatted_code}</span>`}
            </div>
          `)}
        </div>
      `}
      ${!searching && searched && results.length === 0 && query.length >= 2 && html`
        <div class="diagnose-search-dropdown">
          <div class="diagnose-search-result search-no-results">No diagnoses found</div>
        </div>
      `}
      <button type="button" class="edit-btn" style="margin-top: 4px;" onClick=${() => { setOpen(false); setQuery(''); setResults([]); }}>Cancel</button>
    </div>
  `;
}

export function SoapGroup({ title, groupColor, sections, commandBySectionKey, onEditCommand, onDeleteCommand, adHocCommands, assignees, onAddTask, onAddOrder, onAddMedication, onAddAllergy, readOnly, sectionConditions, patientId, noteId, staffId, staffName, recommendations, onEditRecommendation, onDeleteRecommendation, onAcceptRecommendation, onAddCondition, unmatchedConditions, diagnosisSuggestions }) {
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
          const hasRecsForKey = recommendations && recommendations.length > 0 &&
            ((key === 'current_medications' && recommendations.some(r => r.command_type === 'medication_statement')) ||
             (key === 'allergies' && recommendations.some(r => r.command_type === 'allergy')) ||
             (key === 'prescription' && recommendations.some(r => r.command_type === 'prescribe')));
          if (coveredKeys.has(key) && !hasRecsForKey) return null;
          const cmds = commandBySectionKey && commandBySectionKey[key];

          if (cmds && NARRATIVE_SECTIONS.has(key)) {
            const isPlan = PLAN_SECTIONS.has(key);
            // If the A&P has been split into per-condition diagnose commands, render each as DiagnoseRow.
            const hasDiagnoseCommands = isPlan && cmds.some(e => e.command.command_type === 'diagnose');
            if (hasDiagnoseCommands) {
              const unmatched = unmatchedConditions || [];
              return html`
                <div class="subsection" key=${s.key}>
                  <div class="subsection-title">${s.title}</div>
                  ${cmds.filter(e => e.command.command_type === 'diagnose').map(entry => {
                    const hasCode = !!entry.command.data.icd10_code;
                    const isAccepted = hasCode && entry.command.data.accepted;
                    const isIncomplete = !hasCode;
                    const header = entry.command.data.condition_header || '';
                    const suggestions = (!hasCode && diagnosisSuggestions && diagnosisSuggestions[header]) || null;

                    let btnLabel, btnClass;
                    if (isIncomplete) {
                      btnLabel = 'Incomplete';
                      btnClass = 'recommendation-accept-btn incomplete';
                    } else if (isAccepted) {
                      btnLabel = 'Accepted';
                      btnClass = 'recommendation-accept-btn accepted';
                    } else {
                      btnLabel = 'Accept';
                      btnClass = 'recommendation-accept-btn';
                    }

                    return html`
                      <div class="content-block content-block--diagnose recommendation-block${isAccepted ? ' accepted' : ''}" key=${entry.index}>
                        ${!readOnly && html`
                          <div class="recommendation-actions">
                            <button
                              type="button"
                              class=${btnClass}
                              onClick=${() => !isIncomplete && onEditCommand(entry.index, {
                                ...entry.command.data,
                                accepted: !entry.command.data.accepted,
                              }, 'diagnose')}
                              disabled=${isIncomplete}
                            >${btnLabel}</button>
                          </div>
                        `}
                        <${DiagnoseRow}
                          command=${entry.command}
                          commandIndex=${entry.index}
                          onEdit=${onEditCommand}
                          onDelete=${onDeleteCommand}
                          readOnly=${readOnly}
                          suggestions=${suggestions}
                        />
                      </div>
                    `;
                  })}
                  ${unmatched.length > 0 && html`
                    <div class="ap-suggested-codes">
                      <div class="ap-suggested-label">Other detected conditions</div>
                      <div class="ap-suggested-chips">
                        ${unmatched.map(c => {
                          const codes = (c.coding || []).filter(cd => cd.code);
                          const code = codes[0];
                          if (!code) return null;
                          const formatted = code.code.length > 3 ? code.code.slice(0, 3) + '.' + code.code.slice(3) : code.code;
                          const display = c.display || code.display || formatted;
                          return html`
                            <button
                              key=${code.code}
                              type="button"
                              class="ap-suggested-chip"
                              onClick=${() => onAddCondition && onAddCondition(code.code, display)}
                              title="Add ${display}"
                            >${formatted} ${display}</button>
                          `;
                        })}
                      </div>
                    </div>
                  `}
                  ${onAddCondition && !readOnly && html`
                    <div class="ad-hoc-buttons">
                      <${AddConditionSearch} onAdd=${onAddCondition} />
                    </div>
                  `}
                </div>
              `;
            }
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
                    readOnly=${readOnly}
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
                    readOnly=${readOnly}
                  />
                </div>
              </div>
            `;
          }

          if (cmds && key === 'physical_exam') {
            const entry = cmds[0];
            return html`
              <div class="subsection" key=${s.key}>
                <div class="subsection-title">${s.title}</div>
                <div class="content-block has-badge content-block--physical_exam">
                  <span class="content-block-badge badge-physical_exam">PE</span>
                  <${HistoryReviewRow}
                    command=${entry.command}
                    commandIndex=${entry.index}
                    onEdit=${onEditCommand}
                    readOnly=${readOnly}
                  />
                </div>
              </div>
            `;
          }

          if (key === 'current_medications') {
            const medRecs = (recommendations || [])
              .map((cmd, i) => ({ command: cmd, index: i }))
              .filter(e => e.command.command_type === 'medication_statement');
            if (cmds || medRecs.length > 0) {
              return html`
                <div class="subsection" key=${s.key}>
                  <div class="subsection-title">${s.title}</div>
                  ${(cmds || []).map(entry => html`
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
                  ${medRecs.map(entry => {
                    const isAccepted = entry.command.accepted || entry.command.already_documented;
                    return html`
                    <div class="content-block content-block--medication recommendation-block${isAccepted ? ' accepted' : ''}" key=${'rec-med-' + entry.index}>
                      <div class="recommendation-actions">
                        ${entry.command.already_documented
                          ? html`<span class="recommendation-accept-btn accepted">Already in chart</span>`
                          : !readOnly && html`<button type="button" class="recommendation-accept-btn${entry.command.accepted ? ' accepted' : ''}" onClick=${() => onAcceptRecommendation(entry.index)}>${entry.command.accepted ? 'Accepted' : 'Accept'}</button>`
                        }
                      </div>
                      <${MedicationRow}
                        command=${entry.command}
                        commandIndex=${entry.index}
                        onEdit=${onEditRecommendation}
                        readOnly=${readOnly || entry.command.already_documented}
                      />
                    </div>
                    `;
                  })}
                </div>
              `;
            }
          }

          if (key === 'allergies') {
            const allergyRecs = (recommendations || [])
              .map((cmd, i) => ({ command: cmd, index: i }))
              .filter(e => e.command.command_type === 'allergy');
            if (cmds || allergyRecs.length > 0) {
              return html`
                <div class="subsection" key=${s.key}>
                  <div class="subsection-title">${s.title}</div>
                  ${(cmds || []).map(entry => html`
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
                  ${allergyRecs.map(entry => {
                    const isAccepted = entry.command.accepted || entry.command.already_documented;
                    return html`
                    <div class="content-block content-block--allergy recommendation-block${isAccepted ? ' accepted' : ''}" key=${'rec-allergy-' + entry.index}>
                      <div class="recommendation-actions">
                        ${entry.command.already_documented
                          ? html`<span class="recommendation-accept-btn accepted">Already in chart</span>`
                          : !readOnly && html`<button type="button" class="recommendation-accept-btn${entry.command.accepted ? ' accepted' : ''}" onClick=${() => onAcceptRecommendation(entry.index)}>${entry.command.accepted ? 'Accepted' : 'Accept'}</button>`
                        }
                      </div>
                      <${AllergyRow}
                        command=${entry.command}
                        commandIndex=${entry.index}
                        onEdit=${onEditRecommendation}
                        readOnly=${readOnly || entry.command.already_documented}
                      />
                    </div>
                    `;
                  })}
                </div>
              `;
            }
          }

          // Suppress raw prescription text — Rx recs are rendered by the fallback IIFE below.
          if (key === 'prescription') return null;

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
        ${(() => {
          // Render Rx recommendations in the PLAN group (raw prescription text is suppressed above).
          if (title !== 'PLAN') return null;
          const rxRecs = (recommendations || [])
            .map((cmd, i) => ({ command: cmd, index: i }))
            .filter(e => e.command.command_type === 'prescribe');
          if (rxRecs.length === 0) return null;
          return html`
            <div class="subsection">
              <div class="subsection-title">Prescriptions</div>
              ${rxRecs.map(entry => {
                const hasFdb = !!entry.command.data.fdb_code;
                const isIncomplete = !hasFdb;
                const isAccepted = !isIncomplete && (entry.command.accepted || entry.command.already_documented);

                let btnLabel, btnClass;
                if (entry.command.already_documented) {
                  btnLabel = 'Already in chart';
                  btnClass = 'recommendation-accept-btn accepted';
                } else if (isIncomplete) {
                  btnLabel = 'Incomplete';
                  btnClass = 'recommendation-accept-btn incomplete';
                } else if (entry.command.accepted) {
                  btnLabel = 'Accepted';
                  btnClass = 'recommendation-accept-btn accepted';
                } else {
                  btnLabel = 'Accept';
                  btnClass = 'recommendation-accept-btn';
                }

                return html`
                <div class="content-block content-block--prescribe recommendation-block${isAccepted ? ' accepted' : ''}" key=${'rec-rx-' + entry.index}>
                  <div class="recommendation-actions">
                    ${entry.command.already_documented
                      ? html`<span class=${btnClass}>${btnLabel}</span>`
                      : !readOnly && html`<button type="button" class=${btnClass} onClick=${() => !isIncomplete && onAcceptRecommendation(entry.index)} disabled=${isIncomplete}>${btnLabel}</button>`
                    }
                  </div>
                  <${OrderRow}
                    command=${entry.command}
                    commandIndex=${entry.index}
                    onEdit=${onEditRecommendation}
                    readOnly=${readOnly || entry.command.already_documented}
                    patientId=${patientId}
                    noteId=${noteId}
                    staffId=${staffId}
                    staffName=${staffName}
                  />
                </div>
                `;
              })}
            </div>
          `;
        })()}
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
