import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  clearDrafted,
  countDrafted,
  draftedCountLine,
  isDrafted,
  mergeFilled,
} from '../../hyperscribe/scribe/static/questionnaire-fill.js';
import { computeScore, isComplete } from '../../hyperscribe/scribe/static/questionnaire-score.js';

const radio = (dbid, options) => ({
  dbid,
  label: `Q${dbid}`,
  type: 'SING',
  responses: options.map(([odbid, value, score]) => ({
    dbid: odbid, value, code: '', score_value: String(score), selected: false, comment: null,
  })),
});

const checkbox = (dbid, options) => ({ ...radio(dbid, options), type: 'MULT' });

const text = (dbid, value = '') => ({
  dbid,
  label: `Q${dbid}`,
  type: 'TXT',
  responses: [{ dbid: 900 + dbid, value, code: '', score_value: '', selected: value !== '', comment: null }],
});

const fill = (...evidence) => ({
  status: 'answered',
  confidence: 'high',
  rationale: 'because',
  evidence: evidence.length ? evidence : [{ speaker: 'patient', quote: 'a few days', item_id: 't1' }],
});

const select = (question, dbid, extra = {}) => ({
  ...question,
  ...extra,
  responses: question.responses.map(r => ({ ...r, selected: r.dbid === dbid })),
});

test('mergeFilled marks incoming answers proposed rather than selected', () => {
  const current = { questions: [radio(1, [[10, 'Not at all', 0], [11, 'Several days', 1]])] };
  const filled = { questions: [{ ...select(radio(1, [[10, 'Not at all', 0], [11, 'Several days', 1]]), 11), fill: fill() }] };

  const merged = mergeFilled(current, filled);
  const responses = merged.questions[0].responses;
  assert.equal(responses[1].selected, true);
  assert.equal(responses[1].proposed, true);
  assert.equal(responses[0].proposed, undefined);
  assert.equal(merged.questions[0].fill.status, 'answered');
});

test('mergeFilled never overwrites an answer the provider already gave', () => {
  // The automatic fill runs in parallel with note generation, so a draft can land while
  // the clinician is typing. Their answer has to win.
  const answered = select(radio(1, [[10, 'Not at all', 0], [11, 'Several days', 1]]), 10);
  const filled = { questions: [{ ...select(radio(1, [[10, 'Not at all', 0], [11, 'Several days', 1]]), 11), fill: fill() }] };

  const merged = mergeFilled({ questions: [answered] }, filled);
  assert.deepEqual(merged.questions[0].responses.map(r => r.selected), [true, false]);
  assert.equal(merged.questions[0].fill, undefined);
});

test('mergeFilled leaves a typed free-text answer alone', () => {
  const filled = { questions: [{ ...text(1, 'nurse'), fill: fill() }] };
  const merged = mergeFilled({ questions: [text(1, 'truck driver')] }, filled);
  assert.equal(merged.questions[0].responses[0].value, 'truck driver');
  assert.equal(merged.questions[0].fill, undefined);
});

test('mergeFilled matches responses by dbid, not position', () => {
  const current = { questions: [radio(1, [[10, 'Not at all', 0], [11, 'Several days', 1]])] };
  const reordered = { dbid: 1, type: 'SING', fill: fill(), responses: [
    { dbid: 11, value: 'Several days', selected: true },
    { dbid: 10, value: 'Not at all', selected: false },
  ] };
  const merged = mergeFilled(current, { questions: [reordered] });
  assert.deepEqual(merged.questions[0].responses.map(r => !!r.proposed), [false, true]);
});

test('mergeFilled ignores an incoming question with no fill block', () => {
  const current = { questions: [radio(1, [[10, 'No', 0], [11, 'Yes', 1]])] };
  const filled = { questions: [select(radio(1, [[10, 'No', 0], [11, 'Yes', 1]]), 11)] };
  const merged = mergeFilled(current, filled);
  assert.deepEqual(merged.questions[0].responses.map(r => r.selected), [false, false]);
});

test('a merged payload still scores and reports completion', () => {
  // The regression that matters: an earlier version emitted only the answered subset with
  // no score_value, so computeScore returned null and isComplete could never be true.
  const current = { is_scored: true, questions: [
    radio(1, [[10, 'Not at all', 0], [11, 'Several days', 1]]),
    radio(2, [[20, 'Not at all', 0], [21, 'Nearly every day', 3]]),
  ] };
  const filled = { is_scored: true, scoring_function_name: 'sum', questions: [
    { ...select(radio(1, [[10, 'Not at all', 0], [11, 'Several days', 1]]), 11), fill: fill() },
    { ...select(radio(2, [[20, 'Not at all', 0], [21, 'Nearly every day', 3]]), 21), fill: fill() },
  ] };

  const merged = mergeFilled(current, filled);
  assert.equal(isComplete(merged.questions), true);
  assert.equal(computeScore(merged.questions), 4);
  assert.equal(merged.scoring_function_name, 'sum');
});

