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

function ChargeRow({ command, commandIndex, onEdit, onDelete, readOnly, excludeCpts, onEditingChange }) {
  const data = command.data || {};
  const hasCpt = !!data.cpt_code;
  const [editing, setEditing] = useState(!hasCpt);
  useEffect(() => {
    onEditingChange?.(commandIndex, editing);
    return () => onEditingChange?.(commandIndex, false);
  }, [editing, commandIndex]);
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
      <div class="charge-row">
        <div class="history-form-field" style="position: relative;">
          <input
            type="text"
            class="history-form-input"
            value=${query}
            onInput=${handleInput}
            placeholder="Search CPT code or description..."
            autoFocus
          />
          ${searching && html`<span class="diag-search-spinner">Searching...</span>`}
          ${results.length > 0 && html`
            <div class="history-search-dropdown">
              ${results.map(r => html`
                <div
                  key=${r.cpt_code}
                  class="history-search-result"
                  onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
                >
                  <strong>${r.cpt_code}</strong>${' '}${r.short_name || r.full_name}
                </div>
              `)}
            </div>
          `}
          ${!searching && searched && results.length === 0 && query.length >= 2 && html`
            <div class="history-search-dropdown">
              <div class="history-search-result search-no-results">No charges found</div>
            </div>
          `}
        </div>
      </div>
    `;
  }

  return html`
    <div class="charge-view" onClick=${() => !readOnly && setEditing(true)}>
      <span class="charge-view-code">${data.cpt_code}</span>
      <span class="charge-view-desc">${data.description || ''}</span>
    </div>
  `;
}



const REMOVAL_TYPES = new Set(['stop_medication', 'remove_allergy', 'resolve_condition']);

function RemovalRow({ command, commandIndex, onEdit, onDelete, readOnly, patientId, alertFacilityEnabled }) {
  const data = command.data || {};
  const type = command.command_type;
  const hasItem = !!(data.medication_id || data.allergy_id || data.condition_id);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  const config = {
    stop_medication: { endpoint: 'patient-medications', listKey: 'medications', idField: 'medication_id', nameField: 'medication_name', labelPlural: 'medications', placeholder: 'Select medication to stop...', actionLabel: 'STOP' },
    remove_allergy: { endpoint: 'patient-allergies', listKey: 'allergies', idField: 'allergy_id', nameField: 'allergy_name', labelPlural: 'allergies', placeholder: 'Select allergy to remove...', actionLabel: 'REMOVE' },
    resolve_condition: { endpoint: 'patient-conditions', listKey: 'conditions', idField: 'condition_id', nameField: 'condition_name', labelPlural: 'conditions', placeholder: 'Select condition to resolve...', actionLabel: 'RESOLVE' },
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
      </div>
    `;
  }

  const itemName = data[config.nameField] || '';
  return html`
    <div class="removal-row${readOnly ? ' read-only' : ''}">
      <span class="removal-action-label">${config.actionLabel}</span>
      <span class="removal-item-name">${itemName}</span>
      ${type === 'stop_medication' && readOnly && (data.rationale || data.alert_facility) && html`
        <div style="font-size: 13px; color: #6b7280; margin-top: 2px;">
          ${data.rationale || ''}
          ${alertFacilityEnabled && data.alert_facility && html`<span class="badge badge-alert" style="margin-left: 6px;">Alert Facility</span>`}
        </div>
      `}
    </div>
    ${type === 'stop_medication' && hasItem && !readOnly && html`
      <div class="history-form-field" style="margin-top: 8px;">
        <label class="history-form-label">Rationale</label>
        <input
          type="text"
          class="history-form-input"
          value=${data.rationale || ''}
          onInput=${(e) => onEdit(commandIndex, { ...data, rationale: e.target.value })}
          placeholder="Reason for stopping..."
        />
      </div>
      ${alertFacilityEnabled && html`
      <div class="history-form-field" style="margin-top: 8px;">
        <label class="alert-facility-toggle" onClick=${() => onEdit(commandIndex, { ...data, alert_facility: !data.alert_facility })}>
          <div class="toggle-switch${data.alert_facility ? ' on' : ''}">
            <div class="toggle-knob" />
          </div>
          Alert Facility
        </label>
      </div>
      `}
    `}
  `;
}

const NARRATIVE_SECTIONS = new Set(['chief_complaint', 'history_of_present_illness', 'plan', 'assessment_and_plan', 'appointments', 'lab_results', 'imaging_results']);
const PLAN_SECTIONS = new Set(['plan', 'assessment_and_plan']);
const ORDER_TYPES = new Set(['prescribe', 'refill', 'adjust_prescription', 'lab_order', 'imaging_order', 'refer']);
const HISTORY_TYPES = new Set(['familyHistory', 'medicalHistory', 'surgicalHistory']);

// Map section keys to the history command type that belongs under them.
const SECTION_TO_HISTORY_TYPE = {
  'past_medical_history': 'medicalHistory',
  'past_surgical_history': 'surgicalHistory',
  'family_history': 'familyHistory',
};
const HISTORY_ADD_LABELS = {
  'medicalHistory': '+ Medical Hx',
  'surgicalHistory': '+ Surgical Hx',
  'familyHistory': '+ Family Hx',
};

// Returns true if a command/recommendation would have been inserted by handleInsert.
function wasInserted(cmd, isRec = false) {
  // Items added via "Add Now" were already inserted — show them in approved view.
  if (cmd._added_now) return true;
  if (isRec) return !!(cmd.accepted && !cmd.already_documented && cmd.display);
  if (cmd.already_documented || !cmd.display) return false;
  if (cmd.command_type === 'imaging_order' && (!cmd.data.image_code || !cmd.data.service_provider || !cmd.data.ordering_provider_id || !cmd.data.diagnosis_codes || cmd.data.diagnosis_codes.length === 0)) return false;
  if (cmd.command_type === 'prescribe' && (!cmd.data.fdb_code || !cmd.data.sig || cmd.data.quantity_to_dispense == null || !cmd.data.type_to_dispense || cmd.data.refills == null)) return false;
  if ((cmd.command_type === 'refill' || cmd.command_type === 'adjust_prescription') && !cmd.data.fdb_code) return false;
  if (cmd.command_type === 'lab_order' && (!cmd.data.lab_partner || !cmd.data.tests_order_codes || cmd.data.tests_order_codes.length === 0)) return false;
  if (cmd.command_type === 'refer' && (!cmd.data.service_provider || !cmd.data.clinical_question || !cmd.data.notes_to_specialist || !cmd.data.diagnosis_codes || cmd.data.diagnosis_codes.length === 0)) return false;
  if (cmd.command_type === 'perform' && (!cmd.data.cpt_code || cmd.selected === false)) return false;
  if (cmd.command_type === 'diagnose' && (!cmd.data.icd10_code || !cmd.data.accepted)) return false;
  return true;
}

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

const ICON_X = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></svg>`;
const ICON_CHECK = html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 10 18 20 6"/></svg>`;
const ICON_LOCK = html`<svg class="command-row-icon-lock" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`;

