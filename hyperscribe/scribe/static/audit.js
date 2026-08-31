import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useRef } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';

import { connectScribeWS } from '/plugin-io/api/hyperscribe/scribe/static/scribe-ws.js';

const html = htm.bind(h);
const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';

const CATEGORY_COLORS = {
  START_AI: '#3b82f6', START_MANUAL: '#3b82f6', PAUSE: '#3b82f6', RESUME: '#3b82f6', FINISH: '#3b82f6',
  SELECT_TEMPLATE: '#8b5cf6', DESELECT_TEMPLATE: '#8b5cf6',
  GENERATE_START: '#f59e0b', GENERATE_COMPLETE: '#f59e0b', GENERATE_ERROR: '#ef4444',
  APPROVE_START: '#16a34a', APPROVE_COMPLETE: '#16a34a', APPROVE_ERROR: '#ef4444',
  ADD_NOW: '#059669', ADD_NOW_SUCCESS: '#059669', ADD_NOW_ERROR: '#ef4444',
  CACHE_LOADED: '#9ca3af', CACHE_SAVED: '#9ca3af',
  COMMANDS_VERIFIED: '#16a34a', COMMANDS_FAILED: '#ef4444',
  COMMANDS_SENDING: '#3b82f6', COMMANDS_FILTERED: '#f59e0b', TRANSCRIPT_AUTO_SAVED: '#9ca3af',
};

function formatTime(isoString) {
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
      + '.' + String(d.getMilliseconds()).padStart(3, '0');
  } catch { return isoString; }
}

export function Audit({ noteId }) {
  const [events, setEvents] = useState([]);
  const [filter, setFilter] = useState('');
  const [expandedIdx, setExpandedIdx] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (!noteId) return;
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/audit-log?note_id=${encodeURIComponent(noteId)}`);
        const data = await res.json();
        if (!cancelled) setEvents(data.events || []);
      } catch (err) { console.error('Failed to load audit log:', err); }
    }
    load();
    return () => { cancelled = true; };
  }, [noteId]);

  useEffect(() => {
    if (!noteId) return;
    const cleanup = connectScribeWS(noteId, (msg) => {
      if (msg.type === 'AUDIT_EVENTS') {
        setEvents(prev => [...prev, ...(msg.events || [])]);
      }
    });
    return cleanup;
  }, [noteId]);

  useEffect(() => {
    if (bottomRef.current) bottomRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [events.length]);

  const filtered = filter
    ? events.filter(e => e.type.toLowerCase().includes(filter.toLowerCase()) || JSON.stringify(e.details).toLowerCase().includes(filter.toLowerCase()))
    : events;

  return html`
    <div class="audit-container">
      <div class="audit-header">
        <span class="audit-title">Audit Log</span>
        <span class="audit-count">${filtered.length} events</span>
        <input
          class="audit-filter"
          type="text"
          placeholder="Filter events..."
          value=${filter}
          onInput=${(e) => setFilter(e.target.value)}
        />
      </div>
      <div class="audit-list">
        ${filtered.length === 0 && html`<div class="audit-empty">No events recorded yet.</div>`}
        ${filtered.map((evt, i) => {
          const color = CATEGORY_COLORS[evt.type] || '#6b7280';
          const hasDetails = evt.details && Object.keys(evt.details).length > 0;
          const isExpanded = expandedIdx === i;
          return html`
            <div class="audit-row" key=${i} onClick=${() => hasDetails && setExpandedIdx(isExpanded ? null : i)}>
              <span class="audit-time">${formatTime(evt.ts)}</span>
              <span class="audit-type" style="color: ${color}">${evt.type}</span>
              ${hasDetails && html`<span class="audit-expand">${isExpanded ? '\u25BC' : '\u25B6'}</span>`}
              ${isExpanded && hasDetails && html`
                <pre class="audit-details">${JSON.stringify(evt.details, null, 2)}</pre>
              `}
            </div>
          `;
        })}
        <div ref=${bottomRef} />
      </div>
    </div>
  `;
}
