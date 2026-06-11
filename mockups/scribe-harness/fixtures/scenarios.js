/*
 * scenarios.js — named Scribe states composed from the command factories.
 *
 * Each scenario exports a full `config` (the props index.html templates into
 * <Scribe>), including an `initialData` payload. Because initialData
 * short-circuits the initial fetch, each scenario renders directly.
 *
 * SCENARIOS is the ordered list the harness rail enumerates. Adding a scenario
 * here makes it appear in the UI automatically.
 */
import * as c from './commands.js';

const BASE_CONFIG = {
  noteId: 'mock-note-001',
  patientId: 'mock-patient-001',
  staffId: 's1',
  staffName: 'Dr. Alex Reyes',
  providerName: 'Dr. Alex Reyes',
  providerPhotoUrl: '',
  patientName: 'Jamie Rivera',
  patientBirthDate: '1967-03-14',
  patientGender: 'F',
  debugMode: false,
  noteEditable: true,
  isAuthor: true,
  alertFacilityEnabled: false,
};

const ASSIGNEES = [
  { type: 'team', id: 't1', label: 'Care Team' },
  { type: 'staff', id: 's1', label: 'Dr. Alex Reyes' },
  { type: 'staff', id: 's2', label: 'RN Jordan Patel' },
];
const TEMPLATES = [
  { id: 'tmpl-1', name: 'Annual Physical' },
  { id: 'tmpl-2', name: 'Diabetes Follow-up' },
];
const TRANSCRIPT = {
  started: true, finalized: true,
  items: [
    { speaker: 'DOCTOR', start_offset_ms: 0, text: 'Good to see you again. How have your sugars been?', is_final: true },
    { speaker: 'PATIENT', start_offset_ms: 4200, text: 'Pretty good — 110 to 140 in the mornings.', is_final: true },
    { speaker: 'DOCTOR', start_offset_ms: 9800, text: "Great. Let's recheck your A1c today and keep the metformin the same.", is_final: true },
  ],
};

// Compose a config from a summary + optional config/transcript overrides.
function scenario(summaryOver, configOver = {}, transcriptOver = null) {
  const summary = {
    note: null,
    commands: [],
    recommendations: [],
    approved: false,
    was_finalized: false,
    mode: 'ai',
    selected_template_name: 'Diabetes Follow-up',
    unmatched_conditions: [],
    diagnosis_suggestions: {},
    ...summaryOver,
  };
  return {
    ...BASE_CONFIG,
    ...configOver,
    initialData: { summary, assignees: ASSIGNEES, templates: TEMPLATES, transcript: transcriptOver || TRANSCRIPT },
  };
}

// Transcript variants for the recording-phase scenarios.
const NO_TRANSCRIPT = { started: false, finalized: false, items: [] };
const LIVE_TRANSCRIPT = {
  started: true, finalized: false,
  items: [
    { speaker: 'DOCTOR', start_offset_ms: 0, text: 'How have you been since your last visit?', is_final: true },
    { speaker: 'PATIENT', start_offset_ms: 5200, text: 'Mostly good, though my knee has been bothering me.', is_final: true },
    { speaker: 'UNSPECIFIED', start_offset_ms: 9000, text: 'and the swelling went down after a few days', is_final: false },
  ],
};
const PAUSED_TRANSCRIPT = {
  started: true, finalized: false,
  items: [
    { speaker: 'DOCTOR', start_offset_ms: 0, text: 'How have you been since your last visit?', is_final: true },
    { speaker: 'PATIENT', start_offset_ms: 5200, text: 'Mostly good, though my knee has been bothering me.', is_final: true },
  ],
};

// The kitchen-sink command set — one of every command type, across all sections.
function everyCommand() {
  return [
    // SUBJECTIVE
    c.rfv(), c.hpi(), c.reviewOfSystems(),
    // HISTORY
    c.medicalHistory(), c.surgicalHistory(), c.familyHistory(),
    // OBJECTIVE
    c.vitals(), c.physicalExam(),
    c.medicationStatement(), c.stopMedication(),
    c.allergy(), c.removeAllergy(),
    c.labResults(), c.imagingResults(),
    // ASSESSMENT & PLAN
    c.diagnose(), c.assess(),
    c.plan(), c.task(), c.questionnaire(), c.resolveCondition(),
    c.prescribe(), c.refill(), c.adjustPrescription(),
    c.labOrder(), c.imagingOrder(), c.refer(),
    // CHARGES
    c.perform(), c.perform({ display: '36415', data: { cpt_code: '36415', description: 'Routine venipuncture' } }),
  ];
}

const sectionsForEveryCommand = c.noteSections({
  history_of_present_illness: c.hpi().data.narrative,
});

// ── Scenarios ────────────────────────────────────────────────────────────────

