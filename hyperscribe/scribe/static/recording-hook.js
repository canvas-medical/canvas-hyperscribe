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

/**
 * Custom hook encapsulating all recording logic.
 * Returns: { status, entries, error, finalized, startRecording, pauseRecording, resumeRecording, finishRecording }
 */
export function useRecording(noteId) {
  const [status, setStatus] = useState('idle'); // 'idle' | 'recording' | 'paused' | 'finishing'
  const [entries, setEntries] = useState([]);
  const [error, setError] = useState(null);
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

  const [lastSaved, setLastSaved] = useState(null);

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
      setLastSaved(Date.now());
    } catch (err) {
      console.error('Failed to save transcript to cache:', err);
    }
  }, [noteId]);

  const startRecording = useCallback(async () => {
    setError(null);
    const ok = await connectAndRecord();
    if (ok) setStatus('recording');
  }, [connectAndRecord]);

  const pauseRecording = useCallback(async () => {
    setStatus('paused');
    await disconnectAll();
    await saveTranscriptToCache();
  }, [disconnectAll, saveTranscriptToCache]);

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
          // Non-finalized transcript with entries means recording was paused before refresh.
          if (!data.finalized) {
            setStatus('paused');
          }
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

  // Cleanup on unmount — save transcript via sendBeacon before destroying resources.
  useEffect(() => {
    return () => {
      if (noteId && entriesRef.current.length > 0) {
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
    status, entries, error, finalized, lastSaved,
    startRecording, pauseRecording, resumeRecording, finishRecording,
  };
}
