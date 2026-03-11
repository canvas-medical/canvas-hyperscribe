import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useCallback, useRef } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { SoapGroup } from '/plugin-io/api/hyperscribe/scribe/static/soap-group.js';
import { RecommendedGroup } from '/plugin-io/api/hyperscribe/scribe/static/recommended-group.js';

const html = htm.bind(h);

// ── DEV_MOCK: set to true to show a paste-box / mock-note picker instead of calling Nabla ──
const DEV_MOCK = true;

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
  { title: 'SUBJECTIVE', color: 'subjective', keys: new Set(['chief_complaint', 'history_of_present_illness']) },
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

function renderSoapGroups(sections, commandBySectionKey, onEditCommand, onDeleteCommand, { adHocCommands, objectiveAdHocCommands, assignees, onAddTask, onAddOrder, onAddMedication, onAddAllergy, readOnly } = {}) {
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
      />`;
    })
    .filter(Boolean);
}

export function Summary({ noteId }) {
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
  const [seedText, setSeedText] = useState('');
  const [seedError, setSeedError] = useState(null);
  const mockLoaded = useRef(false);

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
        if (type === 'history_review' || type === 'chart_review') {
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
          return { ...cmd, command_type: type, data: newData, display: newData.comment || '' };
        }
        if (type === 'imaging_order') {
          const parts = [newData.comment, newData.priority].filter(Boolean);
          return { ...cmd, command_type: type, data: newData, display: parts.join(' | ') };
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
        return { ...cmd, data: newData, display: newData.medication_text || '' };
      }
      if (type === 'allergy') {
        return { ...cmd, data: newData, display: newData.allergy_text || '' };
      }
      return { ...cmd, data: newData };
    }));
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

  const handleInsert = useCallback(async () => {
    setInserting(true);
    const insertable = commands.filter(c => !c.already_documented && c.display);
    const approvedRecs = recommendations.filter(c => !c.already_documented && c.display);
    const allInsertable = [...insertable, ...approvedRecs];
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

  const insertableCount = commands.filter(c => !c.already_documented && c.display).length
    + recommendations.filter(c => !c.already_documented && c.display).length;
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
        })}
        ${extracting && html`<p class="generating-message">Extracting commands...</p>`}
        ${recommending && html`<p class="generating-message">Finding recommendations...</p>`}
        ${!recommending && recommendations.length > 0 && html`
          <${RecommendedGroup}
            recommendations=${recommendations}
            onEditCommand=${handleEditRecommendation}
            onDeleteCommand=${handleDeleteRecommendation}
          />
        `}
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
