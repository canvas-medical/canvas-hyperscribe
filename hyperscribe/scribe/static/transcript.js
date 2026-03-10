import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useRef, useCallback } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { createScribeClient } from './scribeClient.js';

const html = htm.bind(h);

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const TARGET_SAMPLE_RATE = 16000;

function formatTime(ms) {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function RecordingBanner({ paused }) {
  return html`
    <div class="recording-banner ${paused ? 'paused' : ''}">
      <span class="recording-dot"></span>
      <span>${paused ? 'Paused' : 'Recording in progress'}</span>
    </div>
  `;
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

function cleanupAudio(audioCtxRef, streamRef, workletNodeRef) {
  if (workletNodeRef.current) {
    workletNodeRef.current.disconnect();
    workletNodeRef.current = null;
  }
  if (audioCtxRef.current) {
    audioCtxRef.current.close().catch(() => {});
    audioCtxRef.current = null;
  }
  if (streamRef.current) {
    streamRef.current.getTracks().forEach(t => t.stop());
    streamRef.current = null;
  }
}

export function Scribe({ noteId, providerName, providerPhotoUrl, patientName, onFinish, saved, saveError }) {
  const [status, setStatus] = useState('idle');
  const [entries, setEntries] = useState([]);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [finalized, setFinalized] = useState(false);

  const clientRef = useRef(null);
  const audioCtxRef = useRef(null);
  const streamRef = useRef(null);
  const workletNodeRef = useRef(null);
  const entriesRef = useRef(entries);
  entriesRef.current = entries;

  const handleTranscriptItem = useCallback((item) => {
    setEntries(prev => {
      const idx = prev.findIndex(e => e.item_id && e.item_id === item.item_id);
      if (idx !== -1) {
        const updated = [...prev];
        updated[idx] = item;
        return updated;
      }
      return [...prev, item];
    });
  }, []);

  const connectAndRecord = useCallback(async () => {
    let config;
    try {
      const res = await fetch(`${API_BASE}/config`, { cache: 'no-store' });
      config = await res.json();
      if (config.error) {
        setError(config.error);
        return false;
      }
    } catch (err) {
      setError('Failed to get transcription config');
      return false;
    }

    let client;
    try {
      client = createScribeClient(config);
      client.onTranscriptItem = handleTranscriptItem;
      client.onError = (msg) => setError(msg);
      await client.connect();
    } catch (err) {
      setError('Failed to connect to transcription service');
      return false;
    }
    clientRef.current = client;

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: TARGET_SAMPLE_RATE, channelCount: 1, echoCancellation: true },
      });
    } catch (err) {
      setError('Microphone access denied');
      client.end();
      clientRef.current = null;
      return false;
    }
    streamRef.current = stream;

    try {
      const audioCtx = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
      audioCtxRef.current = audioCtx;

      const processorUrl = new URL('./rawPcm16Processor.js', import.meta.url).href;
      await audioCtx.audioWorklet.addModule(processorUrl);

      const source = audioCtx.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioCtx, 'raw-pcm16-processor');
      workletNodeRef.current = workletNode;

      workletNode.port.onmessage = (event) => {
        if (clientRef.current) {
          clientRef.current.sendAudio(event.data);
        }
      };

      source.connect(workletNode);
      workletNode.connect(audioCtx.destination);
    } catch (err) {
      setError('Audio setup failed: ' + err.message);
      client.end();
      clientRef.current = null;
      cleanupAudio(audioCtxRef, streamRef, workletNodeRef);
      return false;
    }

    return true;
  }, [handleTranscriptItem]);

  const disconnectAll = useCallback(async () => {
    cleanupAudio(audioCtxRef, streamRef, workletNodeRef);
    if (clientRef.current) {
      const client = clientRef.current;
      clientRef.current = null;
      client.onError = () => {};
      client.onEnd = () => {};
      await client.end();
      client.onTranscriptItem = () => {};
    }
  }, []);

  const saveTranscriptToCache = useCallback(async () => {
    if (!noteId || entriesRef.current.length === 0) return;
    try {
      await fetch(`${API_BASE}/save-transcript`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          note_id: noteId,
          transcript: { items: entriesRef.current },
        }),
      });
    } catch (err) {
      console.error('Failed to save transcript to cache:', err);
    }
  }, [noteId]);

  const startRecording = useCallback(async () => {
    setError(null);
    setEntries([]);
    const ok = await connectAndRecord();
    if (ok) setStatus('recording');
  }, [connectAndRecord]);

  const pauseRecording = useCallback(async () => {
    setStatus('paused');
    await saveTranscriptToCache();
    await disconnectAll();
  }, [saveTranscriptToCache, disconnectAll]);

  const resumeRecording = useCallback(async () => {
    setError(null);
    const ok = await connectAndRecord();
    if (ok) {
      setStatus('recording');
    } else {
      setStatus('paused');
    }
  }, [connectAndRecord]);

  const finishRecording = useCallback(async () => {
    setStatus('finishing');
    await disconnectAll();
    setStatus('idle');
    if (onFinish) {
      setSaving(true);
      await onFinish(entriesRef.current);
      setSaving(false);
    }
  }, [onFinish, disconnectAll]);

  // Load cached transcript on mount.
  useEffect(() => {
    if (!noteId) return;
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/transcript?note_id=${noteId}`, { cache: 'no-store' });
        if (!res.ok) {
          console.error('Failed to load transcript:', res.status, res.statusText);
          return;
        }
        const data = await res.json();
        if (!cancelled && data.items && data.items.length > 0) {
          setEntries(data.items);
        }
        if (!cancelled && data.finalized) {
          setFinalized(true);
        }
      } catch (err) {
        console.error('Failed to load transcript:', err);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [noteId]);

  // Cleanup on unmount.
  useEffect(() => {
    return () => {
      cleanupAudio(audioCtxRef, streamRef, workletNodeRef);
      if (clientRef.current) {
        clientRef.current.end();
        clientRef.current = null;
      }
    };
  }, []);

  const isActive = status === 'recording' || status === 'paused';

  return html`
    <div class="scribe-container">
      ${isActive && html`<${RecordingBanner} paused=${status === 'paused'} />`}
      ${error && html`<p class="error">${error}</p>`}
      ${status === 'idle' && !finalized && html`
        <div class="record-area">
          <button class="record-btn" onClick=${startRecording}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <circle cx="12" cy="12" r="8" />
            </svg>
          </button>
          <span class="record-label">Tap to record</span>
        </div>
      `}
      ${isActive && html`
        <div class="control-buttons">
          ${status === 'recording'
            ? html`<button class="control-btn" onClick=${pauseRecording} title="Pause">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="6" y="5" width="4" height="14" rx="1" />
                  <rect x="14" y="5" width="4" height="14" rx="1" />
                </svg>
              </button>`
            : html`<button class="control-btn" onClick=${resumeRecording} title="Resume">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <polygon points="6,4 20,12 6,20" />
                </svg>
              </button>`}
          <button class="finish-btn" onClick=${finishRecording}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            Finish
          </button>
        </div>
      `}
      ${status === 'finishing' && html`
        <p class="generating-message">Finalizing transcript...</p>
      `}
      ${entries.length > 0 && html`
        <div class="transcript-list">
          ${entries.map((entry, i) => html`
            <${TranscriptEntry}
              key=${entry.item_id || i}
              ...${entry}
              providerName=${providerName}
              providerPhotoUrl=${providerPhotoUrl}
              patientName=${patientName}
            />
          `)}
        </div>
      `}
      ${saving && html`<p class="generating-message">Saving transcript...</p>`}
      ${saveError && html`<p class="error">${saveError}</p>`}
      ${saved && html`<p class="saved-message">Recording saved. Open Summary to view the note.</p>`}
      ${status === 'idle' && entries.length === 0 && !finalized && !error && !saving && !saved && !saveError && html`
        <p class="transcript-placeholder">Transcript content will appear here.</p>
      `}
    </div>
  `;
}