test('isDrafted covers single choice, multiselect and free text alike', () => {
  const single = mergeFilled(
    { questions: [radio(1, [[10, 'No', 0], [11, 'Yes', 1]])] },
    { questions: [{ ...select(radio(1, [[10, 'No', 0], [11, 'Yes', 1]]), 11), fill: fill() }] },
  ).questions[0];

  const multi = mergeFilled(
    { questions: [checkbox(2, [[20, 'Sleep', 1], [21, 'Energy', 1], [22, 'Focus', 1]])] },
    { questions: [{
      dbid: 2, type: 'MULT', fill: fill(),
      responses: [{ dbid: 20, selected: false }, { dbid: 21, selected: true }, { dbid: 22, selected: true }],
    }] },
  ).questions[0];

  const free = mergeFilled(
    { questions: [text(3)] },
    { questions: [{ ...text(3, 'truck driver'), fill: fill() }] },
  ).questions[0];

  // One marker per question no matter how many answers it holds — a multiselect has two
  // proposed chips and a free-text answer has no chips at all.
  assert.equal(isDrafted(single), true);
  assert.equal(isDrafted(multi), true);
  assert.equal(multi.responses.filter(r => r.proposed).length, 2);
  assert.equal(isDrafted(free), true);
  assert.equal(free.responses[0].value, 'truck driver');
  assert.equal(countDrafted([single, multi, free]), 3);
});

test('a question stops being drafted once no proposed response remains', () => {
  const multi = mergeFilled(
    { questions: [checkbox(2, [[20, 'Sleep', 1], [21, 'Energy', 1]])] },
    { questions: [{ dbid: 2, type: 'MULT', fill: fill(), responses: [{ dbid: 20, selected: true }, { dbid: 21, selected: true }] }] },
  ).questions[0];

  const oneConfirmed = { ...multi, responses: multi.responses.map((r, i) => i === 0 ? { ...r, proposed: false } : r) };
  assert.equal(isDrafted(oneConfirmed), true, 'still drafted while one proposed answer remains');

  const allConfirmed = { ...multi, responses: multi.responses.map(r => ({ ...r, proposed: false })) };
  assert.equal(isDrafted(allConfirmed), false);
});

test('the fill block carries every speaker turn', () => {
  // A bare "No" on a suicidality screen is not interpretable without the provider's
  // question, so both turns have to survive the merge.
  const filled = { questions: [{
    ...select(radio(1, [[10, 'Not at all', 0], [11, 'Several days', 1]]), 10),
    fill: fill(
      { speaker: 'provider', quote: 'Any thoughts of harming yourself?', item_id: 't1' },
      { speaker: 'patient', quote: 'No, nothing like that.', item_id: 't2' },
    ),
  }] };
  const merged = mergeFilled({ questions: [radio(1, [[10, 'Not at all', 0], [11, 'Several days', 1]])] }, filled);
  assert.deepEqual(merged.questions[0].fill.evidence.map(t => t.speaker), ['provider', 'patient']);
});

test('clearDrafted drops drafted answers and keeps the provider their own', () => {
  const mine = select(radio(1, [[10, 'No', 0], [11, 'Yes', 1]]), 10);
  const drafted = mergeFilled(
    { questions: [radio(2, [[20, 'No', 0], [21, 'Yes', 1]])] },
    { questions: [{ ...select(radio(2, [[20, 'No', 0], [21, 'Yes', 1]]), 21), fill: fill() }] },
  ).questions[0];
  const typed = mergeFilled(
    { questions: [text(3)] },
    { questions: [{ ...text(3, 'nurse'), fill: fill() }] },
  ).questions[0];

  const cleared = clearDrafted([mine, drafted, typed]);
  assert.deepEqual(cleared[0].responses.map(r => r.selected), [true, false], 'provider answer untouched');
  assert.deepEqual(cleared[1].responses.map(r => r.selected), [false, false]);
  assert.equal(cleared[1].fill, null);
  assert.equal(cleared[2].responses[0].value, '');
});

