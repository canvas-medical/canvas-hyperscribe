/*
 * gallery.js — the component gallery view.
 *
 * Mounts each REAL Scribe row component in isolation, showing its distinct
 * states side by side (view / editing / deselected / locked / missing-field).
 * Each card is wrapped in the same `.content-block` SoapGroup uses, so the
 * styling matches production. The cards are LIVE — clicking one enters that
 * component's real edit mode.
 *
 * "editing" specimens pass a command with an empty `display` (and empty data),
 * which is how the real rows auto-open their edit form for a brand-new command.
 */
import { h } from 'https://esm.sh/preact@10.25.4';
import htm from 'https://esm.sh/htm@3.1.1';

import { CommandRow } from '/plugin-io/api/hyperscribe/scribe/static/command-row.js';
import { VitalsRow } from '/plugin-io/api/hyperscribe/scribe/static/vitals-row.js';
import { HistoryReviewRow } from '/plugin-io/api/hyperscribe/scribe/static/history-review-row.js';
import { HistoryEntryRow } from '/plugin-io/api/hyperscribe/scribe/static/history-entry-row.js';
import { MedicationRow } from '/plugin-io/api/hyperscribe/scribe/static/medication-row.js';
import { AllergyRow } from '/plugin-io/api/hyperscribe/scribe/static/allergy-row.js';
import { TaskRow } from '/plugin-io/api/hyperscribe/scribe/static/task-row.js';
import { DiagnoseRow } from '/plugin-io/api/hyperscribe/scribe/static/diagnose-row.js';
import { OrderRow } from '/plugin-io/api/hyperscribe/scribe/static/order-row.js';
import { QuestionnaireRow } from '/plugin-io/api/hyperscribe/scribe/static/questionnaire-row.js';
import { ChargeRow } from '/plugin-io/api/hyperscribe/scribe/static/charge-row.js';

import * as c from './commands.js';

const html = htm.bind(h);
const noop = () => {};
const ASSIGNEES = [
  { type: 'team', id: 't1', label: 'Care Team' },
  { type: 'staff', id: 's1', label: 'Dr. Alex Reyes' },
];

// Lock glyph SoapGroup renders on already-documented cards in amend mode.
const LockIcon = () => html`
  <svg class="command-row-icon-lock" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 1a5 5 0 00-5 5v3H6a2 2 0 00-2 2v9a2 2 0 002 2h12a2 2 0 002-2v-9a2 2 0 00-2-2h-1V6a5 5 0 00-5-5zm3 8H9V6a3 3 0 016 0v3z"/>
  </svg>`;

// Common props every row accepts; per-state props override.
const base = { commandIndex: 0, onEdit: noop, onDelete: noop, onEditingChange: noop, readOnly: false };

// Raw (factory-bypassing) commands for the empty/new "editing" state.
const emptyVitals = { command_type: 'vitals', section_key: 'vitals', selected: true, display: '', data: {} };
const emptyMed = { command_type: 'medication_statement', section_key: 'current_medications', selected: true, display: '', data: { medication_text: '', fdb_code: null, sig: '', alert_facility: false } };
const emptyAllergy = { command_type: 'allergy', section_key: 'allergies', selected: true, display: '', data: { allergy_text: '', concept_id: null, reaction: '', severity: '' } };
const emptyTask = { command_type: 'task', section_key: '_ad_hoc', selected: true, display: '', data: { title: '', due_date: '', assign_to: null, labels: [], comment: '' } };
const emptyCharge = { command_type: 'perform', section_key: 'charges', selected: true, display: '', data: { cpt_code: '', description: '', _pointers: [] } };
const emptyMedHx = { command_type: 'medicalHistory', section_key: '_history_ad_hoc', selected: true, display: '', data: { past_medical_history: '', condition_code: null, approximate_start_date: null, approximate_end_date: null, comments: '' } };
const emptyHpi = { command_type: 'hpi', section_key: 'history_of_present_illness', selected: true, display: '', data: { narrative: '' } };

const diagnoseNoCode = c.diagnose({
  display: 'Hyperlipidemia', data: { icd10_code: '', icd10_display: '', condition_header: 'Hyperlipidemia',
    today_assessment: 'LDL elevated; discuss statin.', background: '', accepted: false },
});
const DX_SUGGESTIONS = [
  { code: 'E785', display: 'Hyperlipidemia, unspecified', formatted_code: 'E78.5' },
  { code: 'E782', display: 'Mixed hyperlipidemia', formatted_code: 'E78.2' },
];

