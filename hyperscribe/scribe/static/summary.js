import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useCallback, useRef } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { SoapGroup, parseAPBlocks, matchCondition } from '/plugin-io/api/hyperscribe/scribe/static/soap-group.js';

const html = htm.bind(h);

// ── DEV_MOCK: set to true to show a paste-box / mock-note picker instead of calling Nabla ──
const DEV_MOCK = false;

const DEV_MOCK_NOTE = {
  title: 'Mock Visit Note',
  sections: [
    { key: 'chief_complaint', title: 'Chief Complaint', text: 'Persistent right-sided headache for 3 days, rated 7/10, worse with screen exposure.' },
    { key: 'history_of_present_illness', title: 'History of Present Illness', text: 'Patient reports a 3-day history of right-sided throbbing headache. Pain worsens with bright lights and prolonged screen use. Associated photophobia and intermittent nausea. Has been taking ibuprofen 400mg TID with minimal relief. Denies fever, neck stiffness, or recent head trauma.' },
    { key: 'past_medical_history', title: 'Past Medical History', text: 'Hypertension diagnosed 2018, well-controlled on lisinopril. Type 2 diabetes diagnosed 2020, managed with metformin. History of seasonal allergies.' },
    { key: 'past_surgical_history', title: 'Past Surgical History', text: 'Appendectomy in 2010. Right knee arthroscopy in 2015.' },
    { key: 'past_obstetric_history', title: 'Past Obstetric History', text: 'G2P2, both uncomplicated vaginal deliveries (2012, 2016). No gestational diabetes or preeclampsia.' },
    { key: 'family_history', title: 'Family History', text: 'Father: Type 2 diabetes, coronary artery disease. Mother: Migraine headaches, hypothyroidism. Sister: Asthma.' },
    { key: 'social_history', title: 'Social History', text: 'Non-smoker. Occasional alcohol use (1-2 drinks/week). Works as a software engineer. Exercises 3x/week. No recreational drug use.' },
    { key: 'allergies', title: 'Allergies', text: 'Penicillin (rash). Sulfa drugs (hives).' },
    { key: 'current_medications', title: 'Current Medications', text: '- Lisinopril 10mg daily\n- Metformin 500mg BID\n- Ibuprofen 400mg PRN' },
    { key: 'vitals', title: 'Vitals', text: 'BP 128/82, HR 76, Temp 98.6F, RR 16, SpO2 99%' },
    { key: 'assessment_and_plan', title: 'Assessment & Plan', text: 'Migraine without aura. Likely triggered by increased screen time and stress.\n\nStart sumatriptan 50mg at onset of migraine. Continue current medications. Lifestyle modifications: reduce screen time, ensure adequate hydration, regular sleep schedule.' },
  ],
};

// ── END DEV_MOCK ──

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';

