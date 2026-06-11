/*
 * mock-recording-hook.js — stub for recording-hook.js (the mic + WebSocket seam).
 *
 * The import map remaps recording-hook.js to this file so <Scribe> renders the
 * REAL recording UI (banners, transcript panel, pause/resume/finish controls)
 * without touching getUserMedia or a transcription WebSocket. Only the IO is
 * faked — the UI is the shipping code.
 *
 * Exposes the exact same interface useRecording returns. Initial state mirrors
 * the real hook's seeding rules (started && !finalized → paused; entries and
 * finalized seeded from the passed transcript) and additionally honors a
 * per-scenario override at window.__MOCK.recording so the harness can drive
 * 'recording' / 'paused' / mic-blocked etc. The control callbacks transition
 * state, so Start AI / Pause / Resume / Finish work live in the mock.
 */
import { useState, useCallback, useRef } from 'https://esm.sh/preact@10.25.4/hooks';

// Ensure each entry has the fields TranscriptEntry reads when spread.
function normalize(items) {
  return (items || []).map((e, i) => ({
    item_id: e.item_id || `mock-${i}`,
    speaker: e.speaker || 'UNSPECIFIED',
    start_offset_ms: e.start_offset_ms || 0,
    end_offset_ms: e.end_offset_ms || e.start_offset_ms || 0,
    text: e.text || '',
    is_final: e.is_final !== false,
  }));
}

export function useRecording(noteId, initialTranscript) {
  const override = (typeof window !== 'undefined' && window.__MOCK && window.__MOCK.recording) || {};

  const [status, setStatus] = useState(() => {
    if (override.status) return override.status;
    // Per-instance status (lets multiple <Scribe>s on one page — e.g. the header
    // states page — show different recording states simultaneously).
    if (initialTranscript?.__recordingStatus) return initialTranscript.__recordingStatus;
    if (initialTranscript?.started && !initialTranscript.finalized) return 'paused';
    return 'idle';
  });
  const [entries, setEntries] = useState(() =>
    normalize(override.entries || initialTranscript?.items || []));
  const [finalized, setFinalized] = useState(() =>
    override.finalized ?? initialTranscript?.finalized ?? false);

  const error = override.error ?? null;
  const lastSaved = override.lastSaved ?? null;
  const audioLevel = override.audioLevel ?? (status === 'recording' ? 0.35 : 0);
  const silenceWarning = override.silenceWarning ?? false;
  const micBlocked = override.micBlocked ?? false;
  const micPrompting = override.micPrompting ?? false;
  const connectionLost = override.connectionLost ?? false;

  const startedRef = useRef(false);

  const startRecording = useCallback(() => { startedRef.current = true; setFinalized(false); setStatus('recording'); }, []);
  const pauseRecording = useCallback(() => setStatus('paused'), []);
  const resumeRecording = useCallback(() => setStatus('recording'), []);
  const finishRecording = useCallback(() => { setStatus('idle'); setFinalized(true); }, []);
  const retryMicPermission = useCallback(() => {}, []);

  return {
    status, entries, error, finalized, lastSaved, audioLevel,
    silenceWarning, micBlocked, micPrompting, connectionLost,
    startRecording, pauseRecording, resumeRecording, finishRecording, retryMicPermission,
  };
}
