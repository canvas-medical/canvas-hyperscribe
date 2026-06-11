/*
 * commands.js — command factories for the Scribe harness.
 *
 * One factory per command_type. Each returns a command object shaped exactly
 * the way the real row component reads it (field names verified against the
 * component source). Pass `overrides` to tweak data/state; pass `over.data`
 * to override individual data fields.
 *
 * These are the building blocks composed by scenarios.js into full
 * `initialData` payloads, and (in later phases) enumerated by the gallery.
 *
 * Section keys mirror SOAP_GROUPS in summary.js:
 *   SUBJECTIVE: chief_complaint, history_of_present_illness, review_of_systems
 *   HISTORY:    past_medical_history, past_surgical_history, family_history, social_history
 *   OBJECTIVE:  vitals, physical_exam, lab_results, imaging_results, current_medications, allergies
 *   A&P:        assessment_and_plan, plan, prescription
 *   CHARGES:    charges
 */

let _uuid = 0;
export const nextUuid = (p = 'cmd') => `${p}-${String(++_uuid).padStart(3, '0')}`;

// Merge helper: shallow-merge top level, deep-merge `data`.
function build(base, over = {}) {
  const { data: dataOver, ...rest } = over;
  return { _localId: nextUuid('loc'), ...base, ...rest, data: { ...base.data, ...(dataOver || {}) } };
}

// ── SUBJECTIVE / narrative (command-row.js) ──────────────────────────────────
export const rfv = (o) => build({
  command_type: 'rfv', section_key: 'chief_complaint', selected: true, already_documented: false,
  display: 'Follow-up for type 2 diabetes and hypertension.',
  data: { comment: 'Follow-up for type 2 diabetes and hypertension.' },
}, o);

export const hpi = (o) => build({
  command_type: 'hpi', section_key: 'history_of_present_illness', selected: true, already_documented: false,
  display: '58-year-old established patient returns for routine diabetes follow-up. Reports good adherence to metformin; home glucose 110–140 mg/dL fasting. No polyuria, polydipsia, or vision changes.',
  data: { narrative: '58-year-old established patient returns for routine diabetes follow-up. Reports good adherence to metformin; home glucose 110–140 mg/dL fasting. No polyuria, polydipsia, or vision changes.' },
}, o);

export const plan = (o) => build({
  command_type: 'plan', section_key: 'assessment_and_plan', selected: true, already_documented: false,
  display: 'Continue metformin. Recheck A1c today. Follow up in 3 months.',
  data: { narrative: 'Continue metformin. Recheck A1c today. Follow up in 3 months.' },
}, o);

export const labResults = (o) => build({
  command_type: 'lab_results', section_key: 'lab_results', selected: true, already_documented: false,
  display: 'A1c 6.8% (prior 7.1%). Lipid panel within target.',
  data: { narrative: 'A1c 6.8% (prior 7.1%). Lipid panel within target.' },
}, o);

export const imagingResults = (o) => build({
  command_type: 'imaging_results', section_key: 'imaging_results', selected: true, already_documented: false,
  display: 'Chest X-ray: no acute cardiopulmonary process.',
  data: { narrative: 'Chest X-ray: no acute cardiopulmonary process.' },
}, o);

// ── Review/structured sections (history-review-row.js) ───────────────────────
// command.data.sections: [{ key, title, text, template_text?, updated? }]
//
// ROS and Physical Exam are seeded from the "Subsequent Visit" visit template.
// The template ships as flat "LABEL: prose" lines; parseTemplateSections() turns
// each line into a HistoryReviewRow section. text === template_text and
// updated === false → the row renders the template baseline (no "updated from
// encounter" badge until a section is modified during the encounter).
const SUBSEQUENT_ROS_TEMPLATE = `CONSTITUTIONAL: Denies fever, chills, loss of appetite, fatigue, or weakness.
CARDIAC: Denies chest pain, shortness of breath with exertion, or swelling in the legs.
RESPIRATORY: Denies cough, nocturnal dyspnea, or shortness of breath.
DIGESTIVE: Denies nausea, vomiting, abdominal pain, constipation, or diarrhea.
MUSCULOSKELETAL: Denies muscle aches or cramps, body aches, or arthritis.
SKIN: Denies lumps/bumps, rash, or skin tear.
OTHER: None reported.`;

const SUBSEQUENT_PE_TEMPLATE = `CONSTITUTIONAL: Alert, no acute distress. Well developed and nourished.
SKIN: Warm and dry, no suspicious lesions.
PULMONARY: Clear bilaterally to auscultation bilaterally.
CARDIOVASCULAR: Regular rate and rhythm, S1, S2 normal, no murmurs.
EXTREMITIES: No clubbing, cyanosis, or edema.
PSYCH: Good eye contact. Normal mood and affect.`;

