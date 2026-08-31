import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  AD_HOC_SECTION_KEYS,
  mergeGeneratedCommands,
} from '../../hyperscribe/scribe/static/command-merge.js';
import { mergeFilled } from '../../hyperscribe/scribe/static/questionnaire-fill.js';

const questionnaireCard = (dbid, questions = []) => ({
  command_type: 'questionnaire',
  display: `Q${dbid}`,
  section_key: '_subjective_ad_hoc',
  _template_inserted: true,
  data: {
    questionnaire_dbid: dbid,
    questionnaire_name: `Q${dbid}`,
    is_scored: false,
    scoring_function_name: '',
    questions,
  },
});

const radio = (dbid, options) => ({
  dbid,
  label: `label ${dbid}`,
  type: 'SING',
  responses: options.map(([odbid, value]) => ({
    dbid: odbid, value, code: '', score_value: '1', selected: false, comment: null,
  })),
});

const select = (question, dbid) => ({
  ...question,
  responses: question.responses.map(r => ({ ...r, selected: r.dbid === dbid })),
});

const fill = () => ({
  status: 'answered', confidence: 'high', rationale: 'because',
  evidence: [{ speaker: 'patient', quote: 'most days', item_id: 't2' }],
});

test('generated commands land first, provider-added cards survive', () => {
  const previous = [
    { command_type: 'questionnaire', section_key: '_subjective_ad_hoc' },
    { command_type: 'vitals', section_key: '_objective_ad_hoc' },
  ];
  const generated = [{ command_type: 'hpi', section_key: 'history_of_present_illness' }];

  const merged = mergeGeneratedCommands(previous, generated);
  assert.deepEqual(merged.map(c => c.command_type), ['hpi', 'questionnaire', 'vitals']);
});

test('a template card is dropped when generation produced that command type', () => {
  // Otherwise the note would show both the template's card and the generated one.
  const previous = [
    { command_type: 'ros', section_key: '_ros', _template_inserted: true },
    { command_type: 'physical_exam', section_key: 'physical_exam', _template_inserted: true },
  ];
  const generated = [{ command_type: 'ros', section_key: '_ros' }];

  const merged = mergeGeneratedCommands(previous, generated);
  assert.deepEqual(merged.map(c => c.command_type), ['ros', 'physical_exam']);
  assert.equal(merged.filter(c => c.command_type === 'ros').length, 1);
});

test('a non-template, non-ad-hoc card is not carried over', () => {
  const previous = [{ command_type: 'hpi', section_key: 'history_of_present_illness' }];
  const merged = mergeGeneratedCommands(previous, []);
  assert.deepEqual(merged, []);
});

test('missing inputs are tolerated', () => {
  assert.deepEqual(mergeGeneratedCommands(null, null), []);
  assert.deepEqual(mergeGeneratedCommands(undefined, [{ command_type: 'hpi' }]).length, 1);
});

test('every ad-hoc section key survives generation', () => {
  const previous = [...AD_HOC_SECTION_KEYS].map(key => ({ command_type: 'x', section_key: key }));
  const merged = mergeGeneratedCommands(previous, []);
  assert.equal(merged.length, AD_HOC_SECTION_KEYS.size);
});

test('drafted questionnaire answers survive a later generation response', () => {
  // THE REGRESSION. The automatic fill lands while generation is still running and merges
  // its answers. Generation must then merge against that post-fill state. Reading a
  // snapshot taken when Generate was clicked silently erased every drafted answer a few
  // seconds after it appeared, with no error anywhere.
  const question = radio(10, [[100, 'Not at all'], [101, 'Nearly every day']]);
  const beforeFill = [questionnaireCard(7, [question])];

  // 1. the fill lands, merging drafted answers into the card
  const filledCard = mergeFilled(
    { ...beforeFill[0].data, dbid: 7, questions: [question] },
    { questions: [{ ...select(question, 101), fill: fill() }] },
  );
  const afterFill = [{ ...beforeFill[0], data: { ...beforeFill[0].data, questions: filledCard.questions } }];
  assert.equal(afterFill[0].data.questions[0].responses[1].proposed, true, 'precondition: answer drafted');

  // 2. generation returns and merges against the LIVE list
  const merged = mergeGeneratedCommands(afterFill, [{ command_type: 'hpi', section_key: 'history_of_present_illness' }]);

  const card = merged.find(c => c.command_type === 'questionnaire');
  assert.ok(card, 'the questionnaire card survives generation');
  assert.equal(card.data.questions[0].responses[1].proposed, true, 'the drafted answer survives generation');
  assert.equal(card.data.questions[0].fill.status, 'answered', 'the provenance survives too');
});

test('merging against the pre-fill snapshot loses the answers, which is the bug', () => {
  // Pins the failure mode so a future refactor cannot quietly reintroduce it.
  const question = radio(10, [[100, 'Not at all'], [101, 'Nearly every day']]);
  const beforeFill = [questionnaireCard(7, [question])];

  const staleMerge = mergeGeneratedCommands(beforeFill, []);
  const card = staleMerge.find(c => c.command_type === 'questionnaire');
  assert.equal(card.data.questions[0].responses[1].proposed, undefined,
    'merging the stale snapshot yields a card with no drafted answer');
});
