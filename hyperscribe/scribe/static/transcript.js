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

function RecordingBanner() {
  return html`
    <div class="recording-banner">
      <span class="recording-dot"></span>
      <span>Recording in progress</span>
    </div>
  `;
}

function TranscriptEntry({ speaker, start_offset_ms, text, is_final }) {
  const isProvider = speaker.toLowerCase().includes('provider') || speaker.toLowerCase().includes('doctor');
  const role = isProvider ? 'provider' : 'patient';
  const initial = isProvider ? 'Dr' : 'Pt';
  const time = formatTime(start_offset_ms);

  return html`
    <div class="transcript-entry ${is_final ? '' : 'partial'}">
      <div class="entry-avatar ${role}">${initial}</div>
      <div class="entry-content">
        <div class="entry-meta">
          <span class="entry-speaker">${speaker}</span>
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

export function Scribe({ noteDbid }) {
  const [recording, setRecording] = useState(false);
  const [entries, setEntries] = useState([]);
  const [error, setError] = useState(null);

  const clientRef = useRef(null);
  const audioCtxRef = useRef(null);
  const streamRef = useRef(null);
  const workletNodeRef = useRef(null);

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

  const startRecording = useCallback(async () => {
    setError(null);
    setEntries([]);

    let config;
    try {
      const configUrl = noteDbid ? `${API_BASE}/config?note_dbid=${noteDbid}` : `${API_BASE}/config`;
      const res = await fetch(configUrl, { cache: 'no-store' });
      config = await res.json();
      if (config.error) {
        setError(config.error);
        return;
      }
    } catch (err) {
      setError('Failed to get transcription config');
      return;
    }

    let client;
    try {
      client = createScribeClient(config);
      client.onTranscriptItem = handleTranscriptItem;
      client.onError = (msg) => setError(msg);
      await client.connect();
    } catch (err) {
      setError('Failed to connect to transcription service');
      return;
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
      return;
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
      return;
    }

    setRecording(true);
  }, [handleTranscriptItem]);

  const stopRecording = useCallback(() => {
    cleanupAudio(audioCtxRef, streamRef, workletNodeRef);

    if (clientRef.current) {
      clientRef.current.end();
      clientRef.current = null;
    }

    setRecording(false);
  }, []);

  useEffect(() => {
    return () => {
      cleanupAudio(audioCtxRef, streamRef, workletNodeRef);
      if (clientRef.current) {
        clientRef.current.end();
        clientRef.current = null;
      }
    };
  }, []);

  const handleToggle = () => {
    if (recording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  return html`
    <div class="scribe-container">
      ${recording && html`<${RecordingBanner} />`}
      <div class="scribe-header">
        <h2>Scribe</h2>
      </div>
      ${error && html`<p class="error">${error}</p>`}
      <div class="record-area">
        <button
          class="record-btn ${recording ? 'recording' : ''}"
          onClick=${handleToggle}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            ${recording
              ? html`<rect x="6" y="6" width="12" height="12" rx="2" />`
              : html`<circle cx="12" cy="12" r="8" />`}
          </svg>
        </button>
        <span class="record-label">${recording ? 'Recording...' : 'Tap to record'}</span>
      </div>
      ${entries.length > 0 && html`
        <div class="transcript-list">
          ${entries.map((entry, i) => html`
            <${TranscriptEntry} key=${entry.item_id || i} ...${entry} />
          `)}
        </div>
      `}
      ${!recording && entries.length === 0 && !error && html`
        <p class="transcript-placeholder">Transcript content will appear here.</p>
      `}
    </div>
  `;
}
