import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

const html = htm.bind(h);
const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const CSS_URL = '/plugin-io/api/hyperscribe/scribe/static/debug.css';

if (!document.querySelector(`link[href="${CSS_URL}"]`)) {
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = CSS_URL;
  document.head.appendChild(link);
}

function FieldRow({ name, value, type }) {
  const isJson = type === 'json';
  const isBool = type === 'bool';
  const isEmpty = value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0) || (typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0);
  const [expanded, setExpanded] = useState(false);

  let display;
  if (isEmpty) {
    display = html`<span class="debug-field-empty">—</span>`;
  } else if (isBool) {
    display = html`<span class="debug-field-bool ${value ? 'true' : 'false'}">${value ? 'true' : 'false'}</span>`;
  } else if (isJson) {
    const preview = Array.isArray(value) ? `[${value.length} items]` : `{${Object.keys(value).length} keys}`;
    display = html`
      <span class="debug-field-json-toggle" onClick=${() => setExpanded(!expanded)}>
        ${expanded ? '▼' : '▶'} ${preview}
      </span>
      ${expanded && html`<pre class="debug-field-json">${JSON.stringify(value, null, 2)}</pre>`}
    `;
  } else {
    display = html`<span class="debug-field-text">${String(value)}</span>`;
  }

  return html`
    <div class="debug-field-row">
      <span class="debug-field-name">${name}</span>
      <div class="debug-field-value">${display}</div>
    </div>
  `;
}

function ModelSection({ title, modelType, data, onDelete, onSave, fields, readOnly }) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState('');

  const handleEdit = () => {
    // Build editable object from fields (exclude updated_at).
    const obj = {};
    for (const f of fields) {
      if (f.key === 'updated_at') continue;
      obj[f.key] = data ? data[f.key] : (f.type === 'json' ? (f.key === 'items' || f.key === 'events' ? [] : {}) : f.type === 'bool' ? false : '');
    }
    setEditText(JSON.stringify(obj, null, 2));
    setEditing(true);
  };

  const handleSave = () => {
    try {
      const parsed = JSON.parse(editText);
      onSave(modelType, parsed);
      setEditing(false);
    } catch (e) {
      alert('Invalid JSON: ' + e.message);
    }
  };

  if (!data && !editing) {
    return html`
      <div class="debug-section">
        <div class="debug-section-header">
          <span class="debug-section-title">${title}</span>
          ${!readOnly && html`<div class="debug-section-actions">
            <button class="debug-btn" onClick=${handleEdit}>Create</button>
          </div>`}
        </div>
        <div class="debug-field-list">
          <div class="debug-field-row"><span class="debug-field-empty" style="padding: 4px 0;">No record</span></div>
        </div>
      </div>
    `;
  }

  return html`
    <div class="debug-section">
      <div class="debug-section-header">
        <span class="debug-section-title">${title}</span>
        ${!readOnly && html`<div class="debug-section-actions">
          ${!editing && html`<button class="debug-btn" onClick=${handleEdit}>Edit</button>`}
          ${data && html`<button class="debug-btn debug-btn-danger" onClick=${onDelete}>Delete</button>`}
        </div>`}
      </div>
      ${editing ? html`
        <textarea
          class="debug-textarea"
          value=${editText}
          onInput=${(e) => setEditText(e.target.value)}
        />
        <div class="debug-edit-actions">
          <button class="debug-btn debug-btn-save" onClick=${handleSave}>Save</button>
          <button class="debug-btn" onClick=${() => setEditing(false)}>Cancel</button>
        </div>
      ` : html`
        <div class="debug-field-list">
          ${fields.map(f => html`
            <${FieldRow} key=${f.name} name=${f.name} value=${data[f.key]} type=${f.type} />
          `)}
        </div>
      `}
    </div>
  `;
}

const TRANSCRIPT_FIELDS = [
  { key: 'items', name: 'items', type: 'json' },
  { key: 'finalized', name: 'finalized', type: 'bool' },
  { key: 'provider_id', name: 'provider_id', type: 'text' },
  { key: 'updated_at', name: 'updated_at', type: 'text' },
];

const SUMMARY_FIELDS = [
  { key: 'note_data', name: 'note_data', type: 'json' },
  { key: 'commands', name: 'commands', type: 'json' },
  { key: 'recommendations', name: 'recommendations', type: 'json' },
  { key: 'unmatched_conditions', name: 'unmatched_conditions', type: 'json' },
  { key: 'diagnosis_suggestions', name: 'diagnosis_suggestions', type: 'json' },
  { key: 'approved', name: 'approved', type: 'bool' },
  { key: 'selected_template_name', name: 'selected_template_name', type: 'text' },
  { key: 'mode', name: 'mode', type: 'text' },
  { key: 'raw_response', name: 'raw_response', type: 'json' },
  { key: 'updated_at', name: 'updated_at', type: 'text' },
];

const AUDIT_FIELDS = [
  { key: 'events', name: 'events', type: 'json' },
  { key: 'updated_at', name: 'updated_at', type: 'text' },
];

export function Debug({ noteId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/debug-cache?note_id=${encodeURIComponent(noteId)}`);
      const json = await res.json();
      if (json.error) setError(json.error);
      else setData(json);
    } catch (err) {
      setError('Failed to load models');
    } finally {
      setLoading(false);
    }
  }, [noteId]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = useCallback(async (type) => {
    try {
      const res = await fetch(
        `${API_BASE}/debug-cache?note_id=${encodeURIComponent(noteId)}&type=${type}`,
        { method: 'DELETE' },
      );
      const json = await res.json();
      if (json.error) setError(json.error);
      else load();
    } catch (err) {
      setError('Delete failed');
    }
  }, [noteId, load]);

  const handleSave = useCallback(async (modelType, fields) => {
    try {
      const res = await fetch(`${API_BASE}/debug-cache`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_id: noteId, type: modelType, fields }),
      });
      const json = await res.json();
      if (json.error) setError(json.error);
      else load();
    } catch (err) {
      setError('Save failed');
    }
  }, [noteId, load]);

  if (loading) {
    return html`<div class="debug-container"><p>Loading models...</p></div>`;
  }

  return html`
    <div class="debug-container">
      <div class="debug-header">
        <span class="debug-header-title">Scribe Models</span>
        <span class="debug-note-id">note: ${noteId}${data && data.note_dbid ? ` (dbid: ${data.note_dbid})` : ''}</span>
        <div class="debug-header-actions">
          <button class="debug-btn" onClick=${load}>Refresh</button>
          <button class="debug-btn debug-btn-danger" onClick=${() => handleDelete('all')}>Delete All</button>
        </div>
      </div>
      ${error && html`<p class="error">${error}</p>`}
      <${ModelSection}
        title="ScribeTranscript"
        modelType="transcript"
        data=${data && data.transcript}
        fields=${TRANSCRIPT_FIELDS}
        onDelete=${() => handleDelete('transcript')}
        onSave=${handleSave}
      />
      <${ModelSection}
        title="ScribeSummary"
        modelType="summary"
        data=${data && data.summary}
        fields=${SUMMARY_FIELDS}
        onDelete=${() => handleDelete('summary')}
        onSave=${handleSave}
      />
      <${ModelSection}
        title="ScribeAuditLog"
        modelType="audit_log"
        data=${data && data.audit_log}
        fields=${AUDIT_FIELDS}
        onDelete=${() => handleDelete('audit_log')}
        onSave=${handleSave}
        readOnly=${true}
      />
    </div>
  `;
}