const titleCase = (s) => s.split(/[\s/]+/).map(w => w.charAt(0) + w.slice(1).toLowerCase()).join(' ');

// "LABEL: prose" lines → [{ key, title, text, template_text, updated }].
function parseTemplateSections(template) {
  return template.split('\n').map((line) => {
    const idx = line.indexOf(':');
    const label = line.slice(0, idx).trim();
    const text = line.slice(idx + 1).trim();
    return {
      key: label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''),
      title: titleCase(label),
      text,
      template_text: text,
      updated: false,
    };
  });
}

export const reviewOfSystems = (o) => build({
  command_type: 'reviewOfSystems', section_key: '_ros', selected: true, already_documented: false,
  display: 'Review of Systems',
  data: { sections: parseTemplateSections(SUBSEQUENT_ROS_TEMPLATE) },
}, o);

export const physicalExam = (o) => build({
  command_type: 'physical_exam', section_key: 'physical_exam', selected: true, already_documented: false,
  display: 'Physical Exam',
  data: { sections: parseTemplateSections(SUBSEQUENT_PE_TEMPLATE) },
}, o);

// ── HISTORY entries (history-entry-row.js) ───────────────────────────────────
export const medicalHistory = (o) => build({
  command_type: 'medicalHistory', section_key: '_history_ad_hoc', selected: true, already_documented: false,
  display: 'Hypertension · 2015',
  data: { past_medical_history: 'Hypertension', condition_code: 'I10',
    approximate_start_date: '2015-06-01', approximate_end_date: null, comments: 'Well controlled on lisinopril.' },
}, o);

export const surgicalHistory = (o) => build({
  command_type: 'surgicalHistory', section_key: '_history_ad_hoc', selected: true, already_documented: false,
  display: 'Appendectomy · 2010-03-15',
  data: { procedure_display: 'Appendectomy', procedure_code: '44960', approximate_date: '2010-03-15', comment: 'Uncomplicated.' },
}, o);

export const familyHistory = (o) => build({
  command_type: 'familyHistory', section_key: '_history_ad_hoc', selected: true, already_documented: false,
  display: 'Type 2 Diabetes · Mother',
  data: { condition_display: 'Type 2 Diabetes', condition_code: 'E11', relative: 'Mother', relative_code: 'MTH', note: 'Diagnosed in her 60s.' },
}, o);

// ── OBJECTIVE: vitals (vitals-row.js) ────────────────────────────────────────
// blood_pressure_position_and_site is an INTEGER index (0–11) into BP_SITE_OPTIONS.
export const vitals = (o) => build({
  command_type: 'vitals', section_key: 'vitals', selected: true, already_documented: false,
  display: 'BP 128/78, HR 72, Temp 98.6 °F, Wt 185 lbs',
  data: { blood_pressure_systole: 128, blood_pressure_diastole: 78, pulse: 72, respiration_rate: 16,
    oxygen_saturation: 98, body_temperature: 98.6, height: 70, weight_lbs: 185,
    blood_pressure_position_and_site: 0, note: 'Patient resting.' },
}, o);

// ── OBJECTIVE: medications / allergies ───────────────────────────────────────
export const medicationStatement = (o) => build({
  command_type: 'medication_statement', section_key: 'current_medications', selected: true, already_documented: false,
  display: 'Metformin 1000 mg tablet',
  data: { medication_text: 'Metformin 1000 mg tablet', fdb_code: '451235',
    sig: 'Take 1 tablet by mouth twice daily', alert_facility: false },
}, o);

export const allergy = (o) => build({
  command_type: 'allergy', section_key: 'allergies', selected: true, already_documented: false,
  display: 'Penicillin — rash (moderate)',
  data: { allergy_text: 'Penicillin', concept_id: 'pcn-1', concept_id_type: 'rxnorm',
    reaction: 'Diffuse rash', severity: 'moderate' },
}, o);

// ── ASSESSMENT & PLAN: diagnose / assess (diagnose-row.js) ───────────────────
export const diagnose = (o) => build({
  command_type: 'diagnose', section_key: 'assessment_and_plan', selected: true, already_documented: false,
  display: 'Type 2 diabetes mellitus without complications',
  data: { icd10_code: 'E119', icd10_display: 'Type 2 diabetes mellitus without complications',
    condition_header: 'Type 2 diabetes mellitus', _original_header: 'Type 2 diabetes mellitus',
    background: 'Diagnosed 2018. On metformin monotherapy.',
    today_assessment: 'Stable, well controlled. Continue current management; recheck A1c today.',
    condition_id: 'cond-1', accepted: true, rejected: false },
}, o);

