import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useRef, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { CommandRow } from '/plugin-io/api/hyperscribe/scribe/static/command-row.js';
import { AllergyRow } from '/plugin-io/api/hyperscribe/scribe/static/allergy-row.js';
import { MedicationRow } from '/plugin-io/api/hyperscribe/scribe/static/medication-row.js';
import { VitalsRow } from '/plugin-io/api/hyperscribe/scribe/static/vitals-row.js';
import { TaskRow } from '/plugin-io/api/hyperscribe/scribe/static/task-row.js';
import { OrderRow } from '/plugin-io/api/hyperscribe/scribe/static/order-row.js';
import { HistoryReviewRow } from '/plugin-io/api/hyperscribe/scribe/static/history-review-row.js';
import { HistoryEntryRow } from '/plugin-io/api/hyperscribe/scribe/static/history-entry-row.js';
import { DiagnoseRow } from '/plugin-io/api/hyperscribe/scribe/static/diagnose-row.js';
import { QuestionnaireRow } from '/plugin-io/api/hyperscribe/scribe/static/questionnaire-row.js';

const html = htm.bind(h);

const CHARGE_SEARCH_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const CHARGE_DEBOUNCE_MS = 300;

function ChargeRow({ command, commandIndex, onEdit, onDelete, readOnly, excludeCpts }) {
  const data = command.data || {};
  const hasCpt = !!data.cpt_code;
  const [editing, setEditing] = useState(!hasCpt);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const timer = useRef(null);

  const doSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setResults([]); setSearched(false); return; }
    setSearching(true);
    try {
      const excludeParam = excludeCpts && excludeCpts.size > 0 ? `&exclude=${[...excludeCpts].join(',')}` : '';
      const res = await fetch(`${CHARGE_SEARCH_BASE}/search-charges?query=${encodeURIComponent(q)}${excludeParam}`);
      const json = await res.json();
      setResults(json.results || []);
    } catch (err) {
      console.error('Charge search failed:', err);
      setResults([]);
    } finally {
      setSearching(false);
      setSearched(true);
    }
  }, [excludeCpts]);

  const handleInput = (e) => {
    const val = e.target.value;
    setQuery(val);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => doSearch(val), CHARGE_DEBOUNCE_MS);
  };

  const handleSelect = (r) => {
    onEdit(commandIndex, {
      ...data,
      cpt_code: r.cpt_code,
      description: r.short_name || r.full_name || '',
      notes: data.notes || '',
    });
    setQuery('');
    setResults([]);
    setSearched(false);
    setEditing(false);
  };

  const handleRemove = (e) => {
    e.stopPropagation();
    onDelete(commandIndex);
  };

  if (!hasCpt || editing) {
    return html`
      <div class="charge-row editing">
        <div class="charge-search-area">
          <input
            type="text"
            class="charge-search-input"
            value=${query}
            onInput=${handleInput}
            placeholder="Search CPT code or description..."
            autoFocus
          />
          ${searching && html`<span class="charge-search-spinner">Searching...</span>`}
          ${results.length > 0 && html`
            <div class="charge-search-dropdown">
              ${results.map(r => html`
                <div
                  key=${r.cpt_code}
                  class="charge-search-result"
                  onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
                >
                  <span class="charge-result-code">${r.cpt_code}</span>
                  <span class="charge-result-name">${r.short_name || r.full_name}</span>
                </div>
              `)}
            </div>
          `}
          ${!searching && searched && results.length === 0 && query.length >= 2 && html`
            <div class="charge-search-dropdown">
              <div class="charge-search-result search-no-results">No charges found</div>
            </div>
          `}
        </div>
        <div class="charge-row-actions">
          ${hasCpt && html`<button type="button" class="edit-btn" onClick=${() => setEditing(false)}>Cancel</button>`}
          <button type="button" class="delete-btn" onClick=${handleRemove} title="Remove charge">x</button>
        </div>
      </div>
    `;
  }

  return html`
    <div class="charge-row${readOnly ? ' read-only' : ''}" onClick=${() => !readOnly && setEditing(true)}>
      <div class="charge-row-display">
        <span class="charge-cpt-code">${data.cpt_code}</span>
        <span class="charge-description">${data.description || ''}</span>
      </div>
      ${!readOnly && html`
        <div class="charge-row-actions">
          <button type="button" class="delete-btn" onClick=${handleRemove} title="Remove charge">x</button>
        </div>
      `}
    </div>
  `;
}

