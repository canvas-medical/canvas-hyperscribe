// CommandRow imports Preact and htm from esm.sh, and the JS test job installs no
// packages. These hooks swap those imports for a minimal stand-in (state hooks
// and an `html` that records the template), so the real component runs here.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';

const stub = `
  export const h = () => null, Fragment = 'Fragment';
  export const useState = (init) => globalThis.__fakeReact.useState(init);
  export const useRef = () => globalThis.__fakeReact.useRef();
  export const useEffect = () => {};
  export default function html(strings, ...values) { return { strings, values }; }
`;
register(`data:text/javascript,${encodeURIComponent(`
  export async function resolve(spec, ctx, next) {
    if (spec.startsWith('https://esm.sh/')) return { url: 'data:text/javascript,' + encodeURIComponent(${JSON.stringify(stub)}), shortCircuit: true };
    return next(spec, ctx);
  }
`)}`);

// One component instance: hook slots persist across renders, like Preact's.
function mount(Component, props) {
  const slots = [];
  let i = 0;
  globalThis.__fakeReact = {
    useState(init) {
      const k = i++;
      if (!(k in slots)) slots[k] = init;
      return [slots[k], (v) => { slots[k] = typeof v === 'function' ? v(slots[k]) : v; }];
    },
    useRef() { const k = i++; if (!(k in slots)) slots[k] = { current: null }; return slots[k]; },
  };
  return { render: (next = props) => { props = next; i = 0; return Component(props); } };
}

// The value bound to `attr` (e.g. 'onClick=', 'value=') in the rendered template,
// optionally only where the tag's text so far contains `near` (e.g. a class name).
function bound(tree, attr, near = '') {
  const walk = (node) => {
    if (!node || typeof node !== 'object' || !node.strings) return undefined;
    for (let k = 0; k < node.values.length; k++) {
      const before = node.strings[k];
      const tag = before.slice(before.lastIndexOf('<'));
      if (before.trimEnd().endsWith(attr) && tag.includes(near)) return node.values[k];
      const inner = walk(node.values[k]);
      if (inner !== undefined) return inner;
    }
    return undefined;
  };
  return walk(tree);
}

const { CommandRow } = await import('../../hyperscribe/scribe/static/command-row.js');

test('saving after dictation keeps the dictated text', () => {
  const saved = [];
  const hpi = (narrative) => ({ command_type: 'hpi', display: narrative, data: { narrative } });
  const props = { command: hpi('Typed text.'), commandIndex: 1, onEdit: (i, data) => saved.push(data.narrative) };
  const row = mount(CommandRow, props);

  // 1. The provider edits the HPI and saves.
  row.render();
  bound(row.render(), 'onClick=')();
  bound(row.render(), 'onClick=', 'form-btn-save')();
  // 2. Dictation appends to the field while the editor is closed.
  row.render({ ...props, command: hpi('Typed text. Dictated text.') });
  // 3. The provider reopens the editor: it shows the dictated text.
  bound(row.render(), 'onClick=')();
  assert.equal(bound(row.render(), 'value='), 'Typed text. Dictated text.');
  // 4. Save writes the dictated text, not the old draft.
  bound(row.render(), 'onClick=', 'form-btn-save')();
  assert.equal(saved.at(-1), 'Typed text. Dictated text.');
});
