import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { Scribe } from '/plugin-io/api/hyperscribe/scribe/static/transcript.js';
import { Summary } from '/plugin-io/api/hyperscribe/scribe/static/summary.js';

const html = htm.bind(h);

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';

export function App({ noteId, view }) {
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const handleFinish = useCallback(async (entries) => {
    setSaveError(null);
    try {
      const res = await fetch(`${API_BASE}/save-transcript`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          note_id: noteId,
          transcript: { items: entries },
        }),
      });
      const data = await res.json();
      if (data.error) {
        setSaveError(data.error);
      } else {
        setSaved(true);
      }
    } catch (err) {
      setSaveError('Failed to save transcript');
    }
  }, [noteId]);

  if (view === 'summary') {
    return html`<${Summary} noteId=${noteId} />`;
  }

  if (view === 'scribe') {
    return html`<${Scribe}
      noteId=${noteId}
      onFinish=${handleFinish}
      saved=${saved}
      saveError=${saveError}
    />`;
  }

  return html`<div class="scribe-container"><p class="error">Unknown view: ${view}</p></div>`;
}
