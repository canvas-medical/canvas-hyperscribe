import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { SoapGroup } from '/plugin-io/api/hyperscribe/scribe/static/soap-group.js';

const html = htm.bind(h);

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';

const SOAP_GROUPS = [
  { title: 'SUBJECTIVE', keys: new Set(['chief_complaint', 'history_of_present_illness',
    'past_medical_history', 'past_surgical_history', 'past_obstetric_history',
    'family_history', 'social_history', 'allergies', 'current_medications', 'immunizations']) },
  { title: 'OBJECTIVE', keys: new Set(['vitals', 'physical_exam', 'lab_results', 'imaging_results']) },
  { title: 'ASSESSMENT', keys: new Set(['assessment']) },
  { title: 'PLAN', keys: new Set(['plan', 'prescription', 'appointments']) },
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

function renderSoapGroups(sections, commandBySectionKey, onEditCommand, onToggleCommand, { adHocCommands, assignees, onAddTask, onAddOrder } = {}) {
  return SOAP_GROUPS
    .map(group => {
      const matching = sections.filter(s => group.keys.has(s.key.toLowerCase()));
      const isPlan = group.title === 'PLAN';
      if (matching.length === 0 && !isPlan) return null;
      return html`<${SoapGroup}
        key=${group.title}
        title=${group.title}
        sections=${matching}
        commandBySectionKey=${commandBySectionKey}
        onEditCommand=${onEditCommand}
        onToggleCommand=${onToggleCommand}
        adHocCommands=${isPlan ? adHocCommands : null}
        assignees=${isPlan ? assignees : null}
        onAddTask=${isPlan ? onAddTask : null}
        onAddOrder=${isPlan ? onAddOrder : null}
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
  const [inserted, setInserted] = useState(false);
  const [assignees, setAssignees] = useState([]);

  // Generate note on mount.
  useEffect(() => {
    let cancelled = false;

    async function generateNote() {
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
        if (!cancelled) {
          setError('Failed to generate note');
        }
      } finally {
        if (!cancelled) {
          setGenerating(false);
        }
      }
    }

    generateNote();
    return () => { cancelled = true; };
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

  const handleEdit = useCallback((index, newData, newType) => {
    setCommands(prev => prev.map((cmd, i) => {
      if (i !== index) return cmd;
      const type = newType || cmd.command_type;
      if (type === 'vitals') {
        return { ...cmd, data: newData };
      }
      if (type === 'medication_statement') {
        return { ...cmd, data: newData, display: newData.medication_text || '' };
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
    }));
  }, []);

  const handleToggle = useCallback((index, selected) => {
    setCommands(prev => prev.map((cmd, i) =>
      i === index ? { ...cmd, selected } : cmd
    ));
  }, []);

  const handleAddTask = useCallback(() => {
    setCommands(prev => [...prev, {
      command_type: 'task',
      display: '',
      data: { title: '', due_date: null, assign_to: null },
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, []);

  const handleAddOrder = useCallback(() => {
    setCommands(prev => [...prev, {
      command_type: 'prescribe',
      display: '',
      data: {},
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, []);

  const handleInsert = useCallback(async () => {
    setInserting(true);
    const insertable = commands.filter(c => !c.already_documented && c.selected !== false && c.display);
    try {
      const res = await fetch(`${API_BASE}/insert-commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_uuid: noteId, commands: insertable }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setInserted(true);
      }
    } catch (err) {
      setError('Failed to insert commands');
    } finally {
      setInserting(false);
    }
  }, [commands, noteId]);

  if (generating) {
    return html`
      <div class="summary-container">
        <p class="generating-message">Generating summary...</p>
      </div>
    `;
  }

  if (error) {
    return html`
      <div class="summary-container">
        <p class="error">${error}</p>
      </div>
    `;
  }

  if (!noteData) {
    return html`
      <div class="summary-container">
        <p class="generating-message">No summary available.</p>
      </div>
    `;
  }

  const commandBySectionKey = buildCommandBySectionKey(commands);
  const adHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_ad_hoc');

  return html`
    <div class="summary-container">
      ${renderSoapGroups(noteData.sections, commandBySectionKey, handleEdit, handleToggle, {
        adHocCommands,
        assignees,
        onAddTask: handleAddTask,
        onAddOrder: handleAddOrder,
      })}
      ${extracting && html`<p class="generating-message">Extracting commands...</p>`}
      ${(() => {
        const insertableCount = commands.filter(c => !c.already_documented && c.selected !== false && c.display).length;
        return !extracting && insertableCount > 0 && !inserted && html`
          <button
            class="insert-btn"
            onClick=${handleInsert}
            disabled=${inserting}
          >
            ${inserting ? 'Inserting...' : `Insert ${insertableCount} Command${insertableCount !== 1 ? 's' : ''} into Note`}
          </button>
        `;
      })()}
      ${inserted && html`
        <p class="insert-success">Commands inserted into note.</p>
      `}
    </div>
  `;
}
