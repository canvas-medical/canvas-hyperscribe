import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);
const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const CSS_URL = '/plugin-io/api/hyperscribe/scribe/static/debug.css';

// Inject debug stylesheet once.
if (!document.querySelector(`link[href="${CSS_URL}"]`)) {
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = CSS_URL;
  document.head.appendChild(link);
}

function CacheSection({ title, data, onSave, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState('');

  const handleEdit = () => {
    setText(JSON.stringify(data, null, 2));
    setEditing(true);
  };

  const handleSave = () => {
    try {
      const parsed = JSON.parse(text);
      onSave(parsed);
      setEditing(false);
    } catch (e) {
      alert('Invalid JSON: ' + e.message);
    }
  };

  return html`
    <div class="debug-section">
      <div class="debug-section-header">
        <span class="debug-section-title">${title}</span>
        <div class="debug-section-actions">
          ${!editing && data && html`<button class="debug-btn" onClick=${handleEdit}>Edit</button>`}
          ${data && html`<button class="debug-btn debug-btn-danger" onClick=${onDelete}>Delete</button>`}
        </div>
      </div>
      ${editing ? html`
        <textarea
          class="debug-textarea"
          value=${text}
          onInput=${(e) => setText(e.target.value)}
        />
        <div class="debug-edit-actions">
          <button class="debug-btn" onClick=${handleSave}>Save</button>
          <button class="debug-btn" onClick=${() => setEditing(false)}>Cancel</button>
        </div>
      ` : html`
        <pre class="debug-json">${data ? JSON.stringify(data, null, 2) : 'Empty'}</pre>
      `}
    </div>
  `;
}

export function Debug({ noteId }) {
  const [cache, setCache] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadCache = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/debug-cache?note_id=${encodeURIComponent(noteId)}`);
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setCache(data);
      }
    } catch (err) {
      setError('Failed to load cache');
    } finally {
      setLoading(false);
    }
  }, [noteId]);

  useEffect(() => { loadCache(); }, [loadCache]);

  const handleDeleteType = useCallback(async (type) => {
    try {
      const res = await fetch(
        `${API_BASE}/debug-cache?note_id=${encodeURIComponent(noteId)}&type=${type}`,
        { method: 'DELETE' },
      );
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        loadCache();
      }
    } catch (err) {
      setError('Failed to delete cache');
    }
  }, [noteId, loadCache]);

  const handleDeleteAll = useCallback(() => handleDeleteType('all'), [handleDeleteType]);

  const handleSaveTranscript = useCallback(async (parsed) => {
    try {
      const items = parsed.items || parsed;
      const finalized = parsed.finalized ?? false;
      await fetch(`${API_BASE}/save-transcript`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_id: noteId, transcript: { items }, finalized }),
      });
      loadCache();
    } catch (err) {
      setError('Failed to save transcript');
    }
  }, [noteId, loadCache]);

  const handleSaveSummary = useCallback(async (parsed) => {
    try {
      await fetch(`${API_BASE}/save-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          note_id: noteId,
          note: parsed.note || {},
          commands: parsed.commands || [],
          approved: parsed.approved ?? false,
        }),
      });
      loadCache();
    } catch (err) {
      setError('Failed to save summary');
    }
  }, [noteId, loadCache]);

  if (loading) {
    return html`<div class="debug-container"><p>Loading cache...</p></div>`;
  }

  return html`
    <div class="debug-container">
      <div class="debug-header">
        <span class="debug-header-title">Cache Debug</span>
        <span class="debug-note-id">note: ${noteId}</span>
        <div class="debug-header-actions">
          <button class="debug-btn" onClick=${loadCache}>Refresh</button>
          <button class="debug-btn debug-btn-danger" onClick=${handleDeleteAll}>Delete All</button>
        </div>
      </div>
      ${error && html`<p class="error">${error}</p>`}
      <${CacheSection}
        title="Transcript"
        data=${cache && cache.transcript}
        onSave=${handleSaveTranscript}
        onDelete=${() => handleDeleteType('transcript')}
      />
      <${CacheSection}
        title="Summary"
        data=${cache && cache.summary}
        onSave=${handleSaveSummary}
        onDelete=${() => handleDeleteType('summary')}
      />
    </div>
  `;
}
