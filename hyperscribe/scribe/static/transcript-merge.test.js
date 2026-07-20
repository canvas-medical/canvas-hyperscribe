import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  normalizeEntry,
  sortEntries,
  promoteStalePartials,
  mergeEntry,
  samplesToMs,
  reconnectSessionOffset,
  drainResolution,
  finishDrainDecision,
  buildConfigFrame,
  appendDictatedText,
  DICTATION_ENTRY_ID,
} from './transcript-merge.js';

test('buildConfigFrame conversation mode keeps the transcribe shape', () => {
  const f = buildConfigFrame('conversation', { encoding: 'PCM_S16LE', sample_rate: 16000, speech_locales: ['ENGLISH_US'], stream_id: 'stream1' });
  assert.equal(f.type, 'CONFIG');
  assert.deepEqual(f.speech_locales, ['ENGLISH_US']);
  assert.equal(f.streams[0].id, 'stream1');
  assert.equal(f.enable_audio_chunk_ack, true);
});

test('buildConfigFrame dictation mode emits the dictate shape', () => {
  const f = buildConfigFrame('dictation', { encoding: 'PCM_S16LE', sample_rate: 16000, dictation_locale: 'ENGLISH_US', punctuation_mode: 'EXPLICIT', text_field_context: { text: '', selection_start: 0, selection_length: 0 } });
  assert.equal(f.type, 'CONFIG');
  assert.equal(f.dictation_locale, 'ENGLISH_US');
  assert.equal(f.punctuation_mode, 'EXPLICIT');
  assert.deepEqual(f.text_field_context, { text: '', selection_start: 0, selection_length: 0 });
  assert.ok(!('streams' in f));
});

test('finishDrainDecision returns drained the moment the buffer empties', () => {
  assert.equal(finishDrainDecision({ pendingMs: 0, accepted: false }), 'drained');
  assert.equal(finishDrainDecision({ pendingMs: 0, accepted: true }), 'drained');
});

test('finishDrainDecision keeps waiting while a backlog remains, even if stalled (never truncates)', () => {
  assert.equal(finishDrainDecision({ pendingMs: 5000, accepted: false }), 'waiting');
});

test('finishDrainDecision returns accepted only on explicit provider accept with a backlog', () => {
  assert.equal(finishDrainDecision({ pendingMs: 5000, accepted: true }), 'accepted');
});

test('normalizeEntry derives a stable id from start_offset_ms when id is missing', () => {
  assert.equal(normalizeEntry({ start_offset_ms: 1200 }).item_id, '__noid_1200');
  assert.equal(normalizeEntry({ item_id: 'x', start_offset_ms: 5 }).item_id, 'x');
});

test('sortEntries orders by start_offset_ms then item_id', () => {
  const out = sortEntries([
    { item_id: 'b', start_offset_ms: 100 },
    { item_id: 'a', start_offset_ms: 100 },
    { item_id: 'c', start_offset_ms: 10 },
  ]);
  assert.deepEqual(out.map(e => e.item_id), ['c', 'a', 'b']);
});

test('promoteStalePartials finalizes partials that sit before the latest final', () => {
  const out = promoteStalePartials([
    { item_id: 'p', start_offset_ms: 10, is_final: false },
    { item_id: 'f', start_offset_ms: 50, is_final: true },
  ]);
  assert.equal(out.find(e => e.item_id === 'p').is_final, true);
});

test('mergeEntry replaces an exact item_id match in place', () => {
  const prev = [{ item_id: 'a', text: 'hi', start_offset_ms: 0, is_final: false }];
  const out = mergeEntry(prev, { item_id: 'a', text: 'hi there', start_offset_ms: 0, is_final: true });
  assert.equal(out.length, 1);
  assert.equal(out[0].text, 'hi there');
});

test('mergeEntry collapses a replayed duplicate (new id, near offset, same text)', () => {
  const prev = [{ item_id: 'old', text: 'not sure', speaker: '', start_offset_ms: 5000, is_final: true }];
  const out = mergeEntry(prev, { item_id: 'new', text: 'Not sure.', speaker: 'PATIENT', start_offset_ms: 5200, is_final: true });
  assert.equal(out.length, 1, 'duplicate must not append a second row');
  assert.equal(out[0].speaker, 'PATIENT', 'keeps the attributed version');
});

test('mergeEntry keeps the longer text when both are final+unattributed', () => {
  const prev = [{ item_id: 'old', text: 'the patient reports', start_offset_ms: 100, is_final: true }];
  const out = mergeEntry(prev, { item_id: 'new', text: 'the patient reports pain', start_offset_ms: 200, is_final: true });
  assert.equal(out.length, 1);
  assert.equal(out[0].text, 'the patient reports pain');
});

test('mergeEntry appends genuinely new content', () => {
  const prev = [{ item_id: 'a', text: 'hello', start_offset_ms: 0, is_final: true }];
  const out = mergeEntry(prev, { item_id: 'b', text: 'completely different', start_offset_ms: 9000, is_final: true });
  assert.equal(out.length, 2);
});

test('mergeEntry does not collapse same text far apart in time', () => {
  const prev = [{ item_id: 'a', text: 'okay', start_offset_ms: 0, is_final: true }];
  const out = mergeEntry(prev, { item_id: 'b', text: 'okay', start_offset_ms: 60000, is_final: true });
  assert.equal(out.length, 2, 'a genuine later "okay" is not a duplicate');
});

