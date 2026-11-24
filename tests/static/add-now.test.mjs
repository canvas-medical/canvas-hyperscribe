import { test } from 'node:test';
import assert from 'node:assert/strict';

import { stampAddNow, updateAddNow } from '../../hyperscribe/scribe/static/add-now.js';
import { mergeGeneratedCommands } from '../../hyperscribe/scribe/static/command-merge.js';

const markAdded = card => ({ ...card, already_documented: true, _added_now: true, _adding: false });

test('Add Now marks the clicked card after generation reorders the list', () => {
  // Before generation: the provider's lab order sits at index 1.
  const labOrder = { command_type: 'lab_order', section_key: '_ad_hoc', display: 'Lab order' };
  const before = [{ command_type: 'diagnose', section_key: 'assessment', display: 'Old dx' }, labOrder];

  // Click Add Now on the lab order.
  const stamped = stampAddNow(before, labOrder, 1, 'id-1');

  // Generation finishes mid-request: generated cards first, the ad-hoc lab order after.
  const generated = [
    { command_type: 'diagnose', section_key: 'assessment', display: 'Generated dx' },
    { command_type: 'plan', section_key: 'plan', display: 'Generated plan' },
  ];
  const reordered = mergeGeneratedCommands(stamped, generated);
  assert.equal(reordered[1].display, 'Generated plan', 'index 1 now holds a different card');

  // Server answers: mark the stamped card.
  const after = updateAddNow(reordered, 'id-1', markAdded);
  const added = after.filter(c => c._added_now).map(c => c.display);
  assert.deepEqual(added, ['Lab order']);
});

test('nothing is marked when the clicked card no longer exists', () => {
  // Recommendations are replaced outright by generation.
  const rec = { command_type: 'prescribe', display: 'Old rec' };
  const stamped = stampAddNow([rec], rec, 0, 'id-2');
  const replaced = [{ command_type: 'diagnose', display: 'New rec' }];
  const after = updateAddNow(replaced, 'id-2', markAdded);
  assert.deepEqual(after, replaced);
  assert.equal(stamped[0]._adding, true);
});

test('stampAddNow falls back to the index when the clicked object is not in the list', () => {
  const list = [{ display: 'a' }, { display: 'b' }];
  const stamped = stampAddNow(list, { display: 'b (copy)' }, 1, 'id-3');
  assert.equal(stamped[1]._addNowId, 'id-3');
  assert.equal(stamped[0]._addNowId, undefined);
});

test('updateAddNow leaves every other card untouched', () => {
  const list = [{ display: 'a', _addNowId: 'other' }, { display: 'b', _addNowId: 'id-4' }];
  const after = updateAddNow(list, 'id-4', markAdded);
  assert.equal(after[0], list[0]);
  assert.equal(after[1]._added_now, true);
});
