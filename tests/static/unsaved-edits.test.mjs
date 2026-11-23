import { test } from 'node:test';
import assert from 'node:assert/strict';
import { unsavedEditsMessage, editKeyBase } from '../../hyperscribe/scribe/static/unsaved-edits.js';

test('names the single unsaved section', () => {
  assert.equal(unsavedEditsMessage(1, ['Chief Complaint']),
    '1 unsaved edit: Chief Complaint \u2014 save or cancel to continue.');
});

test('lists each section once, in order', () => {
  assert.equal(unsavedEditsMessage(3, ['Plan', 'Plan', 'Vitals']),
    '3 unsaved edits: Plan, Vitals \u2014 save or cancel to continue.');
});

test('keeps the old wording when no section was found', () => {
  assert.equal(unsavedEditsMessage(1, [null]),
    '1 unsaved edit \u2014 save or cancel to continue.');
  assert.equal(unsavedEditsMessage(2),
    '2 unsaved edits \u2014 save or cancel to continue.');
});

test('strips the field suffix from editing keys', () => {
  assert.equal(editKeyBase('3:code'), '3');
  assert.equal(editKeyBase(3), '3');
  assert.equal(editKeyBase('physical_exam_placeholder'), 'physical_exam_placeholder');
});