test('samplesToMs converts sample counts to milliseconds', () => {
  assert.equal(samplesToMs(16000, 16000), 1000);
  assert.equal(samplesToMs(8000, 16000), 500);
  assert.equal(samplesToMs(0, 16000), 0);
  assert.equal(samplesToMs(1000, 0), 0); // guard against divide-by-zero
});

test('reconnectSessionOffset anchors to audio-time from the session base', () => {
  // 30s of acked audio into a session that started at 0 -> base 30000ms.
  assert.equal(reconnectSessionOffset({ sessionStartBaseMs: 0, ackedSamples: 480000, sampleRate: 16000 }), 30000);
  // Session that itself started at 300000ms (post-resume) + 10s acked.
  assert.equal(reconnectSessionOffset({ sessionStartBaseMs: 300000, ackedSamples: 160000, sampleRate: 16000 }), 310000);
});

test('drainResolution returns drained the moment the buffer empties', () => {
  assert.equal(drainResolution({ pending: 0, msSinceProgress: 0, msSinceStart: 100, stallMs: 30000, capMs: 300000 }), 'drained');
  // drained wins even if the stall/cap thresholds are also exceeded.
  assert.equal(drainResolution({ pending: 0, msSinceProgress: 999999, msSinceStart: 999999, stallMs: 30000, capMs: 300000 }), 'drained');
});

test('drainResolution keeps waiting while draining within limits', () => {
  assert.equal(drainResolution({ pending: 5000, msSinceProgress: 1000, msSinceStart: 1000, stallMs: 30000, capMs: 300000 }), null);
});

test('drainResolution reports stalled when no progress for stallMs', () => {
  assert.equal(drainResolution({ pending: 5000, msSinceProgress: 30001, msSinceStart: 40000, stallMs: 30000, capMs: 300000 }), 'stalled');
});

test('drainResolution reports cap when the hard cap is exceeded', () => {
  // Still making slow progress (under stall) but total time blew the cap.
  assert.equal(drainResolution({ pending: 5000, msSinceProgress: 1000, msSinceStart: 300001, stallMs: 30000, capMs: 300000 }), 'cap');
});

test('drainResolution prefers stalled over cap when both trip', () => {
  assert.equal(drainResolution({ pending: 5000, msSinceProgress: 40000, msSinceStart: 400000, stallMs: 30000, capMs: 300000 }), 'stalled');
});

test('appendDictatedText seeds a single dictation entry from the first delta', () => {
  const out = appendDictatedText([], 'One');
  assert.equal(out.length, 1);
  assert.equal(out[0].item_id, DICTATION_ENTRY_ID);
  assert.equal(out[0].text, 'One');
  assert.equal(out[0].speaker, 'DOCTOR');
  assert.equal(out[0].is_final, true);
});

test('appendDictatedText concatenates every delta into ONE entry, verbatim', () => {
  // dictate-ws deltas carry their own leading spaces / sub-word splits; Nabla
  // owns spacing, so plain concatenation must reconstruct the monologue.
  let out = [];
  for (const delta of ['One', ' follow', '-', 'up', ' visit']) {
    out = appendDictatedText(out, delta);
  }
  assert.equal(out.length, 1, 'a monologue is one row, not a row per word');
  assert.equal(out[0].text, 'One follow-up visit');
  assert.equal(out[0].item_id, DICTATION_ENTRY_ID);
});

test('appendDictatedText past 12 deltas is still a single entry (no ordering ambiguity)', () => {
  let out = [];
  for (let i = 0; i < 15; i++) out = appendDictatedText(out, ` w${i}`);
  assert.equal(out.length, 1);
  // A single fixed-id entry cannot be reordered by sortEntries on reload.
  assert.deepEqual(sortEntries(out).map(e => e.item_id), [DICTATION_ENTRY_ID]);
});

test('appendDictatedText ignores empty deltas is the callers job; here it appends what it is given', () => {
  // The hook guards empty text before calling; the pure fn appends verbatim.
  const out = appendDictatedText([{ item_id: DICTATION_ENTRY_ID, text: 'hi', speaker: 'DOCTOR', start_offset_ms: 0, end_offset_ms: 0, is_final: true }], ' there');
  assert.equal(out[0].text, 'hi there');
});

// Integration guard for the actual KOALA-5934 fix: an item Nabla emitted but
// did not ack before a drop is replayed and re-transcribed in the fresh
// session. With audio-time rebasing it lands at the same displayed offset as
// its original and collapses. Replicates handleTranscriptItem's `start + base`
// glue inline (that glue is not extracted). Fails if the offset fix regresses
// to wall-clock: base2 would exceed the 1500ms window and leave two rows.
test('replayed item after audio-time reconnect collapses onto its original', () => {
  const sampleRate = 16000;
  // Session 1: item transcribed at audio-offset 55000ms, base 0.
  let entries = mergeEntry([], {
    item_id: 's1', text: 'not sure', speaker: '', start_offset_ms: 0 + 55000, is_final: true,
  });
  // Reconnect after 55s of acked audio -> new session base = 55000ms.
  const base2 = reconnectSessionOffset({ sessionStartBaseMs: 0, ackedSamples: 55 * sampleRate, sampleRate });
  // Session 2 re-emits the same utterance at its offset 0, rebased by base2.
  entries = mergeEntry(entries, {
    item_id: 's2', text: 'Not sure.', speaker: 'PATIENT', start_offset_ms: 0 + base2, is_final: true,
  });
  assert.equal(entries.length, 1, 'replay must not duplicate');
  assert.equal(entries[0].speaker, 'PATIENT', 'keeps the attributed replay');
});
