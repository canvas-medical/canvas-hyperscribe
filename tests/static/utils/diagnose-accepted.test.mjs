import { test } from 'node:test';
import assert from 'node:assert/strict';
import { deriveDiagnoseAccepted } from '../../../hyperscribe/scribe/static/utils/diagnose-accepted.js';

const dx = (data, extra = {}) => ({ command_type: 'diagnose', data, ...extra });

test('accepts a coded row saved as not accepted', () => {
  const [row] = deriveDiagnoseAccepted([dx({ icd10_code: 'E11.9', accepted: false })]);
  assert.equal(row.data.accepted, true);
});

test('keeps uncoded and dismissed rows unaccepted', () => {
  const rows = deriveDiagnoseAccepted([
    dx({ icd10_code: '', accepted: true }),
    dx({ icd10_code: 'E11.9', rejected: true, accepted: true }),
  ]);
  assert.deepEqual(rows.map(r => r.data.accepted), [false, false]);
});

test('leaves chart rows and other commands untouched', () => {
  const input = [
    dx({ icd10_code: 'E11.9', accepted: false }, { command_uuid: 'u1' }),
    dx({ icd10_code: 'E11.9', accepted: false }, { already_documented: true }),
    { command_type: 'assess', data: { accepted: false } },
  ];
  const output = deriveDiagnoseAccepted(input);
  output.forEach((row, i) => assert.equal(row, input[i]));
});
