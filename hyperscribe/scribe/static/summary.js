import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useCallback, useRef } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { SoapGroup, parseAPBlocks, matchCondition } from '/plugin-io/api/hyperscribe/scribe/static/soap-group.js';
import { useRecording } from '/plugin-io/api/hyperscribe/scribe/static/recording-hook.js';

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
  { key: 'current_medications', title: 'Medication List Updates', text: '' },
  { key: 'allergies', title: 'Allergy List Updates', text: '' },
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

function renderSoapGroups(sections, commandBySectionKey, onEditCommand, onDeleteCommand, { adHocCommands, objectiveAdHocCommands, historyAdHocCommands, subjectiveAdHocCommands, chargeAdHocCommands, assignees, onAddTask, onAddOrder, onAddPlan, onAddMedication, onAddAllergy, onAddStopMedication, onAddRemoveAllergy, onAddResolveCondition, onAddHistory, onAddQuestionnaire, onAddCharge, onAddTemplateCharge, onRemoveChargeByCpt, templateCharges, readOnly, sectionConditions, patientId, noteId, staffId, staffName, recommendations, onEditRecommendation, onDeleteRecommendation, onAcceptRecommendation, onAddCondition, unmatchedConditions, diagnosisSuggestions } = {}) {
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
        onAddMedication=${isObjective ? onAddMedication : null}
        onAddAllergy=${isObjective ? onAddAllergy : null}
        onAddStopMedication=${isObjective ? onAddStopMedication : null}
        onAddRemoveAllergy=${isObjective ? onAddRemoveAllergy : null}
        onAddResolveCondition=${isPlan ? onAddResolveCondition : null}
        onAddHistory=${isHistory ? onAddHistory : null}
        onAddQuestionnaire=${isObjective ? onAddQuestionnaire : null}
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
        onAcceptRecommendation=${(isObjective || isPlan) ? onAcceptRecommendation : null}
        onAddCondition=${isPlan ? onAddCondition : null}
        unmatchedConditions=${isPlan ? unmatchedConditions : null}
        diagnosisSuggestions=${isPlan ? diagnosisSuggestions : null}
      />`;
    })
    .filter(Boolean);
}

export function Scribe({ noteId, patientId, staffId, staffName, providerName, providerPhotoUrl, patientName, debugMode }) {
  const [noteData, setNoteData] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [commands, setCommands] = useState([]);
  const [inserting, setInserting] = useState(false);
  const [approved, setApproved] = useState(false);
  const [assignees, setAssignees] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [sectionConditions, setSectionConditions] = useState({});
  const [unmatchedConditions, setUnmatchedConditions] = useState([]);
  const [diagnosisSuggestions, setDiagnosisSuggestions] = useState({});
  const [progress, setProgress] = useState({ step: -1, total: 0, label: '' });
  const [prescriptionWarning, setPrescriptionWarning] = useState(false);

  // Template state.
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [mode, setMode] = useState(null); // null | 'ai'
  const [transcriptCollapsed, setTranscriptCollapsed] = useState(false);
  const [cachedTemplateName, setCachedTemplateName] = useState(null);

  // Recording hook.
  const recording = useRecording(noteId);

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

  // Load summary from cache (no auto-generate — provider clicks "Generate Summary" when ready).
  useEffect(() => {
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
            return;
          }
          // Cache without note — restore ad-hoc commands and mode.
          if (cached.commands && cached.commands.length > 0) {
            setCommands(cached.commands);
          }
        }
      } catch (err) {
        // Cache miss — start with empty skeleton.
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
  const commandsSaveRef = useRef(null);
  useEffect(() => {
    if (commandsSaveRef.current) clearTimeout(commandsSaveRef.current);
    commandsSaveRef.current = setTimeout(() => {
      saveSummaryToCache(noteData, commands, approved, {
        recommendations,
        unmatched_conditions: unmatchedConditions,
        diagnosis_suggestions: diagnosisSuggestions,
        selected_template_name: selectedTemplate?.name || null,
        mode: mode,
      });
    }, 500);
    return () => { if (commandsSaveRef.current) clearTimeout(commandsSaveRef.current); };
  }, [commands, recommendations, selectedTemplate, mode]);

  const handleGenerate = useCallback(async () => {
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
        }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setNoteData(data.note);
        setCommands(prev => {
          const adHocKeys = new Set(['_ad_hoc', '_objective_ad_hoc', '_history_ad_hoc', '_subjective_ad_hoc', '_charges_ad_hoc']);
          const existingAdHoc = prev.filter(c => adHocKeys.has(c.section_key));
          const generated = data.commands || [];
          const generatedTypes = new Set(generated.map(c => c.command_type));
          const templateKeep = prev.filter(c =>
            c._template_inserted && !adHocKeys.has(c.section_key) && !generatedTypes.has(c.command_type)
          );
          return [...generated, ...existingAdHoc, ...templateKeep];
        });
        setRecommendations(data.recommendations || []);
        setSectionConditions(data.section_conditions || {});
        setUnmatchedConditions(data.unmatched_conditions || []);
        setDiagnosisSuggestions(data.diagnosis_suggestions || {});
      }
    } catch (err) {
      setError('Failed to generate summary');
    } finally {
      setGenerating(false);
    }
  }, [noteId, selectedTemplate]);

  // Fetch assignees for task assignment (independent, small).
  useEffect(() => {
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

  // Load visit templates on mount.
  useEffect(() => {
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
      if (mode === 'ai' && !noteData && !generating) {
        handleGenerate();
      }
    }
    prevFinalizedRef.current = recording.finalized;
  }, [recording.finalized, mode, noteData, generating, handleGenerate]);

  // Set mode to 'ai' if we load a finalized transcript from cache (returning to a previous session).
  useEffect(() => {
    if (recording.finalized && mode === null && !noteData && !approved) {
      setMode('ai');
    }
  }, [recording.finalized, mode, noteData, approved]);

  const handleSelectTemplate = useCallback((e) => {
    const templateName = e.target.value;
    if (!templateName) {
      setSelectedTemplate(null);
      setCommands(prev => prev.filter(c => !c._template_inserted));
      saveSummaryToCache(noteData, commands, approved, {
        recommendations, unmatched_conditions: unmatchedConditions,
        diagnosis_suggestions: diagnosisSuggestions, selected_template_name: null,
      });
      return;
    }
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

  const handleStartAI = useCallback(() => {
    setMode('ai');
    recording.startRecording();
  }, [recording]);

  const handleStartManual = useCallback(() => {
    setMode('manual');
    // Pre-populate empty commands for all narrative sections so they render as editable text areas.
    const manualCommands = [
      { command_type: 'rfv', display: '', data: { comment: '' }, selected: true, section_key: 'chief_complaint', already_documented: false },
      { command_type: 'hpi', display: '', data: { narrative: '' }, selected: true, section_key: 'history_of_present_illness', already_documented: false },
      { command_type: 'vitals', display: '', data: {}, selected: true, section_key: 'vitals', already_documented: false },
      { command_type: 'plan', display: '', data: { narrative: '' }, selected: true, section_key: 'assessment_and_plan', already_documented: false },
    ];
    setCommands(prev => {
      // Keep any existing ad-hoc commands, add manual skeleton commands.
      const adHocKeys = new Set(['_ad_hoc', '_objective_ad_hoc', '_history_ad_hoc', '_subjective_ad_hoc', '_charges_ad_hoc']);
      const existing = prev.filter(c => adHocKeys.has(c.section_key));
      return [...manualCommands, ...existing];
    });
  }, []);


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
    if (approved) return;
    setCommands(prev => {
      const updated = prev.map((cmd, i) => {
        if (i !== index) return cmd;
        const type = newType || cmd.command_type;
        if (type === 'history_review' || type === 'chart_review' || type === 'ros') {
          const display = (newData.sections || []).map(s => s.title).join(' | ');
          return { ...cmd, data: newData, display };
        }
        if (type === 'vitals') {
          return { ...cmd, data: newData };
        }
        if (type === 'medication_statement') {
          return { ...cmd, data: newData, display: newData.medication_text || '' };
        }
        if (type === 'allergy') {
          return { ...cmd, data: newData, display: newData.allergy_text || '' };
        }
        if (type === 'task') {
          return { ...cmd, data: newData, display: newData.title || '' };
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
          const parts = [newData.past_medical_history, newData.comments].filter(Boolean);
          return { ...cmd, command_type: type, data: newData, display: parts.join(' — ') || '' };
        }
        if (type === 'surgicalHistory') {
          const parts = [newData.procedure_display, newData.comment].filter(Boolean);
          return { ...cmd, command_type: type, data: newData, display: parts.join(' — ') || '' };
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
          return { ...cmd, command_type: type, data: { ...newData, accepted }, display };
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
    if (approved) return;
    setCommands(prev => {
      const updated = prev.filter((_, i) => i !== index);
      saveSummaryToCache(noteData, updated, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions });
      return updated;
    });
  }, [approved, noteData, saveSummaryToCache, recommendations, unmatchedConditions, diagnosisSuggestions]);

  const handleAddTask = useCallback(() => {
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

  const handleEditRecommendation = useCallback((index, newData, newType) => {
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
    setRecommendations(prev => prev.map((cmd, i) =>
      i === index ? { ...cmd, accepted: !cmd.accepted } : cmd
    ));
  }, []);

  const handleDeleteRecommendation = useCallback((index) => {
    setRecommendations(prev => prev.filter((_, i) => i !== index));
  }, []);

  const handleAddAllergy = useCallback(() => {
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
    if (approved) return;
    setCommands(prev => prev.map(c =>
      c.command_type === 'perform' && c.data.cpt_code === cptCode
        ? { ...c, selected: false }
        : c
    ));
  }, [approved]);

  const handleAddCondition = useCallback((icd10Code, icd10Display, conditionId) => {
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
    setInserting(true);
    const insertable = commands.filter(c => {
      if (c.already_documented || !c.display) return false;
      if (c.command_type === 'imaging_order' && !c.data.service_provider) return false;
      if (c.command_type === 'prescribe' && (!c.data.fdb_code || !c.data.sig || c.data.quantity_to_dispense == null || !c.data.type_to_dispense || c.data.refills == null)) return false;
      if ((c.command_type === 'refill' || c.command_type === 'adjust_prescription') && !c.data.fdb_code) return false;
      if (c.command_type === 'perform' && (!c.data.cpt_code || c.selected === false)) return false;
      return true;
    });
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
    try {
      const res = await fetch(`${API_BASE}/insert-commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_uuid: noteId, commands: allInsertable }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        const hasPrescriptions = allInsertable.some(c => c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription');
        setApproved(true);
        saveSummaryToCache(noteData, commands, true, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });
        if (hasPrescriptions) {
          setPrescriptionWarning(true);
        } else {
          const port = window.__canvasPort && window.__canvasPort();
          if (port) {
            port.postMessage({ type: 'CLOSE_MODAL' });
          }
        }
      }
    } catch (err) {
      setError('Failed to insert commands');
    } finally {
      setInserting(false);
    }
  }, [commands, recommendations, noteId, noteData, saveSummaryToCache, unmatchedConditions, diagnosisSuggestions]);


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
  const showFooter = !approved && (mode === 'manual' || insertableCount > 0);

  const INCOMPLETE_LABELS = { diagnose: 'diagnose', imaging_order: 'imaging order', prescribe: 'prescription', refer: 'referral' };
  const incompleteTypes = [];
  for (const c of commands) {
    if (c.command_type === 'diagnose' && c.display && (!c.data.icd10_code || !c.data.accepted)) {
      if (!incompleteTypes.includes('diagnose')) incompleteTypes.push('diagnose');
    }
    if (c.command_type === 'imaging_order' && c.display && !c.data.service_provider) {
      if (!incompleteTypes.includes('imaging_order')) incompleteTypes.push('imaging_order');
    }
    if ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && c.display && (!c.data.fdb_code || !c.data.sig || c.data.quantity_to_dispense == null || !c.data.type_to_dispense || c.data.refills == null)) {
      if (!incompleteTypes.includes('prescribe')) incompleteTypes.push('prescribe');
    }
  }
  for (const c of recommendations) {
    if (!c.already_documented && c.display) {
      if (c.command_type === 'prescribe' && c.accepted && (!c.data.fdb_code || !c.data.sig || c.data.quantity_to_dispense == null || !c.data.type_to_dispense || c.data.refills == null)) {
        if (!incompleteTypes.includes('prescribe')) incompleteTypes.push('prescribe');
      }
      if (c.command_type === 'refer' && !c.data.service_provider) {
        if (!incompleteTypes.includes('refer')) incompleteTypes.push('refer');
      }
    }
  }
  const incompleteCount = commands.filter(c =>
    (c.command_type === 'diagnose' && c.display && (!c.data.icd10_code || !c.data.accepted)) ||
    (c.command_type === 'imaging_order' && c.display && !c.data.service_provider) ||
    ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && c.display && (!c.data.fdb_code || !c.data.sig || c.data.quantity_to_dispense == null || !c.data.type_to_dispense || c.data.refills == null))
  ).length + recommendations.filter(c =>
    !c.already_documented && c.display && (
      ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && c.accepted && (!c.data.fdb_code || !c.data.sig || c.data.quantity_to_dispense == null || !c.data.type_to_dispense || c.data.refills == null)) ||
      (c.command_type === 'refer' && !c.data.service_provider)
    )
  ).length;

  const effectiveSections = noteData ? noteData.sections : SKELETON_SECTIONS;
  const isRecording = recording.status === 'recording' || recording.status === 'paused';
  const showTopControls = !approved && !noteData && !isRecording && !recording.finalized && !generating && mode === null;

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
              <button class="finish-btn" onClick=${recording.finishRecording}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                Finish
              </button>
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
              ${isRecording && html`<span class="recording-dot"></span>`}
              <span>${isRecording
                ? (recording.status === 'paused' ? 'Paused' : 'Recording in progress')
                : 'Transcript'}</span>
              ${!isRecording && html`<span class="transcript-entry-count">(${recording.entries.filter(e => e.is_final).length})</span>`}
            </div>
            <span class="transcript-panel-toggle">${transcriptCollapsed ? 'Show' : 'Hide'}</span>
          </button>
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
      <div class="summary-body">
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
          onAddCondition: approved ? null : handleAddCondition,
          unmatchedConditions,
          diagnosisSuggestions,
        })}
      </div>
      ${prescriptionWarning && html`
        <div class="rx-verification-banner">
          <div class="rx-verification-icon">!</div>
          <div class="rx-verification-text">
            <strong>Prescriptions require verification</strong>
            <p>Please go to the <strong>Note</strong> tab to review and sign prescriptions before they are sent.</p>
          </div>
          <button class="rx-verification-close" onClick=${() => {
            const port = window.__canvasPort && window.__canvasPort();
            if (port) port.postMessage({ type: 'CLOSE_MODAL' });
          }}>I've reviewed — close</button>
        </div>
      `}
      ${showFooter && html`
        <div class="summary-footer">
          ${incompleteCount > 0 && html`
            <div class="summary-footer-warning">
              ${incompleteCount} incomplete ${incompleteCount === 1 ? 'item' : 'items'} will be skipped: ${incompleteTypes.map(t => INCOMPLETE_LABELS[t]).join(', ')}
            </div>
          `}
          <button
            class="insert-btn"
            onClick=${handleInsert}
            disabled=${inserting}
          >
            ${inserting ? 'Approving...' : 'Approve'}
          </button>
        </div>
      `}
    </div>
  `;
}