// Override display names for subsection titles (backend note data may use different labels).
const SECTION_DISPLAY_NAMES = {
  'current_medications': 'Medication List Updates',
  'allergies': 'Allergy List Updates',
  'past_medical_history': 'Past Medical History Discussed During Encounter',
};

const REMOVAL_TYPES = new Set(['stop_medication', 'remove_allergy', 'resolve_condition']);

function RemovalRow({ command, commandIndex, onEdit, onDelete, readOnly, patientId }) {
  const data = command.data || {};
  const type = command.command_type;
  const hasItem = !!(data.medication_id || data.allergy_id || data.condition_id);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  const config = {
    stop_medication: { endpoint: 'patient-medications', listKey: 'medications', idField: 'medication_id', nameField: 'medication_name', labelPlural: 'medications', placeholder: 'Select medication to stop...' },
    remove_allergy: { endpoint: 'patient-allergies', listKey: 'allergies', idField: 'allergy_id', nameField: 'allergy_name', labelPlural: 'allergies', placeholder: 'Select allergy to remove...' },
    resolve_condition: { endpoint: 'patient-conditions', listKey: 'conditions', idField: 'condition_id', nameField: 'condition_name', labelPlural: 'conditions', placeholder: 'Select condition to resolve...' },
  }[type];

  useEffect(() => {
    if (hasItem || !patientId || !config) return;
    let cancelled = false;
    setLoading(true);
    fetch(`${CHARGE_SEARCH_BASE}/${config.endpoint}?patient_id=${encodeURIComponent(patientId)}`)
      .then(r => r.json())
      .then(json => {
        if (cancelled) return;
        const list = json[config.listKey] || json.conditions || [];
        setItems(list.map(item => ({
          id: item.id || item.condition_id,
          name: item.name || item.display || '',
        })));
      })
      .catch(() => setItems([]))
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [hasItem, patientId, type]);

  const handleSelectChange = (e) => {
    const selectedId = e.target.value;
    if (!selectedId) return;
    const item = items.find(i => i.id === selectedId);
    if (!item) return;
    onEdit(commandIndex, {
      ...data,
      [config.idField]: item.id,
      [config.nameField]: item.name,
    });
  };

  const handleRemove = (e) => {
    e.stopPropagation();
    onDelete(commandIndex);
  };

  if (!hasItem) {
    return html`
      <div class="removal-row">
        ${loading
          ? html`<span class="removal-loading">Loading...</span>`
          : items.length > 0
            ? html`<select class="removal-select" onChange=${handleSelectChange} autoFocus>
                <option value="">${config.placeholder}</option>
                ${items.map(item => html`<option key=${item.id} value=${item.id}>${item.name}</option>`)}
              </select>`
            : html`<span class="removal-empty">No active ${config.labelPlural}</span>`
        }
        <button type="button" class="delete-btn" onClick=${handleRemove} title="Cancel">x</button>
      </div>
    `;
  }

  const itemName = data[config.nameField] || '';
  return html`
    <div class="removal-row${readOnly ? ' read-only' : ''}">
      <span class="removal-item-name">${itemName}</span>
      ${!readOnly && html`
        <button type="button" class="delete-btn" onClick=${handleRemove} title="Remove">x</button>
      `}
    </div>
  `;
}

const NARRATIVE_SECTIONS = new Set(['chief_complaint', 'history_of_present_illness', 'plan', 'assessment_and_plan']);
const PLAN_SECTIONS = new Set(['plan', 'assessment_and_plan']);
const ORDER_TYPES = new Set(['prescribe', 'refill', 'adjust_prescription', 'lab_order', 'imaging_order', 'refer']);
const HISTORY_TYPES = new Set(['familyHistory', 'medicalHistory', 'surgicalHistory']);

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
  const code = raw.replace(/\./g, '').trim().toUpperCase();
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

export function SoapGroup({ title, groupColor, sections, commandBySectionKey, onEditCommand, onDeleteCommand, adHocCommands, assignees, onAddTask, onAddOrder, onAddPlan, onAddMedication, onAddAllergy, onAddStopMedication, onAddRemoveAllergy, onAddResolveCondition, onAddHistory, onAddQuestionnaire, onAddCharge, onAddTemplateCharge, onRemoveChargeByCpt, templateCharges, readOnly, sectionConditions, patientId, noteId, staffId, staffName, recommendations, onEditRecommendation, onDeleteRecommendation, onAcceptRecommendation, onAddCondition, unmatchedConditions, diagnosisSuggestions }) {
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
            <div class="content-block">
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
                  <div class="subsection-title">${SECTION_DISPLAY_NAMES[key] || s.title}</div>
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
                      btnLabel = 'Matched';
                      btnClass = 'recommendation-accept-btn accepted';
                    } else {
                      btnLabel = 'Accept';
                      btnClass = 'recommendation-accept-btn';
                    }

                    return html`
                      <div class="content-block recommendation-block${isAccepted ? ' accepted' : ''}${isIncomplete ? ' incomplete-code' : ''}" key=${entry.index}>
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
                        <div class="recommendation-content">
                          <${DiagnoseRow}
                            command=${entry.command}
                            commandIndex=${entry.index}
                            onEdit=${onEditCommand}
                            onDelete=${onDeleteCommand}
                            readOnly=${readOnly}
                            suggestions=${suggestions}
                          />
                        </div>
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
                          const stripped = code.code.replace(/\./g, '');
                          const formatted = stripped.length > 3 ? stripped.slice(0, 3) + '.' + stripped.slice(3) : stripped;
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
                  ${(onAddCondition || onAddResolveCondition) && !readOnly && html`
                    <div class="ad-hoc-buttons">
                      ${onAddCondition && html`<${AddConditionSearch} onAdd=${onAddCondition} />`}
                      ${onAddResolveCondition && html`<button type="button" class="ad-hoc-btn removal-btn" onClick=${onAddResolveCondition}>- Resolve Condition</button>`}
                    </div>
                  `}
                </div>
              `;
            }
            const entry = cmds[0];
            return html`
              <div class="subsection" key=${s.key}>
                <div class="subsection-title">${SECTION_DISPLAY_NAMES[key] || s.title}</div>
                <div class="content-block">
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

          if (key === 'vitals' && cmds) {
            const entry = cmds[0];
            return html`
              <div class="subsection" key=${s.key}>
                <div class="subsection-title">${SECTION_DISPLAY_NAMES[key] || s.title}</div>
                <div class="content-block">
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
                <div class="subsection-title">${SECTION_DISPLAY_NAMES[key] || s.title}</div>
                <div class="content-block">
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
            if (cmds || medRecs.length > 0 || onAddMedication) {
              return html`
                <div class="subsection" key=${s.key}>
                  <div class="subsection-title">${SECTION_DISPLAY_NAMES[key] || s.title}</div>
                  ${(cmds || []).map(entry => html`
                    <div class="content-block" key=${entry.index}>
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
                    <div class="content-block recommendation-block${isAccepted ? ' accepted' : ''}" key=${'rec-med-' + entry.index}>
                      <div class="recommendation-actions">
                        ${entry.command.already_documented
                          ? html`<span class="recommendation-accept-btn accepted">Already in chart</span>`
                          : !readOnly && html`<button type="button" class="recommendation-accept-btn${entry.command.accepted ? ' accepted' : ''}" onClick=${() => onAcceptRecommendation(entry.index)}>${entry.command.accepted ? 'Accepted' : 'Accept'}</button>`
                        }
                      </div>
                      <div class="recommendation-content">
                        <${MedicationRow}
                          command=${entry.command}
                          commandIndex=${entry.index}
                          onEdit=${onEditRecommendation}
                          readOnly=${readOnly || entry.command.already_documented}
                        />
                      </div>
                    </div>
                    `;
                  })}
                  ${(onAddMedication || onAddStopMedication) && !readOnly && html`
                    <div class="ad-hoc-buttons">
                      ${onAddMedication && html`<button type="button" class="ad-hoc-btn" onClick=${onAddMedication}>+ Medication</button>`}
                      ${onAddStopMedication && html`<button type="button" class="ad-hoc-btn removal-btn" onClick=${onAddStopMedication}>- Stop Medication</button>`}
                    </div>
                  `}
                </div>
              `;
            }
          }

          if (key === 'allergies') {
            const allergyRecs = (recommendations || [])
              .map((cmd, i) => ({ command: cmd, index: i }))
              .filter(e => e.command.command_type === 'allergy');
            if (cmds || allergyRecs.length > 0 || onAddAllergy) {
              return html`
                <div class="subsection" key=${s.key}>
                  <div class="subsection-title">${SECTION_DISPLAY_NAMES[key] || s.title}</div>
                  ${(cmds || []).map(entry => html`
                    <div class="content-block" key=${entry.index}>
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
                    <div class="content-block recommendation-block${isAccepted ? ' accepted' : ''}" key=${'rec-allergy-' + entry.index}>
                      <div class="recommendation-actions">
                        ${entry.command.already_documented
                          ? html`<span class="recommendation-accept-btn accepted">Already in chart</span>`
                          : !readOnly && html`<button type="button" class="recommendation-accept-btn${entry.command.accepted ? ' accepted' : ''}" onClick=${() => onAcceptRecommendation(entry.index)}>${entry.command.accepted ? 'Accepted' : 'Accept'}</button>`
                        }
                      </div>
                      <div class="recommendation-content">
                        <${AllergyRow}
                          command=${entry.command}
                          commandIndex=${entry.index}
                          onEdit=${onEditRecommendation}
                          readOnly=${readOnly || entry.command.already_documented}
                        />
                      </div>
                    </div>
                    `;
                  })}
                  ${(onAddAllergy || onAddRemoveAllergy) && !readOnly && html`
                    <div class="ad-hoc-buttons">
                      ${onAddAllergy && html`<button type="button" class="ad-hoc-btn" onClick=${onAddAllergy}>+ Allergy</button>`}
                      ${onAddRemoveAllergy && html`<button type="button" class="ad-hoc-btn removal-btn" onClick=${onAddRemoveAllergy}>- Remove Allergy</button>`}
                    </div>
                  `}
                </div>
              `;
            }
          }

          // Suppress raw prescription text — Rx recs are rendered by the fallback IIFE below.
          if (key === 'prescription') return null;

          return html`
            <div class="subsection" key=${s.key}>
              <div class="subsection-title">${SECTION_DISPLAY_NAMES[key] || s.title}</div>
              ${s.text && html`<p class="section-text">${s.text}</p>`}
              ${PLAN_SECTIONS.has(key) && (onAddCondition || onAddResolveCondition) && !readOnly && html`
                <div class="ad-hoc-buttons">
                  ${onAddCondition && html`<${AddConditionSearch} onAdd=${onAddCondition} />`}
                  ${onAddResolveCondition && html`<button type="button" class="ad-hoc-btn removal-btn" onClick=${onAddResolveCondition}>- Resolve Condition</button>`}
                </div>
              `}
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
            <div class="subsection-title">Review of Systems</div>
            <div class="content-block">
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
          if (type === 'medication_statement') {
            return html`
              <div class="content-block" key=${entry.index}>
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
              <div class="content-block" key=${entry.index}>
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
              <div class="content-block" key=${entry.index}>
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
            const prescribeIncomplete = type === 'prescribe' && entry.command.display && (
              !entry.command.data.fdb_code || !entry.command.data.sig ||
              entry.command.data.quantity_to_dispense == null || !entry.command.data.type_to_dispense ||
              entry.command.data.refills == null
            );
            return html`
              <div class="content-block${prescribeIncomplete ? ' incomplete-order' : ''}" key=${entry.index}>
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
          if (type === 'history_review') {
            return html`
              <div class="content-block" key=${entry.index}>
                <${HistoryReviewRow}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onDelete=${onDeleteCommand}
                />
              </div>
            `;
          }
          if (HISTORY_TYPES.has(type)) {
            return html`
              <div class="content-block" key=${entry.index}>
                <${HistoryEntryRow}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onDelete=${onDeleteCommand}
                  readOnly=${readOnly}
                />
              </div>
            `;
          }
          if (type === 'questionnaire') {
            return html`
              <div class="content-block" key=${entry.index}>
                <${QuestionnaireRow}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onDelete=${onDeleteCommand}
                  readOnly=${readOnly}
                />
              </div>
            `;
          }
          if (type === 'plan') {
            return html`
              <div class="content-block" key=${entry.index}>
                <${CommandRow}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onDelete=${onDeleteCommand}
                  readOnly=${readOnly}
                />
              </div>
            `;
          }
          if (type === 'perform') return null;
          if (REMOVAL_TYPES.has(type)) {
            return html`
              <div class="content-block" key=${entry.index}>
                <${RemovalRow}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onDelete=${onDeleteCommand}
                  readOnly=${readOnly}
                  patientId=${patientId}
                />
              </div>
            `;
          }
          return null;
        })}
        ${(() => {
          // Build unified checklist: template charges + manually added charges.
          // A charge is "selected" if its command exists AND has selected=true.
          const chargeCommands = (adHocCommands || [])
            .filter(e => e.command.command_type === 'perform' && e.command.data.cpt_code);
          const selectedCpts = new Set(
            chargeCommands.filter(e => e.command.selected !== false).map(e => e.command.data.cpt_code)
          );

          // Template charges (checked if selected command exists).
          const templateItems = (templateCharges || []).map(c => ({
            cpt_code: c.cpt_code,
            description: c.description,
            isAdded: selectedCpts.has(c.cpt_code),
          }));

          // Manually added charges not in the template list (show even if deselected).
          const templateCpts = new Set((templateCharges || []).map(c => c.cpt_code));
          const adHocItems = chargeCommands
            .filter(e => !templateCpts.has(e.command.data.cpt_code))
            .map(e => ({
              cpt_code: e.command.data.cpt_code,
              description: e.command.data.description || '',
              isAdded: e.command.selected !== false,
            }));

          const allItems = [...templateItems, ...adHocItems];
          if (allItems.length === 0) return null;

          return html`
            <div class="charge-checklist">
              ${allItems.map(c => html`
                <label
                  key=${c.cpt_code}
                  class="charge-check-item${c.isAdded ? ' checked' : ''}${readOnly ? ' read-only' : ''}"
                >
                  <input
                    type="checkbox"
                    checked=${c.isAdded}
                    disabled=${readOnly}
                    onChange=${() => {
                      if (c.isAdded) {
                        onRemoveChargeByCpt && onRemoveChargeByCpt(c.cpt_code);
                      } else {
                        onAddTemplateCharge && onAddTemplateCharge(c.cpt_code, c.description);
                      }
                    }}
                  />
                  <span class="charge-check-code">${c.cpt_code}</span>
                  <span class="charge-check-desc">${c.description}</span>
                </label>
              `)}
            </div>
          `;
        })()}
        ${(() => {
          // Render search inputs for charges being added (no cpt_code yet).
          const pending = (adHocCommands || []).filter(
            e => e.command.command_type === 'perform' && !e.command.data.cpt_code
          );
          if (pending.length === 0) return null;
          const allChecklistCpts = new Set([
            ...(templateCharges || []).map(c => c.cpt_code),
            ...(adHocCommands || []).filter(e => e.command.command_type === 'perform' && e.command.data.cpt_code).map(e => e.command.data.cpt_code),
          ]);
          return pending.map(entry => html`
            <div class="content-block" key=${entry.index}>
              <${ChargeRow}
                command=${entry.command}
                commandIndex=${entry.index}
                onEdit=${onEditCommand}
                onDelete=${onDeleteCommand}
                readOnly=${readOnly}
                excludeCpts=${allChecklistCpts}
              />
            </div>
          `);
        })()}
        ${onAddCharge && !readOnly && html`
          <div class="ad-hoc-buttons">
            <button type="button" class="ad-hoc-btn" onClick=${onAddCharge}>+ Charge</button>
          </div>
        `}
        ${onAddQuestionnaire && !readOnly && html`
          <div class="ad-hoc-buttons">
            <button type="button" class="ad-hoc-btn" onClick=${onAddQuestionnaire}>+ Questionnaire</button>
          </div>
        `}
        ${onAddHistory && !readOnly && html`
          <div class="ad-hoc-buttons">
            <button type="button" class="ad-hoc-btn" onClick=${() => onAddHistory('familyHistory')}>+ Family Hx</button>
            <button type="button" class="ad-hoc-btn" onClick=${() => onAddHistory('medicalHistory')}>+ Medical Hx</button>
            <button type="button" class="ad-hoc-btn" onClick=${() => onAddHistory('surgicalHistory')}>+ Surgical Hx</button>
          </div>
        `}
        ${(() => {
          // Render Rx recommendations in the PLAN group (raw prescription text is suppressed above).
          if (title !== 'ASSESSMENT & PLAN') return null;
          const rxRecs = (recommendations || [])
            .map((cmd, i) => ({ command: cmd, index: i }))
            .filter(e => e.command.command_type === 'prescribe');
          if (rxRecs.length === 0) return null;
          return html`
            <div class="subsection">
              <div class="subsection-title">Prescriptions</div>
              ${rxRecs.map(entry => {
                const d = entry.command.data;
                const isIncomplete = !d.fdb_code || !d.sig || d.quantity_to_dispense == null || !d.type_to_dispense || d.refills == null;
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
                <div class="content-block recommendation-block${isAccepted ? ' accepted' : ''}" key=${'rec-rx-' + entry.index}>
                  <div class="recommendation-actions">
                    ${entry.command.already_documented
                      ? html`<span class=${btnClass}>${btnLabel}</span>`
                      : !readOnly && html`<button type="button" class=${btnClass} onClick=${() => !isIncomplete && onAcceptRecommendation(entry.index)} disabled=${isIncomplete}>${btnLabel}</button>`
                    }
                  </div>
                  <div class="recommendation-content">
                    <${OrderRow}
                      command=${entry.command}
                      commandIndex=${entry.index}
                      onEdit=${onEditRecommendation}
                      readOnly=${readOnly || entry.command.already_documented}
                      patientId=${patientId}
                      noteId=${noteId}
                      staffId=${staffId}
                      staffName=${staffName}
                      isRecommendation=${true}
                    />
                  </div>
                </div>
                `;
              })}
            </div>
          `;
        })()}
        ${(() => {
          // Render Refer recommendations in the PLAN group.
          if (title !== 'ASSESSMENT & PLAN') return null;
          const referRecs = (recommendations || [])
            .map((cmd, i) => ({ command: cmd, index: i }))
            .filter(e => e.command.command_type === 'refer');
          if (referRecs.length === 0) return null;
          return html`
            <div class="subsection">
              <div class="subsection-title">Referrals</div>
              ${referRecs.map(entry => {
                const hasProvider = !!entry.command.data.service_provider;
                const isIncomplete = !hasProvider;
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
                <div class="content-block recommendation-block${isAccepted ? ' accepted' : ''}${isIncomplete ? ' incomplete-code' : ''}" key=${'rec-refer-' + entry.index}>
                  <div class="recommendation-actions">
                    ${entry.command.already_documented
                      ? html`<span class=${btnClass}>${btnLabel}</span>`
                      : !readOnly && html`<button type="button" class=${btnClass} onClick=${() => !isIncomplete && onAcceptRecommendation(entry.index)} disabled=${isIncomplete}>${btnLabel}</button>`
                    }
                  </div>
                  <div class="recommendation-content">
                    <${OrderRow}
                      command=${entry.command}
                      commandIndex=${entry.index}
                      onEdit=${onEditRecommendation}
                      readOnly=${readOnly || entry.command.already_documented}
                      patientId=${patientId}
                      noteId=${noteId}
                      staffId=${staffId}
                      staffName=${staffName}
                      isRecommendation=${true}
                    />
                  </div>
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
            ${onAddPlan && html`<button type="button" class="ad-hoc-btn" onClick=${onAddPlan}>+ Plan</button>`}
            ${onAddResolveCondition && html`<button type="button" class="ad-hoc-btn removal-btn" onClick=${onAddResolveCondition}>- Resolve Condition</button>`}
          </div>
        `}
      </div>
    </div>
  `;
}