test('mergeFilled tolerates missing inputs', () => {
  assert.equal(mergeFilled(null, { questions: [] }), null);
  const current = { questions: [text(1)] };
  assert.equal(mergeFilled(current, null), current);
});

// --- outcome status -----------------------------------------------------------------
//
// The server states the outcome rather than leaving the card to infer it. drafted === 0
// means both "read the transcript, nothing supported an answer" and "never ran", and the
// card has to say different things for each.

// Mirrors the branch in QuestionnaireForm's footer, kept in sync with questionnaire-row.js.
function footerMessage(status, drafted, total, canFill = true) {
  if (!canFill) return 'Available when recording ends';
  if (status === 'busy') return 'Reading transcript';
  if (status === 'failed') return 'Fill failed. No answers changed.';
  if (status === 'no_transcript') return 'No transcript on this note.';
  if (status === 'abstained') return 'No answers found in the transcript.';
  if (drafted > 0 && drafted < total) return `${drafted} of ${total} answered from the transcript`;
  return null;
}

test('an abstention reads as a result, not a failure', () => {
  assert.equal(footerMessage('abstained', 0, 9), 'No answers found in the transcript.');
  assert.notEqual(footerMessage('abstained', 0, 9), footerMessage('failed', 0, 9));
});

test('an empty transcript is not reported as a failure', () => {
  // Returning [] from the server used to land here as "Fill failed", which was wrong.
  assert.equal(footerMessage('no_transcript', 0, 9), 'No transcript on this note.');
});

test('the partial count appears only when some but not all questions filled', () => {
  assert.equal(footerMessage('filled', 3, 9), '3 of 9 answered from the transcript');
  // Complete: every chip is navy, so a count would restate the screen.
  assert.equal(footerMessage('filled', 9, 9), null);
  // None: the abstain message covers it, a "0 of 9" would be noise on top.
  assert.equal(footerMessage('abstained', 0, 9), 'No answers found in the transcript.');
});

test('recording state wins over every outcome', () => {
  assert.equal(footerMessage('abstained', 0, 9, false), 'Available when recording ends');
});

test('a partial fill still merges the answers it did find', () => {
  const current = { questions: [
    radio(1, [[10, 'No', 0], [11, 'Yes', 1]]),
    radio(2, [[20, 'No', 0], [21, 'Yes', 1]]),
  ] };
  const filled = { questions: [
    { ...select(radio(1, [[10, 'No', 0], [11, 'Yes', 1]]), 11), fill: fill() },
    radio(2, [[20, 'No', 0], [21, 'Yes', 1]]),
  ] };

  const merged = mergeFilled(current, filled);
  assert.equal(countDrafted(merged.questions), 1);
  assert.equal(footerMessage('filled', countDrafted(merged.questions), merged.questions.length),
    '1 of 2 answered from the transcript');
});

test('an abstained payload leaves every question blank and editable', () => {
  // The card still receives the whole questionnaire so the provider can fill it by hand.
  const current = { questions: [radio(1, [[10, 'No', 0], [11, 'Yes', 1]]), text(2)] };
  const abstained = { questions: [radio(1, [[10, 'No', 0], [11, 'Yes', 1]]), text(2)] };

  const merged = mergeFilled(current, abstained);
  assert.equal(countDrafted(merged.questions), 0);
  assert.equal(merged.questions.length, 2);
  assert.ok(merged.questions.every(q => q.responses.every(r => !r.selected)));
});

test('a complete fill says nothing, because every chip is already navy', () => {
  assert.equal(draftedCountLine(8, 8, 0), null);
  assert.equal(draftedCountLine(0, 8, 0), null);
});

test('a partial fill with nothing failed reports the plain count', () => {
  const line = draftedCountLine(5, 8, 0);
  assert.equal(line.text, '5 of 8 answered from the transcript');
  assert.equal(line.failed, false);
});

test('questions that were never read are named as such, not left looking abstained', () => {
  // THE REGRESSION. A failed chunk left its questions blank next to copy claiming the
  // model had considered them and declined. Silence read as a finding.
  const line = draftedCountLine(5, 8, 3);
  assert.equal(line.text, '5 of 8 answered. 3 could not be read.');
  assert.equal(line.failed, true);
});

test('unread wins over the complete-fill shortcut', () => {
  // 4 of 4 chips navy but a second chunk failed: still has to say so.
  const line = draftedCountLine(4, 4, 2);
  assert.equal(line.failed, true);
  assert.match(line.text, /2 could not be read/);
});