const SOAP_GROUPS = [
  { title: 'SUBJECTIVE', color: 'subjective', keys: new Set(['chief_complaint', 'history_of_present_illness', 'review_of_systems']) },
  { title: 'HISTORY', color: 'history', keys: new Set(['past_medical_history', 'past_surgical_history',
    'past_obstetric_history', 'family_history', 'social_history']) },
  { title: 'OBJECTIVE', color: 'objective', keys: new Set(['vitals', 'lab_results', 'imaging_results',
    'current_medications', 'allergies', 'immunizations']) },
  { title: 'PLAN', color: 'plan', keys: new Set(['plan', 'assessment_and_plan', 'prescription', 'appointments']) },
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

function renderSoapGroups(sections, commandBySectionKey, onEditCommand, onDeleteCommand, { adHocCommands, objectiveAdHocCommands, assignees, onAddTask, onAddOrder, onAddMedication, onAddAllergy, readOnly, sectionConditions, patientId, noteId, staffId, staffName, recommendations, onEditRecommendation, onDeleteRecommendation, onAcceptRecommendation, onAddCondition, unmatchedConditions, diagnosisSuggestions } = {}) {
  return SOAP_GROUPS
    .map(group => {
      const matching = sections.filter(s => group.keys.has(s.key.toLowerCase()));
      const isPlan = group.title === 'PLAN';
      const isObjective = group.title === 'OBJECTIVE';
      if (matching.length === 0 && !isPlan) return null;
      return html`<${SoapGroup}
        key=${group.title}
        title=${group.title}
        groupColor=${group.color}
        sections=${matching}
        commandBySectionKey=${commandBySectionKey}
        onEditCommand=${onEditCommand}
        onDeleteCommand=${onDeleteCommand}
        adHocCommands=${isPlan ? adHocCommands : isObjective ? objectiveAdHocCommands : null}
        assignees=${isPlan ? assignees : null}
        onAddTask=${isPlan ? onAddTask : null}
        onAddOrder=${isPlan ? onAddOrder : null}
        onAddMedication=${isObjective ? onAddMedication : null}
        onAddAllergy=${isObjective ? onAddAllergy : null}
        readOnly=${readOnly}
        sectionConditions=${sectionConditions}
        patientId=${patientId}
        noteId=${noteId}
        staffId=${staffId}
        staffName=${staffName}
        recommendations=${isObjective ? recommendations : null}
        onEditRecommendation=${isObjective ? onEditRecommendation : null}
        onDeleteRecommendation=${isObjective ? onDeleteRecommendation : null}
        onAcceptRecommendation=${isObjective ? onAcceptRecommendation : null}
        onAddCondition=${isPlan ? onAddCondition : null}
        unmatchedConditions=${isPlan ? unmatchedConditions : null}
        diagnosisSuggestions=${isPlan ? diagnosisSuggestions : null}
      />`;
    })
    .filter(Boolean);
}

export function Summary({ noteId, patientId, staffId, staffName }) {
  const [noteData, setNoteData] = useState(null);
  const [generating, setGenerating] = useState(true);
  const [error, setError] = useState(null);
  const [commands, setCommands] = useState([]);
  const [extracting, setExtracting] = useState(false);
  const [inserting, setInserting] = useState(false);
  const [approved, setApproved] = useState(false);
  const [assignees, setAssignees] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [recommending, setRecommending] = useState(false);
  const [sectionConditions, setSectionConditions] = useState({});
  const [unmatchedConditions, setUnmatchedConditions] = useState([]);
  const [diagnosisSuggestions, setDiagnosisSuggestions] = useState({});
  const [seedText, setSeedText] = useState('');
  const [seedError, setSeedError] = useState(null);
  const mockLoaded = useRef(false);
  const suggestionsFetched = useRef(false);

  const saveSummaryToCache = useCallback(async (note, cmds, isApproved) => {
    try {
      await fetch(`${API_BASE}/save-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_id: noteId, note, commands: cmds, approved: isApproved }),
      });
    } catch (err) {
      console.error('Failed to save summary to cache:', err);
    }
  }, [noteId]);

  // Generate note on mount (skip when DEV_MOCK — paste box handles it).
  useEffect(() => {
    if (DEV_MOCK) return;
    let cancelled = false;

    async function loadOrGenerate() {
      // Try cache first.
      try {
        const cacheRes = await fetch(`${API_BASE}/summary?note_id=${encodeURIComponent(noteId)}`);
        if (!cancelled) {
          const cached = await cacheRes.json();
          if (cached.note) {
            mockLoaded.current = true;
            setNoteData(cached.note);
            setCommands(cached.commands || []);
            setApproved(Boolean(cached.approved));
            setGenerating(false);
            return;
          }
        }
      } catch (err) {
        // Cache miss — fall through to generate.
      }

      // No cached summary — try generating automatically.
      try {
        const res = await fetch(`${API_BASE}/generate-note`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note_id: noteId }),
        });
        if (cancelled) return;
        const data = await res.json();
        if (data.error) {
          setError(data.error);
        } else {
          setNoteData(data);
        }
      } catch (err) {
        if (!cancelled) setError('Failed to generate note');
      } finally {
        if (!cancelled) setGenerating(false);
      }
    }

    loadOrGenerate();
    return () => { cancelled = true; };
  }, [noteId]);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/generate-note`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_id: noteId }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setNoteData(data);
      }
    } catch (err) {
      setError('Failed to generate note');
    } finally {
      setGenerating(false);
    }
  }, [noteId]);

  // Extract commands once note is available.
  useEffect(() => {
    if (!noteData) return;

    let cancelled = false;

    async function extractCommands() {
      setExtracting(true);
      try {
        const res = await fetch(`${API_BASE}/extract-commands`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note: noteData, note_uuid: noteId }),
        });
        if (cancelled) return;
        const data = await res.json();
        if (data.commands) {
          setCommands(data.commands);
          // Save initial summary to cache.
          saveSummaryToCache(noteData, data.commands, false);
        }
      } catch (err) {
        console.error('Failed to extract commands:', err);
      } finally {
        if (!cancelled) {
          setExtracting(false);
        }
      }
    }

    extractCommands();
    return () => { cancelled = true; };
  }, [noteData]);

  // Fetch LLM-based recommendations in parallel with extract-commands.
  useEffect(() => {
    if (!noteData) return;

    let cancelled = false;

    async function fetchRecommendations() {
      setRecommending(true);
      try {
        const res = await fetch(`${API_BASE}/recommend-commands`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note: noteData, note_uuid: noteId }),
        });
        if (cancelled) return;
        const data = await res.json();
        if (data.commands) {
          setRecommendations(data.commands);
        }
      } catch (err) {
        console.error('Failed to fetch recommendations:', err);
      } finally {
        if (!cancelled) {
          setRecommending(false);
        }
      }
    }

    fetchRecommendations();
    return () => { cancelled = true; };
  }, [noteData]);

  // Fetch normalized data (ICD-10 codes per section) in parallel.
  useEffect(() => {
    if (!noteData) return;

    let cancelled = false;

    async function fetchNormalizedData() {
      try {
        const res = await fetch(`${API_BASE}/generate-normalized-data`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note: noteData }),
        });
        if (cancelled) return;
        const data = await res.json();
        if (data.section_conditions) {
          setSectionConditions(data.section_conditions);
        }
      } catch (err) {
        console.error('Failed to fetch normalized data:', err);
      }
    }

    fetchNormalizedData();
    return () => { cancelled = true; };
  }, [noteData]);

  // Split A&P plan command into per-condition diagnose commands once normalized data arrives.
  const apSplitDone = useRef(false);
  useEffect(() => {
    if (!sectionConditions || !commands.length || apSplitDone.current) return;
    const apIdx = commands.findIndex(c =>
      c.command_type === 'plan' && (c.section_key === 'assessment_and_plan' || c.section_key === 'plan')
    );
    if (apIdx === -1) return;
    const apCmd = commands[apIdx];
    const codes = sectionConditions['assessment_and_plan'] || sectionConditions['plan'] || [];
    const blocks = parseAPBlocks(apCmd.data.narrative);
    if (blocks.length === 0) return;

    const diagnoseCommands = blocks.map(block => {
      const matched = matchCondition(block.header, codes);
      const icd = matched && (matched.coding || []).find(c => c.code);
      return {
        command_type: 'diagnose',
        display: icd ? (icd.display || matched.display || block.header) : block.header,
        data: {
          icd10_code: icd ? icd.code : null,
          icd10_display: icd ? (icd.display || matched.display || '') : '',
          condition_header: block.header,
          today_assessment: block.body.join('\n'),
        },
        selected: true,
        section_key: apCmd.section_key,
        already_documented: false,
      };
    });

    // Track which sectionConditions were NOT matched to any A&P block.
    const matchedSet = new Set();
    blocks.forEach(block => {
      const m = matchCondition(block.header, codes);
      if (m) matchedSet.add(m);
    });
    setUnmatchedConditions((codes || []).filter(c => !matchedSet.has(c)));

    apSplitDone.current = true;
    setCommands(prev => [
      ...prev.slice(0, apIdx),
      ...diagnoseCommands,
      ...prev.slice(apIdx + 1),
    ]);
  }, [sectionConditions, commands]);

  // Compute unmatched conditions when commands are loaded from cache (apSplit won't run).
  const unmatchedComputedFromCache = useRef(false);
  useEffect(() => {
    if (unmatchedComputedFromCache.current || apSplitDone.current) return;
    if (!sectionConditions || !commands.length) return;
    const hasDiagnose = commands.some(c => c.command_type === 'diagnose');
    const hasPlan = commands.some(c =>
      c.command_type === 'plan' && ['assessment_and_plan', 'plan'].includes(c.section_key)
    );
    // Cache path: diagnose commands exist but no plan command to split.
    if (!hasDiagnose || hasPlan) return;
    unmatchedComputedFromCache.current = true;

    const codes = sectionConditions['assessment_and_plan'] || sectionConditions['plan'] || [];
    if (!codes.length) return;
    const matchedSet = new Set();
    commands.filter(c => c.command_type === 'diagnose').forEach(c => {
      const m = matchCondition(c.data.condition_header || '', codes);
      if (m) matchedSet.add(m);
    });
    setUnmatchedConditions(codes.filter(c => !matchedSet.has(c)));
  }, [sectionConditions, commands]);

  // Fetch LLM suggestions for diagnose blocks that have no ICD code.
  useEffect(() => {
    if (suggestionsFetched.current) return;
    const hasDiagnose = commands.some(c => c.command_type === 'diagnose');
    if (!hasDiagnose) return;
    // Wait for apSplit OR cache-loaded diagnose commands (no plan command left).
    const hasPlan = commands.some(c =>
      c.command_type === 'plan' && ['assessment_and_plan', 'plan'].includes(c.section_key)
    );
    if (hasPlan) return;  // Still waiting for split.
    const unmatchedHeaders = commands
      .filter(c => c.command_type === 'diagnose' && !c.data.icd10_code)
      .map(c => c.data.condition_header)
      .filter(Boolean);
    if (!unmatchedHeaders.length) return;
    suggestionsFetched.current = true;
    fetch(`${API_BASE}/suggest-diagnoses`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conditions: unmatchedHeaders }),
    })
      .then(r => r.json())
      .then(data => { if (data.suggestions) setDiagnosisSuggestions(data.suggestions); })
      .catch(err => console.error('Diagnosis suggestion failed:', err));
  }, [commands]);

  // Fetch assignees for task assignment.
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

  const handleSeedGenerate = useCallback(async () => {
    let items;
    try {
      items = JSON.parse(seedText);
      if (!Array.isArray(items)) throw new Error('Must be an array');
    } catch (e) {
      setSeedError('Invalid JSON: ' + e.message);
      return;
    }
    setSeedError(null);
    setGenerating(true);
    try {
      await fetch(`${API_BASE}/save-transcript`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_id: noteId, transcript: { items } }),
      });
      const res = await fetch(`${API_BASE}/generate-note`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_id: noteId }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setNoteData(data);
      }
    } catch (err) {
      setError('Failed to generate note');
    } finally {
      setGenerating(false);
    }
  }, [seedText, noteId]);

  const handleUseMock = useCallback(() => {
    setNoteData(DEV_MOCK_NOTE);
    setGenerating(false);
  }, []);

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
        if (type === 'prescribe') {
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
        if (type === 'diagnose') {
          const display = newData.icd10_display || newData.condition_header || cmd.display;
          const accepted = newData.icd10_code ? (newData.accepted !== undefined ? newData.accepted : true) : false;
          return { ...cmd, command_type: type, data: { ...newData, accepted }, display };
        }
        const field = cmd.command_type === 'rfv' ? 'comment' : 'narrative';
        const text = newData[field] || '';
        return { ...cmd, data: newData, display: text };
      });
      saveSummaryToCache(noteData, updated, false);
      return updated;
    });
  }, [approved, noteData, saveSummaryToCache]);

  const handleDelete = useCallback((index) => {
    if (approved) return;
    setCommands(prev => {
      const updated = prev.filter((_, i) => i !== index);
      saveSummaryToCache(noteData, updated, false);
      return updated;
    });
  }, [approved, noteData, saveSummaryToCache]);

  const handleAddTask = useCallback(() => {
    if (approved) return;
    setCommands(prev => [...prev, {
      command_type: 'task',
      display: '',
      data: { title: '', due_date: null, assign_to: null },
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

  const handleAddCondition = useCallback((icd10Code, icd10Display) => {
    if (approved) return;
    const apKey = commands.find(c =>
      c.command_type === 'diagnose' && ['assessment_and_plan', 'plan'].includes(c.section_key)
    )?.section_key || 'assessment_and_plan';

    const newCmd = {
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
        c.command_type === 'diagnose' && ['assessment_and_plan', 'plan'].includes(c.section_key) ? i : acc, -1);
      return lastApIdx === -1 ? [...prev, newCmd] : [...prev.slice(0, lastApIdx + 1), newCmd, ...prev.slice(lastApIdx + 1)];
    });

    if (icd10Code) {
      setUnmatchedConditions(prev => prev.filter(c => !(c.coding || []).some(cd => cd.code === icd10Code)));
    }
  }, [approved, commands]);

  const handleInsert = useCallback(async () => {
    setInserting(true);
    const insertable = commands.filter(c => !c.already_documented && c.display);
    const acceptedRecs = recommendations.filter(c => c.accepted && !c.already_documented && c.display);
    let allInsertable = [...insertable, ...acceptedRecs];

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
        setApproved(true);
        saveSummaryToCache(noteData, commands, true);
        // Close the modal via the Canvas message channel.
        const port = window.__canvasPort && window.__canvasPort();
        if (port) {
          port.postMessage({ type: 'CLOSE_MODAL' });
        }
      }
    } catch (err) {
      setError('Failed to insert commands');
    } finally {
      setInserting(false);
    }
  }, [commands, recommendations, noteId, noteData, saveSummaryToCache]);

  if (DEV_MOCK && generating) {
    return html`
      <div class="summary-container">
        <div class="summary-header">
          <span class="summary-header-title">Canvas Scribe</span>
          <span class="summary-header-status">Dev Mode</span>
        </div>
        <div class="dev-seed-panel">
          <textarea
            class="dev-seed-textarea"
            placeholder="Paste transcript JSON array here..."
            value=${seedText}
            onInput=${(e) => setSeedText(e.target.value)}
          />
          ${seedError && html`<p class="error">${seedError}</p>`}
          <div class="dev-seed-actions">
            <button class="insert-btn" onClick=${handleSeedGenerate}>
              Generate from Transcript
            </button>
            <button class="edit-btn" onClick=${handleUseMock}>
              Use Mock Data
            </button>
          </div>
        </div>
      </div>
    `;
  }

  if (generating && !noteData) {
    return html`
      <div class="summary-container">
        <p class="generating-message">Loading...</p>
      </div>
    `;
  }

  if (!noteData) {
    return html`
      <div class="summary-container">
        <div class="summary-empty">
          <p class="summary-empty-description">
            Generate a structured summary from your recorded transcript. This will create a SOAP note with recommended commands you can review before adding to the chart.
          </p>
          <button
            class="generate-btn"
            onClick=${handleGenerate}
            disabled=${generating}
          >
            ${generating ? 'Generating...' : 'Generate Summary'}
          </button>
          ${error && html`<p class="summary-empty-error">${error}</p>`}
        </div>
      </div>
    `;
  }

  const commandBySectionKey = buildCommandBySectionKey(commands);
  const adHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_ad_hoc');
  const objectiveAdHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_objective_ad_hoc');

  const insertableCount = commands.filter(c => {
    if (c.command_type === 'diagnose') return c.data.icd10_code && c.data.accepted && c.display;
    return !c.already_documented && c.display;
  }).length
    + recommendations.filter(c => c.accepted && !c.already_documented && c.display).length;
  const showFooter = !extracting && !approved && (insertableCount > 0);

  return html`
    <div class="summary-container">
      <div class="summary-body">
        ${renderSoapGroups(noteData.sections, commandBySectionKey, handleEdit, handleDelete, {
          adHocCommands,
          objectiveAdHocCommands,
          assignees,
          onAddTask: approved ? null : handleAddTask,
          onAddOrder: approved ? null : handleAddOrder,
          onAddMedication: approved ? null : handleAddMedication,
          onAddAllergy: approved ? null : handleAddAllergy,
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
        ${extracting && html`<p class="generating-message">Extracting commands...</p>`}
        ${recommending && html`<p class="generating-message">Finding recommendations...</p>`}
      </div>
      ${showFooter && html`
        <div class="summary-footer">
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
