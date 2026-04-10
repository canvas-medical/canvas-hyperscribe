import { useState, useRef, useCallback, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import { createScribeClient } from './scribeClient.js';

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const TARGET_SAMPLE_RATE = 16000;

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

// RMS threshold below which audio is considered silence.
// Typical quiet room noise is ~0.001–0.01; speech is ~0.02–0.2.
const SILENCE_RMS_THRESHOLD = 0.005;
// Seconds of continuous silence before showing a warning.
const SILENCE_WARNING_SECONDS = 7.5;
const DING_URL = 'data:audio/wav;base64,UklGRmhWAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAATElTVBoAAABJTkZPSVNGVA4AAABMYXZmNjIuMTIuMTAwAGRhdGEiVgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAP////8AAAAA//8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAABAAEAAQAAAAAA//8AAAAAAAD//////v///wAAAQABAAEA/P/4/wEABgAFAAUABQAKAAsACAAFAAQAAwAGAAoADAAUABMAEQAPAA8ADwATABgA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';

/**
 * Custom hook encapsulating all recording logic.
 * Returns: { status, entries, error, finalized, audioLevel, silenceWarning,
 *            startRecording, pauseRecording, resumeRecording, finishRecording }
 */
export function useRecording(noteId, initialTranscript) {
  const [status, setStatus] = useState(() => {
    if (initialTranscript?.started && !initialTranscript.finalized) return 'paused';
    return 'idle';
  });
  const [entries, setEntries] = useState(() => initialTranscript?.items ?? []);
  const [error, setError] = useState(null);
  const [finalized, setFinalized] = useState(() => initialTranscript?.finalized ?? false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [silenceWarning, setSilenceWarning] = useState(false);
  const [micBlocked, setMicBlocked] = useState(false);
  const [micPrompting, setMicPrompting] = useState(false);
  const [connectionLost, setConnectionLost] = useState(false);
  const lastAudioTimeRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const silenceDingPlayedRef = useRef(false);
  const dingBufferRef = useRef(null);

  const statusRef = useRef(status);
  statusRef.current = status;
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
      client.onDisconnect = () => setConnectionLost(true);
      client.onReconnect = () => {
        setConnectionLost(false);
        // Promote non-final (partial) entries to final — they'll never be
        // finalized through the normal flow since the old WebSocket session
        // is gone, and the ACK'd audio that produced them won't be replayed.
        setEntries(prev => prev.map(e => e.is_final ? e : { ...e, is_final: true }));
      };
      await client.connect();
    } catch (err) {
      setError('Failed to connect to transcription service');
      return false;
    }
    clientRef.current = client;

    let stream;
    try {
      setMicPrompting(true);
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: TARGET_SAMPLE_RATE, channelCount: 1, echoCancellation: true },
      });
    } catch (err) {
      setMicBlocked(true);
      client.end();
      clientRef.current = null;
      return false;
    } finally {
      setMicPrompting(false);
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
        const { pcm16, rms } = event.data;
        setAudioLevel(rms);
        if (rms >= SILENCE_RMS_THRESHOLD) {
          lastAudioTimeRef.current = Date.now();
          setSilenceWarning(false);
        }
        if (clientRef.current) {
          clientRef.current.sendAudio(pcm16);
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
    setAudioLevel(0);
    setSilenceWarning(false);
    setConnectionLost(false);
    if (silenceTimerRef.current) {
      clearInterval(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (clientRef.current) {
      const client = clientRef.current;
      clientRef.current = null;
      client.onError = () => {};
      client.onEnd = () => {};
      client.onDisconnect = () => {};
      client.onReconnect = () => {};
      // end() drains any buffered audio before closing.
      await client.end();
      client.onTranscriptItem = () => {};
    }
  }, []);

  const [lastSaved, setLastSaved] = useState(null);

  const saveTranscriptToCache = useCallback(async () => {
    if (!noteId) return;
    try {
      await fetch(`${API_BASE}/save-transcript`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          note_id: noteId,
          transcript: { items: entriesRef.current },
        }),
      });
      setLastSaved(Date.now());
    } catch (err) {
      console.error('Failed to save transcript to cache:', err);
    }
  }, [noteId]);

  const startRecording = useCallback(async () => {
    setError(null);
    if (window.parent.__startReplayRecording) {
      window.parent.__startReplayRecording();
    } else {
      console.log('[Hyperscribe] Sentry session replay not available');
    }
    setSilenceWarning(false);
    silenceDingPlayedRef.current = false;
    setAudioLevel(0);
    lastAudioTimeRef.current = Date.now();
    const ok = await connectAndRecord();
    if (ok) {
      setMicBlocked(false);
      setStatus('recording');
    }
    return ok;
  }, [connectAndRecord]);

  const pauseRecording = useCallback(async () => {
    setStatus('paused');
    await disconnectAll();
    await saveTranscriptToCache();
  }, [disconnectAll, saveTranscriptToCache]);

  const resumeRecording = useCallback(async () => {
    setError(null);
    setSilenceWarning(false);
    silenceDingPlayedRef.current = false;
    setAudioLevel(0);
    lastAudioTimeRef.current = Date.now();
    const ok = await connectAndRecord();
    if (ok) {
      setMicBlocked(false);
      setStatus('recording');
    } else {
      setStatus('paused');
    }
  }, [connectAndRecord]);

  const finishRecording = useCallback(async () => {
    setStatus('finishing');
    await disconnectAll();
    // Save transcript with finalized flag.
    if (noteId && entriesRef.current.length > 0) {
      try {
        await fetch(`${API_BASE}/save-transcript`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            note_id: noteId,
            transcript: { items: entriesRef.current },
            finalized: true,
          }),
        });
      } catch (err) {
        console.error('Failed to save finalized transcript:', err);
      }
    }
    setFinalized(true);
    setStatus('idle');
  }, [noteId, disconnectAll]);

  // Load cached transcript on mount — skip if initial data was provided server-side.
  useEffect(() => {
    if (initialTranscript || !noteId) return;
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
        if (!cancelled && data.started && !data.finalized) {
          setStatus('paused');
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

  // Auto-save transcript every 10s while recording to prevent data loss.
  useEffect(() => {
    if (status !== 'recording') return;
    const interval = setInterval(() => { saveTranscriptToCache(); }, 10000);
    return () => clearInterval(interval);
  }, [status, saveTranscriptToCache]);

  // Check for prolonged silence while recording.
  useEffect(() => {
    if (status !== 'recording') return;
    silenceTimerRef.current = setInterval(() => {
      const elapsed = (Date.now() - (lastAudioTimeRef.current || Date.now())) / 1000;
      if (elapsed >= SILENCE_WARNING_SECONDS) {
        setSilenceWarning(true);
        if (!silenceDingPlayedRef.current && audioCtxRef.current) {
          silenceDingPlayedRef.current = true;
          const ctx = audioCtxRef.current;
          (async () => {
            try {
              if (!dingBufferRef.current) {
                const res = await fetch(DING_URL);
                dingBufferRef.current = await ctx.decodeAudioData(await res.arrayBuffer());
              }
              const src = ctx.createBufferSource();
              src.buffer = dingBufferRef.current;
              src.connect(ctx.destination);
              src.start();
            } catch { /* ignore playback errors */ }
          })();
        }
      }
    }, 2000);
    return () => {
      clearInterval(silenceTimerRef.current);
      silenceTimerRef.current = null;
    };
  }, [status]);

  // Check microphone permission on mount and listen for changes.
  useEffect(() => {
    let permStatus;
    async function check() {
      try {
        permStatus = await navigator.permissions.query({ name: 'microphone' });
        setMicBlocked(permStatus.state === 'denied');
        permStatus.onchange = () => setMicBlocked(permStatus.state === 'denied');
      } catch {
        // Permissions API not supported — we'll catch denial on getUserMedia instead.
      }
    }
    check();
    return () => { if (permStatus) permStatus.onchange = null; };
  }, []);

  // Re-request microphone permission without reloading the page.
  const retryMicPermission = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(t => t.stop());
      setMicBlocked(false);
    } catch {
      setMicBlocked(true);
    }
  }, []);

  // Cleanup on unmount — save transcript via sendBeacon before destroying resources.
  useEffect(() => {
    return () => {
      if (noteId && (entriesRef.current.length > 0 || statusRef.current !== 'idle')) {
        const payload = new Blob(
          [JSON.stringify({ note_id: noteId, transcript: { items: entriesRef.current } })],
          { type: 'application/json' },
        );
        navigator.sendBeacon(`${API_BASE}/save-transcript`, payload);
      }
      cleanupAudio(audioCtxRef, streamRef, workletNodeRef);
      if (clientRef.current) {
        clientRef.current.end();
        clientRef.current = null;
      }
    };
  }, []);

  return {
    status, entries, error, finalized, lastSaved, audioLevel, silenceWarning, micBlocked, micPrompting, connectionLost,
    startRecording, pauseRecording, resumeRecording, finishRecording, retryMicPermission,
  };
}
