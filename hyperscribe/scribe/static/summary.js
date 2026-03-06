import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { SubjectiveSection } from '/plugin-io/api/hyperscribe/scribe/static/subjective-section.js';
import { ObjectiveSection } from '/plugin-io/api/hyperscribe/scribe/static/objective-section.js';
import { AssessmentPlanSection } from '/plugin-io/api/hyperscribe/scribe/static/assessment-plan-section.js';

const html = htm.bind(h);

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';

function renderSection(section) {
  const key = section.key.toLowerCase();

  if (key.includes('assessment') || key.includes('plan')) {
    const lines = section.text.split('\n').filter(Boolean);
    const diagnosis = lines[0] || '';
    const items = lines.slice(1);
    return html`<${AssessmentPlanSection}
      key=${section.key}
      diagnosis=${diagnosis}
      items=${items}
    />`;
  }

  if (key.includes('objective')) {
    const items = section.text.split('\n').filter(Boolean);
    return html`<${ObjectiveSection} key=${section.key} items=${items} />`;
  }

  // subjective or fallback
  return html`<${SubjectiveSection} key=${section.key} text=${section.text} />`;
}

export function Summary({ noteId }) {
  const [noteData, setNoteData] = useState(null);
  const [generating, setGenerating] = useState(true);
  const [error, setError] = useState(null);

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
      ${noteData.sections.map(renderSection)}
    </div>
  `;
}
