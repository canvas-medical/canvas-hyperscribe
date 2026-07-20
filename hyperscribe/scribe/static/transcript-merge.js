// Pure transcript-timeline logic for the scribe recording hook. No browser
// globals or esm.sh imports so it can be unit-tested under `node --test`.

// If Nabla emits a partial without a stable id, derive one from its start
// offset so re-emitted partials of the same utterance dedupe instead of
// stacking up as separate rows. start_offset_ms is stable across updates of
// the same partial (only end_offset grows), so it's the right key. No data
// is dropped.
export function normalizeEntry(item) {
  if (item && item.item_id) return item;
  return {
    ...item,
    item_id: `__noid_${(item && item.start_offset_ms) || 0}`,
  };
}

// Keep transcript entries chronological so out-of-order arrivals (backfilled
// finals, replay during reconnect) slot into their correct position rather
// than landing at the bottom.
export function sortEntries(items) {
  return [...items].sort((a, b) => {
    const aMs = a.start_offset_ms || 0;
    const bMs = b.start_offset_ms || 0;
    if (aMs !== bMs) return aMs - bMs;
    return (a.item_id || '').localeCompare(b.item_id || '');
  });
}

// A partial entry is "stuck" when at least one final entry has a later
// start_offset_ms — Nabla has moved on past this segment without ever
// finalizing it, so the row stays partial forever and accumulates text
// from later speaker turns under a "Listening" label. Promote those to
// final so they render with whatever speaker they have (or Unspecified)
// instead of staying in the listening intermediate state.
export function promoteStalePartials(items) {
  let latestFinalMs = -Infinity;
  for (const e of items) {
    if (e.is_final) {
      const ms = e.start_offset_ms || 0;
      if (ms > latestFinalMs) latestFinalMs = ms;
    }
  }
  if (latestFinalMs === -Infinity) return items;
  return items.map(e =>
    !e.is_final && (e.start_offset_ms || 0) < latestFinalMs
      ? { ...e, is_final: true }
      : e,
  );
}

// Only Provider/Doctor or Patient count as "attributed" — mirrors the UI
// speaker check in summary.js:TranscriptEntry. Anything else renders
// "Unspecified", so it carries less information than an attributed entry.
function isAttributed(speaker) {
  const s = (speaker || '').toUpperCase();
  return s === 'DOCTOR' || s.includes('PROVIDER') || s.includes('DOCTOR') ||
         s === 'PATIENT' || s.includes('PATIENT');
}

function normalizeText(text) {
  return (text || '')
    .toLowerCase()
    .replace(/[^\w\s]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// attributed-final (2) > final (1) > partial (0).
function infoScore(e) {
  if (e.is_final && isAttributed(e.speaker)) return 2;
  if (e.is_final) return 1;
  return 0;
}

// Pick the entry that carries more information: higher score wins; on a tie,
// the longer text wins; on an exact tie, keep the existing one (arg `a`).
function pickBetter(a, b) {
  const sa = infoScore(a);
  const sb = infoScore(b);
  if (sa !== sb) return sa > sb ? a : b;
  return (b.text || '').length > (a.text || '').length ? b : a;
}

// Merge an incoming transcript item into the accumulated entries.
//   1. Exact item_id -> in-place replace (same-session partial update).
//   2. Different id, |Δstart_offset| <= offsetWindowMs, equal/containing text
//      -> cross-session duplicate from reconnect replay; keep the better one.
//   3. Otherwise -> append.
// Step 2 only works once offsets are anchored to audio-time (reconnect
// continuity); with wall-clock rebasing the duplicate lands outside the window.
// TUNING (KOALA-5934): offsetWindowMs and the substring-containment rule are
// deliberately loose. Short tokens ("okay" vs "okay so") or two speakers
// overlapping within the window can over-merge. Tune both from real
// RECONNECTED audit data — watch UAT for over-merging, not just duplicates.
export function mergeEntry(entries, incoming, { offsetWindowMs = 1500 } = {}) {
  const idIdx = entries.findIndex(e => e.item_id === incoming.item_id);
  if (idIdx !== -1) {
    return entries.map((e, i) => (i === idIdx ? incoming : e));
  }

  const incMs = incoming.start_offset_ms || 0;
  const incText = normalizeText(incoming.text);
  const dupIdx = entries.findIndex(e => {
    if (e.item_id === incoming.item_id) return false;
    if (Math.abs((e.start_offset_ms || 0) - incMs) > offsetWindowMs) return false;
    const t = normalizeText(e.text);
    if (!t || !incText) return false;
    return t === incText || t.includes(incText) || incText.includes(t);
  });
  if (dupIdx !== -1) {
    const winner = pickBetter(entries[dupIdx], incoming);
    return entries.map((e, i) => (i === dupIdx ? winner : e));
  }

  return [...entries, incoming];
}

// Convert a PCM sample count to milliseconds of audio. Guards a zero/absent
// sample rate rather than returning Infinity/NaN.
export function samplesToMs(samples, sampleRate) {
  if (!sampleRate) return 0;
  return Math.round((samples / sampleRate) * 1000);
}

// The displayed-timeline base for a fresh Nabla session opened by an INTERNAL
// reconnect. Nabla restarts start_offset_ms at 0 and the client replays only
// un-acked audio, so offset 0 of the new session corresponds to audio-time
// = (acked audio so far). Anchoring here (instead of wall-clock elapsed) keeps
// replayed transcript at its true position: no dead gap, and duplicates land
// within mergeEntry's offset window so they collapse.
export function reconnectSessionOffset({ sessionStartBaseMs, ackedSamples, sampleRate }) {
  return (sessionStartBaseMs || 0) + samplesToMs(ackedSamples || 0, sampleRate);
}

// Decide whether the finish-time drain wait should stop, given the current
// pending backlog and how long we've been waiting. Pure so the stall/cap
// timing logic is unit-tested rather than living untested inside the React
// poll loop.
//   'drained' — buffer empty, everything reached the service (no data lost)
//   'stalled' — no progress for stallMs (network died again; tail lost)
//   'cap'     — total wait exceeded capMs (pathological slow drain; tail lost)
//   null      — still draining within limits, keep waiting
// Precedence: drained first (empty buffer is success regardless of clocks),
// then stalled, then cap.
export function drainResolution({ pending, msSinceProgress, msSinceStart, stallMs, capMs }) {
  if ((pending || 0) <= 0) return 'drained';
  if (msSinceProgress > stallMs) return 'stalled';
  if (msSinceStart > capMs) return 'cap';
  return null;
}

// Finish-time drain decision for the LOSSLESS path (KOALA-5934). Unlike
// drainResolution, a stalled network never truncates: the only non-drained
// exit is an explicit provider accept. Note generation is gated on this —
// 'drained' (buffer empty, nothing lost) or 'accepted' (provider chose to
// finalize with a gap); otherwise 'waiting' and the drain keeps going.
export function finishDrainDecision({ pendingMs, accepted }) {
  if ((pendingMs || 0) <= 0) return 'drained';
  if (accepted) return 'accepted';
  return 'waiting';
}
