import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';
import { Scribe } from '/plugin-io/api/hyperscribe/scribe/static/summary.js';
import { Debug } from '/plugin-io/api/hyperscribe/scribe/static/debug.js';
import { Audit } from '/plugin-io/api/hyperscribe/scribe/static/audit.js';

const html = htm.bind(h);

export function App({ noteId, view, providerName, providerPhotoUrl, patientName, patientBirthDate, patientGender, patientId, staffId, staffName, debugMode, noteEditable, alertFacilityEnabled }) {
  if (view === 'audit') {
    return html`<${Audit} noteId=${noteId} />`;
  }

  if (view === 'debug') {
    return html`<${Debug} noteId=${noteId} />`;
  }

  if (view === 'scribe' || view === 'summary') {
    return html`<${Scribe}
      noteId=${noteId}
      patientId=${patientId}
      staffId=${staffId}
      staffName=${staffName}
      providerName=${providerName}
      providerPhotoUrl=${providerPhotoUrl}
      patientName=${patientName}
      patientBirthDate=${patientBirthDate}
      patientGender=${patientGender}
      debugMode=${debugMode}
      noteEditable=${noteEditable}
      alertFacilityEnabled=${alertFacilityEnabled}
    />`;
  }

  return html`<div class="scribe-container"><p class="error">Unknown view: ${view}</p></div>`;
}
