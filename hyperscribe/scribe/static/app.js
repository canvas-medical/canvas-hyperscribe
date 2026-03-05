import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';
import { Scribe } from '/plugin-io/api/hyperscribe/scribe/static/transcript.js';
import { Summary } from '/plugin-io/api/hyperscribe/scribe/static/summary.js';

const html = htm.bind(h);

const VIEWS = {
  scribe: Scribe,
  summary: Summary,
};

export function App({ noteDbid, view }) {
  const ViewComponent = VIEWS[view];

  if (!ViewComponent) {
    return html`<div class="scribe-container"><p class="error">Unknown view: ${view}</p></div>`;
  }

  return html`<${ViewComponent} noteDbid=${noteDbid} />`;
}
