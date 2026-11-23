// Guard footer names unsaved sections by finding
// data-edit-key on open editors and data-section-title on section titles.
// A row or title without its label still works, but silently goes unnamed,
// so this test makes the missing label fail CI instead.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';

const STATIC_DIR = new URL('../../hyperscribe/scribe/static/', import.meta.url);
const files = readdirSync(STATIC_DIR)
  .filter(name => name.endsWith('.js'))
  .map(name => ({ name, source: readFileSync(new URL(name, STATIC_DIR), 'utf8') }));

test('every row that reports an open editor labels it with data-edit-key', () => {
  const reports = /onEditingChange(\?\.| && onEditingChange)\(/;
  const missing = files
    .filter(f => reports.test(f.source) && !f.source.includes('data-edit-key='))
    .map(f => f.name);
  assert.deepEqual(missing, [],
    `Add data-edit-key=\${commandIndex} to the editing element in: ${missing.join(', ')}`);
});

test('every section title carries data-section-title', () => {
  const unlabelled = files.flatMap(f =>
    (f.source.match(/<div class="subsection-title"[^>]*>/g) || [])
      .filter(tag => !tag.includes('data-section-title'))
      .map(tag => `${f.name}: ${tag}`));
  assert.deepEqual(unlabelled, [],
    `Add data-section-title to these titles:\n${unlabelled.join('\n')}`);
});