import { useState, useRef, useCallback, useEffect } from 'https://esm.sh/preact@10.25.4/hooks';
import { createDictationClient } from './dictationClient.js';

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';
const TARGET_SAMPLE_RATE = 16000;
// Silence detection (mirrors recording-hook): RMS below this counts as silence.
// If the mic stays silent this long while listening, surface a "no audio" hint —
// the common muted-mic / wrong-input-device failure. Seeded at listening-start so
// a mic that is dead from the very first frame is caught too.
const SILENCE_RMS_THRESHOLD = 0.005;
const SILENCE_TIMEOUT_MS = 4000;

/**
 * Tear down the mic capture graph. Mirrors recording-hook's cleanupAudio but
 * kept local so dictation shares no capture state with ambient recording.
 */
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
    streamRef.current.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }
}

/**
 * useFieldDictation — dictate into ONE note field at a time via Nabla dictate-ws.
 *
 * Deliberately independent of useRecording: its own client, its own mic capture,
 * and it never writes to the transcript / note-generation pipeline. Dictated
 * text is delivered incrementally through `onDictatedText(fieldId, text)` so the
 * caller can append it to the field live; on stop() the field already holds the
 * final text.
 *
 * The browser can only capture one microphone at a time, so the CALLER must not
 * start dictation while ambient recording is active (gate the mic affordance on
 * the recording status).
 *
 * @param {function(string, string): void} onDictatedText — (fieldId, textUnit)
 * @returns {object} controls — activeField, status ('idle'|'connecting'|'listening'|'stopping'),
 *   error, micBlocked, silent (no audio detected while listening), start(fieldId, currentText), stop().
 */
export function useFieldDictation(onDictatedText) {
  const [activeField, setActiveField] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [micBlocked, setMicBlocked] = useState(false);
  const [silent, setSilent] = useState(false);

  const clientRef = useRef(null);
  const audioCtxRef = useRef(null);
  const streamRef = useRef(null);
  const workletNodeRef = useRef(null);
  const activeFieldRef = useRef(null);
  // Silence tracking (refs so audio frames never trigger re-renders; `silent`
  // state flips only on transition).
  const lastAudioTimeRef = useRef(0);
  const silentRef = useRef(false);
  // Keep the latest callback without re-creating start().
  const onTextRef = useRef(onDictatedText);
  onTextRef.current = onDictatedText;

  const resetState = useCallback(() => {
    setStatus('idle');
    setActiveField(null);
    activeFieldRef.current = null;
    silentRef.current = false;
    setSilent(false);
    // (no audio-level meter state — dictation shows a CSS-only pulse, so we avoid
    // re-rendering the summary on every audio frame; only `silent` flips, and only
    // on transition.)
  }, []);

  const stop = useCallback(async () => {
    if (!clientRef.current) {
      resetState();
      return;
    }
    setStatus('stopping');
    // Stop capturing first so no more audio is queued, then drain + END.
    cleanupAudio(audioCtxRef, streamRef, workletNodeRef);
    const client = clientRef.current;
    clientRef.current = null;
    client.onDictatedText = () => {};
    client.onError = () => {};
    try {
      await client.end();
    } catch {
      // best-effort teardown
    }
    resetState();
  }, [resetState]);

  const start = useCallback(async (fieldId, currentText = '') => {
    // One field at a time — finish any in-flight session first.
    if (clientRef.current) {
      await stop();
    }
    setError(null);
    setMicBlocked(false);
    setActiveField(fieldId);
    activeFieldRef.current = fieldId;
    setStatus('connecting');

    const fail = (message) => {
      if (message) setError(message);
      resetState();
      return false;
    };

    let config;
    try {
      const res = await fetch(`${API_BASE}/dictation-config`, { cache: 'no-store' });
      config = await res.json();
      if (config.error) return fail(config.error);
    } catch {
      return fail('Failed to get dictation config');
    }

    let client;
    try {
      client = createDictationClient(config);
    } catch (err) {
      return fail(err.message || 'Failed to start dictation');
    }
    client.onDictatedText = (text) => {
      const fid = activeFieldRef.current;
      if (fid != null && onTextRef.current) onTextRef.current(fid, text);
    };
    client.onError = (msg, code) => {
      // 83011 = Nabla silence timeout; the server closes the socket, which the
      // client already surfaces via its close handling — not user-actionable.
      if (code === 83011) return;
      setError(code ? `${msg} (${code})` : msg);
    };
    clientRef.current = client;

    // Acquire the mic and start capturing BEFORE opening the socket, so buffered
    // audio drains as soon as CONFIG is sent (avoids Nabla's silence timeout) and
    // no leading speech is lost while connecting.
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: TARGET_SAMPLE_RATE, channelCount: 1, echoCancellation: true },
      });
    } catch {
      client.forceEnd();
      clientRef.current = null;
      setMicBlocked(true);
      return fail(null);
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
        if (rms >= SILENCE_RMS_THRESHOLD) {
          lastAudioTimeRef.current = Date.now();
          if (silentRef.current) {
            silentRef.current = false;
            setSilent(false);
          }
        }
        if (clientRef.current) clientRef.current.sendAudio(pcm16);
      };

      source.connect(workletNode);
      workletNode.connect(audioCtx.destination);
    } catch (err) {
      client.forceEnd();
      clientRef.current = null;
      cleanupAudio(audioCtxRef, streamRef, workletNodeRef);
      return fail('Audio setup failed: ' + err.message);
    }

    // Open the socket last. sendAudio() has been buffering into the client, so
    // the queued audio flushes the moment CONFIG is sent.
    try {
      const caret = currentText.length;
      await client.connect({ text: currentText, selection_start: caret, selection_length: 0 });
    } catch {
      client.forceEnd();
      clientRef.current = null;
      cleanupAudio(audioCtxRef, streamRef, workletNodeRef);
      return fail('Failed to connect to dictation service');
    }

    lastAudioTimeRef.current = Date.now();
    silentRef.current = false;
    setSilent(false);
    setStatus('listening');
    return true;
  }, [stop, resetState]);

  // Flip `silent` on while listening if no above-threshold audio has arrived for
  // SILENCE_TIMEOUT_MS. Only touches state on transition, so no per-frame churn.
  useEffect(() => {
    if (status !== 'listening') return undefined;
    const timer = setInterval(() => {
      const last = lastAudioTimeRef.current || Date.now();
      if (Date.now() - last >= SILENCE_TIMEOUT_MS && !silentRef.current) {
        silentRef.current = true;
        setSilent(true);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [status]);

  // Tear everything down if the component unmounts mid-dictation.
  useEffect(() => () => {
    cleanupAudio(audioCtxRef, streamRef, workletNodeRef);
    if (clientRef.current) {
      clientRef.current.forceEnd();
      clientRef.current = null;
    }
  }, []);

  return { activeField, status, error, micBlocked, silent, start, stop };
}