function AssessNarrative({ command, commandIndex, onEdit, readOnly, onEditingChange }) {
  const data = command.data || {};
  const [editing, setEditing] = useState(false);
  useEffect(() => {
    onEditingChange?.(commandIndex, editing);
    return () => onEditingChange?.(commandIndex, false);
  }, [editing, commandIndex]);
  const [narrative, setNarrative] = useState(data.narrative || '');
  const [background, setBackground] = useState(data.background || '');
  const backgroundRef = useRef(null);
  const narrativeRef = useRef(null);

  // Sync local state when ``data`` changes from outside (e.g. carry-forward
  // fetch returning AFTER first render of this row). useState initializes
  // only once at mount, so without this effect a provider opening the edit
  // view before the fetch lands sees an empty textarea. We only sync when
  // not editing, so an in-progress edit isn't clobbered by a late prop change.
  useEffect(() => {
    if (!editing) {
      setNarrative(data.narrative || '');
      setBackground(data.background || '');
    }
  }, [data.narrative, data.background, editing]);

  useEffect(() => {
    if (editing && narrativeRef.current) narrativeRef.current.focus({ preventScroll: true });
  }, [editing]);

  const handleSave = () => {
    onEdit(commandIndex, { ...data, narrative, background }, 'assess');
    setEditing(false);
  };

  const handleCancel = () => {
    setNarrative(data.narrative || '');
    setBackground(data.background || '');
    setEditing(false);
  };

  if (editing && !readOnly) {
    const saveDisabled = narrative.length > 2048 || background.length > 2048;
    return html`
      <div class="diagnose-edit-area editing">
        <div class="diagnose-body-label">Background</div>
        <textarea
          ref=${backgroundRef}
          class="command-row-textarea"
          maxLength=${2048}
          value=${background}
          onInput=${(e) => setBackground(e.target.value)}
          onKeyDown=${(e) => e.key === 'Escape' && handleCancel()}
        />
        <div class="char-counter${background.length > 1900 ? background.length > 2048 ? ' over-limit' : ' near-limit' : ''}">${background.length} / 2048</div>
        <div class="diagnose-body-label">Today's assessment</div>
        <textarea
          ref=${narrativeRef}
          class="command-row-textarea"
          maxLength=${2048}
          value=${narrative}
          onInput=${(e) => setNarrative(e.target.value)}
          onKeyDown=${(e) => e.key === 'Escape' && handleCancel()}
        />
        <div class="char-counter${narrative.length > 1900 ? narrative.length > 2048 ? ' over-limit' : ' near-limit' : ''}">${narrative.length} / 2048</div>
        <div class="command-row-actions">
          <button type="button" class="form-btn form-btn-cancel" onClick=${handleCancel}>Cancel</button>
          <button type="button" class="form-btn form-btn-save" disabled=${saveDisabled} onClick=${handleSave}>Save</button>
        </div>
      </div>
    `;
  }

  const narrativeText = data.narrative || '';
  const backgroundText = data.background || '';
  const hasBackground = backgroundText.length > 0;
  const hasNarrative = narrativeText.length > 0;
  const narrativeOverLimit = narrativeText.length > 2048;
  const backgroundOverLimit = backgroundText.length > 2048;
  return html`
    <div
      class="diagnose-row-body${readOnly ? '' : ' editable'}"
      onClick=${() => !readOnly && setEditing(true)}
    >
      ${!hasBackground && !hasNarrative
        ? html`<div class="diagnose-body-empty">No assessment text</div>`
        : html`
          ${hasBackground && html`
            <div class="diagnose-body-label">Background</div>
            ${backgroundText.split('\n').map((line, i) => html`<div key=${'b' + i} class="diagnose-body-line">${line}</div>`)}
            ${backgroundOverLimit && html`<div class="char-counter over-limit">${backgroundText.length} / 2048 — text must be shortened before approving</div>`}
          `}
          ${hasNarrative && html`
            <div class="diagnose-body-label">Today's assessment</div>
            ${narrativeText.split('\n').map((line, i) => html`<div key=${'n' + i} class="diagnose-body-line">${line}</div>`)}
            ${narrativeOverLimit && html`<div class="char-counter over-limit">${narrativeText.length} / 2048 — text must be shortened before approving</div>`}
          `}
        `
      }
    </div>
  `;
}

function AddConditionSearch({ onAdd, patientId }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [existingConditions, setExistingConditions] = useState([]);
  const [loadingConditions, setLoadingConditions] = useState(false);
  const timer = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!open || !patientId) return;
    setLoadingConditions(true);
    fetch(`${API_BASE}/patient-conditions?patient_id=${encodeURIComponent(patientId)}`)
      .then(res => res.json())
      .then(data => setExistingConditions(data.conditions || []))
      .catch(err => { console.error('Failed to fetch existing conditions:', err); setExistingConditions([]); })
      .finally(() => setLoadingConditions(false));
  }, [open, patientId]);

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
    onAdd(r.code, r.display, null);
    setQuery('');
    setResults([]);
    setSearched(false);
    setOpen(false);
  };

  const handleSelectExisting = (c) => {
    onAdd(c.code, c.display, c.condition_id);
    setQuery('');
    setResults([]);
    setSearched(false);
    setOpen(false);
  };

  const close = () => { setOpen(false); setQuery(''); setResults([]); setSearched(false); };

  // Filter existing conditions by query text.
  const q = query.trim().toLowerCase();
  const filteredExisting = q
    ? existingConditions.filter(c =>
        (c.display || '').toLowerCase().includes(q) ||
        (c.code || '').toLowerCase().includes(q) ||
        (c.formatted_code || '').toLowerCase().includes(q))
    : existingConditions;

  const showDropdown = open && (
    (!loadingConditions && filteredExisting.length > 0) ||
    results.length > 0 ||
    searching ||
    (!searching && searched && results.length === 0 && query.length >= 2)
  );

  if (!open) {
    return html`<button type="button" class="ad-hoc-btn" onClick=${() => setOpen(true)}>+ Add Condition</button>`;
  }

  return html`
    <div class="add-condition-picker" ref=${containerRef}>
      <div class="add-condition-input-row">
        <input
          type="text"
          class="add-condition-input"
          value=${query}
          onInput=${handleInput}
          placeholder="Search existing or new diagnosis..."
          autoFocus
        />
        <button type="button" class="add-condition-close" onClick=${close}>×</button>
      </div>
      ${showDropdown && html`
        <div class="add-condition-dropdown">
          ${loadingConditions && html`<div class="add-condition-loading">Loading...</div>`}
          ${!loadingConditions && filteredExisting.length > 0 && html`
            <div class="add-condition-section-label">Patient conditions</div>
            ${filteredExisting.map(c => html`
              <div
                key=${'ex-' + c.condition_id}
                class="add-condition-option existing"
                onMouseDown=${(e) => { e.preventDefault(); handleSelectExisting(c); }}
              >
                <span class="add-condition-option-name">${c.display}</span>
                ${c.formatted_code && html`<span class="add-condition-option-code">${c.formatted_code}</span>`}
              </div>
            `)}
          `}
          ${results.length > 0 && html`
            <div class="add-condition-section-label">New diagnosis</div>
            ${results.map(r => html`
              <div
                key=${'sr-' + r.code}
                class="add-condition-option"
                onMouseDown=${(e) => { e.preventDefault(); handleSelect(r); }}
              >
                <span class="add-condition-option-name">${r.display}</span>
                ${r.formatted_code && html`<span class="add-condition-option-code">${r.formatted_code}</span>`}
              </div>
            `)}
          `}
          ${searching && html`<div class="add-condition-loading">Searching...</div>`}
          ${!searching && searched && results.length === 0 && query.length >= 2 && html`
            <div class="add-condition-empty">No new diagnoses found</div>
          `}
        </div>
      `}
    </div>
  `;
}

