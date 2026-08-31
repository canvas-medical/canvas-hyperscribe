import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  computeScore,
  isComplete,
  collectQuestionnaireScores,
} from '../../hyperscribe/scribe/static/questionnaire-score.js';

// Helpers to build the question shapes used by the scribe questionnaire UI.
const radio = (selectedScore) => ({
  type: 'SING',
  responses: [
    { selected: false, score_value: '0' },
    { selected: selectedScore != null, score_value: String(selectedScore ?? 0) },
  ],
});

const checkbox = (selectedScores) => ({
  type: 'MULT',
  responses: selectedScores.map(s => ({ selected: s != null, score_value: String(s ?? 0) })),
});

const integer = (value) => ({
  type: 'INT',
  responses: [{ value: value == null ? '' : String(value) }],
});

const text = (value) => ({
  type: 'TXT',
  responses: [{ value: value ?? '' }],
});

const skipped = () => ({ type: 'SING', skipped: true, responses: [] });

test('computeScore sums selected radio score values', () => {
  assert.equal(computeScore([radio(3), radio(2), radio(1)]), 6);
});

test('computeScore sums all selected checkbox responses', () => {
  assert.equal(computeScore([checkbox([1, 2, null]), checkbox([4])]), 7);
});

test('computeScore adds integer answers as numbers', () => {
  assert.equal(computeScore([integer(5), integer(7)]), 12);
});

test('computeScore ignores free-text responses', () => {
  assert.equal(computeScore([radio(3), text('hello')]), 3);
});

test('computeScore ignores skipped questions', () => {
  assert.equal(computeScore([radio(3), skipped()]), 3);
});

test('computeScore returns null when no numeric data could be parsed', () => {
  assert.equal(computeScore([text('a'), text('b')]), null);
  assert.equal(computeScore([]), null);
  assert.equal(computeScore(null), null);
});

test('computeScore does not fall back to LOINC codes that happen to parse', () => {
  // A radio response with only a numeric `code` (e.g. "44249-1") and no score_value
  // must not contribute — that would silently fabricate clinical scores.
  const q = { type: 'SING', responses: [{ selected: true, code: '44249-1' }] };
  assert.equal(computeScore([q]), null);
});

test('isComplete requires every question to be answered or skipped', () => {
  assert.equal(isComplete([radio(3), radio(2)]), true);
  assert.equal(isComplete([radio(3), { type: 'SING', responses: [{ selected: false }] }]), false);
  assert.equal(isComplete([radio(3), skipped()]), true);
  assert.equal(isComplete([integer(5), integer(null)]), false);
  assert.equal(isComplete([]), false);
  assert.equal(isComplete(null), false);
});

test('collectQuestionnaireScores returns one entry per scored complete questionnaire', () => {
  const commands = [
    {
      command_type: 'questionnaire',
      data: { questionnaire_name: 'PHQ-9', is_scored: true, questions: [radio(2), radio(1), radio(3)] },
    },
    {
      command_type: 'questionnaire',
      data: { questionnaire_name: 'GAD-7', is_scored: true, questions: [radio(1), radio(2)] },
    },
  ];
  assert.deepEqual(collectQuestionnaireScores(commands), [
    { name: 'PHQ-9', score: 6 },
    { name: 'GAD-7', score: 3 },
  ]);
});

test('collectQuestionnaireScores skips unscored and incomplete questionnaires', () => {
  const commands = [
    // unscored
    {
      command_type: 'questionnaire',
      data: { questionnaire_name: 'Notes', is_scored: false, questions: [radio(2)] },
    },
    // incomplete
    {
      command_type: 'questionnaire',
      data: {
        questionnaire_name: 'AUDIT-C',
        is_scored: true,
        questions: [radio(2), { type: 'SING', responses: [{ selected: false }] }],
      },
    },
    // ok
    {
      command_type: 'questionnaire',
      data: { questionnaire_name: 'PHQ-2', is_scored: true, questions: [radio(2), radio(1)] },
    },
  ];
  assert.deepEqual(collectQuestionnaireScores(commands), [{ name: 'PHQ-2', score: 3 }]);
});

test('collectQuestionnaireScores ignores non-questionnaire commands', () => {
  const commands = [
    { command_type: 'vitals', data: {} },
    {
      command_type: 'questionnaire',
      data: { questionnaire_name: 'PHQ-9', is_scored: true, questions: [radio(2)] },
    },
  ];
  assert.deepEqual(collectQuestionnaireScores(commands), [{ name: 'PHQ-9', score: 2 }]);
});

test('collectQuestionnaireScores tolerates null / undefined input', () => {
  assert.deepEqual(collectQuestionnaireScores(null), []);
  assert.deepEqual(collectQuestionnaireScores(undefined), []);
  assert.deepEqual(collectQuestionnaireScores([]), []);
});
