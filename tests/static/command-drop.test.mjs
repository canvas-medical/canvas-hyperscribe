import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  dropReason,
  isIntentionalDrop,
  isDismissedCondition,
} from '../../hyperscribe/scribe/static/command-drop.js';

// The record shape taken verbatim from the cached ScribeSummary rows of the notes that
// KOALA-6555 made unsignable on brigade: command_type assess, data.rejected true,
// data.accepted ALSO true (dismissAssess does not clear it), empty narrative, a populated
// condition_id, no `selected` key at all, and no command_uuid.
const STUCK_DISMISSED_ASSESS = {
  command_type: 'assess',
  display: 'Chronic kidney disease, stage 3a',
  section_key: 'assessment_and_plan',
  command_uuid: null,
  already_documented: false,
  data: {
    rejected: true,
    accepted: true,
    narrative: '',
    condition_id: 'c0ffee00-0000-4000-8000-000000000000',
  },
};

test('KOALA-6555: a dismissed assess card is an intentional drop, not a validation failure', () => {
  // This is the regression. Before the fix, this command classified as 'validation',
  // which hard-blocked Approve with "This command has invalid values" and left the note
  // permanently unsignable — naming a card hidden by the hideRejected default.
  assert.equal(dropReason(STUCK_DISMISSED_ASSESS), 'dismissed');
  assert.equal(isIntentionalDrop(STUCK_DISMISSED_ASSESS), true);
});

test('a dismissed assess is still intentional when the backend supplied selected: true', () => {
  // Backend proposals ship `selected: true` (CommandProposal.selected defaults True), so
  // the classification must not lean on `selected` being absent.
  const withSelected = { ...STUCK_DISMISSED_ASSESS, selected: true };
  assert.equal(dropReason(withSelected), 'dismissed');
  assert.equal(isIntentionalDrop(withSelected), true);
});

test('a dismissed diagnose card is also an intentional drop', () => {
  const dismissedDiagnose = {
    command_type: 'diagnose',
    display: 'Other specified polyneuropathies',
    data: { rejected: true, accepted: false, icd10_code: 'G62.89' },
  };
  assert.equal(dropReason(dismissedDiagnose), 'dismissed');
  assert.equal(isIntentionalDrop(dismissedDiagnose), true);
});

test('a live condition card that gets dropped is still a validation failure', () => {
  const liveAssess = {
    command_type: 'assess',
    display: 'Type 2 diabetes mellitus',
    data: { narrative: 'Stable on metformin.', condition_id: 'abc' },
  };
  assert.equal(dropReason(liveAssess), 'validation');
  assert.equal(isIntentionalDrop(liveAssess), false);

  // rejected: false must not be read as dismissed (restoreAssess writes exactly this).
  const restored = { ...liveAssess, data: { ...liveAssess.data, rejected: false } };
  assert.equal(dropReason(restored), 'validation');
});

test('empty_display takes precedence over dismissed and deselected', () => {
  // Preserves the precedence the COMMANDS_FILTERED audit has always used.
  const noDisplay = { ...STUCK_DISMISSED_ASSESS, display: '' };
  assert.equal(dropReason(noDisplay), 'empty_display');
  assert.equal(dropReason({ command_type: 'assess', display: '', selected: false }), 'empty_display');
  assert.equal(dropReason({ command_type: 'perform', display: undefined }), 'empty_display');
});

test('deselected takes precedence over dismissed', () => {
  const both = { ...STUCK_DISMISSED_ASSESS, selected: false };
  assert.equal(dropReason(both), 'deselected');
  assert.equal(isIntentionalDrop(both), true);
});

test('an unchecked row is deselected', () => {
  const deselected = { command_type: 'perform', display: '99213 — Office visit', selected: false };
  assert.equal(dropReason(deselected), 'deselected');
  assert.equal(isIntentionalDrop(deselected), true);
});

test('data.rejected on a NON-condition type does not suppress its validation error', () => {
  // The narrow scoping is the point. A prescribe row is dropped by the Rx-completeness
  // gate, not by any rejected gate, so suppressing its error here would silently lose the
  // prescription — the failure mode droppedForValidation exists to catch. A blanket
  // `!c.data?.rejected` filter would have masked it.
  for (const type of ['prescribe', 'refill', 'adjust_prescription', 'refer', 'imaging_order', 'lab_order']) {
    const cmd = { command_type: type, display: 'Lisinopril 10 mg', data: { rejected: true } };
    assert.equal(isDismissedCondition(cmd), false, `${type} must not count as a dismissed condition`);
    assert.equal(dropReason(cmd), 'validation', `${type} must still report a validation failure`);
    assert.equal(isIntentionalDrop(cmd), false);
  }
});

test('tolerates missing or malformed commands without throwing', () => {
  // Condition cards have reached this code with no `data` before (KOALA-5687), and an
  // unguarded read there blanks the whole Scribe tab.
  assert.equal(dropReason({ command_type: 'assess', display: 'Asthma' }), 'validation');
  assert.equal(dropReason({ command_type: 'assess', display: 'Asthma', data: null }), 'validation');
  assert.equal(dropReason(undefined), 'empty_display');
  assert.equal(dropReason(null), 'empty_display');
  assert.equal(dropReason({}), 'empty_display');
  assert.equal(isDismissedCondition(undefined), false);
  assert.equal(isDismissedCondition({ command_type: 'assess' }), false);
  assert.equal(isDismissedCondition({ command_type: 'assess', data: null }), false);
});

test('isDismissedCondition only recognises the two condition families', () => {
  assert.equal(isDismissedCondition({ command_type: 'assess', data: { rejected: true } }), true);
  assert.equal(isDismissedCondition({ command_type: 'diagnose', data: { rejected: true } }), true);
  assert.equal(isDismissedCondition({ command_type: 'task', data: { rejected: true } }), false);
  assert.equal(isDismissedCondition({ command_type: 'assess', data: { rejected: false } }), false);
});