export const assess = (o) => build({
  command_type: 'assess', section_key: 'assessment_and_plan', selected: true, already_documented: false,
  display: 'Essential (primary) hypertension',
  data: { icd10_code: 'I10', icd10_display: 'Essential (primary) hypertension', code: 'I10',
    label: 'Essential (primary) hypertension', narrative: 'Well controlled on lisinopril. Continue.', accepted: true },
}, o);

// ── ASSESSMENT & PLAN: task (task-row.js) ────────────────────────────────────
export const task = (o) => build({
  command_type: 'task', section_key: '_ad_hoc', selected: true, already_documented: false,
  display: 'Recheck A1c in 3 months',
  data: { title: 'Recheck A1c in 3 months', due_date: '2026-09-11',
    assign_to: { to: 'team', id: 't1' }, labels: ['Lab follow-up'], comment: '' },
}, o);

// ── ASSESSMENT & PLAN: orders (order-row.js) ─────────────────────────────────
export const prescribe = (o) => build({
  command_type: 'prescribe', section_key: '_ad_hoc', selected: true, already_documented: false,
  display: 'Lisinopril 10 mg — Take 1 tablet daily',
  data: { fdb_code: '209876', medication_text: 'Lisinopril 10 mg tablet', sig: 'Take 1 tablet by mouth daily',
    days_supply: 30, quantity_to_dispense: 30, type_to_dispense: 'tablet', type_to_dispense_label: 'tablet',
    refills: 3, substitutions: 'allowed', note_to_pharmacist: '', pharmacy: '5555555555', pharmacy_name: 'Walgreens #1234',
    quantities: [] },
}, o);

export const refill = (o) => build({
  command_type: 'refill', section_key: '_ad_hoc', selected: true, already_documented: false,
  display: 'Metformin 1000 mg — refill',
  data: { fdb_code: '451235', medication_text: 'Metformin 1000 mg tablet', sig: 'Take 1 tablet twice daily',
    days_supply: 90, quantity_to_dispense: 180, type_to_dispense: 'tablet', type_to_dispense_label: 'tablet',
    refills: 3, substitutions: 'allowed', note_to_pharmacist: '', pharmacy: '5555555555', pharmacy_name: 'Walgreens #1234',
    quantities: [] },
}, o);

export const adjustPrescription = (o) => build({
  command_type: 'adjust_prescription', section_key: '_ad_hoc', selected: true, already_documented: false,
  display: 'Adjust Lisinopril → Enalapril 5 mg',
  data: { fdb_code: '209876', medication_text: 'Lisinopril 10 mg tablet', new_fdb_code: '209900', new_medication_text: 'Enalapril 5 mg tablet',
    sig: 'Take 1 tablet daily', days_supply: 30, quantity_to_dispense: 30, type_to_dispense: 'tablet', type_to_dispense_label: 'tablet',
    refills: 3, substitutions: 'allowed', note_to_pharmacist: '', pharmacy: '5555555555', pharmacy_name: 'Walgreens #1234', quantities: [] },
}, o);

export const labOrder = (o) => build({
  command_type: 'lab_order', section_key: '_ad_hoc', selected: true, already_documented: false,
  display: 'Quest Diagnostics — Hemoglobin A1c, Lipid Panel',
  data: { lab_partner: 'quest', lab_partner_name: 'Quest Diagnostics',
    tests_order_codes: ['496', '7600'], test_names: ['Hemoglobin A1c', 'Lipid Panel'],
    diagnosis_codes: ['E11.9'], diagnosis_displays: ['Type 2 diabetes mellitus'],
    fasting_required: true, comment: 'AM draw preferred.' },
}, o);

export const imagingOrder = (o) => build({
  command_type: 'imaging_order', section_key: '_ad_hoc', selected: true, already_documented: false,
  display: 'Chest X-ray — Routine',
  data: { image_code: '71046', image_display: 'Radiologic exam, chest, 2 views',
    diagnosis_codes: ['J06.9'], diagnosis_displays: ['Acute upper respiratory infection'], diagnosis_formatted: ['J06.9'],
    additional_details: 'Persistent cough x 3 weeks.', comment: '', priority: 'Routine',
    ordering_provider_id: 's1', ordering_provider_name: 'Dr. Alex Reyes',
    service_provider: { id: 'ic1' }, service_provider_name: 'City Imaging Center' },
}, o);

