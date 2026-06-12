/*
 * header.js — a page dedicated to the Scribe summary HEADER and how it travels
 * through the workflow's states.
 *
 * The "header" — status pill, the unified top bar (template picker / Start
 * AI+Manual / recording controls), the read-only banner, and the state banners
 * (recording / recording-complete) — is rendered inline by summary.js, not as a
 * standalone component. So each state here mounts the REAL <Scribe> and the page
 * CSS hides the body/footer/transcript-body, leaving just the header region.
 *
 * Each card is an independent <Scribe> instance with its own initialData, so the
 * states render side by side faithfully. Recording vs paused is driven
 * per-instance via transcript.__recordingStatus (see mock-recording-hook).
 */
import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';
import { Scribe } from '/plugin-io/api/hyperscribe/scribe/static/summary.js';

const html = htm.bind(h);

const BASE = {
  noteId: 'mock-note-001', patientId: 'mock-patient-001', staffId: 's1', staffName: 'Dr. Alex Reyes',
  providerName: 'Dr. Alex Reyes', providerPhotoUrl: '', patientName: 'Jamie Rivera',
  patientBirthDate: '1967-03-14', patientGender: 'F', debugMode: false,
  noteEditable: true, isAuthor: true, alertFacilityEnabled: false,
};
const TEMPLATES = [{ id: 'tmpl-1', name: 'Annual Physical' }, { id: 'tmpl-2', name: 'Diabetes Follow-up' }];
const NOTE = { sections: [{ key: 'chief_complaint', title: 'Chief Complaint', text: 'Follow-up for type 2 diabetes and hypertension.' }] };
// Example transcript shown in the header cards for context.
const ITEMS = [
  { speaker: 'DOCTOR', start_offset_ms: 0, text: 'How have you been since your last visit?', is_final: true },
  { speaker: 'PATIENT', start_offset_ms: 5200, text: 'Mostly good, though my knee has been bothering me.', is_final: true },
  { speaker: 'DOCTOR', start_offset_ms: 11000, text: "Let's take a look and check your vitals today.", is_final: true },
];
const LISTENING = [...ITEMS, { speaker: 'UNSPECIFIED', start_offset_ms: 15000, text: 'and the swelling went down after a few days', is_final: false }];

// Recommendations so the "Hide Rejected Recommendations" toggle appears in review.
const RECS = [
  { command_type: 'medication_statement', display: 'Aspirin 81 mg daily', accepted: false, rejected: false,
    section_key: 'current_medications', data: { medication_text: 'Aspirin 81 mg', fdb_code: '1191', sig: 'Take 1 tablet daily' } },
  { command_type: 'task', display: 'Schedule annual eye exam', accepted: false, rejected: true,
    section_key: '_ad_hoc', data: { title: 'Schedule annual eye exam' } },
];

// config builder: (configOver, summaryOver, transcript)
function cfg(configOver, summaryOver, transcript) {
  const summary = {
    note: null, commands: [], recommendations: [], approved: false, was_finalized: false,
    mode: 'ai', selected_template_name: 'Diabetes Follow-up', unmatched_conditions: [], diagnosis_suggestions: {},
    ...summaryOver,
  };
  return {
    view: 'summary', ...BASE, ...configOver,
    initialData: { summary, assignees: [], templates: TEMPLATES, transcript: transcript || { started: false, finalized: false, items: [] } },
  };
}

const NONE = { started: false, finalized: false, items: [] };

export const HEADER_STATES = [
  { id: 'nothing', label: '1 · Nothing selected',
    caption: 'Entry point. No visit type or mode chosen — the template picker shows “Select Visit Type” and Start AI Scribe / Manual are disabled.',
    config: cfg({}, { mode: null, selected_template_name: null, note: null }, NONE) },
  { id: 'template', label: '2 · Template selected',
    caption: 'A visit template is chosen. Start AI Scribe and Manual become enabled; no status pill or banner yet.',
    config: cfg({}, { mode: null, selected_template_name: 'Diabetes Follow-up', note: null }, NONE) },
  { id: 'recording', label: '3 · AI recording',
    caption: 'Capturing audio. The top bar swaps to Pause + Finish; the red “Recording in progress” bar appears.',
    config: cfg({}, { mode: 'ai', note: null }, { started: true, finalized: false, __recordingStatus: 'recording', items: LISTENING }) },
  { id: 'paused', label: '4 · AI paused',
    caption: 'Capture paused. The controls show Resume + Finish and the header reads “Paused”.',
    config: cfg({}, { mode: 'ai', note: null }, { started: true, finalized: false, __recordingStatus: 'paused', items: ITEMS }) },
  { id: 'recorded', label: '5 · Recording complete',
    caption: 'Recording finished, no summary yet. The header offers “Recording complete — Generate a structured summary”.',
    config: cfg({}, { mode: 'ai', note: null }, { started: true, finalized: true, items: ITEMS }) },
  { id: 'review', label: '6 · In review (with recommendations)',
    caption: 'A summary has been generated and includes AI recommendations, so the "Hide Rejected Recommendations" toggle appears in the top bar (right-aligned, in line with the visit type).',
    config: cfg({}, { mode: 'ai', note: NOTE, recommendations: RECS }, { started: true, finalized: true, items: ITEMS }) },
  { id: 'amending', label: '7 · Amending (after sign)',
    caption: 'The signed note is reopened to amend. An amber pill reads “Editing charting”.',
    config: cfg({}, { mode: 'ai', note: NOTE, approved: false, was_finalized: true }, { started: true, finalized: true, items: ITEMS }) },
  { id: 'finalized', label: '8 · Charting finalized',
    caption: 'The Scribe charting is approved/signed. A green pill reads “Charting finalized” with a Make changes action.',
    config: cfg({}, { mode: 'ai', note: NOTE, approved: true, was_finalized: true }, { started: true, finalized: true, items: ITEMS }) },
  { id: 'locked', label: '9 · Locked (incomplete)',
    caption: 'Author, but the note is locked and Scribe documentation is incomplete — a banner directs them to Amend in the note footer.',
    config: cfg({ noteEditable: false }, { mode: 'ai', note: NOTE, approved: false, was_finalized: false }, { started: true, finalized: true, items: ITEMS }) },
  { id: 'non-author', label: '10 · Read-only (non-author)',
    caption: 'A non-author opens the tab. A banner explains only the note author can edit the Scribe tab.',
    config: cfg({ isAuthor: false }, { mode: 'ai', note: NOTE, approved: false }, { started: true, finalized: true, items: ITEMS }) },
];

export function HeaderStates() {
  return html`
    <div class="header-page">
      <div class="header-intro">
        <strong>Summary header — state journey.</strong> Each card is a live <code>Scribe</code> component with the
        body hidden, so you see only the header region (status pill · top bar · banners) as it changes across the workflow.
      </div>
      ${HEADER_STATES.map((s) => html`
        <section class="header-state" id=${`h-${s.id}`}>
          <div class="header-state-label">${s.label}</div>
          <div class="header-state-caption">${s.caption}</div>
          <div class="header-surface">
            <${Scribe} ...${s.config} />
          </div>
        </section>
      `)}
    </div>`;
}

export const HEADER_IDS = HEADER_STATES.map((s) => s.id);
