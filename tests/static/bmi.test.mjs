import { test } from 'node:test';
import assert from 'node:assert/strict';

import { computeBmi } from '../../hyperscribe/scribe/static/bmi.js';

test('computes BMI from height (in) and weight (lbs), rounded to one decimal', () => {
  // 5'10" (70 in), 150 lbs -> (150 / 4900) * 703 = 21.519... -> 21.5
  assert.equal(computeBmi(70, 150), 21.5);
  // 5'5" (65 in), 200 lbs -> (200 / 4225) * 703 = 33.28... -> 33.3
  assert.equal(computeBmi(65, 200), 33.3);
  // 6'0" (72 in), 180 lbs -> (180 / 5184) * 703 = 24.40... -> 24.4
  assert.equal(computeBmi(72, 180), 24.4);
});

test('accepts numeric strings as input', () => {
  assert.equal(computeBmi('70', '150'), 21.5);
  assert.equal(computeBmi('70.0', '150.5'), computeBmi(70, 150.5));
});

test('returns null when either input is missing', () => {
  assert.equal(computeBmi(null, 150), null);
  assert.equal(computeBmi(70, null), null);
  assert.equal(computeBmi(null, null), null);
  assert.equal(computeBmi(undefined, 150), null);
  assert.equal(computeBmi(70, undefined), null);
});

test('returns null for non-finite or non-positive inputs', () => {
  assert.equal(computeBmi(0, 150), null);
  assert.equal(computeBmi(70, 0), null);
  assert.equal(computeBmi(-70, 150), null);
  assert.equal(computeBmi(70, -150), null);
  assert.equal(computeBmi(NaN, 150), null);
  assert.equal(computeBmi(70, NaN), null);
  assert.equal(computeBmi(Infinity, 150), null);
  assert.equal(computeBmi('not a number', 150), null);
});

test('suppresses values outside the plausible 5-100 range to dampen mid-keystroke noise', () => {
  // height = 1 in, weight = 150 lbs -> ~105000 BMI. Hidden.
  assert.equal(computeBmi(1, 150), null);
  // height = 70, weight = 0.1 -> 0.014 BMI. Hidden.
  assert.equal(computeBmi(70, 0.1), null);
});

test('shows values at the boundary of the plausible range', () => {
  // A very low but plausible BMI (extreme but documented).
  // height = 70, weight ~ 35 lbs -> 5.0
  assert.ok(computeBmi(70, 35) >= 5);
  // A very high but plausible BMI (extreme adult obesity).
  // height = 70, weight ~ 690 lbs -> ~99.0
  assert.ok(computeBmi(70, 690) <= 100);
});
