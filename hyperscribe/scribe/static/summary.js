import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { SoapGroup } from '/plugin-io/api/hyperscribe/scribe/static/soap-group.js';
import { CommandsSection } from '/plugin-io/api/hyperscribe/scribe/static/commands-section.js';

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

function renderSoapGroups(sections) {
  return SOAP_GROUPS
    .map(group => {
      const matching = sections.filter(s => group.keys.has(s.key.toLowerCase()));
      if (matching.length === 0) return null;
      return html`<${SoapGroup} key=${group.title} title=${group.title} sections=${matching} />`;
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
          body: JSON.stringify({ note: noteData }),
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

  const handleToggle = useCallback((index) => {
    setCommands(prev => prev.map((cmd, i) =>
      i === index ? { ...cmd, selected: !cmd.selected } : cmd
    ));
  }, []);

  const handleEdit = useCallback((index, newData) => {
    setCommands(prev => prev.map((cmd, i) => {
      if (i !== index) return cmd;
      const field = cmd.command_type === 'rfv' ? 'comment' : 'narrative';
      const text = newData[field] || '';
      const display = text.length > 80 ? text.slice(0, 77) + '...' : text;
      return { ...cmd, data: newData, display };
    }));
  }, []);

  const handleInsert = useCallback(async () => {
    setInserting(true);
    try {
      const selected = commands.filter(c => c.selected);
      const res = await fetch(`${API_BASE}/insert-commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_uuid: noteId, commands: selected }),
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

  return html`
    <div class="summary-container">
      ${renderSoapGroups(noteData.sections)}
      ${extracting && html`<p class="generating-message">Extracting commands...</p>`}
      ${commands.length > 0 && html`
        <${CommandsSection}
          commands=${commands}
          onToggle=${handleToggle}
          onEdit=${handleEdit}
          onInsert=${handleInsert}
          inserting=${inserting}
          inserted=${inserted}
        />
      `}
    </div>
  `;
}
