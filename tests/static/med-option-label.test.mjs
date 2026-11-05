import { test } from 'node:test';
import assert from 'node:assert/strict';

import { medicationOptionLabel, SIG_LABEL_MAX_LENGTH } from '../../hyperscribe/scribe/static/med-option-label.js';

test('joins the drug name and its directions with a hyphen', () => {
  assert.equal(
    medicationOptionLabel('Lisinopril 10 mg tablet', 'Take 1 tablet by mouth daily'),
    'Lisinopril 10 mg tablet - Take 1 tablet by mouth daily',
  );
});

test('distinguishes two entries of the same drug, which is the whole point', () => {
  const first = medicationOptionLabel('Lisinopril 10 mg tablet', 'Take 1 tablet by mouth daily');
  const second = medicationOptionLabel('Lisinopril 10 mg tablet', 'Take 2 tablets by mouth at bedtime');
  assert.notEqual(first, second);
});

test('returns the name alone when there are no directions, with no trailing separator', () => {
  assert.equal(medicationOptionLabel('Atorvastatin 20 mg tablet', ''), 'Atorvastatin 20 mg tablet');
  assert.equal(medicationOptionLabel('Atorvastatin 20 mg tablet', '   '), 'Atorvastatin 20 mg tablet');
  assert.equal(medicationOptionLabel('Atorvastatin 20 mg tablet', null), 'Atorvastatin 20 mg tablet');
  assert.equal(medicationOptionLabel('Atorvastatin 20 mg tablet', undefined), 'Atorvastatin 20 mg tablet');
});

test('trims both inputs and collapses runs of whitespace inside the directions', () => {
  assert.equal(
    medicationOptionLabel('  Metformin 500 mg  ', 'Take 1 tablet\n  twice   daily '),
    'Metformin 500 mg - Take 1 tablet twice daily',
  );
});

test('leaves directions at the limit untouched', () => {
  const sig = 'x'.repeat(SIG_LABEL_MAX_LENGTH);
  assert.equal(medicationOptionLabel('Drug', sig), `Drug - ${sig}`);
});

test('cuts past the limit back to the last whole word and appends an ellipsis', () => {
  const sig = 'Take 1 tablet by mouth twice daily with meals, hold if fasting or if eGFR drops below 30';
  assert.equal(
    medicationOptionLabel('Metformin HCl 500 mg tablet', sig),
    'Metformin HCl 500 mg tablet - Take 1 tablet by mouth twice daily with meals, hold if...',
  );
});

test('falls back to a hard cut when the overlong directions have no space to break on', () => {
  const sig = 'y'.repeat(SIG_LABEL_MAX_LENGTH + 20);
  assert.equal(medicationOptionLabel('Drug', sig), `Drug - ${'y'.repeat(SIG_LABEL_MAX_LENGTH)}...`);
});

test('honors an explicit maxLength', () => {
  assert.equal(medicationOptionLabel('Drug', 'take one tablet daily', 12), 'Drug - take one...');
});

test('returns the directions alone when the name is missing', () => {
  assert.equal(medicationOptionLabel('', 'Take 1 tablet daily'), 'Take 1 tablet daily');
  assert.equal(medicationOptionLabel(null, 'Take 1 tablet daily'), 'Take 1 tablet daily');
});

test('returns an empty string when both inputs are missing', () => {
  assert.equal(medicationOptionLabel(null, null), '');
  assert.equal(medicationOptionLabel(undefined, undefined), '');
});