export const refer = (o) => build({
  command_type: 'refer', section_key: '_ad_hoc', selected: true, already_documented: false,
  display: 'Refer to Cardiology — Dr. Jane Smith',
  data: { service_provider: { id: 'sp1' }, refer_to_display: 'Dr. Jane Smith, Cardiology',
    diagnosis_codes: ['I10'], diagnosis_displays: ['Essential hypertension'], diagnosis_formatted: ['I10'],
    clinical_question: 'Assistance with Ongoing Management', priority: 'Routine',
    notes_to_specialist: 'Please evaluate for resistant hypertension.', comment: '' },
}, o);

// ── ASSESSMENT & PLAN: questionnaire (questionnaire-row.js) ───────────────────
const phqResponses = (sel) => [
  { dbid: 1, value: 'Not at all', code: 'LA6568-5', score_value: '0', selected: sel === 0, comment: null },
  { dbid: 2, value: 'Several days', code: 'LA6569-3', score_value: '1', selected: sel === 1, comment: null },
  { dbid: 3, value: 'More than half the days', code: 'LA6570-1', score_value: '2', selected: sel === 2, comment: null },
  { dbid: 4, value: 'Nearly every day', code: 'LA6571-9', score_value: '3', selected: sel === 3, comment: null },
];
export const questionnaire = (o) => build({
  command_type: 'questionnaire', section_key: '_subjective_ad_hoc', selected: true, already_documented: false,
  display: 'PHQ-9',
  data: { questionnaire_dbid: 42, questionnaire_name: 'PHQ-9', is_scored: true, scoring_function_name: 'phq9',
    questions: [
      { dbid: 101, label: 'Little interest or pleasure in doing things?', type: 'SING', skipped: false, responses: phqResponses(1) },
      { dbid: 102, label: 'Feeling down, depressed, or hopeless?', type: 'SING', skipped: false, responses: phqResponses(2) },
    ] },
}, o);

// ── CHARGES: perform (charge-row.js + charge-matrix.js) ──────────────────────
export const perform = (o) => build({
  command_type: 'perform', section_key: 'charges', selected: true, already_documented: false,
  display: '99214',
  data: { cpt_code: '99214', description: 'Office visit, established patient, moderate complexity', _pointers: [] },
}, o);

// ── Removal rows (soap-group.js RemovalRow) ──────────────────────────────────
export const stopMedication = (o) => build({
  command_type: 'stop_medication', section_key: '_objective_ad_hoc', selected: true, already_documented: false,
  display: 'Stop Atorvastatin 20 mg',
  data: { medication_id: 'med-9', medication_name: 'Atorvastatin 20 mg', rationale: 'Myalgias.', alert_facility: false },
}, o);

export const removeAllergy = (o) => build({
  command_type: 'remove_allergy', section_key: '_objective_ad_hoc', selected: true, already_documented: false,
  display: 'Remove Sulfa allergy',
  data: { allergy_id: 'alg-3', allergy_name: 'Sulfa drugs' },
}, o);

export const resolveCondition = (o) => build({
  command_type: 'resolve_condition', section_key: '_ad_hoc', selected: true, already_documented: false,
  display: 'Resolve Acute sinusitis',
  data: { condition_id: 'cond-7', condition_name: 'Acute sinusitis' },
}, o);

// Note sections (noteData.sections) — keys must cover every section that has commands.
export const noteSections = (over = {}) => {
  const base = {
    chief_complaint: 'Follow-up for type 2 diabetes and hypertension.',
    history_of_present_illness: '',
    review_of_systems: '',
    past_medical_history: '',
    past_surgical_history: '',
    family_history: '',
    social_history: 'Non-smoker. Occasional alcohol. Walks 30 min/day.',
    vitals: '',
    physical_exam: '',
    lab_results: '',
    imaging_results: '',
    current_medications: '',
    allergies: '',
    assessment_and_plan: '',
    charges: '',
  };
  const titles = {
    chief_complaint: 'Chief Complaint', history_of_present_illness: 'History of Present Illness',
    review_of_systems: 'Review of Systems', past_medical_history: 'Past Medical History Discussed During Encounter',
    past_surgical_history: 'Past Surgical History', family_history: 'Family History', social_history: 'Social History',
    vitals: 'Vitals', physical_exam: 'Physical Exam', lab_results: 'Lab Results', imaging_results: 'Imaging Results',
    current_medications: 'Meds Discussed', allergies: 'Allergies Discussed',
    assessment_and_plan: 'Assessment & Plan', charges: 'Charges',
  };
  const text = { ...base, ...over };
  return Object.keys(titles).map((key) => ({ key, title: titles[key], text: text[key] || '' }));
};