// Each group: one component, with a row of labelled states.
const GROUPS = [
  { title: 'CommandRow', file: 'command-row.js', note: 'rfv / hpi / plan / lab & imaging results narrative',
    Comp: CommandRow, states: [
      { name: 'view', props: { command: c.hpi() } },
      { name: 'editing (new)', props: { command: emptyHpi } },
      { name: 'deselected', props: { command: c.hpi({ selected: false }) } },
      { name: 'read-only', props: { command: c.hpi(), readOnly: true } },
    ] },
  { title: 'VitalsRow', file: 'vitals-row.js', note: 'BP / HR / temp / height / weight + BMI',
    Comp: VitalsRow, states: [
      { name: 'view', props: { command: c.vitals() } },
      { name: 'editing (new)', props: { command: emptyVitals } },
      { name: 'read-only', props: { command: c.vitals(), readOnly: true } },
    ] },
  { title: 'HistoryReviewRow', file: 'history-review-row.js', note: 'ROS & Physical Exam (Subsequent Visit template)',
    Comp: HistoryReviewRow, states: [
      { name: 'ROS (view)', props: { command: c.reviewOfSystems() } },
      { name: 'Physical Exam (view)', props: { command: c.physicalExam() } },
      { name: 'read-only', props: { command: c.reviewOfSystems(), readOnly: true } },
    ] },
  { title: 'HistoryEntryRow', file: 'history-entry-row.js', note: 'medical / surgical / family history entries',
    Comp: HistoryEntryRow, states: [
      { name: 'medical (view)', props: { command: c.medicalHistory() } },
      { name: 'surgical (view)', props: { command: c.surgicalHistory() } },
      { name: 'family (view)', props: { command: c.familyHistory() } },
      { name: 'editing (new)', props: { command: emptyMedHx } },
    ] },
  { title: 'MedicationRow', file: 'medication-row.js', note: 'medication_statement',
    Comp: MedicationRow, states: [
      { name: 'view', props: { command: c.medicationStatement(), alertFacilityEnabled: true } },
      { name: 'editing (new)', props: { command: emptyMed } },
      { name: 'documented (locked)', props: { command: c.medicationStatement({ already_documented: true }), readOnly: true }, locked: true },
    ] },
  { title: 'AllergyRow', file: 'allergy-row.js', note: 'allergy with severity',
    Comp: AllergyRow, states: [
      { name: 'view (moderate)', props: { command: c.allergy() } },
      { name: 'view (severe)', props: { command: c.allergy({ display: 'Penicillin — anaphylaxis (severe)', data: { reaction: 'Anaphylaxis', severity: 'severe' } }) } },
      { name: 'editing (new)', props: { command: emptyAllergy } },
    ] },
  { title: 'TaskRow', file: 'task-row.js', note: 'task with due date / assignee / labels',
    Comp: TaskRow, states: [
      { name: 'view', props: { command: c.task(), assignees: ASSIGNEES } },
      { name: 'editing (new)', props: { command: emptyTask, assignees: ASSIGNEES } },
    ] },
  { title: 'DiagnoseRow', file: 'diagnose-row.js', note: 'per-condition assessment (A&P)',
    Comp: DiagnoseRow, states: [
      { name: 'view (coded)', props: { command: c.diagnose(), onAccept: noop, suggestions: [] } },
      { name: 'missing code + suggestions', props: { command: diagnoseNoCode, onAccept: noop, suggestions: DX_SUGGESTIONS } },
      { name: 'read-only', props: { command: c.diagnose(), readOnly: true, onAccept: noop, suggestions: [] } },
    ] },
  { title: 'OrderRow', file: 'order-row.js', note: 'prescribe / refill / adjust / lab / imaging / refer',
    Comp: OrderRow, states: [
      { name: 'prescribe (view)', props: { command: c.prescribe(), patientId: 'p1', noteId: 'n1', staffId: 's1', staffName: 'Dr. Reyes' } },
      { name: 'lab (view)', props: { command: c.labOrder(), patientId: 'p1', noteId: 'n1', staffId: 's1', staffName: 'Dr. Reyes' } },
      { name: 'imaging (view)', props: { command: c.imagingOrder(), patientId: 'p1', noteId: 'n1', staffId: 's1', staffName: 'Dr. Reyes' } },
      { name: 'refer (view)', props: { command: c.refer(), patientId: 'p1', noteId: 'n1', staffId: 's1', staffName: 'Dr. Reyes' } },
    ] },
  { title: 'QuestionnaireRow', file: 'questionnaire-row.js', note: 'PHQ-9 (scored)',
    Comp: QuestionnaireRow, states: [
      { name: 'view', props: { command: c.questionnaire() } },
      { name: 'read-only', props: { command: c.questionnaire(), readOnly: true } },
    ] },
  { title: 'ChargeRow', file: 'charge-row.js', note: 'single CPT charge (also rendered in the matrix)',
    Comp: ChargeRow, states: [
      { name: 'view', props: { command: c.perform() } },
      { name: 'editing (new)', props: { command: emptyCharge } },
    ] },
];

function StateCard({ Comp, name, props, locked }) {
  return html`
    <div class="gallery-state">
      <div class="gallery-state-label">${name}</div>
      <div class="summary-container">
        <div class="summary-body">
          <div class=${`content-block${locked ? ' command-locked' : ''}`}>
            ${locked && html`<${LockIcon} />`}
            <${Comp} ...${{ ...base, ...props }} />
          </div>
        </div>
      </div>
    </div>`;
}

export function Gallery() {
  return html`
    <div class="gallery">
      <div class="gallery-intro">
        <strong>Component gallery</strong> — every Scribe row component in isolation.
        Cards are live: click one to enter its real edit mode.
      </div>
      ${GROUPS.map((g) => html`
        <section class="gallery-group" id=${`g-${g.title}`}>
          <h2 class="gallery-group-title">${g.title} <span class="gallery-group-file">${g.file}</span></h2>
          <div class="gallery-group-note">${g.note}</div>
          <div class="gallery-states">
            ${g.states.map((s) => html`<${StateCard} Comp=${g.Comp} name=${s.name} props=${s.props} locked=${s.locked} />`)}
          </div>
        </section>
      `)}
    </div>`;
}

export const GALLERY_GROUPS = GROUPS.map((g) => ({ title: g.title, count: g.states.length }));