export function SoapGroup({ title, groupColor, sections, commandBySectionKey, onEditCommand, onDeleteCommand, adHocCommands, assignees, onAddTask, onAddOrder, onAddPlan, onAddVitals, onAddMedication, onAddAllergy, onAddStopMedication, onAddRemoveAllergy, onAddResolveCondition, onAddHistory, onAddQuestionnaire, onAddCharge, onAddTemplateCharge, onRemoveChargeByCpt, templateCharges, readOnly, sectionConditions, patientId, noteId, staffId, staffName, recommendations, onEditRecommendation, onDeleteRecommendation, onAcceptRecommendation, onRejectRecommendation, onAddCondition, unmatchedConditions, diagnosisSuggestions, onAddNow, hideRejected, alertFacilityEnabled, onEditingChange, questionnaireScores }) {
  const coveredKeys = getCoveredKeys(commandBySectionKey);

  // In approved (readOnly) mode, only show items that actually made it into the note.
  // When hideRejected is on, also filter out rejected recommendations before approval.
  const shouldHideRejected = hideRejected || readOnly;
  const visibleRecs = (recommendations || [])
    .map((c, origIndex) => ({ ...c, _origIndex: origIndex }))
    .filter(c => readOnly ? wasInserted(c, true) : shouldHideRejected ? !c.rejected : true);
  const visibleAdHoc = readOnly
    ? (adHocCommands || []).filter(e => wasInserted(e.command))
    : (adHocCommands || []);

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
          // Filter out sections that are rendered as structured cards.
          const STRUCTURED_KEYS = new Set();
          const filteredSections = (entry.command.data.sections || []).filter(s => !STRUCTURED_KEYS.has(s.key));
          if (filteredSections.length === 0) return null;
          const filteredCommand = { ...entry.command, data: { ...entry.command.data, sections: filteredSections } };
          return html`
            <div class=${`content-block rec-narrative${entry.command.already_documented ? ' command-locked' : ''}`}>
              ${entry.command.already_documented && ICON_LOCK}
              <${HistoryReviewRow}
                command=${filteredCommand}
                commandIndex=${entry.index}
                onEdit=${onEditCommand}
                readOnly=${readOnly || entry.command.already_documented}
                onEditingChange=${onEditingChange}
              />
            </div>
          `;
        })()}
        ${sections.map(s => {
          const key = s.key.toLowerCase();
          const hasRecsForKey = visibleRecs.length > 0 &&
            ((key === 'current_medications' && visibleRecs.some(r => r.command_type === 'medication_statement')) ||
             (key === 'allergies' && visibleRecs.some(r => r.command_type === 'allergy')) ||
             (key === 'prescription' && visibleRecs.some(r => r.command_type === 'prescribe')));
          const DEDICATED_SECTION_KEYS = new Set(['current_medications', 'allergies']);
          const HISTORY_SECTION_KEYS = new Set(['past_medical_history', 'past_surgical_history', 'family_history']);
          const isCoveredHistory = coveredKeys.has(key) && HISTORY_SECTION_KEYS.has(key);
          if (coveredKeys.has(key) && !hasRecsForKey && !DEDICATED_SECTION_KEYS.has(key) && !HISTORY_SECTION_KEYS.has(key)) return null;
          const cmds = commandBySectionKey && commandBySectionKey[key];

          if (cmds && NARRATIVE_SECTIONS.has(key)) {
            const isPlan = PLAN_SECTIONS.has(key);
            // If the A&P has been split into per-condition commands, render each diagnose as DiagnoseRow and assess as CommandRow.
            const hasConditionCommands = isPlan && cmds.some(e => e.command.command_type === 'diagnose' || e.command.command_type === 'assess');
            if (hasConditionCommands) {
              const unmatched = unmatchedConditions || [];
              return html`
                <div class="subsection" key=${s.key}>
                  <div class="subsection-title">${s.title}</div>
                  ${cmds.filter(e => e.command.command_type === 'assess').map(entry => {
                    const aData = entry.command.data || {};
                    const aCode = aData.icd10_code ? aData.icd10_code.replace(/\./g, '').trim().toUpperCase() : '';
                    const aFormatted = aCode.length > 3 ? aCode.slice(0, 3) + '.' + aCode.slice(3) : aCode;
                    return html`
                      <div class=${`content-block recommendation-block rec-assess${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                        ${entry.command.already_documented && ICON_LOCK}
                        <div class="recommendation-content">
                          <div class="diagnose-row">
                            <div class="diagnose-row-header">
                              <span class="diagnose-row-title">
                                ${aFormatted && html`<span class="diagnose-icd-prefix">${aFormatted}</span>`}
                                ${' '}${entry.command.display}
                              </span>
                            </div>
                            <${AssessNarrative}
                              command=${entry.command}
                              commandIndex=${entry.index}
                              onEdit=${onEditCommand}
                              readOnly=${readOnly || entry.command.already_documented}
                              onEditingChange=${onEditingChange}
                            />
                          </div>
                        </div>
                        ${!readOnly && html`
                          <div class="recommendation-actions">
                            <button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button>
                          </div>
                        `}
                      </div>
                    `;
                  })}
                  ${cmds.filter(e => e.command.command_type === 'diagnose' && (!readOnly || wasInserted(e.command)) && (!shouldHideRejected || !e.command.data.rejected)).map(entry => {
                    const hasCode = !!entry.command.data.icd10_code;
                    const isAccepted = hasCode && entry.command.data.accepted;
                    const isRejected = entry.command.data.rejected;
                    const isIncomplete = !hasCode && !isRejected;
                    const header = entry.command.data.condition_header || '';
                    const suggestions = (!hasCode && !isRejected && diagnosisSuggestions && diagnosisSuggestions[header]) || null;

                    const handleAcceptDiagnose = () => onEditCommand(entry.index, { ...entry.command.data, accepted: true, rejected: false }, 'diagnose');
                    const handleRejectDiagnose = () => onEditCommand(entry.index, { ...entry.command.data, rejected: true, accepted: false }, 'diagnose');

                    return html`
                      <div class=${`content-block recommendation-block rec-diagnose${isRejected ? ' rec-rejected' : ''}${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                        ${entry.command.already_documented && ICON_LOCK}
                        <div class="recommendation-content">
                          <${DiagnoseRow}
                            command=${entry.command}
                            commandIndex=${entry.index}
                            onEdit=${onEditCommand}
                            onDelete=${onDeleteCommand}
                            readOnly=${readOnly || isRejected || entry.command.already_documented}
                            suggestions=${suggestions}
                            onAccept=${handleAcceptDiagnose}
                            onEditingChange=${onEditingChange}
                          />
                        </div>
                        ${!readOnly && html`
                          <div class="recommendation-actions">
                            ${isIncomplete && html`<span class="rec-warning-pill">Missing Diagnosis Code</span>`}
                            ${isRejected && html`<span class="rec-rejected-badge">Rejected</span>`}
                            ${isAccepted && html`<span class="rec-accepted-badge">Accepted</span>`}
                            <button type="button" class="rec-btn ${isRejected ? 'rec-btn-reject' : 'rec-btn-muted'}" onClick=${handleRejectDiagnose} title="Reject">${ICON_X}</button>
                            <button type="button" class="rec-btn ${isAccepted ? 'rec-btn-accept' : 'rec-btn-muted'}" onClick=${handleAcceptDiagnose} title="Accept">${ICON_CHECK}</button>
                          </div>
                        `}
                      </div>
                    `;
                  })}
                  ${!readOnly && unmatched.length > 0 && html`
                    <div class="diagnose-suggestions" style="margin-top: 12px;">
                      <div class="history-form-label">Other detected conditions</div>
                      <div class="diagnose-suggestions-list">
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
                              class="diagnose-suggestion-btn"
                              onClick=${() => onAddCondition && onAddCondition(code.code, display)}
                            ><strong>${formatted}</strong>${' '}${display}</button>
                          `;
                        })}
                      </div>
                    </div>
                  `}
                  ${(visibleAdHoc.filter(e => e.command.command_type === 'resolve_condition')).map(re => html`
                    <div class=${`content-block recommendation-block rec-removal${re.command.already_documented ? ' command-locked' : ''}`} key=${re.index}>
                      ${re.command.already_documented && ICON_LOCK}
                      <div class="recommendation-content">
                        <${RemovalRow}
                          command=${re.command}
                          commandIndex=${re.index}
                          onEdit=${onEditCommand}
                          onDelete=${onDeleteCommand}
                          readOnly=${readOnly || re.command.already_documented}
                          patientId=${patientId}
                          alertFacilityEnabled=${alertFacilityEnabled}
                        />
                      </div>
                      ${!readOnly && html`<div class="recommendation-actions"><button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(re.index)} title="Remove">${ICON_X}</button></div>`}
                    </div>
                  `)}
                  ${(onAddCondition || onAddResolveCondition) && !readOnly && html`
                    <div class="ad-hoc-buttons">
                      ${onAddCondition && html`<${AddConditionSearch} onAdd=${onAddCondition} patientId=${patientId} />`}
                      ${onAddResolveCondition && html`<button type="button" class="ad-hoc-btn removal-btn" onClick=${onAddResolveCondition}>- Resolve Condition</button>`}
                    </div>
                  `}
                </div>
              `;
            }
            const entry = cmds[0];
            if (readOnly && !entry.command.display) return null;
            const showConditionBtns = isPlan && (onAddCondition || onAddResolveCondition) && !readOnly;
            const planResolves = isPlan ? visibleAdHoc.filter(e => e.command.command_type === 'resolve_condition') : [];
            return html`
              <div class="subsection" key=${s.key}>
                <div class="subsection-title">${s.title}</div>
                <div class=${`content-block rec-narrative${entry.command.already_documented ? ' command-locked' : ''}`}>
                  ${entry.command.already_documented && ICON_LOCK}
                  <${CommandRow}
                    command=${entry.command}
                    commandIndex=${entry.index}
                    onEdit=${onEditCommand}
                    readOnly=${readOnly || entry.command.already_documented}
                    onEditingChange=${onEditingChange}
                  />
                </div>
                ${planResolves.map(re => html`
                  <div class=${`content-block recommendation-block rec-removal${re.command.already_documented ? ' command-locked' : ''}`} key=${re.index}>
                    ${re.command.already_documented && ICON_LOCK}
                    <div class="recommendation-content">
                      <${RemovalRow}
                        command=${re.command}
                        commandIndex=${re.index}
                        onEdit=${onEditCommand}
                        onDelete=${onDeleteCommand}
                        readOnly=${readOnly || re.command.already_documented}
                        patientId=${patientId}
                      />
                    </div>
                    ${!readOnly && html`<div class="recommendation-actions"><button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(re.index)} title="Remove">${ICON_X}</button></div>`}
                  </div>
                `)}
                ${showConditionBtns && html`
                  <div class="ad-hoc-buttons">
                    ${onAddCondition && html`<${AddConditionSearch} onAdd=${onAddCondition} patientId=${patientId} />`}
                    ${onAddResolveCondition && html`<button type="button" class="ad-hoc-btn removal-btn" onClick=${onAddResolveCondition}>- Resolve Condition</button>`}
                  </div>
                `}
              </div>
            `;
          }

          if (key === 'vitals') {
            const adHocVitals = visibleAdHoc.filter(e => e.command.command_type === 'vitals');
            const allVitals = [...(cmds || []), ...adHocVitals];
            const hasAny = allVitals.some(e => Object.values(e.command.data || {}).some(v => v != null));
            if (readOnly && !hasAny) return null;
            if (allVitals.length === 0 && !onAddVitals) return null;
            return html`
              <div class="subsection" key=${s.key}>
                <div class="subsection-title">${s.title}</div>
                ${allVitals.map((entry, idx) => html`
                  <div class=${`content-block rec-vitals${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                    ${entry.command.already_documented && ICON_LOCK}
                    <${VitalsRow}
                      command=${entry.command}
                      commandIndex=${entry.index}
                      onEdit=${onEditCommand}
                      readOnly=${readOnly || entry.command.already_documented}
                      onEditingChange=${onEditingChange}
                      questionnaireScores=${idx === 0 ? questionnaireScores : []}
                    />
                  </div>
                `)}
                ${onAddVitals && !readOnly && html`
                  <div class="ad-hoc-buttons">
                    <button type="button" class="ad-hoc-btn" onClick=${onAddVitals}>+ Vitals</button>
                  </div>
                `}
              </div>
            `;
          }

          if (cmds && key === 'physical_exam') {
            const entry = cmds[0];
            return html`
              <div class="subsection" key=${s.key}>
                <div class="subsection-title">${s.title}</div>
                <div class=${`content-block rec-narrative${entry.command.already_documented ? ' command-locked' : ''}`}>
                  ${entry.command.already_documented && ICON_LOCK}
                  <${HistoryReviewRow}
                    command=${entry.command}
                    commandIndex=${entry.index}
                    onEdit=${onEditCommand}
                    readOnly=${readOnly || entry.command.already_documented}
                    textareaRows=${2}
                    onEditingChange=${onEditingChange}
                  />
                </div>
              </div>
            `;
          }

          if (key === 'current_medications') {
            const medRecs = visibleRecs
              .map(cmd => ({ command: cmd, index: cmd._origIndex }))
              .filter(e => e.command.command_type === 'medication_statement');
            const adHocMeds = visibleAdHoc.filter(e => e.command.command_type === 'medication_statement');
            const adHocStopMeds = visibleAdHoc.filter(e => e.command.command_type === 'stop_medication');
            if (cmds || medRecs.length > 0 || adHocMeds.length > 0 || adHocStopMeds.length > 0 || onAddMedication) {
              return html`
                <div class="subsection" key=${s.key}>
                  <div class="subsection-title">Med List Updates</div>
                  ${(cmds || []).map(entry => html`
                    <div class=${`content-block recommendation-block rec-medication${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                      ${entry.command.already_documented && ICON_LOCK}
                      <div class="recommendation-content">
                        <${MedicationRow}
                          command=${entry.command}
                          commandIndex=${entry.index}
                          onEdit=${onEditCommand}
                          onDelete=${onDeleteCommand}
                          alertFacilityEnabled=${alertFacilityEnabled}
                          readOnly=${readOnly || entry.command.already_documented}
                          onEditingChange=${onEditingChange}
                        />
                      </div>
                      ${!readOnly && html`
                        <div class="recommendation-actions">
                          ${entry.command.already_documented
                            ? html`<span class="rec-documented-badge">${entry.command._added_now ? 'Added' : 'Already in chart'}</span>`
                            : onAddNow && entry.command.display && html`<button type="button" class="rec-btn-add-now" disabled=${entry.command._adding} onClick=${() => !entry.command._adding && onAddNow(entry.command, false, entry.index)}>${entry.command._adding ? 'Adding...' : 'Add Now'}</button>`
                          }
                          ${!entry.command.already_documented && !entry.command._adding && html`<button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button>`}
                        </div>
                      `}
                    </div>
                  `)}
                  ${adHocMeds.map(entry => html`
                    <div class=${`content-block recommendation-block rec-medication${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                      ${entry.command.already_documented && ICON_LOCK}
                      <div class="recommendation-content">
                        <${MedicationRow}
                          command=${entry.command}
                          commandIndex=${entry.index}
                          onEdit=${onEditCommand}
                          onDelete=${onDeleteCommand}
                          alertFacilityEnabled=${alertFacilityEnabled}
                          readOnly=${readOnly || entry.command.already_documented}
                          onEditingChange=${onEditingChange}
                        />
                      </div>
                      ${!readOnly && html`
                        <div class="recommendation-actions">
                          ${entry.command.already_documented
                            ? html`<span class="rec-documented-badge">${entry.command._added_now ? 'Added' : 'Already in chart'}</span>`
                            : onAddNow && entry.command.display && html`<button type="button" class="rec-btn-add-now" disabled=${entry.command._adding} onClick=${() => !entry.command._adding && onAddNow(entry.command, false, entry.index)}>${entry.command._adding ? 'Adding...' : 'Add Now'}</button>`
                          }
                          ${!entry.command.already_documented && !entry.command._adding && html`<button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button>`}
                        </div>
                      `}
                    </div>
                  `)}
                  ${medRecs.map(entry => {
                    const isAccepted = entry.command.accepted && !entry.command.rejected;
                    const isRejected = entry.command.rejected;
                    const isUnreviewed = !isAccepted && !isRejected;
                    return html`
                    <div class=${`content-block recommendation-block rec-medication${isRejected ? ' rec-rejected' : ''}${entry.command.already_documented ? ' command-locked' : ''}`} key=${'rec-med-' + entry.index}>
                      ${entry.command.already_documented && ICON_LOCK}
                      <div class="recommendation-content">
                        <${MedicationRow}
                          command=${entry.command}
                          commandIndex=${entry.index}
                          onEdit=${onEditRecommendation}
                          alertFacilityEnabled=${alertFacilityEnabled}
                          readOnly=${readOnly || entry.command.already_documented || isRejected}
                          onEditingChange=${onEditingChange}
                        />
                      </div>
                      <div class="recommendation-actions">
                        ${entry.command.already_documented
                          ? html`<span class="rec-documented-badge">${entry.command._added_now ? 'Added' : 'Already in chart'}</span>`
                          : !readOnly && html`
                              ${isRejected && html`<span class="rec-rejected-badge">Rejected</span>`}
                              ${isAccepted && html`<span class="rec-accepted-badge">Accepted</span>`}
                              ${onAddNow && isAccepted && html`<button type="button" class="rec-btn-add-now" disabled=${entry.command._adding} onClick=${() => !entry.command._adding && onAddNow(entry.command, true, entry.index)}>${entry.command._adding ? 'Adding...' : 'Add Now'}</button>`}
                              ${!entry.command._adding && html`
                                <button type="button" class="rec-btn ${isRejected ? 'rec-btn-reject' : 'rec-btn-muted'}" onClick=${() => onRejectRecommendation(entry.index)} title="Reject">${ICON_X}</button>
                                <button type="button" class="rec-btn ${isAccepted ? 'rec-btn-accept' : 'rec-btn-muted'}" onClick=${() => onAcceptRecommendation(entry.index)} title="Accept">${ICON_CHECK}</button>
                              `}
                            `
                        }
                      </div>
                    </div>
                    `;
                  })}
                  ${adHocStopMeds.map(entry => html`
                    <div class=${`content-block recommendation-block rec-removal${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                      ${entry.command.already_documented && ICON_LOCK}
                      <div class="recommendation-content">
                        <${RemovalRow}
                          command=${entry.command}
                          commandIndex=${entry.index}
                          onEdit=${onEditCommand}
                          onDelete=${onDeleteCommand}
                          readOnly=${readOnly || entry.command.already_documented}
                          patientId=${patientId}
                          alertFacilityEnabled=${alertFacilityEnabled}
                        />
                      </div>
                      ${!readOnly && html`<div class="recommendation-actions">
                        ${entry.command.already_documented
                          ? html`<span class="rec-documented-badge">${entry.command._added_now ? 'Added' : 'Already in chart'}</span>`
                          : onAddNow && entry.command.display && html`<button type="button" class="rec-btn-add-now" disabled=${entry.command._adding} onClick=${() => !entry.command._adding && onAddNow(entry.command, false, entry.index)}>${entry.command._adding ? 'Adding...' : 'Add Now'}</button>`
                        }
                        ${!entry.command.already_documented && !entry.command._adding && html`<button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button>`}
                      </div>`}
                    </div>
                  `)}
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
            const allergyRecs = visibleRecs
              .map(cmd => ({ command: cmd, index: cmd._origIndex }))
              .filter(e => e.command.command_type === 'allergy');
            const adHocAllergies = visibleAdHoc.filter(e => e.command.command_type === 'allergy');
            const adHocRemoveAllergies = visibleAdHoc.filter(e => e.command.command_type === 'remove_allergy');
            if (cmds || allergyRecs.length > 0 || adHocAllergies.length > 0 || adHocRemoveAllergies.length > 0 || onAddAllergy) {
              return html`
                <div class="subsection" key=${s.key}>
                  <div class="subsection-title">Allergy List Updates</div>
                  ${(cmds || []).map(entry => html`
                    <div class=${`content-block recommendation-block rec-allergy${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                      ${entry.command.already_documented && ICON_LOCK}
                      <div class="recommendation-content">
                        <${AllergyRow}
                          command=${entry.command}
                          commandIndex=${entry.index}
                          onEdit=${onEditCommand}
                          onDelete=${onDeleteCommand}
                          readOnly=${readOnly || entry.command.already_documented}
                          onEditingChange=${onEditingChange}
                        />
                      </div>
                      ${!readOnly && html`
                        <div class="recommendation-actions">
                          <button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button>
                        </div>
                      `}
                    </div>
                  `)}
                  ${adHocAllergies.map(entry => html`
                    <div class=${`content-block recommendation-block rec-allergy${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                      ${entry.command.already_documented && ICON_LOCK}
                      <div class="recommendation-content">
                        <${AllergyRow}
                          command=${entry.command}
                          commandIndex=${entry.index}
                          onEdit=${onEditCommand}
                          onDelete=${onDeleteCommand}
                          readOnly=${readOnly || entry.command.already_documented}
                          onEditingChange=${onEditingChange}
                        />
                      </div>
                      ${!readOnly && html`
                        <div class="recommendation-actions">
                          <button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button>
                        </div>
                      `}
                    </div>
                  `)}
                  ${allergyRecs.map(entry => {
                    const isAccepted = entry.command.accepted && !entry.command.rejected;
                    const isRejected = entry.command.rejected;
                    return html`
                    <div class=${`content-block recommendation-block rec-allergy${isRejected ? ' rec-rejected' : ''}${entry.command.already_documented ? ' command-locked' : ''}`} key=${'rec-allergy-' + entry.index}>
                      ${entry.command.already_documented && ICON_LOCK}
                      <div class="recommendation-content">
                        <${AllergyRow}
                          command=${entry.command}
                          commandIndex=${entry.index}
                          onEdit=${onEditRecommendation}
                          readOnly=${readOnly || entry.command.already_documented || isRejected}
                          onEditingChange=${onEditingChange}
                        />
                      </div>
                      <div class="recommendation-actions">
                        ${entry.command.already_documented
                          ? html`<span class="rec-documented-badge">Already in chart</span>`
                          : !readOnly && html`
                              ${isRejected && html`<span class="rec-rejected-badge">Rejected</span>`}
                              ${isAccepted && html`<span class="rec-accepted-badge">Accepted</span>`}
                              <button type="button" class="rec-btn ${isRejected ? 'rec-btn-reject' : 'rec-btn-muted'}" onClick=${() => onRejectRecommendation(entry.index)} title="Reject">${ICON_X}</button>
                              <button type="button" class="rec-btn ${isAccepted ? 'rec-btn-accept' : 'rec-btn-muted'}" onClick=${() => onAcceptRecommendation(entry.index)} title="Accept">${ICON_CHECK}</button>
                            `
                        }
                      </div>
                    </div>
                    `;
                  })}
                  ${adHocRemoveAllergies.map(entry => html`
                    <div class=${`content-block recommendation-block rec-removal${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                      ${entry.command.already_documented && ICON_LOCK}
                      <div class="recommendation-content">
                        <${RemovalRow}
                          command=${entry.command}
                          commandIndex=${entry.index}
                          onEdit=${onEditCommand}
                          onDelete=${onDeleteCommand}
                          readOnly=${readOnly || entry.command.already_documented}
                          patientId=${patientId}
                          alertFacilityEnabled=${alertFacilityEnabled}
                        />
                      </div>
                      ${!readOnly && html`<div class="recommendation-actions"><button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button></div>`}
                    </div>
                  `)}
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

          const historyType = SECTION_TO_HISTORY_TYPE[key];
          const historyEntries = historyType
            ? visibleAdHoc.filter(e => e.command.command_type === historyType)
            : [];
          const showHistoryText = s.text && !isCoveredHistory;
          if (readOnly && !showHistoryText && !cmds && historyEntries.length === 0) return null;
          if (!showHistoryText && historyEntries.length === 0 && !onAddHistory && !cmds) return null;
          return html`
            <div class="subsection" key=${s.key}>
              <div class="subsection-title">${s.title}</div>
              ${showHistoryText && html`<p class="section-text">${s.text}</p>`}
              ${historyEntries.map(entry => html`
                <div class=${`content-block recommendation-block rec-history${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                  ${entry.command.already_documented && ICON_LOCK}
                  <div class="recommendation-content">
                    <${HistoryEntryRow}
                      command=${entry.command}
                      commandIndex=${entry.index}
                      onEdit=${onEditCommand}
                      onDelete=${onDeleteCommand}
                      readOnly=${readOnly || entry.command.already_documented}
                      onEditingChange=${onEditingChange}
                    />
                  </div>
                  ${!readOnly && html`<div class="recommendation-actions"><button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button></div>`}
                </div>
              `)}
              ${historyType && onAddHistory && !readOnly && html`
                <div class="ad-hoc-buttons">
                  <button type="button" class="ad-hoc-btn" onClick=${() => onAddHistory(historyType)}>${HISTORY_ADD_LABELS[historyType]}</button>
                </div>
              `}
              ${PLAN_SECTIONS.has(key) && (() => {
                const adHocResolves = visibleAdHoc.filter(e => e.command.command_type === 'resolve_condition');
                return html`
                  ${adHocResolves.map(entry => html`
                    <div class=${`content-block recommendation-block rec-removal${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                      ${entry.command.already_documented && ICON_LOCK}
                      <div class="recommendation-content">
                        <${RemovalRow}
                          command=${entry.command}
                          commandIndex=${entry.index}
                          onEdit=${onEditCommand}
                          onDelete=${onDeleteCommand}
                          readOnly=${readOnly || entry.command.already_documented}
                          patientId=${patientId}
                          alertFacilityEnabled=${alertFacilityEnabled}
                        />
                      </div>
                      ${!readOnly && html`<div class="recommendation-actions"><button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button></div>`}
                    </div>
                  `)}
                  ${(onAddCondition || onAddResolveCondition) && !readOnly && html`
                    <div class="ad-hoc-buttons">
                      ${onAddCondition && html`<${AddConditionSearch} onAdd=${onAddCondition} patientId=${patientId} />`}
                      ${onAddResolveCondition && html`<button type="button" class="ad-hoc-btn removal-btn" onClick=${onAddResolveCondition}>- Resolve Condition</button>`}
                    </div>
                  `}
                `;
              })()}
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
            <div class=${`content-block rec-narrative${entry.command.already_documented ? ' command-locked' : ''}`}>
              ${entry.command.already_documented && ICON_LOCK}
              <${HistoryReviewRow}
                command=${entry.command}
                commandIndex=${entry.index}
                onEdit=${onEditCommand}
                readOnly=${readOnly || entry.command.already_documented}
                textareaRows=${2}
                onEditingChange=${onEditingChange}
              />
            </div>
          `;
        })()}
        ${visibleAdHoc.map(entry => {
          const type = entry.command.command_type;
          if (type === 'medication_statement') return null;
          if (type === 'allergy') return null;
          if (type === 'stop_medication') return null;
          if (type === 'remove_allergy') return null;
          if (type === 'resolve_condition') return null;
          if (type === 'task') {
            return html`
              <div class=${`content-block recommendation-block rec-task${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                ${entry.command.already_documented && ICON_LOCK}
                <div class="recommendation-content">
                  <${TaskRow}
                    command=${entry.command}
                    commandIndex=${entry.index}
                    onEdit=${onEditCommand}
                    onDelete=${onDeleteCommand}
                    assignees=${assignees}
                    readOnly=${readOnly || entry.command.already_documented}
                    onEditingChange=${onEditingChange}
                  />
                </div>
                ${!readOnly && html`<div class="recommendation-actions">
                  ${entry.command.already_documented
                    ? html`<span class="rec-documented-badge">${entry.command._added_now ? 'Added' : 'Already in chart'}</span>`
                    : onAddNow && entry.command.display && html`<button type="button" class="rec-btn-add-now" disabled=${entry.command._adding} onClick=${() => !entry.command._adding && onAddNow(entry.command, false, entry.index)}>${entry.command._adding ? 'Adding...' : 'Add Now'}</button>`
                  }
                  ${!entry.command.already_documented && !entry.command._adding && html`<button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button>`}
                </div>`}
              </div>
            `;
          }
          if (ORDER_TYPES.has(type)) {
            const d = entry.command.data;
            const orderMissing = [];
            if (type === 'prescribe' && entry.command.display) {
              if (!d.fdb_code) orderMissing.push('Medication');
              if (!d.sig) orderMissing.push('Sig');
              if (d.quantity_to_dispense == null) orderMissing.push('Qty');
              if (!d.type_to_dispense) orderMissing.push('Dispense type');
              if (d.refills == null) orderMissing.push('Refills');
            }
            if (type === 'lab_order' && entry.command.display) {
              if (!d.lab_partner) orderMissing.push('Lab partner');
              if (!d.tests_order_codes || d.tests_order_codes.length === 0) orderMissing.push('Tests');
            }
            if (type === 'imaging_order' && entry.command.display) {
              if (!d.image_code) orderMissing.push('Image');
              if (!d.service_provider) orderMissing.push('Imaging center');
              if (!d.ordering_provider_id) orderMissing.push('Ordering provider');
              if (!d.diagnosis_codes || d.diagnosis_codes.length === 0) orderMissing.push('Indications');
            }
            if (type === 'refer' && entry.command.display) {
              if (!d.service_provider) orderMissing.push('Provider');
              if (!d.clinical_question) orderMissing.push('Clinical question');
              if (!d.notes_to_specialist) orderMissing.push('Notes to specialist');
              if (!d.diagnosis_codes || d.diagnosis_codes.length === 0) orderMissing.push('Indications');
            }
            const orderIncomplete = orderMissing.length > 0;
            return html`
              <div class=${`content-block recommendation-block rec-order${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                ${entry.command.already_documented && ICON_LOCK}
                <div class="recommendation-content">
                  <${OrderRow}
                    command=${entry.command}
                    commandIndex=${entry.index}
                    onEdit=${onEditCommand}
                    onDelete=${onDeleteCommand}
                    readOnly=${readOnly || entry.command.already_documented}
                    patientId=${patientId}
                    noteId=${noteId}
                    staffId=${staffId}
                    staffName=${staffName}
                    onEditingChange=${onEditingChange}
                  />
                </div>
                ${!readOnly && html`<div class="recommendation-actions">
                  ${orderIncomplete && html`<span class="rec-warning-pill">Missing: ${orderMissing.join(', ')}</span>`}
                  ${entry.command.already_documented
                    ? html`<span class="rec-documented-badge">${entry.command._added_now ? 'Added' : 'Already in chart'}</span>`
                    : onAddNow && entry.command.display && !orderIncomplete && html`<button type="button" class="rec-btn-add-now" disabled=${entry.command._adding} onClick=${() => !entry.command._adding && onAddNow(entry.command, false, entry.index)}>${entry.command._adding ? 'Adding...' : 'Add Now'}</button>`
                  }
                  ${!entry.command.already_documented && !entry.command._adding && html`<button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button>`}
                </div>`}
              </div>
            `;
          }
          if (type === 'history_review') {
            return html`
              <div class="content-block recommendation-block rec-narrative" key=${entry.index}>
                <div class="recommendation-content">
                  <${HistoryReviewRow}
                    command=${entry.command}
                    commandIndex=${entry.index}
                    onEdit=${onEditCommand}
                    onDelete=${onDeleteCommand}
                    onEditingChange=${onEditingChange}
                  />
                </div>
                ${!readOnly && html`<div class="recommendation-actions"><button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button></div>`}
              </div>
            `;
          }
          if (HISTORY_TYPES.has(type)) return null;
          if (type === 'questionnaire') return null;
          if (type === 'plan') {
            return html`
              <div class=${`content-block recommendation-block rec-plan${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                ${entry.command.already_documented && ICON_LOCK}
                <div class="recommendation-content">
                  <${CommandRow}
                    command=${entry.command}
                    commandIndex=${entry.index}
                    onEdit=${onEditCommand}
                    onDelete=${onDeleteCommand}
                    readOnly=${readOnly || entry.command.already_documented}
                    onEditingChange=${onEditingChange}
                  />
                </div>
                ${!readOnly && html`<div class="recommendation-actions"><button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button></div>`}
              </div>
            `;
          }
          if (type === 'perform') return null;
          if (REMOVAL_TYPES.has(type)) {
            return html`
              <div class=${`content-block recommendation-block rec-removal${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                ${entry.command.already_documented && ICON_LOCK}
                <div class="recommendation-content">
                  <${RemovalRow}
                    command=${entry.command}
                    commandIndex=${entry.index}
                    onEdit=${onEditCommand}
                    onDelete=${onDeleteCommand}
                    readOnly=${readOnly || entry.command.already_documented}
                    patientId=${patientId}
                  />
                </div>
                ${!readOnly && html`<div class="recommendation-actions"><button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button></div>`}
              </div>
            `;
          }
          return null;
        })}
        ${(() => {
          const questionnaireCommands = visibleAdHoc
            .filter(e => e.command.command_type === 'questionnaire');
          if (questionnaireCommands.length === 0 && !onAddQuestionnaire) return null;
          return html`
            <div class="subsection">
              <div class="subsection-title">Questionnaires</div>
              ${questionnaireCommands.map(entry => html`
                <div class=${`content-block recommendation-block rec-questionnaire${entry.command.already_documented ? ' command-locked' : ''}`} key=${entry.index}>
                  ${entry.command.already_documented && ICON_LOCK}
                  <div class="recommendation-content">
                    <${QuestionnaireRow}
                      command=${entry.command}
                      commandIndex=${entry.index}
                      onEdit=${onEditCommand}
                      onDelete=${onDeleteCommand}
                      readOnly=${readOnly || entry.command.already_documented}
                      onEditingChange=${onEditingChange}
                    />
                  </div>
                  ${!readOnly && html`<div class="recommendation-actions"><button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button></div>`}
                </div>
              `)}
              ${onAddQuestionnaire && !readOnly && html`
                <div class="ad-hoc-buttons">
                  <button type="button" class="ad-hoc-btn" onClick=${onAddQuestionnaire}>+ Questionnaire</button>
                </div>
              `}
            </div>
          `;
        })()}
        ${(() => {
          // Build unified checklist: template charges + manually added charges.
          // A charge is "selected" if its command exists AND has selected=true.
          const chargeCommands = visibleAdHoc
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
          const visibleCharges = readOnly ? allItems.filter(c => c.isAdded) : allItems;
          if (visibleCharges.length === 0) return null;

          return html`
            <div class="charge-checklist">
              ${visibleCharges.map(c => html`
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
          // In readOnly mode, pending charges (no CPT) were never inserted — skip them.
          if (readOnly) return null;
          const pending = visibleAdHoc.filter(
            e => e.command.command_type === 'perform' && !e.command.data.cpt_code
          );
          if (pending.length === 0) return null;
          const allChecklistCpts = new Set([
            ...(templateCharges || []).map(c => c.cpt_code),
            ...visibleAdHoc.filter(e => e.command.command_type === 'perform' && e.command.data.cpt_code).map(e => e.command.data.cpt_code),
          ]);
          return pending.map(entry => html`
            <div class="content-block recommendation-block rec-charge" key=${entry.index}>
              <div class="recommendation-content">
                <${ChargeRow}
                  command=${entry.command}
                  commandIndex=${entry.index}
                  onEdit=${onEditCommand}
                  onDelete=${onDeleteCommand}
                  readOnly=${readOnly}
                  excludeCpts=${allChecklistCpts}
                  onEditingChange=${onEditingChange}
                />
              </div>
              ${!readOnly && html`<div class="recommendation-actions"><button type="button" class="rec-btn rec-btn-reject" onClick=${() => onDeleteCommand(entry.index)} title="Remove">${ICON_X}</button></div>`}
            </div>
          `);
        })()}
        ${onAddCharge && !readOnly && html`
          <div class="ad-hoc-buttons">
            <button type="button" class="ad-hoc-btn" onClick=${onAddCharge}>+ Charge</button>
          </div>
        `}
        ${(() => {
          // Render Rx recommendations in the PLAN group (raw prescription text is suppressed above).
          if (title !== 'ASSESSMENT & PLAN') return null;
          const rxRecs = visibleRecs
            .map(cmd => ({ command: cmd, index: cmd._origIndex }))
            .filter(e => e.command.command_type === 'prescribe');
          if (rxRecs.length === 0) return null;
          return html`
            <div class="subsection">
              <div class="subsection-title">Prescriptions</div>
              ${rxRecs.map(entry => {
                const d = entry.command.data;
                const missingFields = [];
                if (!d.fdb_code) missingFields.push('Medication');
                if (d.quantity_to_dispense == null) missingFields.push('Qty');
                if (!d.type_to_dispense) missingFields.push('Dispense type');
                if (!d.sig) missingFields.push('Sig');
                if (d.refills == null) missingFields.push('Refills');
                const isIncomplete = missingFields.length > 0;
                const isAccepted = entry.command.accepted && !entry.command.rejected;
                const isRejected = entry.command.rejected;

                return html`
                <div class=${`content-block recommendation-block rec-prescribe${isRejected ? ' rec-rejected' : ''}${entry.command.already_documented ? ' command-locked' : ''}`} key=${'rec-rx-' + entry.index}>
                  ${entry.command.already_documented && ICON_LOCK}
                  <div class="recommendation-content">
                    <${OrderRow}
                      command=${entry.command}
                      commandIndex=${entry.index}
                      onEdit=${onEditRecommendation}
                      readOnly=${readOnly || entry.command.already_documented || isRejected}
                      patientId=${patientId}
                      noteId=${noteId}
                      staffId=${staffId}
                      staffName=${staffName}
                      isRecommendation=${true}
                      onEditingChange=${onEditingChange}
                    />
                  </div>
                  <div class="recommendation-actions">
                    ${entry.command.already_documented
                      ? html`<span class="rec-documented-badge">${entry.command._added_now ? 'Added' : 'Already in chart'}</span>`
                      : !readOnly && html`
                          ${isIncomplete && !isRejected && html`<span class="rec-warning-pill">Missing: ${missingFields.join(', ')}</span>`}
                          ${isRejected && html`<span class="rec-rejected-badge">Rejected</span>`}
                          ${isAccepted && !isIncomplete && html`<span class="rec-accepted-badge">Accepted</span>`}
                          ${onAddNow && isAccepted && !isIncomplete && html`<button type="button" class="rec-btn-add-now" disabled=${entry.command._adding} onClick=${() => !entry.command._adding && onAddNow(entry.command, true, entry.index)}>${entry.command._adding ? 'Adding...' : 'Add Now'}</button>`}
                          ${!entry.command._adding && html`
                            <button type="button" class="rec-btn ${isRejected ? 'rec-btn-reject' : 'rec-btn-muted'}" onClick=${() => onRejectRecommendation(entry.index)} title="Reject">${ICON_X}</button>
                            <button type="button" class="rec-btn ${isAccepted && !isIncomplete ? 'rec-btn-accept' : 'rec-btn-muted'}" onClick=${() => (isRejected || !isIncomplete) && onAcceptRecommendation(entry.index)} title="Accept">${ICON_CHECK}</button>
                          `}
                        `
                    }
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
          const referRecs = visibleRecs
            .map(cmd => ({ command: cmd, index: cmd._origIndex }))
            .filter(e => e.command.command_type === 'refer');
          if (referRecs.length === 0) return null;
          return html`
            <div class="subsection">
              <div class="subsection-title">Referrals</div>
              ${referRecs.map(entry => {
                const missingFields = [];
                if (!entry.command.data.service_provider) missingFields.push('Provider');
                if (!entry.command.data.clinical_question) missingFields.push('Clinical question');
                if (!entry.command.data.notes_to_specialist) missingFields.push('Notes to specialist');
                if (!entry.command.data.diagnosis_codes || entry.command.data.diagnosis_codes.length === 0) missingFields.push('Indications');
                const isIncomplete = missingFields.length > 0;
                const isAccepted = entry.command.accepted && !entry.command.rejected;
                const isRejected = entry.command.rejected;

                return html`
                <div class=${`content-block recommendation-block rec-refer${isRejected ? ' rec-rejected' : ''}${entry.command.already_documented ? ' command-locked' : ''}`} key=${'rec-refer-' + entry.index}>
                  ${entry.command.already_documented && ICON_LOCK}
                  <div class="recommendation-content">
                    <${OrderRow}
                      command=${entry.command}
                      commandIndex=${entry.index}
                      onEdit=${onEditRecommendation}
                      readOnly=${readOnly || entry.command.already_documented || isRejected}
                      patientId=${patientId}
                      noteId=${noteId}
                      staffId=${staffId}
                      staffName=${staffName}
                      isRecommendation=${true}
                      onEditingChange=${onEditingChange}
                    />
                  </div>
                  <div class="recommendation-actions">
                    ${entry.command.already_documented
                      ? html`<span class="rec-documented-badge">${entry.command._added_now ? 'Added' : 'Already in chart'}</span>`
                      : !readOnly && html`
                          ${isIncomplete && !isRejected && html`<span class="rec-warning-pill">Missing: ${missingFields.join(', ')}</span>`}
                          ${isRejected && html`<span class="rec-rejected-badge">Rejected</span>`}
                          ${isAccepted && !isIncomplete && html`<span class="rec-accepted-badge">Accepted</span>`}
                          ${onAddNow && isAccepted && !isIncomplete && html`<button type="button" class="rec-btn-add-now" disabled=${entry.command._adding} onClick=${() => !entry.command._adding && onAddNow(entry.command, true, entry.index)}>${entry.command._adding ? 'Adding...' : 'Add Now'}</button>`}
                          ${!entry.command._adding && html`
                            <button type="button" class="rec-btn ${isRejected ? 'rec-btn-reject' : 'rec-btn-muted'}" onClick=${() => onRejectRecommendation(entry.index)} title="Reject">${ICON_X}</button>
                            <button type="button" class="rec-btn ${isAccepted && !isIncomplete ? 'rec-btn-accept' : 'rec-btn-muted'}" onClick=${() => (isRejected || !isIncomplete) && onAcceptRecommendation(entry.index)} title="Accept">${ICON_CHECK}</button>
                          `}
                        `
                    }
                  </div>
                </div>
                `;
              })}
            </div>
          `;
        })()}
        ${(() => {
          if (title !== 'ASSESSMENT & PLAN') return null;
          const taskRecs = visibleRecs
            .map(cmd => ({ command: cmd, index: cmd._origIndex }))
            .filter(e => e.command.command_type === 'task');
          if (taskRecs.length === 0) return null;
          return html`
            <div class="subsection">
              <div class="subsection-title">Recommended Tasks</div>
              ${taskRecs.map(entry => {
                const isAccepted = entry.command.accepted && !entry.command.rejected;
                const isRejected = entry.command.rejected;
                return html`
                <div class=${`content-block recommendation-block rec-task${isRejected ? ' rec-rejected' : ''}${entry.command.already_documented ? ' command-locked' : ''}`} key=${'rec-task-' + entry.index}>
                  ${entry.command.already_documented && ICON_LOCK}
                  <div class="recommendation-content">
                    <${TaskRow}
                      command=${entry.command}
                      commandIndex=${entry.index}
                      onEdit=${onEditRecommendation}
                      onDelete=${onDeleteRecommendation}
                      assignees=${assignees}
                      readOnly=${readOnly || entry.command.already_documented || isRejected}
                      onEditingChange=${onEditingChange}
                    />
                    ${entry.command.data.due_date_hint && html`<div class="rec-hint">Suggested timing: ${entry.command.data.due_date_hint}</div>`}
                    ${entry.command.data.assignee_hint && html`<div class="rec-hint">Suggested assignee: ${entry.command.data.assignee_hint}</div>`}
                  </div>
                  <div class="recommendation-actions">
                    ${entry.command.already_documented
                      ? html`<span class="rec-documented-badge">${entry.command._added_now ? 'Added' : 'Already in chart'}</span>`
                      : !readOnly && html`
                          ${isRejected && html`<span class="rec-rejected-badge">Rejected</span>`}
                          ${isAccepted && html`<span class="rec-accepted-badge">Accepted</span>`}
                          ${onAddNow && isAccepted && html`<button type="button" class="rec-btn-add-now" disabled=${entry.command._adding} onClick=${() => !entry.command._adding && onAddNow(entry.command, true, entry.index)}>${entry.command._adding ? 'Adding...' : 'Add Now'}</button>`}
                          ${!entry.command._adding && html`
                            <button type="button" class="rec-btn ${isRejected ? 'rec-btn-reject' : 'rec-btn-muted'}" onClick=${() => onRejectRecommendation(entry.index)} title="Reject">${ICON_X}</button>
                            <button type="button" class="rec-btn ${isAccepted ? 'rec-btn-accept' : 'rec-btn-muted'}" onClick=${() => onAcceptRecommendation(entry.index)} title="Accept">${ICON_CHECK}</button>
                          `}
                        `
                    }
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
          </div>
        `}
      </div>
    </div>
  `;
}