// 1. Kitchen sink — every command type in review state.
const reviewAll = scenario({
  note: { sections: sectionsForEveryCommand },
  commands: everyCommand(),
});

// 2. Manual mode — clinician-driven, no AI transcript. mode 'manual' shows the
//    footer immediately and seeds the standard manual command set.
const manualMode = scenario({
  note: { sections: c.noteSections() },
  mode: 'manual',
  commands: [c.rfv({ display: '', data: { comment: '' } }), c.hpi({ display: '', data: { narrative: '' } }),
    c.vitals(), c.physicalExam(), c.plan({ display: '', data: { narrative: '' } })],
}, {});

// 3. Read-only — viewer who is not the author / note locked.
const readOnly = scenario({
  note: { sections: sectionsForEveryCommand },
  commands: everyCommand(),
  approved: true,
  was_finalized: true,
}, { noteEditable: false, isAuthor: false });

// 4. Amending a signed note — was_finalized + not approved. Already-documented
//    commands carry a command_uuid and render locked; editable sections unlock.
//    syncNoteCommands drops local UUIDs absent from /note-commands, so these
//    same commands are echoed back via the scenario's `noteCommands`.
const amendingCommands = [
  c.rfv({ command_uuid: c.nextUuid('note'), already_documented: true }),
  c.hpi({ command_uuid: c.nextUuid('note'), already_documented: true }),
  c.vitals({ command_uuid: c.nextUuid('note'), already_documented: true }),
  c.diagnose({ command_uuid: c.nextUuid('note'), already_documented: true }),
  c.assess({ command_uuid: c.nextUuid('note'), already_documented: true }),
  c.perform({ command_uuid: c.nextUuid('note'), already_documented: true }),
];
const amending = scenario({
  note: { sections: sectionsForEveryCommand },
  approved: false,
  was_finalized: true,
  commands: amendingCommands,
});

// 5. Recommendations — AI suggestions in pending / accepted / rejected states.
const recommendations = scenario({
  note: { sections: c.noteSections() },
  commands: [c.rfv(), c.hpi()],
  recommendations: [
    c.medicationStatement({ accepted: false, rejected: false }),                 // pending
    c.allergy({ accepted: true, rejected: false, display: 'Aspirin — GI upset (mild)',
      data: { allergy_text: 'Aspirin', reaction: 'GI upset', severity: 'mild' } }),  // accepted
    c.task({ rejected: true, accepted: false, display: 'Schedule eye exam' }),   // rejected
    c.diagnose({ accepted: false, rejected: false, display: 'Hyperlipidemia',
      data: { icd10_code: 'E785', icd10_display: 'Hyperlipidemia, unspecified', condition_header: 'Hyperlipidemia',
        today_assessment: 'LDL elevated; consider statin.', background: '', accepted: false } }),  // pending dx
  ],
});

// 6. Empty / generate state — finalized transcript, no note yet.
const empty = scenario({
  note: null,
  commands: [],
  mode: 'ai',
});

// 7. Fresh start — no visit template chosen and no mode selected yet. The top
//    bar shows the template picker + Start AI / Manual (disabled until a
//    template is chosen). This is the very first thing a clinician sees.
const start = scenario(
  { note: null, commands: [], mode: null, selected_template_name: null },
  {},
  NO_TRANSCRIPT,
);

// 8. AI recording — actively capturing. Live transcript streams (last line is a
//    not-yet-final "listening" partial); top bar shows Pause + Finish.
const aiRecording = scenario(
  { note: null, commands: [], mode: 'ai' },
  {},
  LIVE_TRANSCRIPT,
);

// 9. AI paused — capture paused mid-visit. Top bar shows Resume + Finish.
const aiPaused = scenario(
  { note: null, commands: [], mode: 'ai' },
  {},
  PAUSED_TRANSCRIPT,
);

export const SCENARIOS = [
  // Recording phase (in flow order).
  { id: 'start', group: 'Recording', label: 'Start · nothing selected', config: start },
  { id: 'ai-recording', group: 'Recording', label: 'AI · recording', config: aiRecording, recording: { status: 'recording' } },
  { id: 'ai-paused', group: 'Recording', label: 'AI · paused', config: aiPaused, recording: { status: 'paused' } },
  { id: 'empty', group: 'Recording', label: 'AI · generate summary', config: empty },
  // Review phase.
  { id: 'review-all', group: 'States', label: 'Summary · every command', config: reviewAll },
  { id: 'manual', group: 'States', label: 'Manual mode', config: manualMode },
  { id: 'recommendations', group: 'States', label: 'Recommendations', config: recommendations },
  { id: 'amending', group: 'States', label: 'Amending signed note', config: amending, noteCommands: amendingCommands },
  { id: 'read-only', group: 'States', label: 'Read-only viewer', config: readOnly },
];

export const byId = (id) => SCENARIOS.find((s) => s.id === id) || SCENARIOS[0];
