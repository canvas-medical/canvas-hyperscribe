import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useCallback, useRef } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { SoapGroup, parseAPBlocks, matchCondition } from '/plugin-io/api/hyperscribe/scribe/static/soap-group.js';
import { useRecording } from '/plugin-io/api/hyperscribe/scribe/static/recording-hook.js';
import { initAuditLog, logEvent } from '/plugin-io/api/hyperscribe/scribe/static/audit-log.js';
import { connectScribeWS } from '/plugin-io/api/hyperscribe/scribe/static/scribe-ws.js';
import { FinishRecordingButton } from '/plugin-io/api/hyperscribe/scribe/static/finish-button.js';

const html = htm.bind(h);

function formatTime(ms) {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function TranscriptEntry({ speaker, start_offset_ms, text, is_final, providerName, providerPhotoUrl, patientName }) {
  const s = (speaker || '').toUpperCase();
  const isUnspecified = !s || s === 'UNSPECIFIED';
  const isProvider = s === 'DOCTOR' || s.includes('PROVIDER') || s.includes('DOCTOR');
  const isPatient = s === 'PATIENT' || s.includes('PATIENT');
  const time = formatTime(start_offset_ms);

  if (!is_final && isUnspecified) {
    return html`
      <div class="transcript-entry partial">
        <div class="entry-avatar listening">...</div>
        <div class="entry-content">
          <div class="entry-meta">
            <span class="entry-speaker listening-label">Listening</span>
            <span class="entry-time">${time}</span>
          </div>
          <p class="entry-text">${text}</p>
        </div>
      </div>
    `;
  }

  const role = isProvider ? 'provider' : isPatient ? 'patient' : 'unspecified';
  const label = isProvider ? (providerName || 'Provider') : isPatient ? (patientName || 'Patient') : 'Unspecified';
  const initial = isProvider ? 'Dr' : isPatient ? 'Pt' : '?';

  return html`
    <div class="transcript-entry ${is_final ? '' : 'partial'}">
      ${isProvider && providerPhotoUrl
        ? html`<img class="entry-avatar-img" src=${providerPhotoUrl} alt=${label} />`
        : html`<div class="entry-avatar ${role}">${initial}</div>`}
      <div class="entry-content">
        <div class="entry-meta">
          <span class="entry-speaker">${label}</span>
          <span class="entry-time">${time}</span>
        </div>
        <p class="entry-text">${text}</p>
      </div>
    </div>
  `;
}


function VerificationSummary({ result }) {
  const [expanded, setExpanded] = useState(false);
  const total = result.verified.length + result.failed.length;
  const headline = result.ok
    ? `All ${total} command(s) inserted successfully`
    : `${result.failed.length} of ${total} command(s) failed to insert`;
  return html`
    <div class="verification-banner ${result.ok ? 'verification-ok' : 'verification-error'}">
      <div class="verification-headline" onClick=${() => setExpanded(prev => !prev)}>
        <span>${headline}</span>
        <span class="verification-chevron ${expanded ? 'open' : ''}">\u25BE</span>
      </div>
      ${expanded && html`
        <div class="verification-details">
          ${result.failed.length > 0 && html`
            <div class="verification-group verification-group-failed">
              ${result.failed.map(f => html`
                <div class="verification-item" key=${f.command_uuid}>
                  <span class="verification-tag failed-tag">${f.command_type}</span>
                  <span>${f.display || ''}</span>
                </div>
              `)}
            </div>
          `}
          ${result.verified.map(v => html`
            <div class="verification-item" key=${v.command_uuid}>
              <span class="verification-tag passed-tag">${v.command_type}</span>
              <span>${v.display || ''}</span>
            </div>
          `)}
        </div>
      `}
    </div>
  `;
}

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';

const SOAP_GROUPS = [
  { title: 'SUBJECTIVE', color: 'subjective', keys: new Set(['chief_complaint', 'history_of_present_illness', 'review_of_systems']) },
  { title: 'HISTORY', color: 'history', keys: new Set(['past_medical_history', 'past_surgical_history',
    'past_obstetric_history', 'family_history', 'social_history']) },
  { title: 'OBJECTIVE', color: 'objective', keys: new Set(['vitals', 'physical_exam', 'lab_results', 'imaging_results',
    'current_medications', 'allergies', 'immunizations']) },
  { title: 'ASSESSMENT & PLAN', color: 'plan', keys: new Set(['plan', 'assessment_and_plan', 'prescription', 'appointments']) },
  { title: 'CHARGES', color: 'charges', keys: new Set(['charges']) },
];

const SKELETON_SECTIONS = [
  { key: 'chief_complaint', title: 'Chief Complaint', text: '' },
  { key: 'history_of_present_illness', title: 'History of Present Illness', text: '' },
  { key: 'past_medical_history', title: 'Past Medical History Discussed During Encounter', text: '' },
  { key: 'past_surgical_history', title: 'Past Surgical History', text: '' },
  { key: 'family_history', title: 'Family History', text: '' },
  { key: 'social_history', title: 'Social History', text: '' },
  { key: 'vitals', title: 'Vitals', text: '' },
  { key: 'physical_exam', title: 'Physical Exam', text: '' },
  { key: 'current_medications', title: 'Meds Discussed', text: '' },
  { key: 'allergies', title: 'Allergies Discussed', text: '' },
  { key: 'assessment_and_plan', title: 'Assessment & Plan', text: '' },
];

const PROGRESS_STEPS = [
  'Generating note',
  'Structuring the note',
  'Extracting commands',
  'Generating recommendations',
  'Suggesting diagnoses',
];

function buildCommandBySectionKey(commands) {
  const map = {};
  commands.forEach((cmd, index) => {
    if (cmd.section_key) {
      if (!map[cmd.section_key]) {
        map[cmd.section_key] = [];
      }
      map[cmd.section_key].push({ command: cmd, index });
    }
  });
  return map;
}

function renderSoapGroups(sections, commandBySectionKey, onEditCommand, onDeleteCommand, { adHocCommands, objectiveAdHocCommands, historyAdHocCommands, subjectiveAdHocCommands, chargeAdHocCommands, assignees, onAddTask, onAddOrder, onAddPlan, onAddMedication, onAddAllergy, onAddStopMedication, onAddRemoveAllergy, onAddResolveCondition, onAddHistory, onAddQuestionnaire, onAddCharge, onAddTemplateCharge, onRemoveChargeByCpt, templateCharges, readOnly, sectionConditions, patientId, noteId, staffId, staffName, recommendations, onEditRecommendation, onDeleteRecommendation, onAcceptRecommendation, onRejectRecommendation, onAddCondition, unmatchedConditions, diagnosisSuggestions, onAddNow, onAddVitals, hideRejected, alertFacilityEnabled, onEditingChange } = {}) {
  return SOAP_GROUPS
    .map(group => {
      const matching = sections.filter(s => group.keys.has(s.key.toLowerCase()));
      const isPlan = group.title === 'ASSESSMENT & PLAN';
      const isObjective = group.title === 'OBJECTIVE';
      const isHistory = group.title === 'HISTORY';
      const isSubjective = group.title === 'SUBJECTIVE';
      const isCharges = group.title === 'CHARGES';
      return html`<${SoapGroup}
        key=${group.title}
        title=${group.title}
        groupColor=${group.color}
        sections=${matching}
        commandBySectionKey=${commandBySectionKey}
        onEditCommand=${onEditCommand}
        onDeleteCommand=${onDeleteCommand}
        adHocCommands=${isPlan ? adHocCommands : isObjective ? objectiveAdHocCommands : isHistory ? historyAdHocCommands : isSubjective ? subjectiveAdHocCommands : isCharges ? chargeAdHocCommands : null}
        assignees=${isPlan ? assignees : null}
        onAddTask=${isPlan ? onAddTask : null}
        onAddOrder=${isPlan ? onAddOrder : null}
        onAddPlan=${isPlan ? onAddPlan : null}
        onAddVitals=${isObjective ? onAddVitals : null}
        onAddMedication=${isObjective ? onAddMedication : null}
        onAddAllergy=${isObjective ? onAddAllergy : null}
        onAddStopMedication=${isObjective ? onAddStopMedication : null}
        onAddRemoveAllergy=${isObjective ? onAddRemoveAllergy : null}
        onAddResolveCondition=${isPlan ? onAddResolveCondition : null}
        onAddHistory=${isHistory ? onAddHistory : null}
        onAddQuestionnaire=${isSubjective ? onAddQuestionnaire : null}
        onAddCharge=${isCharges ? onAddCharge : null}
        onAddTemplateCharge=${isCharges ? onAddTemplateCharge : null}
        onRemoveChargeByCpt=${isCharges ? onRemoveChargeByCpt : null}
        templateCharges=${isCharges ? templateCharges : null}
        readOnly=${readOnly}
        sectionConditions=${sectionConditions}
        patientId=${patientId}
        noteId=${noteId}
        staffId=${staffId}
        staffName=${staffName}
        recommendations=${(isObjective || isPlan) ? recommendations : null}
        onEditRecommendation=${(isObjective || isPlan) ? onEditRecommendation : null}
        onDeleteRecommendation=${(isObjective || isPlan) ? onDeleteRecommendation : null}
        onRejectRecommendation=${(isObjective || isPlan) ? onRejectRecommendation : null}
        onAcceptRecommendation=${(isObjective || isPlan) ? onAcceptRecommendation : null}
        onAddCondition=${isPlan ? onAddCondition : null}
        unmatchedConditions=${isPlan ? unmatchedConditions : null}
        diagnosisSuggestions=${isPlan ? diagnosisSuggestions : null}
        onAddNow=${(isPlan || isObjective) ? onAddNow : null}
        hideRejected=${hideRejected}
        alertFacilityEnabled=${alertFacilityEnabled}
        onEditingChange=${onEditingChange}
      />`;
    })
    .filter(Boolean);
}

export function Scribe({ noteId, patientId, staffId, staffName, providerName, providerPhotoUrl, patientName, patientBirthDate, patientGender, debugMode, noteEditable = true, alertFacilityEnabled = false, initialData = null }) {
  const initSummary = initialData?.summary ?? null;
  const [noteData, setNoteData] = useState(initSummary?.note ?? null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [commands, setCommands] = useState(initSummary?.commands ?? []);
  const [inserting, setInserting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [approved, setApproved] = useState(initSummary?.approved ?? false);
  const [isNoteEditable, setNoteEditable] = useState(noteEditable);
  const [hideRejected, setHideRejected] = useState(true);
  const [assignees, setAssignees] = useState(initialData?.assignees ?? []);
  const [recommendations, setRecommendations] = useState(initSummary?.recommendations ?? []);
  const [sectionConditions, setSectionConditions] = useState({});
  const [unmatchedConditions, setUnmatchedConditions] = useState(initSummary?.unmatched_conditions ?? []);
  const [diagnosisSuggestions, setDiagnosisSuggestions] = useState(initSummary?.diagnosis_suggestions ?? {});
  const [progress, setProgress] = useState({ step: -1, total: 0, label: '' });
  const [verificationResult, setVerificationResult] = useState(null);
  const [validationError, setValidationError] = useState(null);

  // Template state.
  const [templates, setTemplates] = useState(initialData?.templates ?? []);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [mode, setMode] = useState(() => {
    const cached = initSummary?.mode ?? null;
    // Dead state recovery: ai mode was persisted but recording was never started (e.g.
    // mic failure persisted mode before startRecording could revert it). Only applies
    // to 'ai' — manual mode legitimately has no transcript.
    if (cached === 'ai' && !initSummary?.note && !initialData?.transcript?.started) {
      return null;
    }
    return cached;
  });
  const [transcriptCollapsed, setTranscriptCollapsed] = useState(false);
  const [cachedTemplateName, setCachedTemplateName] = useState(initSummary?.selected_template_name ?? null);
  const cacheLoadedRef = useRef(!!initialData);
  const addNowAttemptedRef = useRef([]);

  const [editingFields, setEditingFields] = useState(new Set());

  // Recording hook.
  const recording = useRecording(noteId, initialData?.transcript);

  const [showSavedToast, setShowSavedToast] = useState(false);
  useEffect(() => {
    if (!recording.lastSaved) return;
    logEvent('TRANSCRIPT_AUTO_SAVED', { entryCount: recording.entries.length });
    setShowSavedToast(true);
    const timer = setTimeout(() => setShowSavedToast(false), 2000);
    return () => clearTimeout(timer);
  }, [recording.lastSaved]);

  // Audit logging.
  useEffect(() => { initAuditLog(noteId); }, [noteId]);

  // WebSocket: listen for note state changes in real time.
  useEffect(() => {
    if (!noteId) return;
    const cleanup = connectScribeWS(noteId, (msg) => {
      if (msg.type === 'NOTE_STATE_CHANGED') {
        setNoteEditable(msg.editable);
      }
    });
    return cleanup;
  }, [noteId]);

  const noteLocked = !isNoteEditable && !approved;

  const saveSummaryToCache = useCallback(async (note, cmds, isApproved, extras = {}) => {
    try {
      await fetch(`${API_BASE}/save-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_id: noteId, note, commands: cmds, approved: isApproved, ...extras }),
      });
    } catch (err) {
      console.error('Failed to save summary to cache:', err);
    }
  }, [noteId]);

  // Load summary from cache — skip if initial data was provided server-side.
  useEffect(() => {
    if (initialData) return;
    let cancelled = false;

    async function loadOrGenerate() {
      try {
        const cacheRes = await fetch(`${API_BASE}/summary?note_id=${encodeURIComponent(noteId)}`);
        if (!cancelled) {
          const cached = await cacheRes.json();
          // Restore cached template name (resolved against templates once they load).
          if (cached.selected_template_name) {
            setCachedTemplateName(cached.selected_template_name);
          }
          if (cached.mode) {
            setMode(cached.mode);
          }
          if (cached.approved) {
            setApproved(true);
          }
          if (cached.note) {
            // Full cached summary — restore everything.
            setNoteData(cached.note);
            setCommands(cached.commands || []);
            setRecommendations(cached.recommendations || []);
            setUnmatchedConditions(cached.unmatched_conditions || []);
            setDiagnosisSuggestions(cached.diagnosis_suggestions || {});
            // Repopulate Add Now attempted entries from cached items for verification merge.
            addNowAttemptedRef.current = [
              ...(cached.commands || []),
              ...(cached.recommendations || []),
            ]
              .filter(c => c._added_now && c.command_uuid)
              .map(c => ({
                command_uuid: c.command_uuid,
                command_type: c.command_type,
                display: (c.display || '').slice(0, 80),
              }));
            logEvent('CACHE_LOADED', { hasNote: !!cached.note, commandCount: (cached.commands || []).length });
            return;
          }
          // Cache without note — restore ad-hoc commands and mode.
          if (cached.commands && cached.commands.length > 0) {
            setCommands(cached.commands);
            logEvent('CACHE_LOADED', { hasNote: false, commandCount: cached.commands.length });
          }
        }
      } catch (err) {
        // Cache miss — start with empty skeleton.
      } finally {
        cacheLoadedRef.current = true;
      }
    }

    loadOrGenerate();
    return () => { cancelled = true; };
  }, [noteId]);

  // Poll progress while generating.
  useEffect(() => {
    if (!generating) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/summary-progress?note_id=${encodeURIComponent(noteId)}`);
        const data = await res.json();
        setProgress(data);
      } catch (err) {
        // Ignore polling errors.
      }
    }, 1500);
    return () => clearInterval(interval);
  }, [generating, noteId]);

  // Auto-save commands to cache (debounced) so ad-hoc items added before generation persist on reload.
  // Skip until cache has loaded to avoid overwriting persisted noteData with null.
  const commandsSaveRef = useRef(null);
  useEffect(() => {
    if (!cacheLoadedRef.current) return;
    if (commandsSaveRef.current) clearTimeout(commandsSaveRef.current);
    commandsSaveRef.current = setTimeout(() => {
      saveSummaryToCache(noteData, commands, approved || inserting, {
        recommendations,
        unmatched_conditions: unmatchedConditions,
        diagnosis_suggestions: diagnosisSuggestions,
        selected_template_name: selectedTemplate?.name || null,
        mode: mode,
      });
    }, 500);
    return () => { if (commandsSaveRef.current) clearTimeout(commandsSaveRef.current); };
  }, [commands, recommendations, selectedTemplate, mode, approved, inserting]);

  // Auto-verify on load when approved with command UUIDs.
  useEffect(() => {
    if (!approved || verificationResult) return;
    const withUuids = [
      ...commands.filter(c => c.command_uuid),
      ...recommendations.filter(c => c.command_uuid),
    ];
    if (withUuids.length === 0) return;
    const attempted = withUuids.map(c => ({
      command_uuid: c.command_uuid,
      command_type: c.command_type,
      display: (c.display || '').slice(0, 80),
    }));
    let cancelled = false;
    async function verify() {
      try {
        const res = await fetch(`${API_BASE}/verify-commands`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note_uuid: noteId, attempted }),
        });
        const data = await res.json();
        if (cancelled) return;
        const failedCount = data.failed?.length || 0;
        setVerificationResult(failedCount > 0
          ? { ok: false, verified: data.verified || [], failed: data.failed }
          : { ok: true, verified: data.verified || [], failed: [] });
      } catch (err) {
        console.error('Auto-verify failed:', err);
      }
    }
    verify();
    return () => { cancelled = true; };
  }, [approved, noteId, commands, recommendations]);

  const handleGenerate = useCallback(async () => {
    logEvent('GENERATE_START');
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/generate-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          note_id: noteId,
          note_uuid: noteId,
          patient_id: patientId,
          template_ros_sections: selectedTemplate?.ros_sections || null,
          template_pe_sections: selectedTemplate?.pe_sections || null,
          patient_context: {
            name: patientName || '',
            birth_date: patientBirthDate || '',
            gender: patientGender || '',
          },
        }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
        logEvent('GENERATE_ERROR', { error: data.error });
      } else {
        const adHocKeys = new Set(['_ad_hoc', '_objective_ad_hoc', '_history_ad_hoc', '_subjective_ad_hoc', '_charges_ad_hoc']);
        const existingAdHoc = commands.filter(c => adHocKeys.has(c.section_key));
        const generated = data.commands || [];
        const generatedTypes = new Set(generated.map(c => c.command_type));
        const templateKeep = commands.filter(c =>
          c._template_inserted && !adHocKeys.has(c.section_key) && !generatedTypes.has(c.command_type)
        );
        const newCommands = [...generated, ...existingAdHoc, ...templateKeep];
        const newRecs = data.recommendations || [];
        setNoteData(data.note);
        setCommands(newCommands);
        setRecommendations(newRecs);
        setSectionConditions(data.section_conditions || {});
        setUnmatchedConditions(data.unmatched_conditions || []);
        setDiagnosisSuggestions(data.diagnosis_suggestions || {});
        // Save to cache immediately so a refresh doesn't lose the generated note.
        saveSummaryToCache(data.note, newCommands, false, {
          recommendations: newRecs,
          unmatched_conditions: data.unmatched_conditions || [],
          diagnosis_suggestions: data.diagnosis_suggestions || {},
          selected_template_name: selectedTemplate?.name || null,
          mode: mode,
        });
        logEvent('GENERATE_COMPLETE', { commandCount: (data.commands || []).length, recCount: (data.recommendations || []).length });
      }
    } catch (err) {
      setError('Failed to generate summary');
      logEvent('GENERATE_ERROR', { error: err.message });
    } finally {
      setGenerating(false);
    }
  }, [noteId, selectedTemplate, commands, mode]);

  // Fetch assignees for task assignment (independent, small).
  useEffect(() => {
    if (initialData) return;
    let cancelled = false;
    async function fetchAssignees() {
      try {
        const res = await fetch(`${API_BASE}/assignees`, { cache: 'no-store' });
        if (cancelled) return;
        const data = await res.json();
        if (data.assignees) setAssignees(data.assignees);
      } catch (err) {
        console.error('Failed to fetch assignees:', err);
      }
    }
    fetchAssignees();
    return () => { cancelled = true; };
  }, []);

  // Load visit templates on mount — skip if initial data was provided server-side.
  useEffect(() => {
    if (initialData) return;
    let cancelled = false;
    async function loadTemplates() {
      try {
        const res = await fetch(`${API_BASE}/visit-templates`);
        const data = await res.json();
        if (!cancelled && data.templates) setTemplates(data.templates);
      } catch (err) {
        console.error('Failed to load visit templates:', err);
      }
    }
    loadTemplates();
    return () => { cancelled = true; };
  }, []);

  // Restore selected template from cache once templates are loaded.
  useEffect(() => {
    if (cachedTemplateName && templates.length > 0 && !selectedTemplate) {
      const match = templates.find(t => t.name === cachedTemplateName);
      if (match) setSelectedTemplate(match);
    }
  }, [cachedTemplateName, templates, selectedTemplate]);

  // Auto-generate summary after recording finishes.
  const prevFinalizedRef = useRef(false);
  useEffect(() => {
    if (recording.finalized && !prevFinalizedRef.current) {
      // Collapse transcript once recording is done.
      setTranscriptCollapsed(true);
      // Only auto-generate if cache has loaded (prevents regeneration on reload when
      // noteData hasn't been restored yet from cache).
      if (cacheLoadedRef.current && mode === 'ai' && !noteData && !generating) {
        handleGenerate();
      }
    }
    prevFinalizedRef.current = recording.finalized;
  }, [recording.finalized, mode, noteData, generating, handleGenerate]);

  // Warn before navigating away during recording or insertion.
  const activeRecording = recording.status === 'recording';
  useEffect(() => {
    if (!inserting && !activeRecording) return;
    const handler = (e) => { e.preventDefault(); };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [inserting, activeRecording]);

  // Set mode to 'ai' if we load a finalized transcript from cache (returning to a previous session).
  useEffect(() => {
    if (recording.finalized && mode === null && !noteData && !approved) {
      setMode('ai');
    }
  }, [recording.finalized, mode, noteData, approved]);


  const handleSelectTemplate = useCallback((e) => {
    const templateName = e.target.value;
    if (!templateName) {
      logEvent('DESELECT_TEMPLATE');
      setSelectedTemplate(null);
      setCommands(prev => prev.filter(c => !c._template_inserted));
      saveSummaryToCache(noteData, commands, approved, {
        recommendations, unmatched_conditions: unmatchedConditions,
        diagnosis_suggestions: diagnosisSuggestions, selected_template_name: null,
      });
      return;
    }
    logEvent('SELECT_TEMPLATE', { name: templateName });
    const tmpl = templates.find(t => t.name === templateName);
    if (!tmpl) return;
    setSelectedTemplate(tmpl);

    // Build questionnaire commands from the resolved template data.
    const qCommands = tmpl.questionnaires.map(q => ({
      command_type: 'questionnaire',
      display: q.questionnaire_name,
      data: {
        questionnaire_dbid: q.questionnaire_dbid,
        questionnaire_name: q.questionnaire_name,
        questions: q.questions.map(question => ({
          dbid: question.dbid,
          label: question.label,
          type: question.type,
          responses: question.options.map(o => ({
            dbid: o.dbid,
            value: (question.type === 'TXT' || question.type === 'INT') ? '' : o.value,
            selected: false,
            comment: null,
          })),
        })),
      },
      selected: true,
      section_key: '_subjective_ad_hoc',
      already_documented: false,
      _template_inserted: true,
    }));

    const templateCommands = [...qCommands];

    if (tmpl.ros_sections && tmpl.ros_sections.length > 0) {
      templateCommands.push({
        command_type: 'ros',
        display: tmpl.ros_sections.map(s => s.title).join(' | '),
        data: { sections: tmpl.ros_sections },
        selected: true,
        section_key: '_ros',
        already_documented: false,
        _template_inserted: true,
      });
    }

    if (tmpl.pe_sections && tmpl.pe_sections.length > 0) {
      templateCommands.push({
        command_type: 'physical_exam',
        display: tmpl.pe_sections.map(s => s.title).join(' | '),
        data: { sections: tmpl.pe_sections },
        selected: true,
        section_key: 'physical_exam',
        already_documented: false,
        _template_inserted: true,
      });
    }

    // Replace previous template commands, keep everything else.
    setCommands(prev => {
      const nonTemplate = prev.filter(c => !c._template_inserted);
      const updated = [...nonTemplate, ...templateCommands];
      saveSummaryToCache(noteData, updated, approved, {
        recommendations, unmatched_conditions: unmatchedConditions,
        diagnosis_suggestions: diagnosisSuggestions, selected_template_name: tmpl.name,
      });
      return updated;
    });
  }, [templates, noteData, approved, recommendations, unmatchedConditions, diagnosisSuggestions, saveSummaryToCache]);

  const handleStartAI = useCallback(async () => {
    logEvent('START_AI');
    setMode('ai');
    const ok = await recording.startRecording();
    if (!ok) {
      logEvent('START_AI_FAILED');
      setMode(null);
    }
  }, [recording]);

  const handleStartManual = useCallback(() => {
    logEvent('START_MANUAL');
    setMode('manual');
    // Pre-populate empty commands for all narrative sections so they render as editable text areas.
    const manualCommands = [
      { command_type: 'rfv', display: '', data: { comment: '' }, selected: true, section_key: 'chief_complaint', already_documented: false },
      { command_type: 'hpi', display: '', data: { narrative: '' }, selected: true, section_key: 'history_of_present_illness', already_documented: false },
      { command_type: 'vitals', display: '', data: {}, selected: true, section_key: 'vitals', already_documented: false },
      { command_type: 'plan', display: '', data: { narrative: '' }, selected: true, section_key: 'assessment_and_plan', already_documented: false },
    ];
    // Add PE from template if available.
    if (selectedTemplate?.pe_sections?.length > 0) {
      const peSections = selectedTemplate.pe_sections.map(s => ({ key: s.key, title: s.title, text: s.text, updated: false, template_text: s.text }));
      const peDisplay = peSections.map(s => s.title).join(' | ');
      manualCommands.push({ command_type: 'physical_exam', display: peDisplay, data: { sections: peSections }, selected: true, section_key: 'physical_exam', already_documented: false });
    }
    setCommands(prev => {
      // Keep any existing ad-hoc commands and template-inserted commands (ROS, PE, questionnaires).
      const adHocKeys = new Set(['_ad_hoc', '_objective_ad_hoc', '_history_ad_hoc', '_subjective_ad_hoc', '_charges_ad_hoc']);
      const existing = prev.filter(c => {
        if (c._template_inserted && c.command_type === 'physical_exam') return false;
        return adHocKeys.has(c.section_key) || c._template_inserted;
      });
      return [...manualCommands, ...existing];
    });
  }, [selectedTemplate]);


  // Compute unmatched conditions when loading from old cache format (no unmatched_conditions key).
  useEffect(() => {
    // Only run for cache loads where we have commands + sectionConditions but no unmatched_conditions.
    if (!noteData || !commands.length || unmatchedConditions.length > 0) return;
    if (!sectionConditions || !Object.keys(sectionConditions).length) return;
    const hasDiagnose = commands.some(c => c.command_type === 'diagnose');
    const hasPlan = commands.some(c =>
      c.command_type === 'plan' && ['assessment_and_plan', 'plan'].includes(c.section_key)
    );
    if (!hasDiagnose || hasPlan) return;

    const codes = sectionConditions['assessment_and_plan'] || sectionConditions['plan'] || [];
    if (!codes.length) return;
    const matchedSet = new Set();
    commands.filter(c => c.command_type === 'diagnose').forEach(c => {
      const m = matchCondition(c.data.condition_header || '', codes);
      if (m) matchedSet.add(m);
    });
    setUnmatchedConditions(codes.filter(c => !matchedSet.has(c)));
  }, [sectionConditions, commands, noteData, unmatchedConditions]);


  const handleEdit = useCallback((index, newData, newType) => {
    logEvent('EDIT_COMMAND', { index, commandType: newType || commands[index]?.command_type, sectionKey: commands[index]?.section_key, data: newData });
    if (approved) return;
    setCommands(prev => {
      const updated = prev.map((cmd, i) => {
        if (i !== index) return cmd;
        const type = newType || cmd.command_type;
        if (type === 'history_review' || type === 'chart_review' || type === 'ros' || type === 'physical_exam') {
          const display = (newData.sections || []).map(s => s.title).join(' | ');
          return { ...cmd, data: newData, display };
        }
        if (type === 'vitals') {
          const vParts = [];
          const sys = newData.blood_pressure_systole;
          const dia = newData.blood_pressure_diastole;
          if (sys != null && dia != null) vParts.push(`BP ${sys}/${dia} mmHg`);
          if (newData.pulse != null) vParts.push(`HR ${newData.pulse} bpm`);
          if (newData.respiration_rate != null) vParts.push(`RR ${newData.respiration_rate} /min`);
          if (newData.oxygen_saturation != null) vParts.push(`SpO2 ${newData.oxygen_saturation}%`);
          if (newData.body_temperature != null) vParts.push(`Temp ${newData.body_temperature} °F`);
          if (newData.height != null) vParts.push(`Height ${newData.height} in`);
          if (newData.weight_lbs != null) vParts.push(`Weight ${newData.weight_lbs} lbs`);
          if (newData.blood_pressure_position_and_site != null) {
            const siteLabels = {
              0: 'Sitting, Right Upper Arm', 1: 'Sitting, Left Upper Arm',
              2: 'Sitting, Right Lower Arm', 3: 'Sitting, Left Lower Arm',
              4: 'Standing, Right Upper Arm', 5: 'Standing, Left Upper Arm',
              6: 'Standing, Right Lower Arm', 7: 'Standing, Left Lower Arm',
              8: 'Supine, Right Upper Arm', 9: 'Supine, Left Upper Arm',
              10: 'Supine, Right Lower Arm', 11: 'Supine, Left Lower Arm',
            };
            const label = siteLabels[newData.blood_pressure_position_and_site];
            if (label) vParts.push(`Site: ${label}`);
          }
          if (newData.note) vParts.push(`Note: ${newData.note}`);
          return { ...cmd, data: newData, display: vParts.join(', ') || 'Vitals' };
        }
        if (type === 'medication_statement') {
          return { ...cmd, data: newData, display: newData.medication_text || '' };
        }
        if (type === 'allergy') {
          return { ...cmd, data: newData, display: newData.allergy_text || '' };
        }
        if (type === 'task') {
          const parts = [newData.title || ''];
          if (newData.comment) parts.push(`Comment: ${newData.comment}`);
          return { ...cmd, data: newData, display: parts.join(' \u2014 ') };
        }
        if (type === 'prescribe' || type === 'refill' || type === 'adjust_prescription') {
          return { ...cmd, command_type: type, data: newData, display: newData.medication_text || '' };
        }
        if (type === 'lab_order') {
          const parts = [];
          if (newData.lab_partner_name) parts.push(newData.lab_partner_name);
          if (newData.test_names && newData.test_names.length) parts.push(newData.test_names.join(', '));
          if (newData.comment) parts.push(newData.comment);
          if (newData.fasting_required) parts.push('Fasting');
          return { ...cmd, command_type: type, data: newData, display: parts.join(' | ') || '' };
        }
        if (type === 'imaging_order') {
          const parts = [newData.image_display, newData.additional_details, newData.comment, newData.priority].filter(Boolean);
          return { ...cmd, command_type: type, data: newData, display: parts.join(' | ') };
        }
        if (type === 'refer') {
          const parts = [newData.refer_to_display, newData.clinical_question, newData.priority].filter(Boolean);
          return { ...cmd, command_type: type, data: newData, display: parts.join(' | ') || 'Referral' };
        }
        if (type === 'familyHistory') {
          const parts = [newData.condition_display, newData.relative, newData.note].filter(Boolean);
          return { ...cmd, command_type: type, data: newData, display: parts.join(' — ') || '' };
        }
        if (type === 'medicalHistory') {
          const parts = [newData.past_medical_history];
          const dates = [newData.approximate_start_date, newData.approximate_end_date].filter(Boolean);
          if (dates.length) parts.push(dates.join(' – '));
          if (newData.comments) parts.push(newData.comments);
          return { ...cmd, command_type: type, data: newData, display: parts.filter(Boolean).join(' — ') || '' };
        }
        if (type === 'surgicalHistory') {
          const parts = [newData.procedure_display];
          if (newData.approximate_date) parts.push(newData.approximate_date);
          if (newData.comment) parts.push(newData.comment);
          return { ...cmd, command_type: type, data: newData, display: parts.filter(Boolean).join(' — ') || '' };
        }
        if (type === 'questionnaire') {
          return { ...cmd, command_type: type, data: newData, display: newData.questionnaire_name || '' };
        }
        if (type === 'perform') {
          const display = newData.cpt_code ? `${newData.cpt_code} — ${newData.description || ''}` : '';
          return { ...cmd, command_type: type, data: newData, display };
        }
        if (type === 'stop_medication') {
          return { ...cmd, command_type: type, data: newData, display: newData.medication_name || '' };
        }
        if (type === 'remove_allergy') {
          return { ...cmd, command_type: type, data: newData, display: newData.allergy_name || '' };
        }
        if (type === 'resolve_condition') {
          return { ...cmd, command_type: type, data: newData, display: newData.condition_name || '' };
        }
        if (type === 'diagnose') {
          const display = newData.icd10_display || newData.condition_header || cmd.display;
          const accepted = newData.icd10_code ? (newData.accepted !== undefined ? newData.accepted : true) : false;
          const rejected = newData.rejected || false;
          return { ...cmd, command_type: type, data: { ...newData, accepted, rejected }, display };
        }
        if (type === 'assess') {
          return { ...cmd, data: newData };
        }
        const field = cmd.command_type === 'rfv' ? 'comment' : 'narrative';
        const text = newData[field] || '';
        return { ...cmd, data: newData, display: text };
      });
      saveSummaryToCache(noteData, updated, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions });
      return updated;
    });
  }, [approved, noteData, saveSummaryToCache, recommendations, unmatchedConditions, diagnosisSuggestions]);

  const handleDelete = useCallback((index) => {
    logEvent('DELETE_COMMAND', { index, commandType: commands[index]?.command_type });
    if (approved) return;
    setCommands(prev => {
      const updated = prev.filter((_, i) => i !== index);
      saveSummaryToCache(noteData, updated, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions });
      return updated;
    });
  }, [approved, noteData, saveSummaryToCache, recommendations, unmatchedConditions, diagnosisSuggestions]);

  const handleAddTask = useCallback(() => {
    logEvent('ADD_TASK');
    if (approved) return;
    setCommands(prev => [...prev, {
      command_type: 'task',
      display: '',
      data: { title: '', due_date: null, assign_to: null, labels: [] },
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, [approved]);

  const handleAddOrder = useCallback(() => {
    logEvent('ADD_ORDER');
    if (approved) return;
    setCommands(prev => [...prev, {
      command_type: 'prescribe',
      display: '',
      data: {},
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, [approved]);

  const handleAddPlan = useCallback(() => {
    logEvent('ADD_PLAN');
    if (approved) return;
    setCommands(prev => [...prev, {
      command_type: 'plan',
      display: '',
      data: { narrative: '' },
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, [approved]);

  const handleAddHistory = useCallback((commandType) => {
    logEvent('ADD_HISTORY', { type: commandType });
    if (approved) return;
    setCommands(prev => [...prev, {
      command_type: commandType,
      display: '',
      data: {},
      selected: true,
      section_key: '_history_ad_hoc',
      already_documented: false,
    }]);
  }, [approved]);

  const handleAddMedication = useCallback(() => {
    logEvent('ADD_MEDICATION');
    if (approved) return;
    setCommands(prev => [...prev, {
      command_type: 'medication_statement',
      display: '',
      data: { medication_text: '', fdb_code: null, sig: '' },
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [approved]);

  const handleAddVitals = useCallback(() => {
    logEvent('ADD_VITALS');
    if (approved) return;
    setCommands(prev => [...prev, {
      command_type: 'vitals',
      display: '',
      data: {},
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [approved]);

  const handleEditRecommendation = useCallback((index, newData, newType) => {
    logEvent('EDIT_REC', { index, commandType: newType, data: newData });
    setRecommendations(prev => prev.map((cmd, i) => {
      if (i !== index) return cmd;
      const type = newType || cmd.command_type;
      if (type === 'medication_statement') {
        return { ...cmd, data: newData, display: newData.medication_text || '', accepted: true };
      }
      if (type === 'allergy') {
        return { ...cmd, data: newData, display: newData.allergy_text || '', accepted: true };
      }
      if (type === 'prescribe' || type === 'refill' || type === 'adjust_prescription') {
        return { ...cmd, command_type: type, data: newData, display: newData.medication_text || '', accepted: true };
      }
      if (type === 'refer') {
        const parts = [newData.refer_to_display, newData.clinical_question, newData.priority].filter(Boolean);
        return { ...cmd, command_type: type, data: newData, display: parts.join(' | ') || 'Referral', accepted: true };
      }
      return { ...cmd, data: newData, accepted: true };
    }));
  }, []);

  const handleAcceptRecommendation = useCallback((index) => {
    logEvent('ACCEPT_REC', { index });
    setRecommendations(prev => prev.map((cmd, i) =>
      i === index ? { ...cmd, accepted: true, rejected: false } : cmd
    ));
  }, []);

  const handleRejectRecommendation = useCallback((index) => {
    logEvent('REJECT_REC', { index });
    setRecommendations(prev => prev.map((cmd, i) =>
      i === index ? { ...cmd, rejected: true, accepted: false } : cmd
    ));
  }, []);

  const handleDeleteRecommendation = useCallback((index) => {
    logEvent('DELETE_REC', { index });
    setRecommendations(prev => prev.filter((_, i) => i !== index));
  }, []);

  const handleEditingChange = useCallback((key, isEditing) => {
    setEditingFields(prev => {
      const next = new Set(prev);
      if (isEditing) next.add(key);
      else next.delete(key);
      return next;
    });
  }, []);

  const handleAddAllergy = useCallback(() => {
    logEvent('ADD_ALLERGY');
    if (approved) return;
    setCommands(prev => [...prev, {
      command_type: 'allergy',
      display: '',
      data: { allergy_text: '', concept_id: null, concept_id_type: null, reaction: '', severity: null },
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [approved]);

  const handleAddStopMedication = useCallback(() => {
    logEvent('ADD_STOP_MED');
    if (approved) return;
    setCommands(prev => [...prev, {
      command_type: 'stop_medication',
      display: '',
      data: { medication_id: null, medication_name: '', rationale: '' },
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [approved]);

  const handleAddRemoveAllergy = useCallback(() => {
    logEvent('ADD_REMOVE_ALLERGY');
    if (approved) return;
    setCommands(prev => [...prev, {
      command_type: 'remove_allergy',
      display: '',
      data: { allergy_id: null, allergy_name: '', narrative: '' },
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [approved]);

  const handleAddResolveCondition = useCallback(() => {
    logEvent('ADD_RESOLVE_CONDITION');
    if (approved) return;
    setCommands(prev => [...prev, {
      command_type: 'resolve_condition',
      display: '',
      data: { condition_id: null, condition_name: '', rationale: '' },
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, [approved]);

  const handleAddQuestionnaire = useCallback(() => {
    logEvent('ADD_QUESTIONNAIRE');
    if (approved) return;
    setCommands(prev => [...prev, {
      command_type: 'questionnaire',
      display: '',
      data: { questionnaire_dbid: null, questionnaire_name: '', questions: [] },
      selected: true,
      section_key: '_subjective_ad_hoc',
      already_documented: false,
    }]);
  }, [approved]);

  const handleAddCharge = useCallback(() => {
    logEvent('ADD_CHARGE');
    if (approved) return;
    setCommands(prev => [...prev, {
      command_type: 'perform',
      display: '',
      data: { cpt_code: null, description: '', notes: '' },
      selected: true,
      section_key: '_charges_ad_hoc',
      already_documented: false,
    }]);
  }, [approved]);

  const handleAddTemplateCharge = useCallback((cptCode, description) => {
    logEvent('ADD_TEMPLATE_CHARGE', { cptCode, description });
    if (approved) return;
    setCommands(prev => {
      // Re-select if already exists but deselected.
      const existing = prev.find(c => c.command_type === 'perform' && c.data.cpt_code === cptCode);
      if (existing) {
        return prev.map(c =>
          c.command_type === 'perform' && c.data.cpt_code === cptCode
            ? { ...c, selected: true }
            : c
        );
      }
      return [...prev, {
        command_type: 'perform',
        display: `${cptCode} — ${description}`,
        data: { cpt_code: cptCode, description, notes: '' },
        selected: true,
        section_key: '_charges_ad_hoc',
        already_documented: false,
      }];
    });
  }, [approved]);

  const handleRemoveChargeByCpt = useCallback((cptCode) => {
    logEvent('REMOVE_CHARGE', { cptCode });
    if (approved) return;
    setCommands(prev => prev.map(c =>
      c.command_type === 'perform' && c.data.cpt_code === cptCode
        ? { ...c, selected: false }
        : c
    ));
  }, [approved]);

  const handleAddCondition = useCallback((icd10Code, icd10Display, conditionId) => {
    logEvent('ADD_CONDITION', { icd10Code, display: icd10Display });
    if (approved) return;
    const apKey = commands.find(c =>
      (c.command_type === 'diagnose' || c.command_type === 'assess') && ['assessment_and_plan', 'plan'].includes(c.section_key)
    )?.section_key || 'assessment_and_plan';

    const newCmd = conditionId
      ? {
          command_type: 'assess',
          display: icd10Display || '',
          data: {
            condition_id: conditionId,
            icd10_code: icd10Code || null,
            narrative: '',
            background: null,
            status: null,
          },
          section_key: apKey,
          already_documented: false,
        }
      : {
          command_type: 'diagnose',
          display: icd10Display || '',
          data: {
            icd10_code: icd10Code || null,
            icd10_display: icd10Display || '',
            condition_header: icd10Display || '',
            today_assessment: '',
            accepted: !!icd10Code,
          },
          selected: true,
          section_key: apKey,
          already_documented: false,
        };

    setCommands(prev => {
      const lastApIdx = prev.reduce((acc, c, i) =>
        (c.command_type === 'diagnose' || c.command_type === 'assess') && ['assessment_and_plan', 'plan'].includes(c.section_key) ? i : acc, -1);
      return lastApIdx === -1 ? [...prev, newCmd] : [...prev.slice(0, lastApIdx + 1), newCmd, ...prev.slice(lastApIdx + 1)];
    });

    if (icd10Code) {
      setUnmatchedConditions(prev => prev.filter(c => !(c.coding || []).some(cd => cd.code === icd10Code)));
    }
  }, [approved, commands]);

  const handleInsert = useCallback(async () => {
    if (approved || inserting) return;
    setValidationError(null);
    logEvent('APPROVE_START', { totalCommands: commands.length, commandTypes: commands.map(c => c.command_type) });
    setInserting(true);

    // Persist approved state to cache early so a page reload can't re-submit.
    saveSummaryToCache(noteData, commands, true, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });

    const SECTION_TYPES = new Set(['physical_exam', 'ros', 'chart_review', 'history_review']);
    const insertable = commands.filter(c => {
      if (c.already_documented) return false;
      if (!c.display && !(SECTION_TYPES.has(c.command_type) && c.data?.sections?.length > 0)) return false;
      if (c.command_type === 'imaging_order' && (!c.data.image_code || !c.data.service_provider || !c.data.ordering_provider_id || !c.data.diagnosis_codes || c.data.diagnosis_codes.length === 0)) return false;
      if (c.command_type === 'prescribe' && (!c.data.fdb_code || !c.data.sig || c.data.quantity_to_dispense == null || !c.data.type_to_dispense || c.data.refills == null)) return false;
      if ((c.command_type === 'refill' || c.command_type === 'adjust_prescription') && !c.data.fdb_code) return false;
      if (c.command_type === 'lab_order' && (!c.data.lab_partner || !c.data.tests_order_codes || c.data.tests_order_codes.length === 0)) return false;
      if (c.command_type === 'refer' && (!c.data.service_provider || !c.data.clinical_question || !c.data.notes_to_specialist || !c.data.diagnosis_codes || c.data.diagnosis_codes.length === 0)) return false;
      if (c.command_type === 'perform' && (!c.data.cpt_code || c.selected === false)) return false;
      return true;
    });
    const dropped = commands.filter(c => !c.already_documented && !insertable.includes(c));
    if (dropped.length > 0) {
      logEvent('COMMANDS_FILTERED', { dropped: dropped.map(c => ({
        type: c.command_type, display: (c.display || '').slice(0, 80), sectionKey: c.section_key,
        reason: !c.display ? 'empty_display' : c.selected === false ? 'deselected' : 'validation',
      })) });
    }
    const acceptedRecs = recommendations.filter(c => c.accepted && !c.already_documented && c.display);
    let allInsertable = [...insertable, ...acceptedRecs]
      .map(({ _template_inserted, ...c }) => c); // Strip internal marker.

    // Convert diagnose commands: match against patient conditions to decide assess vs diagnose.
    // Skip diagnose commands with no ICD code (provider didn't select one).
    try {
      const condRes = await fetch(
        `${API_BASE}/patient-conditions?patient_id=${encodeURIComponent(patientId)}`
      );
      const condData = await condRes.json();
      const patientConditions = condData.conditions || [];

      allInsertable = allInsertable
        .filter(c => c.command_type !== 'diagnose' || (c.data.icd10_code && c.data.accepted))
        .map(c => {
          if (c.command_type !== 'diagnose') return c;
          const code = (c.data.icd10_code || '').replace('.', '').toUpperCase();
          const match = patientConditions.find(pc => {
            const pcCode = (pc.code || '').replace('.', '').toUpperCase();
            return pcCode === code;
          });
          if (match) {
            return {
              ...c,
              command_type: 'assess',
              data: {
                condition_id: match.condition_id,
                narrative: c.data.today_assessment || '',
                background: c.data.background || null,
                status: null,
              },
            };
          }
          return c;
        });
    } catch (err) {
      console.error('Failed to fetch patient conditions for assess check:', err);
    }
    // Prescriptions first so they appear at the top of the note.
    const RX_SET = new Set(['prescribe', 'refill', 'adjust_prescription']);
    allInsertable.sort((a, b) => (RX_SET.has(a.command_type) ? 0 : 1) - (RX_SET.has(b.command_type) ? 0 : 1));
    logEvent('COMMANDS_SENDING', { commands: allInsertable.map(c => ({
      type: c.command_type, display: (c.display || '').slice(0, 80), sectionKey: c.section_key,
    })) });
    try {
      const res = await fetch(`${API_BASE}/insert-commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_uuid: noteId, commands: allInsertable }),
      });
      const data = await res.json();
      if (data.error) {
        if (data.validation_errors) {
          setValidationError(data.validation_errors);
        } else {
          setError(data.error);
        }
        setApproved(false);
        setConfirming(false);
        saveSummaryToCache(noteData, commands, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });
        logEvent('APPROVE_ERROR', { error: data.error, validation_errors: data.validation_errors });
      } else {
        // Phase 2: Insert metadata if any pending
        if (data.metadata_pending && data.metadata_pending.length > 0) {
          try {
            await fetch(`${API_BASE}/insert-metadata`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ pending: data.metadata_pending }),
            });
          } catch (metaErr) {
            console.error('Failed to insert metadata:', metaErr);
          }
        }
        // Stamp commands with their UUIDs and save immediately (before modal closes).
        let updatedCommands = commands;
        if (data.attempted && data.attempted.length > 0) {
          const uuidMap = new Map(data.attempted.map(a => [`${a.command_type}:${a.display}`, a.command_uuid]));
          updatedCommands = commands.map(cmd => {
            const key = `${cmd.command_type}:${(cmd.display || '').slice(0, 80)}`;
            const uuid = uuidMap.get(key);
            return uuid ? { ...cmd, command_uuid: uuid } : cmd;
          });
          setCommands(updatedCommands);
          saveSummaryToCache(noteData, updatedCommands, true, {
            recommendations, unmatched_conditions: unmatchedConditions,
            diagnosis_suggestions: diagnosisSuggestions,
            selected_template_name: selectedTemplate?.name || null, mode,
          });
        }
        const hasPrescriptions = commands.some(c => c.display && RX_SET.has(c.command_type))
          || recommendations.some(c => c.display && !c.rejected && RX_SET.has(c.command_type));
        logEvent('APPROVE_COMPLETE', { insertedCount: allInsertable.length, effectCount: data.inserted, hasPendingMetadata: (data.metadata_pending?.length || 0) > 0 });
        // Verify commands were actually created (include Add Now items).
        const allAttempted = [...addNowAttemptedRef.current, ...(data.attempted || [])];
        if (allAttempted.length > 0) {
          try {
            const verifyRes = await fetch(`${API_BASE}/verify-commands`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ note_uuid: noteId, attempted: allAttempted }),
            });
            const verifyData = await verifyRes.json();
            const failedCount = verifyData.failed?.length || 0;
            const verifiedCount = verifyData.verified?.length || 0;
            const vResult = failedCount > 0
              ? { ok: false, verified: verifyData.verified || [], failed: verifyData.failed }
              : { ok: true, verified: verifyData.verified || [], failed: [] };
            setVerificationResult(vResult);
            if (failedCount > 0) {
              logEvent('COMMANDS_FAILED', { failed: verifyData.failed });
            } else {
              logEvent('COMMANDS_VERIFIED', { total: verifiedCount });
            }
          } catch (verifyErr) {
            console.error('Verification failed:', verifyErr);
          }
        }
        setApproved(true);
          if (!hasPrescriptions) {
            try {
              await fetch(`${API_BASE}/sign-note`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ note_uuid: noteId }),
              });
              logEvent('NOTE_SIGNED');
            } catch (signErr) {
              console.error('Failed to sign note:', signErr);
            }
          }
          const port = window.__canvasPort && window.__canvasPort();
          if (port) port.postMessage({ type: 'CLOSE_MODAL' });
      }
    } catch (err) {
      setError('Failed to insert commands');
      setApproved(false);
      setConfirming(false);
      saveSummaryToCache(noteData, commands, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });
      logEvent('APPROVE_ERROR', { error: 'Failed to insert commands' });
    } finally {
      setInserting(false);
    }
  }, [commands, recommendations, noteId, noteData, saveSummaryToCache, unmatchedConditions, diagnosisSuggestions, approved, inserting]);

  const handleAddNow = useCallback(async (command, isRecommendation, index) => {
    logEvent('ADD_NOW', { commandType: command.command_type, isRecommendation, index });
    // Mark as adding to show spinner and prevent double-clicks.
    const setAdding = (flag) => {
      if (isRecommendation) {
        setRecommendations(prev => prev.map((rec, i) => i === index ? { ...rec, _adding: flag } : rec));
      } else {
        setCommands(prev => prev.map((cmd, i) => i === index ? { ...cmd, _adding: flag } : cmd));
      }
    };
    setAdding(true);
    try {
      const { _template_inserted, ...payload } = command;
      const res = await fetch(`${API_BASE}/insert-commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_uuid: noteId, commands: [payload] }),
      });
      const data = await res.json();
      if (data.error) { setAdding(false); logEvent('ADD_NOW_ERROR', { commandType: command.command_type, index }); return; }
      // Phase 2: insert metadata if needed (e.g. alert_facility).
      if (data.metadata_pending && data.metadata_pending.length > 0) {
        try {
          await fetch(`${API_BASE}/insert-metadata`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pending: data.metadata_pending }),
          });
        } catch (metaErr) { console.error('Add Now metadata failed:', metaErr); }
      }
      // Track attempted entry for verification merge with Approve All.
      const attemptedEntry = data.attempted && data.attempted[0];
      if (attemptedEntry) {
        addNowAttemptedRef.current.push(attemptedEntry);
      }
      if (isRecommendation) {
        setRecommendations(prev => prev.map((rec, i) =>
          i === index ? { ...rec, already_documented: true, accepted: true, _added_now: true, _adding: false, command_uuid: attemptedEntry?.command_uuid || null } : rec
        ));
      } else {
        setCommands(prev => prev.map((cmd, i) =>
          i === index ? { ...cmd, already_documented: true, _added_now: true, _adding: false, command_uuid: attemptedEntry?.command_uuid || null } : cmd
        ));
      }
      logEvent('ADD_NOW_SUCCESS', { commandType: command.command_type, index });
    } catch (err) {
      console.error('Add Now failed:', err);
      setAdding(false);
      logEvent('ADD_NOW_ERROR', { commandType: command.command_type, index });
    }
  }, [noteId]);


  const commandBySectionKey = buildCommandBySectionKey(commands);
  const adHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_ad_hoc');
  const objectiveAdHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_objective_ad_hoc');
  const historyAdHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_history_ad_hoc');
  const subjectiveAdHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_subjective_ad_hoc');
  const chargeAdHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_charges_ad_hoc');

  const insertableCount = commands.filter(c => {
    if (c.command_type === 'diagnose') return c.data.icd10_code && c.data.accepted && c.display;
    return !c.already_documented && c.display;
  }).length
    + recommendations.filter(c => c.accepted && !c.already_documented && c.display).length;
  const RX_TYPES = new Set(['prescribe', 'refill', 'adjust_prescription']);
  const hasRxCommands = commands.some(c => c.display && RX_TYPES.has(c.command_type))
    || recommendations.some(c => c.display && !c.rejected && RX_TYPES.has(c.command_type));
  const showFooter = !approved && (mode === 'manual' || insertableCount > 0);

  const INCOMPLETE_LABELS = { diagnose: 'diagnose', imaging_order: 'imaging order', prescribe: 'prescription', refer: 'referral', lab_order: 'lab order' };
  const _isRxIncomplete = (d) => !d.fdb_code || !d.sig || d.quantity_to_dispense == null || !d.type_to_dispense || d.refills == null;
  const _isLabIncomplete = (d) => !d.lab_partner || !d.tests_order_codes || d.tests_order_codes.length === 0;
  const _isImagingIncomplete = (d) => !d.image_code || !d.service_provider || !d.ordering_provider_id || !d.diagnosis_codes || d.diagnosis_codes.length === 0;
  const _isReferIncomplete = (d) => !d.service_provider || !d.clinical_question || !d.notes_to_specialist || !d.diagnosis_codes || d.diagnosis_codes.length === 0;
  const incompleteTypes = [];
  for (const c of commands) {
    if (c.already_documented) continue;
    if (c.command_type === 'imaging_order' && c.display && _isImagingIncomplete(c.data)) {
      if (!incompleteTypes.includes('imaging_order')) incompleteTypes.push('imaging_order');
    }
    if ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && c.display && _isRxIncomplete(c.data)) {
      if (!incompleteTypes.includes('prescribe')) incompleteTypes.push('prescribe');
    }
    if (c.command_type === 'lab_order' && c.display && _isLabIncomplete(c.data)) {
      if (!incompleteTypes.includes('lab_order')) incompleteTypes.push('lab_order');
    }
    if (c.command_type === 'refer' && c.display && _isReferIncomplete(c.data)) {
      if (!incompleteTypes.includes('refer')) incompleteTypes.push('refer');
    }
  }
  for (const c of recommendations) {
    if (c.already_documented || !c.display || c.rejected) continue;
    if ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && _isRxIncomplete(c.data)) {
      if (!incompleteTypes.includes('prescribe')) incompleteTypes.push('prescribe');
    }
    if (c.command_type === 'refer' && _isReferIncomplete(c.data)) {
      if (!incompleteTypes.includes('refer')) incompleteTypes.push('refer');
    }
  }
  const incompleteCount = commands.filter(c =>
    !c.already_documented && c.display && (
      (c.command_type === 'imaging_order' && _isImagingIncomplete(c.data)) ||
      ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && _isRxIncomplete(c.data)) ||
      (c.command_type === 'lab_order' && _isLabIncomplete(c.data)) ||
      (c.command_type === 'refer' && _isReferIncomplete(c.data))
    )
  ).length + recommendations.filter(c =>
    !c.already_documented && c.display && !c.rejected && (
      ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && _isRxIncomplete(c.data)) ||
      (c.command_type === 'refer' && _isReferIncomplete(c.data))
    )
  ).length;
  const UNDECIDED_LABELS = { diagnose: 'diagnosis', medication_statement: 'medication', allergy: 'allergy', prescribe: 'prescription', refill: 'prescription', adjust_prescription: 'prescription', refer: 'referral' };
  const undecidedTypes = [];
  for (const c of commands) {
    if (!c.already_documented && c.display && c.command_type === 'diagnose' && !c.data.accepted && !c.data.rejected) {
      if (!undecidedTypes.includes(c.command_type)) undecidedTypes.push(c.command_type);
    }
  }
  for (const c of recommendations) {
    if (!c.already_documented && c.display && !c.accepted && !c.rejected) {
      if (!undecidedTypes.includes(c.command_type)) undecidedTypes.push(c.command_type);
    }
  }
  const undecidedRecommendationCount = commands.filter(c =>
    !c.already_documented && c.display && c.command_type === 'diagnose' && !c.data.accepted && !c.data.rejected
  ).length + recommendations.filter(c =>
    !c.already_documented && c.display && !c.accepted && !c.rejected
  ).length;
  const hasUnsavedEdits = editingFields.size > 0;

  // Ensure sections with ad-hoc buttons are always present even if Nabla omits them.
  const ENSURE_KEYS = new Map([
    ['vitals', { key: 'vitals', title: 'Vitals', text: '' }],
    ['current_medications', { key: 'current_medications', title: 'Meds Discussed', text: '' }],
    ['allergies', { key: 'allergies', title: 'Allergies Discussed', text: '' }],
    ['past_medical_history', { key: 'past_medical_history', title: 'Past Medical History', text: '' }],
    ['past_surgical_history', { key: 'past_surgical_history', title: 'Past Surgical History', text: '' }],
    ['family_history', { key: 'family_history', title: 'Family History', text: '' }],
    ['lab_results', { key: 'lab_results', title: 'Lab Results', text: '' }],
    ['physical_exam', { key: 'physical_exam', title: 'Physical Exam', text: '' }],
  ]);
  const effectiveSections = (() => {
    const base = noteData ? noteData.sections : SKELETON_SECTIONS;
    const existing = new Set(base.map(s => s.key.toLowerCase()));
    const missing = [...ENSURE_KEYS.entries()].filter(([k]) => !existing.has(k)).map(([, v]) => v);
    return missing.length > 0 ? [...base, ...missing] : base;
  })();
  const isRecording = recording.status === 'recording' || recording.status === 'paused';
  const showTopControls = !approved && !noteData && !isRecording && !recording.finalized && !generating && mode === null;

  if (noteLocked) {
    return html`
      <div class="summary-container">
        <div class="signed-note-block">
          <div class="signed-note-icon">${'\uD83D\uDD12'}</div>
          <h2 class="signed-note-title">Note Locked</h2>
          <p class="signed-note-message">
            This note is no longer editable. To make changes, please amend the note first.
          </p>
        </div>
      </div>
    `;
  }

  return html`
    <div class="summary-container">
      ${!approved && html`
        <div class="unified-top-bar">
          ${templates.length > 0 && html`
            <select
              class="template-select"
              onChange=${handleSelectTemplate}
              value=${selectedTemplate ? selectedTemplate.name : ''}
              disabled=${approved || generating || noteData !== null || mode !== null}
            >
              <option value="">Select Visit Type</option>
              ${templates.map(t => html`<option key=${t.name} value=${t.name}>${t.name}</option>`)}
            </select>
          `}
          ${showTopControls && html`
            <button class="start-ai-btn" onClick=${handleStartAI} disabled=${!selectedTemplate}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="8" /></svg>
              Start AI Scribe
            </button>
            <button class="start-manual-btn" onClick=${handleStartManual} disabled=${!selectedTemplate}>
              Manual
            </button>
          `}
          ${isRecording && html`
            <div class="recording-controls-inline">
              ${recording.status === 'recording'
                ? html`<button class="control-btn" onClick=${recording.pauseRecording} title="Pause">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <rect x="6" y="5" width="4" height="14" rx="1" />
                      <rect x="14" y="5" width="4" height="14" rx="1" />
                    </svg>
                    Pause
                  </button>`
                : html`<button class="control-btn" onClick=${recording.resumeRecording} title="Resume">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <polygon points="6,4 20,12 6,20" />
                    </svg>
                    Resume
                  </button>`}
              <${FinishRecordingButton} onFinish=${recording.finishRecording} />
            </div>
          `}
          ${recording.status === 'finishing' && html`
            <span class="generating-label">Finalizing transcript...</span>
          `}
          ${false && debugMode && noteData && !approved && !generating && !isRecording && html`
            <button class="regenerate-btn" onClick=${handleGenerate} disabled=${!selectedTemplate}>
              Regenerate${!selectedTemplate ? ' (select visit type)' : ''}
            </button>
          `}
        </div>
      `}
      ${(isRecording || recording.entries.length > 0) && html`
        <div class="transcript-panel">
          <button class="transcript-panel-header ${isRecording ? '' : 'finalized'}" onClick=${() => setTranscriptCollapsed(prev => !prev)}>
            <div class="transcript-panel-status ${isRecording ? '' : 'finalized'}">
              ${isRecording && recording.status === 'recording' && html`
                <span class="recording-dot recording-dot-live"
                  style=${{
                    transform: `scale(${1 + Math.min(recording.audioLevel * 8, 1)})`,
                    opacity: 0.6 + Math.min(recording.audioLevel * 6, 0.4),
                  }}
                ></span>
              `}
              ${isRecording && recording.status === 'paused' && html`<span class="recording-dot recording-dot-paused"></span>`}
              <span>${isRecording
                ? (recording.status === 'paused' ? 'Paused' : 'Recording in progress')
                : 'Transcript'}</span>
              ${!isRecording && html`<span class="transcript-entry-count">(${recording.entries.filter(e => e.is_final).length})</span>`}
            </div>
            <span class="transcript-panel-toggle">${transcriptCollapsed ? 'Show' : 'Hide'}</span>
          </button>
          ${showSavedToast && html`<div class="transcript-saved-toast">Transcript saved</div>`}
          ${!transcriptCollapsed && html`
            <div class="transcript-panel-body">
              ${recording.entries.length > 0
                ? html`
                  <div class="transcript-list">
                    ${recording.entries.map((entry, i) => html`
                      <${TranscriptEntry}
                        key=${entry.item_id || i}
                        ...${entry}
                        providerName=${providerName}
                        providerPhotoUrl=${providerPhotoUrl}
                        patientName=${patientName}
                      />
                    `)}
                  </div>
                `
                : html`<p class="transcript-placeholder">Transcript will appear here as you speak...</p>`}
            </div>
          `}
        </div>
      `}
      ${recording.silenceWarning && recording.status === 'recording' && html`
        <div class="silence-warning">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink: 0;">
            <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
          </svg>
          No audio detected — check your microphone permissions and make sure it is not muted
        </div>
      `}
      ${recording.error && html`<p class="error" style="padding: 0 16px;">${recording.error}</p>`}
      ${generating && html`
        <div class="summary-generating-banner">
          <div class="generating-bar" style="width: ${Math.max(((progress.step + 1) / PROGRESS_STEPS.length) * 100, 5)}%" />
          <span class="generating-label">${PROGRESS_STEPS[Math.max(progress.step, 0)] || 'Generating...'}...</span>
        </div>
      `}
      ${!noteData && !generating && recording.finalized && mode === 'ai' && html`
        <div class="summary-generate-banner">
          <p class="summary-banner-description">Recording complete. Generate a structured summary from your transcript.</p>
          <button class="generate-btn" onClick=${handleGenerate}>Generate Summary</button>
        </div>
      `}
      ${error && html`<p class="error" style="padding: 0 16px;">${error}</p>`}
      ${!approved && recommendations.length > 0 && html`
        <div class="hide-rejected-toggle">
          <label class="hide-rejected-label" onClick=${() => setHideRejected(prev => !prev)}>
            <div class="toggle-switch${hideRejected ? ' on' : ''}">
              <div class="toggle-knob" />
            </div>
            Hide Rejected Recommendations
          </label>
        </div>
      `}
      <div class=${`summary-body${inserting ? ' summary-body--inserting' : ''}`}>
        ${renderSoapGroups(effectiveSections, commandBySectionKey, handleEdit, handleDelete, {
          adHocCommands,
          objectiveAdHocCommands,
          historyAdHocCommands,
          subjectiveAdHocCommands,
          chargeAdHocCommands,
          assignees,
          onAddTask: approved ? null : handleAddTask,
          onAddOrder: approved ? null : handleAddOrder,
          onAddPlan: approved ? null : handleAddPlan,
          onAddVitals: approved ? null : handleAddVitals,
          onAddMedication: approved ? null : handleAddMedication,
          onAddAllergy: approved ? null : handleAddAllergy,
          onAddStopMedication: approved ? null : handleAddStopMedication,
          onAddRemoveAllergy: approved ? null : handleAddRemoveAllergy,
          onAddResolveCondition: approved ? null : handleAddResolveCondition,
          onAddHistory: approved ? null : handleAddHistory,
          onAddQuestionnaire: approved ? null : handleAddQuestionnaire,
          onAddCharge: approved ? null : handleAddCharge,
          onAddTemplateCharge: approved ? null : handleAddTemplateCharge,
          onRemoveChargeByCpt: approved ? null : handleRemoveChargeByCpt,
          templateCharges: selectedTemplate ? (selectedTemplate.charges || []) : [],
          readOnly: approved,
          sectionConditions,
          patientId,
          noteId,
          staffId,
          staffName,
          recommendations,
          onEditRecommendation: handleEditRecommendation,
          onDeleteRecommendation: handleDeleteRecommendation,
          onAcceptRecommendation: handleAcceptRecommendation,
          onRejectRecommendation: handleRejectRecommendation,
          onAddCondition: approved ? null : handleAddCondition,
          unmatchedConditions,
          diagnosisSuggestions,
          onAddNow: approved ? null : handleAddNow,
          hideRejected,
          alertFacilityEnabled,
          onEditingChange: handleEditingChange,
        })}
      </div>
      ${verificationResult && html`<${VerificationSummary} result=${verificationResult} />`}
      ${validationError && html`
        <div class="validation-error">
          <strong>Please fix before approving:</strong>
          <ul>
            ${(Array.isArray(validationError) ? validationError : [{ display: '', errors: [validationError] }]).map(v => html`
              ${v.errors.map(e => html`<li key=${e}><strong>${v.display || v.command_type}</strong>: ${e}</li>`)}
            `)}
          </ul>
        </div>
      `}
      ${showFooter && html`
        <div class="summary-footer">
          ${inserting ? html`
            <div class="approve-progress">
              <div class="approve-spinner" />
              <span>Inserting ${insertableCount} ${insertableCount === 1 ? 'command' : 'commands'} into note...</span>
            </div>
          ` : confirming ? html`
            <div class="approve-confirm-block">
              ${hasUnsavedEdits && html`
                <div class="summary-footer-warning">
                  ${editingFields.size} unsaved ${editingFields.size === 1 ? 'edit' : 'edits'} \u2014 save or cancel to continue.
                </div>
              `}
              <button class="insert-btn confirm" disabled=${hasUnsavedEdits} onClick=${handleInsert}>${hasRxCommands ? 'Confirm: Accept and review prescriptions' : 'Confirm: Accept and sign'}</button>
              <button class="approve-cancel" onClick=${() => setConfirming(false)}>Cancel</button>
            </div>
          ` : html`
            <div class="approve-block">
              ${incompleteCount > 0 && html`
                <div class="summary-footer-warning">
                  ${incompleteCount} incomplete ${incompleteCount === 1 ? 'item' : 'items'} will be skipped: ${incompleteTypes.map(t => INCOMPLETE_LABELS[t]).join(', ')}
                </div>
              `}
              ${undecidedRecommendationCount > 0 && html`
                <div class="summary-footer-warning">
                  ${undecidedRecommendationCount} ${undecidedRecommendationCount === 1 ? 'recommendation needs' : 'recommendations need'} a decision, ${undecidedRecommendationCount === 1 ? 'it has' : 'they have'} not been accepted nor rejected: ${undecidedTypes.map(t => UNDECIDED_LABELS[t] || t).join(', ')}
                </div>
              `}
              ${hasUnsavedEdits && html`
                <div class="summary-footer-warning">
                  ${editingFields.size} unsaved ${editingFields.size === 1 ? 'edit' : 'edits'} \u2014 save or cancel to continue.
                </div>
              `}
              <button class="insert-btn" disabled=${undecidedRecommendationCount > 0 || hasUnsavedEdits} onClick=${() => setConfirming(true)}>${hasRxCommands ? 'Accept and review prescriptions' : 'Accept and sign'}</button>
              <div class="approve-warning">This action is permanent and cannot be undone.</div>
            </div>
          `}
        </div>
      `}
    </div>
  `;
}
