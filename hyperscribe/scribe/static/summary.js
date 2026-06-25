import { h } from 'https://esm.sh/preact@10.25.4';
import { useState, useEffect, useCallback, useRef, useMemo } from 'https://esm.sh/preact@10.25.4/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { SoapGroup, parseAPBlocks, matchCondition } from '/plugin-io/api/hyperscribe/scribe/static/soap-group.js';
import { collectQuestionnaireScores } from '/plugin-io/api/hyperscribe/scribe/static/questionnaire-score.js';
import { useRecording } from '/plugin-io/api/hyperscribe/scribe/static/recording-hook.js';
import { initAuditLog, logEvent } from '/plugin-io/api/hyperscribe/scribe/static/audit-log.js';
import { connectScribeWS } from '/plugin-io/api/hyperscribe/scribe/static/scribe-ws.js';
import { FinishRecordingButton } from '/plugin-io/api/hyperscribe/scribe/static/finish-button.js';
import { canSignCharges, MAX_POINTERS, MAX_MODIFIERS } from '/plugin-io/api/hyperscribe/scribe/static/charge-matrix.js';

const html = htm.bind(h);

// Mirrors hyperscribe/scribe/commands/_rx_validation.py and the canvas-core
// Prescribe schema. Prescribe / Refill / Adjust Prescription all funnel
// through the same schema during REVIEW, and any missing or invalid field
// causes the transaction to roll back even though /insert-commands has
// already returned 200. Keep this predicate aligned with the server-side
// validate_rx_payload function — they MUST agree on both presence AND value.
const RX_COMMAND_TYPES = new Set(['prescribe', 'refill', 'adjust_prescription']);
const RX_SIG_MAX_LENGTH = 1000;
const RX_NOTE_TO_PHARMACIST_MAX_LENGTH = 210;
const RX_REFILLS_MIN = 0;
const RX_REFILLS_MAX = 99;
// Mirrors _RE_INVALID_CHARACTERS in _rx_validation.py: Surescripts only allows
// printable ASCII space..tilde for sig / note_to_pharmacist.
const RX_NON_ASCII_RE = /[^\x20-\x7E]/;
const _isBlankString = (v) => typeof v === 'string' && v.trim() === '';
const isRxIncomplete = (d) => {
  if (!d) return true;
  // Required strings (reject null / empty / whitespace-only).
  if (!d.fdb_code || _isBlankString(d.fdb_code)) return true;
  if (!d.sig || _isBlankString(d.sig)) return true;
  if (!d.type_to_dispense) return true;
  // Quantity: present, parseable, > 0.
  if (d.quantity_to_dispense == null || d.quantity_to_dispense === '') return true;
  const qty = Number(d.quantity_to_dispense);
  if (!Number.isFinite(qty) || qty <= 0) return true;
  // Mirror canvas-core's dispense_quantity_validator and the OrderRow Save
  // gate: Surescripts NewRx wire format rejects trailing zeros after a
  // decimal point ("1.0", "10.", "5.20"). Number("30.0") === 30 strips the
  // shape, so we have to inspect the source string.
  const qtyStr = String(d.quantity_to_dispense).trim();
  if (qtyStr.includes('.') && (qtyStr.endsWith('0') || qtyStr.endsWith('.'))) return true;
  // Refills: present, integer in [REFILLS_MIN, REFILLS_MAX].
  if (d.refills == null || d.refills === '') return true;
  const refills = Number(d.refills);
  if (!Number.isInteger(refills) || refills < RX_REFILLS_MIN || refills > RX_REFILLS_MAX) return true;
  // Days supply: optional, but if present must be a non-negative integer
  // (mirrors _validate_days_supply: rejects fractional floats and negatives).
  if (d.days_supply != null && d.days_supply !== '') {
    const days = Number(d.days_supply);
    if (!Number.isFinite(days) || !Number.isInteger(days) || days < 0) return true;
  }
  // Substitutions: enum value required.
  if (d.substitutions !== 'allowed' && d.substitutions !== 'not_allowed') return true;
  // Sig: length + Surescripts ASCII charset.
  if (typeof d.sig === 'string' && (d.sig.length > RX_SIG_MAX_LENGTH || RX_NON_ASCII_RE.test(d.sig))) return true;
  // Note to pharmacist: optional, but if present must satisfy length + charset.
  if (typeof d.note_to_pharmacist === 'string' && d.note_to_pharmacist !== ''
      && (d.note_to_pharmacist.length > RX_NOTE_TO_PHARMACIST_MAX_LENGTH || RX_NON_ASCII_RE.test(d.note_to_pharmacist))) return true;
  return false;
};
const isRxCommand = (cmd) => RX_COMMAND_TYPES.has(cmd?.command_type);

// Mirrors the refer-completeness gate in the `insertable` filter. Both the
// Approve filter and the recommendations filter must apply this — the
// LLM recommender (recommendations/refer.py) does not emit `diagnosis_codes`,
// so any accepted-without-edit referral would otherwise hit the server's
// `ReferParser.validate` ("At least one indication is required") and reject
// the whole batch.
const isReferIncompleteForApprove = (d) => {
  if (!d) return true;
  if (!d.service_provider) return true;
  if (!d.clinical_question) return true;
  if (!d.notes_to_specialist) return true;
  if (!d.diagnosis_codes || d.diagnosis_codes.length === 0) return true;
  return false;
};
// Single source of truth for recommendation-side validation. Returns the
// failure reason for the COMMANDS_FILTERED audit, or null if insertable.
const getAcceptedRecFailureReason = (c) => {
  if (isRxCommand(c) && isRxIncomplete(c.data)) return 'rx_incomplete';
  if (c.command_type === 'refer' && isReferIncompleteForApprove(c.data)) return 'refer_incomplete';
  return null;
};
// Classify a dropped command for the validation-error surface. Mirrors the
// type-specific gates in the `insertable` filter so the user gets the same
// per-card error they'd see for a server-side rejection.
const _commandValidationReason = (c) => {
  if (isRxCommand(c) && isRxIncomplete(c.data)) return 'rx_incomplete';
  if (c.command_type === 'refer') return 'refer_incomplete';
  if (c.command_type === 'imaging_order') return 'imaging_incomplete';
  if (c.command_type === 'lab_order') return 'lab_incomplete';
  if (c.command_type === 'perform') return 'perform_incomplete';
  return 'validation';
};
const _validationErrorMessage = (c, reason, context = 'approving') => {
  const suffix = `Open it to fix before ${context}.`;
  if (reason === 'rx_incomplete') return `This prescription is missing required fields or contains invalid values (e.g. non-ASCII characters in sig, refills out of range, trailing-zero quantity). ${suffix}`;
  if (reason === 'refer_incomplete') return `This referral is missing required fields (indications, notes to specialist, clinical question, or service provider). ${suffix}`;
  if (reason === 'imaging_incomplete') return `This imaging order is missing required fields (image code, service provider, ordering provider, or diagnosis codes). ${suffix}`;
  if (reason === 'lab_incomplete') return `This lab order is missing required fields (lab partner or tests). ${suffix}`;
  if (reason === 'perform_incomplete') return `This perform command is missing a CPT code. ${suffix}`;
  return `This command has invalid values. ${suffix}`;
};

function formatTime(ms) {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function TranscriptEntry({ speaker, start_offset_ms, text, is_final, providerName, providerPhotoUrl, patientName }) {
  const s = (speaker || '').toUpperCase();
  const isUnspecified = !s || s === 'UNSPECIFIED';
  const isProvider = s === 'DOCTOR' || s.includes('PROVIDER') || s.includes('DOCTOR');
  const isPatient = s === 'PATIENT' || s.includes('PATIENT');
  const time = formatTime(start_offset_ms);

  if (!is_final && isUnspecified) {
    return html`
      <div class="transcript-entry partial">
        <div class="entry-avatar listening">...</div>
        <div class="entry-content">
          <div class="entry-meta">
            <span class="entry-speaker listening-label">Listening</span>
            <span class="entry-time">${time}</span>
          </div>
          <p class="entry-text">${text}</p>
        </div>
      </div>
    `;
  }

  const role = isProvider ? 'provider' : isPatient ? 'patient' : 'unspecified';
  const label = isProvider ? (providerName || 'Provider') : isPatient ? (patientName || 'Patient') : 'Unspecified';
  const initial = isProvider ? 'Dr' : isPatient ? 'Pt' : '?';

  return html`
    <div class="transcript-entry ${is_final ? '' : 'partial'}">
      ${isProvider && providerPhotoUrl
        ? html`<img class="entry-avatar-img" src=${providerPhotoUrl} alt=${label} />`
        : html`<div class="entry-avatar ${role}">${initial}</div>`}
      <div class="entry-content">
        <div class="entry-meta">
          <span class="entry-speaker">${label}</span>
          <span class="entry-time">${time}</span>
        </div>
        <p class="entry-text">${text}</p>
      </div>
    </div>
  `;
}


function VerificationSummary({ result }) {
  const [expanded, setExpanded] = useState(false);
  const total = result.verified.length + result.failed.length;
  const headline = result.ok
    ? `All ${total} command(s) inserted successfully`
    : `${result.failed.length} of ${total} command(s) failed to insert`;
  return html`
    <div class="verification-banner ${result.ok ? 'verification-ok' : 'verification-error'}">
      <div class="verification-headline" onClick=${() => setExpanded(prev => !prev)}>
        <span>${headline}</span>
        <span class="verification-chevron ${expanded ? 'open' : ''}">\u25BE</span>
      </div>
      ${expanded && html`
        <div class="verification-details">
          ${result.failed.length > 0 && html`
            <div class="verification-group verification-group-failed">
              ${result.failed.map(f => html`
                <div class="verification-item" key=${f.command_uuid}>
                  <span class="verification-tag failed-tag">${f.command_type}</span>
                  <span>${f.display || ''}</span>
                </div>
              `)}
            </div>
          `}
          ${result.verified.map(v => html`
            <div class="verification-item" key=${v.command_uuid}>
              <span class="verification-tag passed-tag">${v.command_type}</span>
              <span>${v.display || ''}</span>
            </div>
          `)}
        </div>
      `}
    </div>
  `;
}

const API_BASE = '/plugin-io/api/hyperscribe/scribe-session';

// Section_key for commands the backend can't map to a Scribe section.
// They render in the "FROM THE NOTE" catch-all block at the bottom of the
// tab.
const FROM_THE_NOTE_SECTION = 'from_the_note';

// Convert a schema_key/command_type (camelCase or snake_case) into a Title
// Case label for display: 'prescriptionChangeResponse' → 'Prescription
// Change Response', 'lab_review' → 'Lab Review'. Used by the FROM THE NOTE
// renderer when the Scribe doesn't know the command's structure.
function humanizeCommandType(type) {
  if (!type) return 'Command';
  return type
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .trim();
}

const SOAP_GROUPS = [
  { title: 'SUBJECTIVE', color: 'subjective', keys: new Set(['chief_complaint', 'history_of_present_illness', 'review_of_systems']) },
  { title: 'HISTORY', color: 'history', keys: new Set(['past_medical_history', 'past_surgical_history',
    'past_obstetric_history', 'family_history', 'social_history']) },
  { title: 'OBJECTIVE', color: 'objective', keys: new Set(['vitals', 'physical_exam', 'lab_results', 'imaging_results',
    'current_medications', 'allergies', 'immunizations']) },
  { title: 'ASSESSMENT & PLAN', color: 'plan', keys: new Set(['plan', 'assessment_and_plan', 'prescription', 'appointments']) },
  { title: 'CHARGES', color: 'charges', keys: new Set(['charges']) },
];

// KOALA-5485: section_keys whose already-documented commands can be edited
// during amendment. RFV (chief_complaint) goes through a direct EDIT effect;
// CustomCommand-routed sections (_ros, _history_review, _chart_review,
// physical_exam, lab_results, imaging_results) go through EnterInError +
// Originate; everything else goes through EnterInError + Originate + Commit.
//
// Covers every command_type in `_BUILDERS` EXCEPT orders (prescribe, refill,
// adjust_prescription, refer, imaging_order, lab_order) and questionnaires
// (which need a 4-effect amend route, deferred to a follow-up ticket).
//
// MIRRORED in three places - keep all in sync until single-sourcing lands
// (follow-up ticket):
//   - hyperscribe/scribe/commands/builder.py (EDITABLE_AMEND_SECTIONS)
//   - hyperscribe/scribe/static/summary.js (this file)
//   - hyperscribe/scribe/static/soap-group.js (EDITABLE_AMEND_SECTIONS)
const EDITABLE_AMEND_SECTIONS = new Set([
  // DIRECT_EDIT
  'chief_complaint',
  // CUSTOM_COMMAND_ROUTED
  '_ros',
  '_history_review',
  '_chart_review',
  'physical_exam',
  'lab_results',
  'imaging_results',
  // VOID_RECREATE - SOAP-section-anchored
  'history_of_present_illness',
  'current_medications',
  'allergies',
  'vitals',
  'past_medical_history',
  'past_surgical_history',
  'family_history',
  'assessment_and_plan',
  'plan',
  // VOID_RECREATE - ad-hoc buckets (rows added during a session retain these
  // section_keys after approval+reload).
  '_ad_hoc',
  '_objective_ad_hoc',
  '_history_ad_hoc',
  '_subjective_ad_hoc',
  '_charges_ad_hoc',
]);

// Command types that MUST NEVER be amended, regardless of section_key.
// Three reasons a command_type lands here (see builder.py for fuller writeup):
//   1. STRUCTURALLY IMPOSSIBLE: no COMMIT_*_COMMAND interpreter in home-app.
//   2. STRUCTURALLY AWKWARD: EIE works, no COMMIT - needs a 4-effect route.
//   3. POLICY EXCLUDED: full wiring exists, but amend-after-dispatch is the
//      wrong abstraction (a cancel/resend workflow is the right shape).
//
// Both lists work together: section_key gates "is this an amendable spot in
// the UI?", and command_type gates "is this kind of action safe to void
// and recreate?". An order added via the _ad_hoc bucket would pass the
// section gate but must still be denied by the command gate.
//
// Questionnaire IS amendable now (originate(commit=True) shortcut — backend
// emits EIE + originate-with-values-and-commit, 2 effects).
//
// MIRRORED with builder.py's NON_EDITABLE_AMEND_COMMAND_TYPES.
const NON_EDITABLE_AMEND_COMMAND_TYPES = new Set([
  // 1. Structurally impossible (no COMMIT_*_COMMAND interpreter):
  'prescribe',
  'refill',
  'adjust_prescription',
  // 2. Structurally awkward (EIE exists, no COMMIT - 4-effect route needed):
  'refer',
  'imaging_order',
  // 3. Policy excluded (full wiring exists; amend after lab-partner ticket
  //    dispatch creates downstream confusion - cancel/resend is the right shape):
  'lab_order',
]);

function isAmendingSectionEditable(command, isAmending) {
  // During amendment, allow editing iff (a) we're in amendment mode (wasFinalized
  // && !approved), (b) the section is in the allowlist, (c) the command_type
  // is not in the denylist (orders, questionnaire), and (d) the command was
  // originally inserted by Scribe (has a command_uuid we can target). New
  // ad-hoc commands added during amendment go through the normal insert path.
  return Boolean(
    isAmending &&
    command &&
    command.command_uuid &&
    EDITABLE_AMEND_SECTIONS.has(command.section_key) &&
    !NON_EDITABLE_AMEND_COMMAND_TYPES.has(command.command_type)
  );
}

const SKELETON_SECTIONS = [
  { key: 'chief_complaint', title: 'Chief Complaint', text: '' },
  { key: 'history_of_present_illness', title: 'History of Present Illness', text: '' },
  { key: 'past_medical_history', title: 'Past Medical History Discussed During Encounter', text: '' },
  { key: 'past_surgical_history', title: 'Past Surgical History', text: '' },
  { key: 'family_history', title: 'Family History', text: '' },
  { key: 'social_history', title: 'Social History', text: '' },
  { key: 'vitals', title: 'Vitals', text: '' },
  { key: 'physical_exam', title: 'Physical Exam', text: '' },
  { key: 'current_medications', title: 'Meds Discussed', text: '' },
  { key: 'allergies', title: 'Allergies Discussed', text: '' },
  { key: 'assessment_and_plan', title: 'Assessment & Plan', text: '' },
];

const FINALIZE_LABEL = 'Finalizing transcript';
const PROGRESS_STEPS = [
  'Generating note',
  'Structuring the note',
  'Extracting commands',
  'Generating recommendations',
  'Suggesting diagnoses',
];
// Total steps shown to the user = "Finalizing transcript" + the server-driven
// SUMMARY_STEPS pipeline. Used for the % progress calculation.
const TOTAL_PROGRESS_STEPS = PROGRESS_STEPS.length + 1;

function buildCommandBySectionKey(commands) {
  const map = {};
  commands.forEach((cmd, index) => {
    if (cmd.section_key) {
      if (!map[cmd.section_key]) {
        map[cmd.section_key] = [];
      }
      map[cmd.section_key].push({ command: cmd, index });
    }
  });
  return map;
}

function renderSoapGroups(sections, commandBySectionKey, onEditCommand, onDeleteCommand, { adHocCommands, objectiveAdHocCommands, historyAdHocCommands, subjectiveAdHocCommands, chargeAdHocCommands, assignees, onAddTask, onAddOrder, onAddPlan, onAddMedication, onAddAllergy, onAddStopMedication, onAddRemoveAllergy, onAddResolveCondition, onAddHistory, onAddQuestionnaire, onAddCharge, onAddTemplateCharge, onRemoveChargeByCpt, templateCharges, readOnly, isAmending, sectionConditions, patientId, noteId, staffId, staffName, recommendations, onEditRecommendation, onDeleteRecommendation, onAcceptRecommendation, onRejectRecommendation, onAddCondition, unmatchedConditions, diagnosisSuggestions, onAddNow, onAddVitals, hideRejected, alertFacilityEnabled, onEditingChange, questionnaireScores, chargeMatrixDiagnoses, chargeMatrixCharges, searchCharges, suggestedCharges, onToggleChargePointer, onReorderDiagnoses, onAddChargeModifier, onRemoveChargeModifier, onSetChargeComment, onClearChargeComment, onRemoveChargeByUuid, examTemplates, onCarryForwardExam, noteDiagnoses } = {}) {
  return SOAP_GROUPS
    .map(group => {
      const matching = sections.filter(s => group.keys.has(s.key.toLowerCase()));
      const isPlan = group.title === 'ASSESSMENT & PLAN';
      const isObjective = group.title === 'OBJECTIVE';
      const isHistory = group.title === 'HISTORY';
      const isSubjective = group.title === 'SUBJECTIVE';
      const isCharges = group.title === 'CHARGES';
      return html`<${SoapGroup}
        key=${group.title}
        title=${group.title}
        groupColor=${group.color}
        sections=${matching}
        commandBySectionKey=${commandBySectionKey}
        onEditCommand=${onEditCommand}
        onDeleteCommand=${onDeleteCommand}
        adHocCommands=${isPlan ? adHocCommands : isObjective ? objectiveAdHocCommands : isHistory ? historyAdHocCommands : isSubjective ? subjectiveAdHocCommands : isCharges ? chargeAdHocCommands : null}
        assignees=${isPlan ? assignees : null}
        onAddTask=${isPlan ? onAddTask : null}
        onAddOrder=${isPlan ? onAddOrder : null}
        onAddPlan=${isPlan ? onAddPlan : null}
        onAddVitals=${isObjective ? onAddVitals : null}
        onAddMedication=${isObjective ? onAddMedication : null}
        onAddAllergy=${isObjective ? onAddAllergy : null}
        onAddStopMedication=${isObjective ? onAddStopMedication : null}
        onAddRemoveAllergy=${isObjective ? onAddRemoveAllergy : null}
        onAddResolveCondition=${isPlan ? onAddResolveCondition : null}
        onAddHistory=${isHistory ? onAddHistory : null}
        onAddQuestionnaire=${isSubjective ? onAddQuestionnaire : null}
        onAddCharge=${isCharges ? onAddCharge : null}
        searchCharges=${isCharges ? searchCharges : null}
        suggestedCharges=${isCharges ? suggestedCharges : null}
        onAddTemplateCharge=${isCharges ? onAddTemplateCharge : null}
        onRemoveChargeByCpt=${isCharges ? onRemoveChargeByCpt : null}
        templateCharges=${isCharges ? templateCharges : null}
        chargeMatrixDiagnoses=${isCharges ? chargeMatrixDiagnoses : null}
        chargeMatrixCharges=${isCharges ? chargeMatrixCharges : null}
        onToggleChargePointer=${isCharges ? onToggleChargePointer : null}
        onReorderDiagnoses=${isCharges ? onReorderDiagnoses : null}
        onAddChargeModifier=${isCharges ? onAddChargeModifier : null}
        onRemoveChargeModifier=${isCharges ? onRemoveChargeModifier : null}
        onSetChargeComment=${isCharges ? onSetChargeComment : null}
        onClearChargeComment=${isCharges ? onClearChargeComment : null}
        onRemoveChargeByUuid=${isCharges ? onRemoveChargeByUuid : null}
        readOnly=${readOnly}
        isAmending=${isAmending}
        sectionConditions=${sectionConditions}
        patientId=${patientId}
        noteId=${noteId}
        staffId=${staffId}
        staffName=${staffName}
        recommendations=${(isObjective || isPlan) ? recommendations : null}
        onEditRecommendation=${(isObjective || isPlan) ? onEditRecommendation : null}
        onDeleteRecommendation=${(isObjective || isPlan) ? onDeleteRecommendation : null}
        onRejectRecommendation=${(isObjective || isPlan) ? onRejectRecommendation : null}
        onAcceptRecommendation=${(isObjective || isPlan) ? onAcceptRecommendation : null}
        onAddCondition=${isPlan ? onAddCondition : null}
        unmatchedConditions=${isPlan ? unmatchedConditions : null}
        diagnosisSuggestions=${isPlan ? diagnosisSuggestions : null}
        noteDiagnoses=${noteDiagnoses}
        onAddNow=${(isPlan || isObjective) ? onAddNow : null}
        hideRejected=${hideRejected}
        alertFacilityEnabled=${alertFacilityEnabled}
        onEditingChange=${onEditingChange}
        questionnaireScores=${isObjective ? questionnaireScores : null}
        examTemplates=${(isObjective || isSubjective) ? examTemplates : null}
        onCarryForwardExam=${(isObjective || isSubjective) ? onCarryForwardExam : null}
      />`;
    })
    .filter(Boolean);
}

export function Scribe({ noteId, patientId, staffId, staffName, providerName, providerPhotoUrl, patientName, patientBirthDate, patientGender, debugMode, noteEditable = true, isAuthor = false, alertFacilityEnabled = false, manualModeOnly = false, initialData = null }) {
  const initSummary = initialData?.summary ?? null;
  const [noteData, setNoteData] = useState(initSummary?.note ?? null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [commands, setCommands] = useState(initSummary?.commands ?? []);
  const [inserting, setInserting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [approved, setApproved] = useState(initSummary?.approved ?? false);
  // Fall back to `approved` so pre-existing finalized notes (saved before the
  // was_finalized latch shipped) still surface the amendment pill on open.
  // New rows ride the explicit latch from _save_summary.
  const [wasFinalized, setWasFinalized] = useState(
    initSummary?.was_finalized ?? !!initSummary?.approved
  );
  const [isNoteEditable, setNoteEditable] = useState(noteEditable);
  const [hideRejected, setHideRejected] = useState(true);
  const [assignees, setAssignees] = useState(initialData?.assignees ?? []);
  const [recommendations, setRecommendations] = useState(initSummary?.recommendations ?? []);
  const [sectionConditions, setSectionConditions] = useState({});
  const [unmatchedConditions, setUnmatchedConditions] = useState(initSummary?.unmatched_conditions ?? []);
  const [diagnosisSuggestions, setDiagnosisSuggestions] = useState(initSummary?.diagnosis_suggestions ?? {});
  const [progress, setProgress] = useState({ step: -1, total: 0, label: '' });
  const [verificationResult, setVerificationResult] = useState(null);
  const [validationError, setValidationError] = useState(null);
  const [chargeErrors, setChargeErrors] = useState([]);

  // Template state.
  const [templates, setTemplates] = useState(initialData?.templates ?? []);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [mode, setMode] = useState(() => {
    const cached = initSummary?.mode ?? null;
    // Dead state recovery: ai mode was persisted but recording was never started (e.g.
    // mic failure persisted mode before startRecording could revert it). Only applies
    // to 'ai' — manual mode legitimately has no transcript.
    if (cached === 'ai' && !initSummary?.note && !initialData?.transcript?.started) {
      return null;
    }
    return cached;
  });
  const [transcriptCollapsed, setTranscriptCollapsed] = useState(false);
  // Auto-scroll the transcript body to the latest entry whenever live capture
  // is producing or refining content. We deliberately don't try to "respect"
  // a user's scroll-up while recording — clinicians want to keep seeing the
  // running transcription as proof the capture is working, and the scroll
  // would just keep losing fights with new entries anyway. Once the session
  // is finalized, entries stop changing and the user can scroll freely.
  const transcriptBodyRef = useRef(null);
  const [cachedTemplateName, setCachedTemplateName] = useState(initSummary?.selected_template_name ?? null);
  const cacheLoadedRef = useRef(!!initialData);
  const addNowAttemptedRef = useRef([]);
  // KOALA-5687: amend edits use VOID_RECREATE (EnterInError old uuid + originate
  // new uuid). Between the EIE and the local re-stamp there's a window where the
  // chart's uuids no longer match local state; a syncNoteCommands landing in that
  // window would drop the local rich card and re-append the chart row stamped
  // `from_the_note`, reshuffling amended 1st-party commands into ADDITIONAL
  // COMMANDS. Three coordinated guards keep the sync from corrupting state:
  //   - amendEditInFlightRef: true for the duration of /edit-existing-commands +
  //     re-stamp; syncNoteCommands bails if it sees this set (at fetch start or
  //     after the fetch resolves).
  //   - amendGenRef: bumped once each amend completes; a sync that captured an
  //     older generation before its fetch bails after the await (the amend
  //     finished mid-fetch).
  //   - amendUuidRemapRef: accumulates old_uuid -> new_uuid across the session so
  //     a sync that still holds an old uuid can bridge it to the re-originated
  //     command instead of dropping the rich local card.
  const amendEditInFlightRef = useRef(false);
  const amendGenRef = useRef(0);
  const amendUuidRemapRef = useRef(new Map());
  // KOALA_5634_RECOMMENDATIONS_REF: live mirror of `recommendations`. syncNoteCommands
  // needs to consult both `commands` (via the `setCommands(prev => ...)` updater) AND
  // `recommendations` when deciding whether a fetched uuid is "Scribe-side" vs
  // "ad-hoc / brand new." Adding `recommendations` to the useCallback deps would
  // re-create syncNoteCommands on every recommendation accept / reject and re-fire
  // every effect that depends on it; a ref keeps the callback stable while still
  // exposing the latest value at call time. Bug context (KOALA-5634): without this,
  // accepted recommendations get appended as `from_the_note` duplicates on the next
  // syncNoteCommands call after approval.
  const recommendationsRef = useRef(recommendations);
  // KOALA_5634_RECOMMENDATIONS_REF: commitRecommendations() is the canonical
  // entry point for ALL approval-flow setRecommendations writes (cache-load
  // restore, /insert-commands success re-stamp, handleAddNow rec stamp).
  // Why a helper instead of a one-off inline prime per call site:
  //   - React's setRecommendations batches into a future commit. The useEffect
  //     mirror at ~600 only runs post-commit. Approval-flow sites trigger
  //     syncNoteCommands synchronously (cache-load via its `finally`, approve
  //     via the post-success CLOSE_MODAL → NOTE_TAB_CHANGE bridge, handleAddNow
  //     via NOTE_TAB_CHANGE on the just-inserted command). Without an imperative
  //     prime that closes the gap, recommendationsRef.current reads stale and
  //     syncNoteCommands appends just-stamped recs as `from_the_note` duplicates.
  //   - Three sites is enough that an extracted helper beats remembering the
  //     prime-then-set ordering at each call site.
  // The ref mirror at ~600 stays as belt-and-braces for non-approval setRecommendations
  // call sites (handleGenerate, handleMakeChanges, per-rec toggles) — they do not
  // race against a synchronous syncNoteCommands trigger and don't need this helper.
  const commitRecommendations = (next) => {
    recommendationsRef.current = typeof next === 'function' ? next(recommendationsRef.current) : next;
    setRecommendations(next);
  };
  // Set to true after the first save-summary 403 (`_authorize_edit` denial:
  // note locked or wrong author). Gates subsequent autosaves so the Scribe
  // tab doesn't fire one POST per state change against a note it can't
  // actually save to. Brigade was generating ~11.9k of these in 14 days.
  const saveBlockedRef = useRef(false);

  const [editingFields, setEditingFields] = useState(new Set());

  // Every command needs a STABLE, UNIQUE client id for the charges matrix to
  // tell rows/columns apart. Scribe-generated diagnose/assess commands have
  // neither a command_uuid (assigned only after insertion) nor a _localId, so
  // without this they'd all share the same (undefined) identity — checking one
  // checkbox in a column would visually check the whole column. We stamp a
  // _localId on any command missing one and key the matrix on _localId (NOT
  // command_uuid) so the identity stays stable across the insert boundary,
  // which also keeps the diagnosis-pointer -> code resolution correct at
  // /enrich-charges time.
  useEffect(() => {
    if (commands.some(c => !c._localId)) {
      setCommands(prev => prev.map(c => (c._localId ? c : { ...c, _localId: crypto.randomUUID() })));
    }
  }, [commands]);

  // --- Charge matrix view-models (derived from commands) ---
  const chargeMatrixDiagnoses = useMemo(() => commands
    .filter(c => (c.command_type === 'diagnose' || c.command_type === 'assess')
      && (c.data?.icd10_code || c.data?.code) && c._localId
      && (c.already_documented || c.command_uuid
          // diagnose: must be explicitly accepted (absent = unreviewed AI rec → hide)
          // assess:   absent accepted = manually added via old code → show; only hide on false
          || (c.command_type === 'assess' ? c.data?.accepted !== false : c.data?.accepted)))
    .map(c => ({
      command_uuid: c._localId,
      code: c.data?.icd10_code || c.data?.code || '',
      label: c.data?.icd10_display || c.data?.label || c.display || '',
      locked: Boolean(c.already_documented || c.command_uuid),
    })), [commands]);

  // Accepted A&P diagnoses staged in this note, shaped for the referral
  // Indications dropdown ({code, formatted_code, display}). Reuses the same
  // accept filter as chargeMatrixDiagnoses so unreviewed AI suggestions stay
  // hidden. `code` is normalized (no dot, upper) to dedup against chart
  // conditions and already-selected chips; formatted_code keeps the dotted form.
  const noteDiagnoses = useMemo(() => chargeMatrixDiagnoses
    .filter(d => d.code)
    .map(d => ({
      code: d.code.replace(/\./g, '').toUpperCase(),
      formatted_code: d.code,
      display: d.label,
    })), [chargeMatrixDiagnoses]);

  // Prune stale diagnosis pointers. When a linked diagnosis is rejected or removed
  // it leaves chargeMatrixDiagnoses, but its _localId lingers in charges' _pointers.
  // Stale UUIDs eat cap slots and can push the sign payload over MAX_POINTERS
  // (reject a linked dx → add a replacement → re-accept the original = 5 live
  // pointers → server 422). Drop any pointer not backed by a live matrix diagnosis.
  // Safe against load churn: _localId is preserved across cache restore / sync, so a
  // valid diagnosis never drops out of the live set and never has its pointer pruned.
  useEffect(() => {
    const live = new Set(chargeMatrixDiagnoses.map(d => d.command_uuid));
    setCommands(prev => {
      let changed = false;
      const next = prev.map(c => {
        if (c.command_type !== 'perform' || !('_pointers' in (c.data || {}))) return c;
        const cur = c.data._pointers || [];
        const pruned = cur.filter(u => live.has(u));
        if (pruned.length === cur.length) return c;
        changed = true;
        return { ...c, data: { ...c.data, _pointers: pruned } };
      });
      return changed ? next : prev; // same ref when nothing pruned → no re-render loop
    });
  }, [chargeMatrixDiagnoses]);

  const chargeMatrixCharges = useMemo(() => {
    const dxRefs = new Set(chargeMatrixDiagnoses.map(d => d.command_uuid));
    return commands
      .filter(c => c.command_type === 'perform' && c.data?.cpt_code && c.selected !== false && !c._amend_deleted && c._localId)
      .map(c => ({
        command_uuid: c._localId,
        cpt: c.data.cpt_code,
        description: c.data.description || '',
        comment: c.data.notes || '',
        modifiers: c.data._modifiers || [],
        pointers: (c.data._pointers || []).filter(u => dxRefs.has(u)),
        // True only when this plugin has written _pointers to the charge. Pre-plugin
        // historical charges have no _pointers key at all and are grandfathered out of
        // the sign gate and the error-pill so they don't block amendment on old notes.
        hasPointerData: '_pointers' in (c.data || {}),
      }));
  }, [commands, chargeMatrixDiagnoses]);

  // The matrix keys rows/columns on _localId (stable, unique per command).
  const matrixRef = (localId) => (c) => c._localId === localId;

  const onToggleChargePointer = useCallback((chargeUuid, dxUuid) => {
    // Use the live (dxRefs-filtered) count for the cap check — raw _pointers may
    // contain stale UUIDs from rejected diagnoses that were previously linked,
    // causing the cap to fire even though the footer pill reads < MAX_POINTERS.
    const liveDxUuids = new Set(chargeMatrixDiagnoses.map(d => d.command_uuid));
    setCommands(prev => prev.map(c => {
      if (!matrixRef(chargeUuid)(c)) return c;
      const cur = c.data._pointers || [];
      const has = cur.includes(dxUuid);
      const liveCount = cur.filter(u => liveDxUuids.has(u)).length;
      if (!has && liveCount >= MAX_POINTERS) return c;
      return { ...c, data: { ...c.data, _pointers: has ? cur.filter(u => u !== dxUuid) : [...cur, dxUuid] } };
    }));
  }, [chargeMatrixDiagnoses]);

  // Both modifier handlers also stamp _pointers so a modifier-only edit opts the
  // charge into plugin-managed enrichment. The enrich filter (and hasPointerData)
  // key on the _pointers KEY being present; without this stamp, a modifier added
  // to a pre-plugin charge (no _pointers key) is silently excluded from
  // /enrich-charges and never written to the BLI. Mirrors onToggleChargePointer.
  const onAddChargeModifier = useCallback((chargeUuid, code) => setCommands(prev => prev.map(c => {
    if (!matrixRef(chargeUuid)(c)) return c;
    const cur = c.data._modifiers || [];
    if (cur.includes(code) || cur.length >= MAX_MODIFIERS) return c;
    return { ...c, data: { ...c.data, _pointers: c.data._pointers || [], _modifiers: [...cur, code] } };
  })), []);

  const onRemoveChargeModifier = useCallback((chargeUuid, code) => setCommands(prev => prev.map(c =>
    matrixRef(chargeUuid)(c)
      ? { ...c, data: { ...c.data, _pointers: c.data._pointers || [], _modifiers: (c.data._modifiers || []).filter(m => m !== code) } }
      : c)), []);

  // Comment handlers write the perform command's native `notes` field, committed
  // via /insert-commands and rendered by the existing scribe-print template —
  // no enrichment needed (unlike _modifiers/_pointers on the BLI).
  //
  // For a charge NOT yet on the claim (fresh note, or one added during this
  // amendment) we edit notes in place; the insert path carries it.
  //
  // For a charge ALREADY on the signed claim, notes can't be edited in place
  // (committed perform commands reject .edit(); the only edit path re-originates).
  // So we mirror the home-app "enter in error + re-enter" gesture: void the old
  // command (_amend_deleted → /delete-existing-commands) and add a fresh clone
  // carrying the same CPT/modifiers/pointers with the new comment (→ /insert-
  // commands). Entering the old command in error leaves its BillingLineItem
  // ACTIVE (command_id is null on BLIs, so home-app can't auto-void it), so the
  // sign flow explicitly removes the old charge's BLI after the delete and BEFORE
  // the clone is inserted — see the "early charge-BLI removal" step in handleInsert.
  const setChargeComment = (chargeUuid, notes) => setCommands(prev => {
    const idx = prev.findIndex(c => matrixRef(chargeUuid)(c));
    if (idx < 0) return prev;
    const target = prev[idx];
    // Mirror onRemoveChargeByUuid's gate: only a charge actually on the signed
    // claim needs the void+re-enter dance. Everything else edits notes in place.
    if (!(target.already_documented && isAmendingSectionEditable(target, wasFinalized && !approved))) {
      return prev.map(c => matrixRef(chargeUuid)(c) ? { ...c, data: { ...c.data, notes } } : c);
    }
    const { _amend_edited, _template_inserted, ...base } = target;
    const clone = {
      ...base,
      _localId: crypto.randomUUID(),
      command_uuid: null,
      already_documented: false,
      _amend_deleted: false,
      selected: true,
      data: { ...target.data, notes },
    };
    const next = prev.map((c, i) => i === idx ? { ...c, selected: false, _amend_deleted: true } : c);
    next.splice(idx + 1, 0, clone);
    return next;
  });
  const onSetChargeComment = useCallback((chargeUuid, text) => setChargeComment(chargeUuid, text), [wasFinalized, approved]);
  const onClearChargeComment = useCallback((chargeUuid) => setChargeComment(chargeUuid, ''), [wasFinalized, approved]);

  const onReorderDiagnoses = useCallback((nextUuids) => setCommands(prev => {
    // The matrix keys rows on _localId (stable, unique), so reorder must too —
    // matching by command_uuid would miss already-documented diagnoses (whose
    // _localId the matrix sends) and the cover-check below would bail.
    // isDx must mirror chargeMatrixDiagnoses exactly so dxBy.size matches
    // nextUuids.length — otherwise the size guard always bails.
    const idOf = c => c._localId;
    const isDx = c => (c.command_type === 'diagnose' || c.command_type === 'assess')
      && (c.data?.icd10_code || c.data?.code) && c._localId
      && (c.already_documented || c.command_uuid
          || (c.command_type === 'assess' ? c.data?.accepted !== false : c.data?.accepted));
    const dxBy = new Map(prev.filter(isDx).map(c => [idOf(c), c]));
    const reordered = nextUuids.map(u => dxBy.get(u)).filter(Boolean);
    // If the incoming order doesn't cover every diagnosis row exactly once, bail
    // rather than write undefined slots into commands.
    if (reordered.length !== dxBy.size) return prev;
    let i = 0;
    return prev.map(c => isDx(c) ? reordered[i++] : c);
  }), []);

  // onRemoveChargeByUuid: removes a charge from the matrix. Reuses the same
  // _amend_deleted tagging path as handleRemoveChargeByCpt so the amend-delete
  // EIE flow in handleInsert fires correctly for already-documented charges.
  const onRemoveChargeByUuid = useCallback((chargeUuid) => {
    const amending = wasFinalized && !approved;
    setCommands(prev => prev.map(c => {
      if (!matrixRef(chargeUuid)(c)) return c;
      if (c.already_documented && isAmendingSectionEditable(c, amending)) {
        return { ...c, selected: false, _amend_deleted: true };
      }
      return { ...c, selected: false };
    }));
  }, [wasFinalized, approved]);
  // --- End charge matrix ---

  // Recording hook.
  const recording = useRecording(noteId, initialData?.transcript);

  // Keep the transcript pinned to the latest entry as new ones stream in or
  // get refined (in-place partial updates, speaker-attribution flips, etc.).
  // RAF defers the scroll until after layout so scrollHeight reflects the
  // post-update height. Skipped once the recording is finalized so we don't
  // yank a user reading the saved transcript on later mounts.
  useEffect(() => {
    if (transcriptCollapsed) return;
    if (recording.finalized) return;
    const el = transcriptBodyRef.current;
    if (!el) return;
    const rafId = requestAnimationFrame(() => {
      const node = transcriptBodyRef.current;
      if (!node) return;
      node.scrollTo({ top: node.scrollHeight, behavior: 'smooth' });
    });
    return () => cancelAnimationFrame(rafId);
  }, [recording.entries, transcriptCollapsed, recording.finalized]);

  const [showSavedToast, setShowSavedToast] = useState(false);
  useEffect(() => {
    if (!recording.lastSaved) return;
    logEvent('TRANSCRIPT_AUTO_SAVED', { entryCount: recording.entries.length });
    setShowSavedToast(true);
    const timer = setTimeout(() => setShowSavedToast(false), 2000);
    return () => clearTimeout(timer);
  }, [recording.lastSaved]);

  // Audit logging.
  useEffect(() => { initAuditLog(noteId); }, [noteId]);

  // WebSocket: listen for note state changes in real time.
  useEffect(() => {
    if (!noteId) return;
    const cleanup = connectScribeWS(noteId, (msg) => {
      if (msg.type === 'NOTE_STATE_CHANGED') {
        setNoteEditable(msg.editable);
      }
    });
    return cleanup;
  }, [noteId]);

  const noteLocked = !isNoteEditable && !approved;
  const canEdit = isAuthor && isNoteEditable && !approved;
  // Lock takes precedence over authorship in the banner messaging.
  const readOnlyReason = noteLocked
    ? 'locked'
    : (!isAuthor && !approved ? 'non_author' : null);

  const saveSummaryToCache = useCallback(async (note, cmds, isApproved, extras = {}) => {
    // Skip the request entirely when we already know the server will reject
    // it: non-author viewers and locked notes both fail `_authorize_edit`
    // server-side. The read-only banner elsewhere already covers these cases
    // visually; no point firing a request to be told "no" again.
    if (!isAuthor) return;
    if (!isNoteEditable) return;
    // Once the server has rejected an autosave for this note (typical cause:
    // the note finalized while the Scribe tab was still attached), stop
    // sending. The note can't become editable again without an explicit user
    // action (Amend / state change), and those paths reset isNoteEditable
    // via the NOTE_STATE_CHANGED WS message — they don't go through here.
    if (saveBlockedRef.current) return;
    try {
      const res = await fetch(`${API_BASE}/save-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_id: noteId, note, commands: cmds, approved: isApproved, ...extras }),
      });
      if (res.status === 403) {
        // _authorize_edit denial — "Note is not editable" or "Only the note
        // author can modify the Scribe tab". Gate further autosaves silently;
        // the existing locked / non-author banner already explains why edits
        // aren't sticking.
        saveBlockedRef.current = true;
      }
    } catch (err) {
      console.error('Failed to save summary to cache:', err);
    }
  }, [noteId, isAuthor, isNoteEditable]);

  // Resetting the gate when the note becomes editable again (post-Amend, or
  // the user re-loads onto a fresh note in the same iframe). isNoteEditable
  // flips via the NOTE_STATE_CHANGED WS message — see the listener above.
  useEffect(() => {
    if (isNoteEditable) saveBlockedRef.current = false;
  }, [isNoteEditable, noteId]);

  const handleMakeChanges = useCallback(() => {
    if (!isAuthor || !isNoteEditable || !approved) return;
    // Either `already_documented` OR `command_uuid` means "already on the note"
    // — same predicate as the `insertable` filter (see 8ea1df36 back-compat
    // fix). Pre-existing finalized notes (signed before the explicit
    // already_documented stamping shipped) carry command_uuid but not the
    // explicit flag; using `already_documented` alone here would wipe every
    // such command on Make Changes. command_uuid is the authoritative
    // "on the note" signal.
    const onNote = (c) => c.already_documented || c.command_uuid;
    const documentedCount = commands.filter(onNote).length;
    // KOALA-5687: keep recommendations that are already on the note (accepted +
    // inserted: command_uuid + already_documented). They live in the
    // `recommendations` array — NOT `commands` — and carry no section_key, so
    // syncNoteCommands relies on `recommendationUuids` (built from
    // recommendationsRef) to keep them out of the from_the_note bucket. Blanket
    // -clearing here emptied that guard, so the next sync re-appended these
    // still-on-chart commands (medication_statement, allergy, refer, task,
    // prescribe) as ADDITIONAL COMMANDS. Filtering by `onNote` preserves the
    // KOALA-5634 protection while still dropping un-inserted AI recs (the
    // original intent — they have no uuid/flag, so they won't re-insert).
    const keptRecommendations = recommendations.filter(onNote);
    logEvent('AMENDMENT_STARTED', {
      commands_at_start: documentedCount,
      dropped_commands: commands.length - documentedCount,
      dropped_recommendations: recommendations.length - keptRecommendations.length,
    });
    // Scribe should mirror the signed note during amendment: drop AI recs that
    // never made it into the note. Leaving them in state would also re-insert
    // them on re-Approve via the `insertable` filter.
    setCommands(prev => prev.filter(onNote));
    // commitRecommendations primes recommendationsRef synchronously so the very
    // next syncNoteCommands sees the kept uuids and keeps them out of
    // ADDITIONAL COMMANDS (KOALA_5634_RECOMMENDATIONS_REF).
    commitRecommendations(keptRecommendations);
    setUnmatchedConditions([]);
    setDiagnosisSuggestions({});
    setApproved(false);
    // Optimistically keep wasFinalized=true; it's a one-way latch server-side
    // already, but ensure the React state matches without waiting for the
    // /summary refetch.
    setWasFinalized(true);
  }, [isAuthor, isNoteEditable, approved, commands, recommendations]);

  // Keep the recommendations ref in lockstep with state so syncNoteCommands
  // (a stable callback that intentionally avoids `recommendations` in its deps)
  // sees the latest uuids when filtering fetched commands. See KOALA_5634_RECOMMENDATIONS_REF.
  useEffect(() => {
    recommendationsRef.current = recommendations;
  }, [recommendations]);

  // Pull the note's actual Command rows from the server and merge them into
  // local state. Commands the Scribe already inserted itself stay as-is
  // (richer local data); commands that exist on the note but not locally are
  // appended (ad-hoc additions from the note-body editor); local commands
  // with a UUID that's no longer on the note are dropped (user removed them
  // outside the Scribe).
  const syncNoteCommands = useCallback(async () => {
    if (!noteId) return;
    // KOALA-5687: don't sync while an amend edit is mid-flight. The window
    // between EnterInError (old uuid voided on the chart) and the local
    // re-stamp (local rows updated to the new uuids) is exactly when a sync
    // would see the old uuid missing from the fetch, drop the rich local card,
    // and re-append the chart row as a `from_the_note` bucket — reshuffling
    // amended 1st-party commands into ADDITIONAL COMMANDS.
    if (amendEditInFlightRef.current) return;
    const genAtFetchStart = amendGenRef.current;
    try {
      const res = await fetch(
        `${API_BASE}/note-commands?note_id=${encodeURIComponent(noteId)}`,
        { credentials: 'include' }
      );
      if (!res.ok) return;
      const data = await res.json();
      // KOALA-5687: if an amend started or completed while this fetch was in
      // flight, the payload is stale (taken against pre-amend chart uuids).
      // Bail — a fresh sync will run after the amend settles.
      if (amendEditInFlightRef.current || amendGenRef.current !== genAtFetchStart) return;
      const fetched = data.commands || [];
      const fetchedByUuid = new Map(fetched.map(c => [c.command_uuid, c]));
      // KOALA_5634_SYNC_CONSULTS_RECOMMENDATIONS: collect uuids from the live
      // recommendations list as well — accepted recs that were just inserted
      // carry a command_uuid (stamped in handleInsert) but live in
      // `recommendations`, not `commands`. Without this guard the next sync
      // would treat the rec's uuid as unknown and append the chart row as a
      // duplicate `from_the_note` card under ADDITIONAL COMMANDS (KOALA-5634).
      const recommendationUuids = new Set(
        (recommendationsRef.current || [])
          .map(r => r && r.command_uuid)
          .filter(Boolean)
      );
      // KOALA-5687: old_uuid -> new_uuid for commands re-originated by amend
      // this session. Lets the drop branch below bridge a local card whose
      // (old) uuid is gone from the chart to its re-originated row, keeping the
      // rich local entry (snake command_type + structured data + original
      // section_key) instead of losing it to the thin `from_the_note` fetch.
      const amendRemap = amendUuidRemapRef.current;
      setCommands(prev => {
        const merged = [];
        const keptUuids = new Set();
        for (const cmd of prev) {
          if (!cmd.command_uuid) {
            // Local draft (no UUID yet) — preserve.
            merged.push(cmd);
            continue;
          }
          if (fetchedByUuid.has(cmd.command_uuid)) {
            const fetchedCmd = fetchedByUuid.get(cmd.command_uuid);
            // KOALA_5689_FROM_NOTE_OVERLAY: for from_the_note cards the chart
            // is the source of truth — overlay the fetched payload so
            // post-add updates (user edits the ad-hoc command on the Note
            // tab) propagate into ADDITIONAL COMMANDS. For Scribe-side
            // commands we preserve the local entry as before; overlaying
            // would force section_key to from_the_note and yank the card
            // out of its original SOAP group.
            if (cmd.section_key === FROM_THE_NOTE_SECTION || cmd._from_note) {
              merged.push({ ...fetchedCmd, already_documented: true });
            } else {
              merged.push({ ...cmd, already_documented: true });
            }
            keptUuids.add(cmd.command_uuid);
            continue;
          }
          // KOALA-5687: the local uuid is gone from the chart. Before dropping,
          // check whether amend re-originated this command under a new uuid that
          // IS on the chart. If so, keep the rich local card under the new uuid
          // (preserving its SOAP section_key + structured data) rather than
          // letting it fall away and resurface as a thin `from_the_note` card.
          const bridgedUuid = amendRemap.get(cmd.command_uuid);
          if (bridgedUuid && fetchedByUuid.has(bridgedUuid) && !keptUuids.has(bridgedUuid)) {
            merged.push({ ...cmd, command_uuid: bridgedUuid, already_documented: true });
            keptUuids.add(bridgedUuid);
            continue;
          }
          // else: had a UUID but it's gone from the note → drop.
        }
        for (const cmd of fetched) {
          if (keptUuids.has(cmd.command_uuid)) continue;
          // KOALA_5634_SYNC_CONSULTS_RECOMMENDATIONS: skip uuids that are
          // already represented by a stamped recommendation — they render in
          // the SOAP groups via the `recommendations` array, not as locked
          // ADDITIONAL COMMANDS cards.
          if (recommendationUuids.has(cmd.command_uuid)) continue;
          // New ad-hoc command from the note body — append as-is so it
          // lands in the FROM THE NOTE block.
          merged.push(cmd);
        }
        return merged;
      });
    } catch (err) {
      // Sync failures are non-fatal — leave whatever's already on screen.
    }
  }, [noteId]);

  // Pull the note's command rail whenever the user switches Note tabs.
  // The home-app broker sends NOTE_TAB_CHANGE to every Note Application
  // iframe on every tab switch; `index.html` bridges port messages to a
  // `canvas-message` CustomEvent on `window`. We sync on every event
  // regardless of the new active tab — the cost is a single GET and the
  // alternative (matching this iframe's app identifier) adds branchy client
  // code for no real win.
  useEffect(() => {
    const onCanvasMessage = (event) => {
      if (event.detail?.type === 'NOTE_TAB_CHANGE') {
        syncNoteCommands();
      }
    };
    window.addEventListener('canvas-message', onCanvasMessage);
    return () => window.removeEventListener('canvas-message', onCanvasMessage);
  }, [syncNoteCommands]);

  // Pull the note's command rail once on mount so ADDITIONAL COMMANDS
  // populates without waiting for a tab switch. The cache-load effect below
  // also calls syncNoteCommands in its `finally`, but it early-exits when
  // server-side `initialData` is present — in that path nothing else triggers
  // the initial sync.
  useEffect(() => {
    if (!noteId) return;
    syncNoteCommands();
  }, [noteId, syncNoteCommands]);

  // Load summary from cache — skip if initial data was provided server-side.
  useEffect(() => {
    if (initialData) return;
    let cancelled = false;

    async function loadOrGenerate() {
      try {
        const cacheRes = await fetch(`${API_BASE}/summary?note_id=${encodeURIComponent(noteId)}`);
        if (!cancelled) {
          const cached = await cacheRes.json();
          // Restore cached template name (resolved against templates once they load).
          if (cached.selected_template_name) {
            setCachedTemplateName(cached.selected_template_name);
          }
          if (cached.mode) {
            setMode(cached.mode);
          }
          if (cached.approved) {
            setApproved(true);
          }
          // Treat cached.approved as implying was_finalized for pre-existing
          // finalized notes that predate the explicit latch.
          if (cached.was_finalized || cached.approved) {
            setWasFinalized(true);
          }
          if (cached.note) {
            // Full cached summary — restore everything.
            setNoteData(cached.note);
            setCommands(cached.commands || []);
            // KOALA_5634_RECOMMENDATIONS_REF: commitRecommendations() primes the
            // ref synchronously before the syncNoteCommands() call in the `finally`
            // block fires. Without that prime, a fetched command_uuid that belongs
            // to a cached, stamped recommendation would be appended as a
            // from_the_note duplicate (KOALA-5634), and the duplicate would
            // persist because the next sync sees it in `commands` and preserves it.
            commitRecommendations(cached.recommendations || []);
            setUnmatchedConditions(cached.unmatched_conditions || []);
            setDiagnosisSuggestions(cached.diagnosis_suggestions || {});
            // Repopulate Add Now attempted entries from cached items for verification merge.
            addNowAttemptedRef.current = [
              ...(cached.commands || []),
              ...(cached.recommendations || []),
            ]
              .filter(c => c._added_now && c.command_uuid)
              .map(c => ({
                command_uuid: c.command_uuid,
                command_type: c.command_type,
                display: (c.display || '').slice(0, 80),
              }));
            logEvent('CACHE_LOADED', { hasNote: !!cached.note, commandCount: (cached.commands || []).length });
            return;
          }
          // Cache without note — restore ad-hoc commands and mode.
          if (cached.commands && cached.commands.length > 0) {
            setCommands(cached.commands);
            logEvent('CACHE_LOADED', { hasNote: false, commandCount: cached.commands.length });
          }
        }
      } catch (err) {
        // Cache miss — start with empty skeleton.
      } finally {
        cacheLoadedRef.current = true;
        // Pull any commands already on the note's command rail (added via
        // the note-body editor, Add Now, etc.) so the Scribe tab reflects
        // them on first paint.
        if (!cancelled) {
          syncNoteCommands();
        }
      }
    }

    loadOrGenerate();
    return () => { cancelled = true; };
  }, [noteId, syncNoteCommands]);

  // Poll progress while generating.
  useEffect(() => {
    if (!generating) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/summary-progress?note_id=${encodeURIComponent(noteId)}`);
        const data = await res.json();
        setProgress(data);
      } catch (err) {
        // Ignore polling errors.
      }
    }, 1500);
    return () => clearInterval(interval);
  }, [generating, noteId]);

  // Auto-save commands to cache (debounced) so ad-hoc items added before generation persist on reload.
  // Skip until cache has loaded to avoid overwriting persisted noteData with null.
  const commandsSaveRef = useRef(null);
  useEffect(() => {
    if (!cacheLoadedRef.current) return;
    if (commandsSaveRef.current) clearTimeout(commandsSaveRef.current);
    commandsSaveRef.current = setTimeout(() => {
      saveSummaryToCache(noteData, commands, approved || inserting, {
        recommendations,
        unmatched_conditions: unmatchedConditions,
        diagnosis_suggestions: diagnosisSuggestions,
        selected_template_name: selectedTemplate?.name || null,
        mode: mode,
      });
    }, 500);
    return () => { if (commandsSaveRef.current) clearTimeout(commandsSaveRef.current); };
  }, [commands, recommendations, selectedTemplate, mode, approved, inserting]);

  // Auto-verify on load when approved with command UUIDs.
  useEffect(() => {
    if (!approved || verificationResult) return;
    const withUuids = [
      ...commands.filter(c => c.command_uuid),
      ...recommendations.filter(c => c.command_uuid),
    ];
    if (withUuids.length === 0) return;
    const attempted = withUuids.map(c => ({
      command_uuid: c.command_uuid,
      command_type: c.command_type,
      display: (c.display || '').slice(0, 80),
    }));
    let cancelled = false;
    async function verify() {
      try {
        const res = await fetch(`${API_BASE}/verify-commands`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note_uuid: noteId, attempted }),
        });
        const data = await res.json();
        if (cancelled) return;
        const failedCount = data.failed?.length || 0;
        setVerificationResult(failedCount > 0
          ? { ok: false, verified: data.verified || [], failed: data.failed }
          : { ok: true, verified: data.verified || [], failed: [] });
      } catch (err) {
        console.error('Auto-verify failed:', err);
      }
    }
    verify();
    return () => { cancelled = true; };
  }, [approved, noteId, commands, recommendations]);

  const handleGenerate = useCallback(async () => {
    logEvent('GENERATE_START');
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/generate-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          note_id: noteId,
          note_uuid: noteId,
          patient_id: patientId,
          patient_context: {
            name: patientName || '',
            birth_date: patientBirthDate || '',
            gender: patientGender || '',
          },
        }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
        logEvent('GENERATE_ERROR', { error: data.error });
      } else {
        const adHocKeys = new Set(['_ad_hoc', '_objective_ad_hoc', '_history_ad_hoc', '_subjective_ad_hoc', '_charges_ad_hoc']);
        const existingAdHoc = commands.filter(c => adHocKeys.has(c.section_key));
        const generated = data.commands || [];
        const generatedTypes = new Set(generated.map(c => c.command_type));
        const templateKeep = commands.filter(c =>
          c._template_inserted && !adHocKeys.has(c.section_key) && !generatedTypes.has(c.command_type)
        );
        const newCommands = [...generated, ...existingAdHoc, ...templateKeep];
        const newRecs = data.recommendations || [];
        setNoteData(data.note);
        setCommands(newCommands);
        setRecommendations(newRecs);
        setSectionConditions(data.section_conditions || {});
        setUnmatchedConditions(data.unmatched_conditions || []);
        setDiagnosisSuggestions(data.diagnosis_suggestions || {});
        // Save to cache immediately so a refresh doesn't lose the generated note.
        saveSummaryToCache(data.note, newCommands, false, {
          recommendations: newRecs,
          unmatched_conditions: data.unmatched_conditions || [],
          diagnosis_suggestions: data.diagnosis_suggestions || {},
          selected_template_name: selectedTemplate?.name || null,
          mode: mode,
        });
        logEvent('GENERATE_COMPLETE', { commandCount: (data.commands || []).length, recCount: (data.recommendations || []).length });
      }
    } catch (err) {
      setError('Failed to generate summary');
      logEvent('GENERATE_ERROR', { error: err.message });
    } finally {
      setGenerating(false);
    }
  }, [noteId, selectedTemplate, commands, mode]);

  // Fetch assignees for task assignment (independent, small).
  useEffect(() => {
    if (initialData) return;
    let cancelled = false;
    async function fetchAssignees() {
      try {
        const res = await fetch(`${API_BASE}/assignees`, { cache: 'no-store' });
        if (cancelled) return;
        const data = await res.json();
        if (data.assignees) setAssignees(data.assignees);
      } catch (err) {
        console.error('Failed to fetch assignees:', err);
      }
    }
    fetchAssignees();
    return () => { cancelled = true; };
  }, []);

  // Load visit templates on mount — skip if initial data was provided server-side.
  useEffect(() => {
    if (initialData) return;
    let cancelled = false;
    async function loadTemplates() {
      try {
        const res = await fetch(`${API_BASE}/visit-templates`);
        const data = await res.json();
        if (!cancelled && data.templates) setTemplates(data.templates);
      } catch (err) {
        console.error('Failed to load visit templates:', err);
      }
    }
    loadTemplates();
    return () => { cancelled = true; };
  }, []);

  // Restore selected template from cache once templates are loaded.
  useEffect(() => {
    if (cachedTemplateName && templates.length > 0 && !selectedTemplate) {
      const match = templates.find(t => t.name === cachedTemplateName);
      if (match) setSelectedTemplate(match);
    }
  }, [cachedTemplateName, templates, selectedTemplate]);

  // Auto-generate summary after recording finishes.
  const prevFinalizedRef = useRef(false);
  useEffect(() => {
    if (recording.finalized && !prevFinalizedRef.current) {
      // Collapse transcript once recording is done.
      setTranscriptCollapsed(true);
      // Only auto-generate if cache has loaded (prevents regeneration on reload when
      // noteData hasn't been restored yet from cache).
      if (cacheLoadedRef.current && mode === 'ai' && !noteData && !generating) {
        handleGenerate();
      }
    }
    prevFinalizedRef.current = recording.finalized;
  }, [recording.finalized, mode, noteData, generating, handleGenerate]);

  // Warn before navigating away during recording or insertion.
  const activeRecording = recording.status === 'recording';
  useEffect(() => {
    if (!inserting && !activeRecording) return;
    const handler = (e) => { e.preventDefault(); };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [inserting, activeRecording]);

  // Set mode to 'ai' if we load a finalized transcript from cache (returning to a previous session).
  useEffect(() => {
    if (recording.finalized && mode === null && !noteData && !approved) {
      setMode('ai');
    }
  }, [recording.finalized, mode, noteData, approved]);


  const handleSelectTemplate = useCallback((e) => {
    if (!canEdit) return;
    const templateName = e.target.value;
    if (!templateName) {
      logEvent('DESELECT_TEMPLATE');
      setSelectedTemplate(null);
      setCommands(prev => prev.filter(c => !c._template_inserted));
      saveSummaryToCache(noteData, commands, approved, {
        recommendations, unmatched_conditions: unmatchedConditions,
        diagnosis_suggestions: diagnosisSuggestions, selected_template_name: null,
      });
      return;
    }
    logEvent('SELECT_TEMPLATE', { name: templateName });
    const tmpl = templates.find(t => t.name === templateName);
    if (!tmpl) return;
    setSelectedTemplate(tmpl);

    // Build questionnaire commands from the resolved template data.
    const qCommands = tmpl.questionnaires.map(q => ({
      command_type: 'questionnaire',
      display: q.questionnaire_name,
      data: {
        questionnaire_dbid: q.questionnaire_dbid,
        questionnaire_name: q.questionnaire_name,
        is_scored: !!q.is_scored,
        scoring_function_name: q.scoring_function_name || '',
        questions: q.questions.map(question => ({
          dbid: question.dbid,
          label: question.label,
          type: question.type,
          responses: question.options.map(o => ({
            dbid: o.dbid,
            value: (question.type === 'TXT' || question.type === 'INT') ? '' : o.value,
            code: o.code || '',
            score_value: o.score_value || '',
            selected: false,
            comment: null,
          })),
        })),
      },
      selected: true,
      section_key: '_subjective_ad_hoc',
      already_documented: false,
      _template_inserted: true,
    }));

    const templateCommands = [...qCommands];

    if (tmpl.ros_sections && tmpl.ros_sections.length > 0) {
      templateCommands.push({
        command_type: 'ros',
        display: tmpl.ros_sections.map(s => s.title).join(' | '),
        data: { sections: tmpl.ros_sections },
        selected: true,
        section_key: '_ros',
        already_documented: false,
        _template_inserted: true,
      });
    }

    if (tmpl.pe_sections && tmpl.pe_sections.length > 0) {
      templateCommands.push({
        command_type: 'physical_exam',
        display: tmpl.pe_sections.map(s => s.title).join(' | '),
        data: { sections: tmpl.pe_sections },
        selected: true,
        section_key: 'physical_exam',
        already_documented: false,
        _template_inserted: true,
      });
    }

    // Replace previous template commands, keep everything else.
    setCommands(prev => {
      const nonTemplate = prev.filter(c => !c._template_inserted);
      const updated = [...nonTemplate, ...templateCommands];
      saveSummaryToCache(noteData, updated, approved, {
        recommendations, unmatched_conditions: unmatchedConditions,
        diagnosis_suggestions: diagnosisSuggestions, selected_template_name: tmpl.name,
      });
      return updated;
    });
  }, [templates, noteData, approved, canEdit, recommendations, unmatchedConditions, diagnosisSuggestions, saveSummaryToCache]);

  const handleStartAI = useCallback(async () => {
    if (!canEdit) return;
    logEvent('START_AI');
    setMode('ai');
    const ok = await recording.startRecording();
    if (!ok) {
      logEvent('START_AI_FAILED');
      setMode(null);
    }
  }, [recording, canEdit]);

  const handleStartManual = useCallback(() => {
    if (!canEdit) return;
    logEvent('START_MANUAL');
    setMode('manual');
    // Pre-populate empty commands for all narrative sections so they render as editable text areas.
    const manualCommands = [
      { command_type: 'rfv', display: '', data: { comment: '' }, selected: true, section_key: 'chief_complaint', already_documented: false },
      { command_type: 'hpi', display: '', data: { narrative: '' }, selected: true, section_key: 'history_of_present_illness', already_documented: false },
      // Vitals is intentionally NOT pre-populated: an empty vitals card auto-opens its editor and blocks
      // commit until saved/cancelled (KOALA-5802). It's added on demand via the "+ Vitals" button instead.
      // Plan is intentionally NOT pre-populated either: providers add it on demand via the "+ Plan" button
      // so Assessment & Plan starts empty rather than showing a blank Plan card.
    ];
    // Add PE from template if available.
    if (selectedTemplate?.pe_sections?.length > 0) {
      const peSections = selectedTemplate.pe_sections.map(s => ({ key: s.key, title: s.title, text: s.text, updated: false, template_text: s.text }));
      const peDisplay = peSections.map(s => s.title).join(' | ');
      manualCommands.push({ command_type: 'physical_exam', display: peDisplay, data: { sections: peSections }, selected: true, section_key: 'physical_exam', already_documented: false });
    }
    setCommands(prev => {
      // Keep any existing ad-hoc commands and template-inserted commands (ROS, PE, questionnaires).
      const adHocKeys = new Set(['_ad_hoc', '_objective_ad_hoc', '_history_ad_hoc', '_subjective_ad_hoc', '_charges_ad_hoc']);
      const existing = prev.filter(c => {
        if (c._template_inserted && c.command_type === 'physical_exam') return false;
        return adHocKeys.has(c.section_key) || c._template_inserted;
      });
      return [...manualCommands, ...existing];
    });
  }, [selectedTemplate, canEdit]);


  // Compute unmatched conditions when loading from old cache format (no unmatched_conditions key).
  useEffect(() => {
    // Only run for cache loads where we have commands + sectionConditions but no unmatched_conditions.
    if (!noteData || !commands.length || unmatchedConditions.length > 0) return;
    if (!sectionConditions || !Object.keys(sectionConditions).length) return;
    const hasDiagnose = commands.some(c => c.command_type === 'diagnose');
    const hasPlan = commands.some(c =>
      c.command_type === 'plan' && ['assessment_and_plan', 'plan'].includes(c.section_key)
    );
    if (!hasDiagnose || hasPlan) return;

    const codes = sectionConditions['assessment_and_plan'] || sectionConditions['plan'] || [];
    if (!codes.length) return;
    const matchedSet = new Set();
    commands.filter(c => c.command_type === 'diagnose').forEach(c => {
      const m = matchCondition(c.data.condition_header || '', codes);
      if (m) matchedSet.add(m);
    });
    setUnmatchedConditions(codes.filter(c => !matchedSet.has(c)));
  }, [sectionConditions, commands, noteData, unmatchedConditions]);


  // Carry forward the most recent prior Physical Exam / Review of Systems the
  // provider documented in Scribe (last note they were the provider on).
  // Returns an array of {key,title,text} sections, or [] when none is found.
  const handleCarryForwardExam = useCallback(async (kind) => {
    try {
      const res = await fetch(`${API_BASE}/last-exam?note_id=${encodeURIComponent(noteId)}&kind=${encodeURIComponent(kind)}`);
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data.sections) ? data.sections : [];
    } catch (e) {
      console.error('carry-forward exam failed:', e);
      return [];
    }
  }, [noteId]);

  const handleEdit = useCallback((index, newData, newType) => {
    logEvent('EDIT_COMMAND', { index, commandType: newType || commands[index]?.command_type, sectionKey: commands[index]?.section_key, data: newData });
    if (!canEdit) return;
    // KOALA-5485: during amendment, edits to already-documented commands in
    // EDITABLE_AMEND_SECTIONS are routed through /edit-existing-commands on
    // Save changes. Tag the row so handleInsert can split it out from the
    // normal insertable filter.
    //
    // The tag is applied UNIFORMLY at the bottom of the per-command branch
    // (single tag point) so every command_type participates in the amend
    // split. The gate `isAmendingSectionEditable` is the authoritative
    // eligibility filter: it checks `wasFinalized && !approved` (we're
    // amending), `command_uuid` presence (Scribe-inserted, not freshly
    // ad-hoc), section_key allowlist, and command_type denylist. Orders
    // (prescribe, refill, adjust_prescription, refer, imaging_order,
    // lab_order), questionnaire, and freshly-added ad-hoc rows are correctly
    // excluded by the gate, not by per-branch tag omission.
    const isAmendEdit = (cmd) => isAmendingSectionEditable(cmd, wasFinalized && !approved);
    setCommands(prev => {
      const updated = prev.map((cmd, i) => {
        if (i !== index) return cmd;
        const type = newType || cmd.command_type;
        let next;
        if (type === 'history_review' || type === 'chart_review' || type === 'ros' || type === 'physical_exam') {
          const display = (newData.sections || []).map(s => s.title).join(' | ');
          next = { ...cmd, data: newData, display };
        } else if (type === 'vitals') {
          const vParts = [];
          const sys = newData.blood_pressure_systole;
          const dia = newData.blood_pressure_diastole;
          if (sys != null && dia != null) vParts.push(`BP ${sys}/${dia} mmHg`);
          if (newData.pulse != null) vParts.push(`HR ${newData.pulse} bpm`);
          if (newData.respiration_rate != null) vParts.push(`RR ${newData.respiration_rate} /min`);
          if (newData.oxygen_saturation != null) vParts.push(`SpO2 ${newData.oxygen_saturation}%`);
          if (newData.body_temperature != null) vParts.push(`Temp ${newData.body_temperature} °F`);
          if (newData.height != null) vParts.push(`Height ${newData.height} in`);
          if (newData.weight_lbs != null) vParts.push(`Weight ${newData.weight_lbs} lbs`);
          if (newData.blood_pressure_position_and_site != null) {
            const siteLabels = {
              0: 'Sitting, Right Upper Arm', 1: 'Sitting, Left Upper Arm',
              2: 'Sitting, Right Lower Arm', 3: 'Sitting, Left Lower Arm',
              4: 'Standing, Right Upper Arm', 5: 'Standing, Left Upper Arm',
              6: 'Standing, Right Lower Arm', 7: 'Standing, Left Lower Arm',
              8: 'Supine, Right Upper Arm', 9: 'Supine, Left Upper Arm',
              10: 'Supine, Right Lower Arm', 11: 'Supine, Left Lower Arm',
            };
            const label = siteLabels[newData.blood_pressure_position_and_site];
            if (label) vParts.push(`Site: ${label}`);
          }
          if (newData.note) vParts.push(`Note: ${newData.note}`);
          next = { ...cmd, data: newData, display: vParts.join(', ') || 'Vitals' };
        } else if (type === 'medication_statement') {
          next = { ...cmd, data: newData, display: newData.medication_text || '' };
        } else if (type === 'allergy') {
          next = { ...cmd, data: newData, display: newData.allergy_text || '' };
        } else if (type === 'task') {
          const parts = [newData.title || ''];
          if (newData.comment) parts.push(`Comment: ${newData.comment}`);
          next = { ...cmd, data: newData, display: parts.join(' \u2014 ') };
        } else if (type === 'prescribe' || type === 'refill' || type === 'adjust_prescription') {
          next = { ...cmd, command_type: type, data: newData, display: newData.medication_text || '' };
        } else if (type === 'lab_order') {
          const parts = [];
          if (newData.lab_partner_name) parts.push(newData.lab_partner_name);
          if (newData.test_names && newData.test_names.length) parts.push(newData.test_names.join(', '));
          if (newData.comment) parts.push(newData.comment);
          if (newData.fasting_required) parts.push('Fasting');
          next = { ...cmd, command_type: type, data: newData, display: parts.join(' | ') || '' };
        } else if (type === 'imaging_order') {
          const parts = [newData.image_display, newData.additional_details, newData.comment, newData.priority].filter(Boolean);
          next = { ...cmd, command_type: type, data: newData, display: parts.join(' | ') };
        } else if (type === 'refer') {
          // Headline is the specialty only (refer_to_display); clinical_question /
          // priority show on the detail line, not the collapsed headline.
          next = { ...cmd, command_type: type, data: newData, display: newData.refer_to_display || 'Referral' };
        } else if (type === 'familyHistory') {
          const parts = [newData.condition_display, newData.relative, newData.note].filter(Boolean);
          next = { ...cmd, command_type: type, data: newData, display: parts.join(' — ') || '' };
        } else if (type === 'medicalHistory') {
          const parts = [newData.past_medical_history];
          const dates = [newData.approximate_start_date, newData.approximate_end_date].filter(Boolean);
          if (dates.length) parts.push(dates.join(' – '));
          if (newData.comments) parts.push(newData.comments);
          next = { ...cmd, command_type: type, data: newData, display: parts.filter(Boolean).join(' — ') || '' };
        } else if (type === 'surgicalHistory') {
          const parts = [newData.procedure_display];
          if (newData.approximate_date) parts.push(newData.approximate_date);
          if (newData.comment) parts.push(newData.comment);
          next = { ...cmd, command_type: type, data: newData, display: parts.filter(Boolean).join(' — ') || '' };
        } else if (type === 'questionnaire') {
          next = { ...cmd, command_type: type, data: newData, display: newData.questionnaire_name || '' };
        } else if (type === 'perform') {
          const display = newData.cpt_code ? `${newData.cpt_code} — ${newData.description || ''}` : '';
          next = { ...cmd, command_type: type, data: newData, display };
        } else if (type === 'stop_medication') {
          next = { ...cmd, command_type: type, data: newData, display: newData.medication_name || '' };
        } else if (type === 'remove_allergy') {
          next = { ...cmd, command_type: type, data: newData, display: newData.allergy_name || '' };
        } else if (type === 'resolve_condition') {
          next = { ...cmd, command_type: type, data: newData, display: newData.condition_name || '' };
        } else if (type === 'diagnose') {
          const display = newData.icd10_display || newData.condition_header || cmd.display;
          const accepted = newData.icd10_code ? (newData.accepted !== undefined ? newData.accepted : true) : false;
          const rejected = newData.rejected || false;
          next = { ...cmd, command_type: type, data: { ...newData, accepted, rejected }, display };
        } else if (type === 'assess') {
          next = { ...cmd, data: newData };
        } else {
          // Default path: rfv (chief_complaint), hpi (history_of_present_illness),
          // lab_results, imaging_results, plan, and any other narrative-shaped
          // command. rfv uses the `comment` field; everything else uses
          // `narrative`. Any of these can be amended during the amendment flow.
          const field = cmd.command_type === 'rfv' ? 'comment' : 'narrative';
          const text = newData[field] || '';
          next = { ...cmd, data: newData, display: text };
        }
        // Single tag point (KOALA-5485 silent no-op fix). The gate
        // `isAmendEdit` filters by section_key allowlist + command_type
        // denylist + command_uuid presence + amending mode. Without this,
        // edits to vitals/allergy/task/familyHistory/medicalHistory/
        // surgicalHistory/diagnose/assess/perform/stop_medication/
        // remove_allergy/resolve_condition were silently dropped at
        // handleInsert because `_amend_edited` was never set on those
        // branches.
        return isAmendEdit(cmd) ? { ...next, _amend_edited: true } : next;
      });
      saveSummaryToCache(noteData, updated, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions });
      return updated;
    });
  }, [canEdit, wasFinalized, approved, noteData, saveSummaryToCache, recommendations, unmatchedConditions, diagnosisSuggestions]);

  const handleDelete = useCallback((index) => {
    logEvent('DELETE_COMMAND', { index, commandType: commands[index]?.command_type });
    if (!canEdit) return;
    setCommands(prev => {
      const updated = prev.filter((_, i) => i !== index);
      saveSummaryToCache(noteData, updated, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions });
      return updated;
    });
  }, [canEdit, noteData, saveSummaryToCache, recommendations, unmatchedConditions, diagnosisSuggestions]);

  const handleAddTask = useCallback(() => {
    logEvent('ADD_TASK');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'task',
      display: '',
      data: { title: '', due_date: null, assign_to: null, labels: [] },
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddOrder = useCallback(() => {
    logEvent('ADD_ORDER');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'prescribe',
      display: '',
      data: {},
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddPlan = useCallback(() => {
    logEvent('ADD_PLAN');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'plan',
      display: '',
      data: { narrative: '' },
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddHistory = useCallback((commandType) => {
    logEvent('ADD_HISTORY', { type: commandType });
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: commandType,
      display: '',
      data: {},
      selected: true,
      section_key: '_history_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddMedication = useCallback(() => {
    logEvent('ADD_MEDICATION');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'medication_statement',
      display: '',
      data: { medication_text: '', fdb_code: null, sig: '' },
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddVitals = useCallback(() => {
    logEvent('ADD_VITALS');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'vitals',
      display: '',
      data: {},
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleEditRecommendation = useCallback((index, newData, newType) => {
    if (!canEdit) return;
    logEvent('EDIT_REC', { index, commandType: newType, data: newData });
    setRecommendations(prev => prev.map((cmd, i) => {
      if (i !== index) return cmd;
      const type = newType || cmd.command_type;
      if (type === 'medication_statement') {
        return { ...cmd, data: newData, display: newData.medication_text || '', accepted: true };
      }
      if (type === 'allergy') {
        return { ...cmd, data: newData, display: newData.allergy_text || '', accepted: true };
      }
      if (type === 'prescribe' || type === 'refill' || type === 'adjust_prescription') {
        return { ...cmd, command_type: type, data: newData, display: newData.medication_text || '', accepted: true };
      }
      if (type === 'refer') {
        return { ...cmd, command_type: type, data: newData, display: newData.refer_to_display || 'Referral', accepted: true };
      }
      return { ...cmd, data: newData, accepted: true };
    }));
  }, [canEdit]);

  const handleAcceptRecommendation = useCallback((index) => {
    if (!canEdit) return;
    logEvent('ACCEPT_REC', { index });
    setRecommendations(prev => prev.map((cmd, i) =>
      i === index ? { ...cmd, accepted: true, rejected: false } : cmd
    ));
  }, [canEdit]);

  const handleRejectRecommendation = useCallback((index) => {
    if (!canEdit) return;
    logEvent('REJECT_REC', { index });
    setRecommendations(prev => prev.map((cmd, i) =>
      i === index ? { ...cmd, rejected: true, accepted: false } : cmd
    ));
  }, [canEdit]);

  const handleDeleteRecommendation = useCallback((index) => {
    if (!canEdit) return;
    logEvent('DELETE_REC', { index });
    setRecommendations(prev => prev.filter((_, i) => i !== index));
  }, [canEdit]);

  const handleEditingChange = useCallback((key, isEditing) => {
    setEditingFields(prev => {
      const next = new Set(prev);
      if (isEditing) next.add(key);
      else next.delete(key);
      return next;
    });
  }, []);

  const handleAddAllergy = useCallback(() => {
    logEvent('ADD_ALLERGY');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'allergy',
      display: '',
      data: { allergy_text: '', concept_id: null, concept_id_type: null, reaction: '', severity: null },
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddStopMedication = useCallback(() => {
    logEvent('ADD_STOP_MED');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'stop_medication',
      display: '',
      data: { medication_id: null, medication_name: '', rationale: '' },
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddRemoveAllergy = useCallback(() => {
    logEvent('ADD_REMOVE_ALLERGY');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'remove_allergy',
      display: '',
      data: { allergy_id: null, allergy_name: '', narrative: '' },
      selected: true,
      section_key: '_objective_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddResolveCondition = useCallback(() => {
    logEvent('ADD_RESOLVE_CONDITION');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'resolve_condition',
      display: '',
      data: { condition_id: null, condition_name: '', rationale: '' },
      selected: true,
      section_key: '_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddQuestionnaire = useCallback(() => {
    logEvent('ADD_QUESTIONNAIRE');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'questionnaire',
      display: '',
      data: { questionnaire_dbid: null, questionnaire_name: '', questions: [] },
      selected: true,
      section_key: '_subjective_ad_hoc',
      already_documented: false,
    }]);
  }, [canEdit]);

  const handleAddCharge = useCallback(() => {
    logEvent('ADD_CHARGE');
    if (!canEdit) return;
    setCommands(prev => [...prev, {
      command_type: 'perform',
      display: '',
      data: { cpt_code: null, description: '', notes: '', _modifiers: [], _pointers: [] },
      selected: true,
      section_key: '_charges_ad_hoc',
      already_documented: false,
      _localId: crypto.randomUUID(),
    }]);
  }, [canEdit]);

  // CPT/HCPCS search for the matrix "+" add-charge picker. Backed by the
  // /search-charges endpoint (ChargeDescriptionMaster). Returns the raw
  // results array ([{cpt_code, short_name, full_name}]).
  const searchCharges = useCallback(async (query) => {
    try {
      const res = await fetch(`${API_BASE}/search-charges?query=${encodeURIComponent(query)}`);
      if (!res.ok) return [];
      const data = await res.json().catch(() => ({}));
      return data.results || [];
    } catch (_err) {
      return [];
    }
  }, []);

  const handleAddTemplateCharge = useCallback((cptCode, description) => {
    logEvent('ADD_TEMPLATE_CHARGE', { cptCode, description });
    if (!canEdit) return;
    setCommands(prev => {
      // Re-select if already exists but deselected. KOALA-5485: if this was
      // an amend-mode delete that the user just toggled back on, also clear
      // the `_amend_deleted` tag so handleInsert does NOT POST a delete for
      // it. The user changed their mind - no chart state change required.
      // Optional chaining is required: perform commands synced from /note-commands
      // (charges added via the chart command-rail outside Scribe) land in commands[]
      // with NO `data` key, so `c.data.cpt_code` would throw a TypeError inside this
      // reducer and silently kill the add. `undefined?.cpt_code` is falsy → skipped.
      const existing = prev.find(c => c.command_type === 'perform' && c.data?.cpt_code === cptCode);
      if (existing) {
        return prev.map(c => {
          if (c.command_type === 'perform' && c.data?.cpt_code === cptCode) {
            const { _amend_deleted, ...rest } = c;
            return { ...rest, selected: true };
          }
          return c;
        });
      }
      return [...prev, {
        command_type: 'perform',
        display: `${cptCode} — ${description}`,
        data: { cpt_code: cptCode, description, notes: '', _modifiers: [], _pointers: [] },
        selected: true,
        section_key: '_charges_ad_hoc',
        already_documented: false,
        _localId: crypto.randomUUID(),
      }];
    });
  }, [canEdit]);

  const handleRemoveChargeByCpt = useCallback((cptCode) => {
    logEvent('REMOVE_CHARGE', { cptCode });
    if (!canEdit) return;
    // KOALA-5485: in amend mode, unchecking an already-documented charge must
    // also set `_amend_deleted: true` so handleInsert POSTs a delete to mark
    // the chart row entered-in-error. The `_amend_deleted` tag is gated by
    // `isAmendingSectionEditable` (same eligibility filter as edit) so
    // freshly-added ad-hoc charges (no command_uuid) and non-amend toggles
    // continue to behave as before - just `selected: false`.
    //
    // Without this tag the uncheck silently no-ops: handleInsert's insertable
    // filter drops the deselected command, but because no edit happened the
    // `_amend_edited` tag is never set either, so the existing amend POST
    // also drops it. Chart stays committed.
    const amending = wasFinalized && !approved;
    setCommands(prev => prev.map(c => {
      // Optional chaining: synced from_the_note perform commands have no `data` key
      // (see handleAddTemplateCharge); `c.data.cpt_code` would throw here otherwise.
      if (c.command_type !== 'perform' || c.data?.cpt_code !== cptCode) return c;
      if (c.already_documented && isAmendingSectionEditable(c, amending)) {
        return { ...c, selected: false, _amend_deleted: true };
      }
      return { ...c, selected: false };
    }));
  }, [canEdit, wasFinalized, approved]);

  const handleAddCondition = useCallback((icd10Code, icd10Display, conditionId) => {
    logEvent('ADD_CONDITION', { icd10Code, display: icd10Display });
    if (!canEdit) return;
    const apKey = commands.find(c =>
      (c.command_type === 'diagnose' || c.command_type === 'assess') && ['assessment_and_plan', 'plan'].includes(c.section_key)
    )?.section_key || 'assessment_and_plan';

    const newCmd = conditionId
      ? {
          command_type: 'assess',
          display: icd10Display || '',
          data: {
            condition_id: conditionId,
            icd10_code: icd10Code || null,
            narrative: '',
            background: null,
            status: null,
            accepted: !!icd10Code,
          },
          section_key: apKey,
          already_documented: false,
        }
      : {
          command_type: 'diagnose',
          display: icd10Display || '',
          data: {
            icd10_code: icd10Code || null,
            icd10_display: icd10Display || '',
            condition_header: icd10Display || '',
            today_assessment: '',
            accepted: !!icd10Code,
          },
          selected: true,
          section_key: apKey,
          already_documented: false,
        };

    setCommands(prev => {
      const lastApIdx = prev.reduce((acc, c, i) =>
        (c.command_type === 'diagnose' || c.command_type === 'assess') && ['assessment_and_plan', 'plan'].includes(c.section_key) ? i : acc, -1);
      return lastApIdx === -1 ? [...prev, newCmd] : [...prev.slice(0, lastApIdx + 1), newCmd, ...prev.slice(lastApIdx + 1)];
    });

    if (icd10Code) {
      setUnmatchedConditions(prev => prev.filter(c => !(c.coding || []).some(cd => cd.code === icd10Code)));
    }

    // Carry-forward the background from the most recent prior signed assessment
    // for the same (patient, condition). Non-blocking: the user can start
    // typing immediately; the fetch may race. If it lands AFTER the user has
    // typed something, we MUST NOT overwrite their input — guard with
    // ``!c.data.background``. The /insert-commands belt is a safety net for
    // approval, but this fetch is what makes the carry-forward visible in the
    // assess edit drawer BEFORE the provider approves.
    if (conditionId) {
      fetch(`${API_BASE}/carry-forward-background`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_uuid: noteId, condition_id: conditionId }),
      })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (!data || !data.background) return;
          setCommands(prev => prev.map(c =>
            c.command_type === 'assess' && c.data.condition_id === conditionId && !c.data.background
              ? { ...c, data: { ...c.data, background: data.background } }
              : c
          ));
        })
        .catch(err => console.error('Carry-forward background fetch failed:', err));
    }
  }, [canEdit, commands, noteId]);

  const handleInsert = useCallback(async () => {
    if (!canEdit || inserting) return;
    setValidationError(null);
    setChargeErrors([]);
    logEvent('APPROVE_START', { totalCommands: commands.length, commandTypes: commands.map(c => c.command_type) });
    setInserting(true);

    // KOALA-5485: cache flip to approved=true is delayed until AFTER amend
    // success (amend branch ~1290) AND/OR AFTER /insert-commands success
    // (cache write ~1450, runs UNCONDITIONALLY on success - see
    // CACHE_FLIP_UNCONDITIONAL_ON_APPROVE_SUCCESS).
    // Two cache-flip landing points cover the relevant paths:
    //   (a) Amend-only path: amend branch writes approved=true after
    //       /edit-existing-commands success and BEFORE /insert-commands. If
    //       /insert-commands later fails, the catch block rolls cache back to
    //       approved=false (so /save-summary holds the latest user-facing state).
    //   (b) Fresh-approve or amend+insert success: the success branch writes
    //       approved=true unconditionally. The unconditional write covers the
    //       amend-mode-with-zero-edits edge case (no `data.attempted` entries
    //       to gate on) and the empty-note approval crash-recovery case.
    // If a browser crash happens before either landing point, the cache stays
    // approved=false and the next page load shows pre-amend state - far safer
    // than a phantom-approved-but-lost-edit state.
    // (Original eager flip used to live here pre-amend; removed for KOALA-5485.)

    // KOALA-5485: Amend edits go through /edit-existing-commands FIRST so the
    // uuid map is available before the verify step. The frontend re-stamps
    // ScribeSummary.commands with the new uuids returned by the backend.
    //
    // Critical ordering: re-stamp happens IMMEDIATELY after amend success,
    // BEFORE the conditions fetch and /insert-commands POST. The amend POST
    // is a hard commit point - once those effects landed in home-app, the
    // plugin's local state MUST reflect it. If /insert-commands later fails,
    // the user can retry it, but they must not re-submit the (now-voided)
    // old uuid as an amend - which is what would happen if we kept the
    // re-stamp inside the /insert-commands success branch.
    const amendEdits = commands.filter(c => c._amend_edited && c.command_uuid);
    // KOALA-5485 charge-delete regression: unchecking an already-documented
    // perform command sets `_amend_deleted` (see handleRemoveChargeByCpt).
    // Send these to /delete-existing-commands BEFORE the edit POST so that:
    //  - The delete is a hard commit point of its own (EIE landed in home-app).
    //  - The frontend removes them from `workingCommands` so /insert-commands
    //    never sees them and /edit-existing-commands never tries to edit
    //    them either (they should not have `_amend_edited` set; the gate is
    //    structural - delete vs edit are mutually exclusive gestures).
    const amendDeletes = commands.filter(c => c._amend_deleted && c.command_uuid && c.already_documented);
    let amendUuidRemap = new Map(); // old_uuid -> new_uuid
    let amendAttempted = [];
    // The commands array we work with from here on. We mutate this in-place
    // (via reassign) to reflect amend success even if /insert-commands fails.
    let workingCommands = commands;
    if (amendDeletes.length > 0) {
      const deletePayload = amendDeletes.map(({ _template_inserted, _amend_edited, _amend_deleted, ...rest }) => rest);
      logEvent('AMEND_DELETE_SENDING', { count: deletePayload.length, sectionKeys: deletePayload.map(c => c.section_key) });
      try {
        const delRes = await fetch(`${API_BASE}/delete-existing-commands`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note_uuid: noteId, commands: deletePayload }),
        });
        const delData = await delRes.json();
        if (delData.error) {
          if (delData.validation_errors) {
            setValidationError(delData.validation_errors);
          } else if (delData.conflicts) {
            setError(`${delData.error}. Reload the page to see the latest state.`);
          } else {
            setError(delData.error);
          }
          setApproved(false);
          setConfirming(false);
          // `workingCommands` is still identical to `commands` here (no
          // hard-commit has run yet), but use it for consistency with every
          // other cache write in this callback so a future reorder can't
          // reintroduce the stale-`commands` cache bug.
          saveSummaryToCache(noteData, workingCommands, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });
          setInserting(false);
          logEvent('AMEND_DELETE_ERROR', { error: delData.error, conflicts: delData.conflicts || null });
          return;
        }
        logEvent('AMEND_DELETE_COMPLETE', { count: (delData.attempted || []).length });
        // Hard commit point: the deleted commands' chart rows are now
        // entered_in_error. Filter them out of workingCommands so they
        // don't appear in subsequent POSTs (edit, insert) or in the
        // cache write. The next page load will not see them in cache;
        // home-app already considers them voided.
        const deletedUuids = new Set(amendDeletes.map(c => c.command_uuid));
        workingCommands = commands.filter(c => !(c.command_uuid && deletedUuids.has(c.command_uuid)));
        setCommands(workingCommands);
        saveSummaryToCache(noteData, workingCommands, true, {
          recommendations, unmatched_conditions: unmatchedConditions,
          diagnosis_suggestions: diagnosisSuggestions,
          selected_template_name: selectedTemplate?.name || null, mode,
        });
        // Early charge-BLI removal. Entering a perform command in error does NOT
        // void its BillingLineItem (BLIs carry command_id=null, so home-app can't
        // auto-void them), so a just-deleted charge leaves an orphan ACTIVE BLI.
        // Remove those orphans NOW — after the EIE hard-commit, before any clone
        // is inserted — while each CPT still resolves to exactly one ACTIVE BLI,
        // so enrich's CPT fallback captures the correct BLI id. Without this, a
        // comment edit's re-entered clone would create a second same-CPT BLI and
        // wedge the final enrich (ambiguous-CPT → billing_line_item_not_found).
        // Best-effort: the final enrich retries removed_charges as a backstop, so
        // a failure here never blocks signing.
        const earlyRemovedChargeUuids = amendDeletes
          .filter(c => c.command_type === 'perform' && c.command_uuid)
          .map(c => c.command_uuid);
        if (earlyRemovedChargeUuids.length) {
          try {
            await fetch(`${API_BASE}/enrich-charges`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ note_uuid: noteId, charges: [], removed_charges: earlyRemovedChargeUuids }),
            });
          } catch (earlyErr) {
            console.warn('early charge-BLI removal failed (final enrich retries):', earlyErr);
          }
        }
      } catch (err) {
        console.error('Amend deletes failed:', err);
        setError('Failed to apply amendment deletes');
        setApproved(false);
        setConfirming(false);
        setInserting(false);
        logEvent('AMEND_DELETE_ERROR', { error: 'network' });
        return;
      }
    }
    if (amendEdits.length > 0) {
      const amendPayload = amendEdits.map(({ _template_inserted, _amend_edited, ...rest }) => rest);
      logEvent('AMEND_EDIT_SENDING', { count: amendPayload.length, sectionKeys: amendPayload.map(c => c.section_key) });
      try {
        // KOALA-5687: guard the EIE→re-stamp window. While this is set,
        // syncNoteCommands bails instead of dropping the (about-to-be-voided)
        // local rows and re-bucketing the re-originated rows into ADDITIONAL
        // COMMANDS. Cleared on every exit path of this block.
        amendEditInFlightRef.current = true;
        const editRes = await fetch(`${API_BASE}/edit-existing-commands`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note_uuid: noteId, commands: amendPayload }),
        });
        const editData = await editRes.json();
        if (editData.error) {
          // Backend rejected before any effects were emitted. Pass the
          // conflict shape through if present so the user can reload a
          // stale tab; otherwise show the generic error.
          if (editData.validation_errors) {
            setValidationError(editData.validation_errors);
          } else if (editData.conflicts) {
            setError(`${editData.error}. Reload the page to see the latest state.`);
          } else {
            setError(editData.error);
          }
          setApproved(false);
          setConfirming(false);
          // The edit backend rejected before emitting edit effects, but an
          // amend-delete in the branch above may have already committed
          // server-side. Persist `workingCommands` (deletes filtered out), not
          // the stale closure `commands`, so the cache doesn't resurrect the
          // already-voided deleted commands on reload. Mirrors 1539 / 1692.
          saveSummaryToCache(noteData, workingCommands, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });
          setInserting(false);
          amendEditInFlightRef.current = false;
          logEvent('AMEND_EDIT_ERROR', { error: editData.error, conflicts: editData.conflicts || null });
          return;
        }
        amendAttempted = editData.attempted || [];
        for (const entry of amendAttempted) {
          amendUuidRemap.set(entry.old_command_uuid, entry.new_command_uuid);
        }
        logEvent('AMEND_EDIT_COMPLETE', { count: amendAttempted.length });

        // Hard commit point: re-stamp commands now. After this point the
        // home-app has executed EIE+Originate (and Commit for dedicated-class
        // sections). The local state must mirror that or a retry of
        // /insert-commands will resend the (now-voided) old uuid as an amend.
        //
        // KOALA-5485: map over `workingCommands` (NOT the original `commands`)
        // so that deleted commands (filtered out by the delete branch above)
        // don't re-appear here. Mapping over the original would re-introduce
        // them with their old uuid - and they'd then go through the insertable
        // filter (which drops them on `already_documented` anyway, so no chart
        // damage), but the cache write below would persist them.
        workingCommands = workingCommands.map(cmd => {
          if (cmd._amend_edited && cmd.command_uuid && amendUuidRemap.has(cmd.command_uuid)) {
            const newUuid = amendUuidRemap.get(cmd.command_uuid);
            const { _amend_edited, ...rest } = cmd;
            return { ...rest, command_uuid: newUuid, already_documented: true };
          }
          return cmd;
        });
        setCommands(workingCommands);
        saveSummaryToCache(noteData, workingCommands, true, {
          recommendations, unmatched_conditions: unmatchedConditions,
          diagnosis_suggestions: diagnosisSuggestions,
          selected_template_name: selectedTemplate?.name || null, mode,
        });
        // KOALA-5687: record this session's old→new uuid mappings so a later
        // sync can bridge a stale local uuid to its re-originated row, bump the
        // amend generation so a sync that raced this edit bails, then release
        // the in-flight guard now that local state mirrors the chart.
        for (const [oldUuid, newUuid] of amendUuidRemap) {
          amendUuidRemapRef.current.set(oldUuid, newUuid);
        }
        amendGenRef.current += 1;
        amendEditInFlightRef.current = false;
      } catch (err) {
        console.error('Amend edits failed:', err);
        setError('Failed to apply amendment edits');
        setApproved(false);
        setConfirming(false);
        setInserting(false);
        amendEditInFlightRef.current = false;
        logEvent('AMEND_EDIT_ERROR', { error: 'network' });
        return;
      }
    }

    // KOALA_5634_DIAGNOSE_TO_ASSESS_UPSTREAM_FLIP: convert in place any diagnose row
    // whose ICD-10 code matches an existing patient condition into an assess. Done
    // BEFORE the insertable filter so the local `workingCommands` row already carries
    // command_type='assess' by the time `/insert-commands` is POSTed and stamped.
    // Why upstream-flip (Option A) instead of a post-stamp alias (the old approach):
    // the alias keyed `diagnose:<truncated display>` against `assess:<truncated display>`,
    // which could collide with an unrelated assess row that happened to share the
    // 80-char display. Flipping the local row's command_type means the canonical
    // `${command_type}:${display}` stamping key matches without any alias bookkeeping
    // — and the local Scribe-side representation now matches what's actually on
    // the chart. (KOALA-5634)
    // Recommendations are not flipped here: the recommendations pipeline does not
    // emit diagnose entries (medication_statement / allergy / refer / task /
    // prescribe-via-rec only), so the rec stamp pass has no diagnose→assess
    // mismatch to reconcile.
    try {
      const condRes = await fetch(
        `${API_BASE}/patient-conditions?patient_id=${encodeURIComponent(patientId)}`
      );
      const condData = await condRes.json();
      const codeToMatch = new Map();
      for (const pc of (condData.conditions || [])) {
        codeToMatch.set((pc.code || '').replace('.', '').toUpperCase(), pc);
      }
      workingCommands = workingCommands.map(c => {
        if (c.command_type !== 'diagnose') return c;
        // Only flip rows the provider actually accepted with an ICD - mirrors the
        // downstream `allInsertable` filter that drops unaccepted/no-ICD diagnose
        // rows entirely. Flipping a row without an ICD would create an assess
        // with `condition_id=undefined` which would tank /insert-commands.
        if (!c.data?.icd10_code || !c.data?.accepted) return c;
        const code = (c.data.icd10_code || '').replace('.', '').toUpperCase();
        const match = codeToMatch.get(code);
        if (!match) return c;
        return {
          ...c,
          command_type: 'assess',
          data: {
            condition_id: match.condition_id,
            narrative: c.data.today_assessment || '',
            background: c.data.background || null,
            status: null,
            icd10_code: c.data.icd10_code,
            icd10_display: c.data.icd10_display,
            accepted: c.data.accepted,
          },
        };
      });
    } catch (err) {
      console.error('Failed to fetch patient conditions for assess check:', err);
    }

    const SECTION_TYPES = new Set(['physical_exam', 'ros', 'chart_review', 'history_review']);
    const insertable = workingCommands.filter(c => {
      // Either flag means "already on the note." command_uuid is the
      // authoritative signal (set whenever a command is inserted, whether
      // via full Approve or Add Now). already_documented is the explicit
      // marker. Treat either as exclusionary so pre-existing finalized
      // notes (which have UUIDs but no already_documented flag) don't
      // double-insert on amendment re-Approve.
      // (Amend-edited commands have been re-stamped above with the new
      // uuid + already_documented=true, so they naturally filter out here.)
      if (c.already_documented || c.command_uuid) return false;
      if (!c.display && !(SECTION_TYPES.has(c.command_type) && c.data?.sections?.length > 0)) return false;
      if (c.command_type === 'imaging_order' && (!c.data.image_code || !c.data.service_provider || !c.data.ordering_provider_id || !c.data.diagnosis_codes || c.data.diagnosis_codes.length === 0)) return false;
      // All three Rx command types share the same canvas-core schema and must
      // satisfy the same required-field set; using one predicate keeps the
      // Approve filter, the Add Now gate, and the Save button gate aligned.
      if (isRxCommand(c) && isRxIncomplete(c.data)) return false;
      if (c.command_type === 'lab_order' && (!c.data.lab_partner || !c.data.tests_order_codes || c.data.tests_order_codes.length === 0)) return false;
      if (c.command_type === 'refer' && (!c.data.service_provider || !c.data.clinical_question || !c.data.notes_to_specialist || !c.data.diagnosis_codes || c.data.diagnosis_codes.length === 0)) return false;
      if (c.command_type === 'perform' && (!c.data.cpt_code || c.selected === false)) return false;
      return true;
    });
    // Pre-existing finalized notes (signed before the explicit
    // already_documented stamping shipped) carry command_uuid but not the
    // flag, so treat either as "already on the chart" to match the
    // insertable filter at line 1634 and handleMakeChanges.onNote at line 547.
    // Without this, untouched legacy commands land in `dropped` and trip the
    // halt block below with a misleading "invalid values" error.
    const dropped = workingCommands.filter(c => !(c.already_documented || c.command_uuid) && !insertable.includes(c));
    if (dropped.length > 0) {
      logEvent('COMMANDS_FILTERED', { dropped: dropped.map(c => ({
        type: c.command_type, display: (c.display || '').slice(0, 80), sectionKey: c.section_key,
        reason: !c.display ? 'empty_display' : c.selected === false ? 'deselected' : 'validation',
      })) });
    }
    // The Approve filter for recommendations has to apply the same gates the
    // insertable filter applies for Rx + refer — recommendations bypass the
    // OrderRow editor, so without these checks an LLM payload that the
    // server's validate_rx_payload (or ReferParser.validate) will reject
    // slips into /insert-commands and tanks the whole batch.
    const candidateRecs = recommendations.filter(c => c.accepted && !c.already_documented && c.display);
    const droppedRecs = candidateRecs.filter(c => getAcceptedRecFailureReason(c) !== null);
    const acceptedRecs = candidateRecs.filter(c => getAcceptedRecFailureReason(c) === null);
    // Surface client-side validation drops the same way a server 400 would:
    // setValidationError, revert the optimistic approval, halt. Without this,
    // a saved command with smart punctuation in sig (OrderRow Save has no
    // ASCII screen) is dropped from `insertable` and the rest of the batch
    // POSTs successfully — modal closes, user has no idea the Rx was lost.
    // Filter dropped commands to `validation` reasons (empty_display and
    // deselected are intentional user choices, not silent failures).
    const droppedForValidation = dropped.filter(c => c.display && c.selected !== false);
    const allValidationFailures = [
      ...droppedForValidation.map(c => ({ command: c, reason: _commandValidationReason(c) })),
      ...droppedRecs.map(c => ({ command: c, reason: getAcceptedRecFailureReason(c) })),
    ];
    if (allValidationFailures.length > 0) {
      setValidationError(allValidationFailures.map(({ command, reason }) => ({
        command_type: command.command_type,
        display: (command.display || '').slice(0, 80),
        errors: [_validationErrorMessage(command, reason)],
      })));
      setApproved(false);
      setConfirming(false);
      // Persist `workingCommands` (not the stale closure-captured `commands`):
      // if an amend edit already committed earlier in this click, the home-app
      // has executed EIE+Originate and `workingCommands` carries the re-stamped
      // uuids. Writing `commands` here would revert the cache to pre-amend state
      // and a retry would resend the now-voided uuid as an amend. Mirrors 1762.
      saveSummaryToCache(noteData, workingCommands, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });
      setInserting(false);
      logEvent('APPROVE_ERROR', {
        error: 'client_validation_failed',
        dropped_commands: droppedForValidation.length,
        dropped_recs: droppedRecs.length,
      });
      return;
    }
    // Strip internal marker. Then drop any unmatched / unaccepted diagnose row that
    // survived `insertable` (which only gates on `display`): the upstream Option-A
    // flip (KOALA_5634_DIAGNOSE_TO_ASSESS_UPSTREAM_FLIP, just before the insertable
    // filter) converts ICD-matched, accepted diagnose rows into assess rows, but
    // rows that are unaccepted or lack an ICD stay as diagnose and must be dropped
    // here before /insert-commands sees them (those rows have no condition_id and
    // would tank the batch).
    const allInsertable = [...insertable, ...acceptedRecs]
      .map(({ _template_inserted, ...c }) => c)
      .filter(c => c.command_type !== 'diagnose' || (c.data?.icd10_code && c.data?.accepted));

    // Prescriptions first so they appear at the top of the note.
    // Diagnosis rank is the commands[] order of diagnose/assess rows (the matrix
    // reorder mutates that order). Do NOT reorder diagnoses when building the
    // insert batch, or ClaimDiagnosisCode.rank will diverge from the matrix.
    // The RX sort below only moves Rx to position 0; it does not disturb the
    // relative order of diagnose/assess rows against each other.
    const RX_SET = new Set(['prescribe', 'refill', 'adjust_prescription']);
    allInsertable.sort((a, b) => (RX_SET.has(a.command_type) ? 0 : 1) - (RX_SET.has(b.command_type) ? 0 : 1));
    logEvent('COMMANDS_SENDING', { commands: allInsertable.map(c => ({
      type: c.command_type, display: (c.display || '').slice(0, 80), sectionKey: c.section_key,
    })) });
    try {
      const res = await fetch(`${API_BASE}/insert-commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_uuid: noteId, commands: allInsertable }),
      });
      const data = await res.json();
      if (data.error) {
        // If amend already succeeded, the home-app already executed those
        // EIE+Originate effects. We persist `workingCommands` (which carries
        // the re-stamped uuids) so a retry of /insert-commands won't re-send
        // the now-voided old uuid as an amend. The `approved` flag is reset
        // so the user can fix the insert-commands payload and retry.
        if (data.validation_errors) {
          setValidationError(data.validation_errors);
        } else if (amendAttempted.length > 0) {
          setError(`${data.error}. Amendments were saved; retry to complete insertion.`);
        } else {
          setError(data.error);
        }
        setApproved(false);
        setConfirming(false);
        saveSummaryToCache(noteData, workingCommands, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });
        logEvent('APPROVE_ERROR', { error: data.error, validation_errors: data.validation_errors, amendAttempted: amendAttempted.length });
      } else {
        // Phase 2: Insert metadata if any pending
        if (data.metadata_pending && data.metadata_pending.length > 0) {
          try {
            await fetch(`${API_BASE}/insert-metadata`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ note_uuid: noteId, pending: data.metadata_pending }),
            });
          } catch (metaErr) {
            console.error('Failed to insert metadata:', metaErr);
          }
        }
        // Stamp commands with their UUIDs and save immediately (before modal closes).
        // Amend re-stamping happened earlier (right after /edit-existing-commands
        // succeeded); here we only re-stamp the freshly-inserted commands.
        let updatedCommands = workingCommands;
        // KOALA_5634_STAMP_RECOMMENDATIONS_ON_APPROVE: parallel re-stamp pass for
        // accepted recommendations. Accepted recs are POSTed to /insert-commands
        // alongside `workingCommands`, but the original stamping loop only iterated
        // `workingCommands` — recs landed on the chart with server-side uuids while
        // local `recommendations` stayed unstamped. The next syncNoteCommands then
        // saw "new" uuids it couldn't match and appended every accepted rec under
        // ADDITIONAL COMMANDS (KOALA-5634). Stamping recs the same way drops them
        // into syncNoteCommands' uuid-match branch (line ~617), which preserves
        // their section_key and only flips `already_documented=true`.
        // Defaults to the unmodified closure; only reassigned below when `attempted`
        // has entries to stamp. Empty-attempted = nothing to stamp = closure is
        // faithful (no recs landed on the chart, so persisting the pre-stamp
        // recommendations array is correct).
        let updatedRecommendations = recommendations;
        if (data.attempted && data.attempted.length > 0) {
          const uuidMap = new Map();
          for (const a of (data.attempted || [])) {
            uuidMap.set(`${a.command_type}:${a.display}`, a.command_uuid);
          }
          updatedCommands = workingCommands.map(cmd => {
            const key = `${cmd.command_type}:${(cmd.display || '').slice(0, 80)}`;
            const uuid = uuidMap.get(key);
            // Stamp already_documented=true alongside command_uuid so the existing
            // `insertable` filter naturally excludes these commands on re-Approve
            // during amendment. Today's flow only sets already_documented from the
            // Add Now path; the full-Approve path skipped it, which would have
            // caused double-insertion on re-Approve. (KOALA-5485)
            return uuid ? { ...cmd, command_uuid: uuid, already_documented: true } : cmd;
          });
          setCommands(updatedCommands);
          updatedRecommendations = recommendations.map(rec => {
            // Only stamp recs that we actually attempted to insert: accepted +
            // not already on the chart + has a display string. Skip anything
            // that already has a uuid (defensive — shouldn't happen on a fresh
            // approval, but matters for re-approve flows).
            if (rec.command_uuid || !rec.accepted || rec.already_documented || !rec.display) return rec;
            const key = `${rec.command_type}:${(rec.display || '').slice(0, 80)}`;
            const uuid = uuidMap.get(key);
            return uuid ? { ...rec, command_uuid: uuid, already_documented: true } : rec;
          });
          // KOALA_5634_RECOMMENDATIONS_REF: commitRecommendations() primes the
          // ref before the next syncNoteCommands fires (whether triggered by the
          // post-success CLOSE_MODAL → NOTE_TAB_CHANGE bridge or by any other path)
          // so it sees the stamped uuids without waiting for the useEffect
          // ref-mirror to run post-commit.
          commitRecommendations(updatedRecommendations);
        }

        // Enrich charges: write diagnosis pointers + modifiers onto each charge's
        // BillingLineItem after the perform commands are committed (BLIs exist now).
        // Uses updatedCommands (fully UUID-stamped) so every perform command_uuid is
        // valid. amendDeletes have already been filtered out of workingCommands.
        {
          const dxCodeByRef = new Map(chargeMatrixDiagnoses.map(d => [d.command_uuid, d.code]));
          const enrichCharges = updatedCommands
            // Only send plugin-managed charges (_pointers key present). Pre-plugin
            // historical charges (no _pointers key) are grandfathered and must not
            // be touched.
            .filter(c => c.command_type === 'perform' && c.data?.cpt_code && c.command_uuid
              && '_pointers' in (c.data || {}))
            .map(c => {
              const rawPointers = c.data._pointers || [];
              const diagnosis_pointers = rawPointers
                .map(u => ({ command_uuid: u, icd10_code: dxCodeByRef.get(u) || '' }))
                .filter(p => p.icd10_code);
              // If all stored pointers are stale (the diagnoses were removed from the
              // note after the charge was linked), sending an empty payload would
              // destructively clear a previously-enriched BLI. Skip silently instead.
              // Only send empty when _pointers was truly [] — that means advisory-only
              // (never linked) or amendment unlink-all (provider deliberately unchecked).
              if (rawPointers.length > 0 && diagnosis_pointers.length === 0) return null;
              return { command_uuid: c.command_uuid, diagnosis_pointers, modifiers: c.data._modifiers || [] };
            })
            .filter(Boolean);
          // Charge-BLI removal is handled by the EARLY removal step (after
          // /delete-existing-commands, before /insert-commands), where each
          // removed charge's CPT still resolves to exactly one ACTIVE BLI. We
          // must NOT re-send removed_charges here: a comment edit re-enters a
          // clone with the SAME CPT, so by now the old uuid's CPT fallback would
          // resolve to the CLONE's BLI and this loop would delete it. Leave empty.
          const removedCharges = [];

          if (enrichCharges.length || removedCharges.length) {
            // The home-app applies the /insert-commands originate+commit effects
            // asynchronously. Retry on timing-race errors (billing_line_item_not_found
            // and no_assessment_resolved) until the commits propagate, then sign.
            const enrichBody = JSON.stringify({ note_uuid: noteId, charges: enrichCharges, removed_charges: removedCharges });
            let enrichData = {};
            let blocked = false;
            for (let attempt = 0; attempt < 8; attempt++) {
              try {
                const enrichRes = await fetch(`${API_BASE}/enrich-charges`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: enrichBody,
                });
                enrichData = await enrichRes.json().catch(() => ({}));
                if (enrichRes.status === 422) { blocked = true; break; }
                // fetch() only rejects on network failure, not on HTTP error status.
                // A 5xx (deploy/proxy), 401/403 (auth flip), or any non-OK response
                // would otherwise leave enrichData={} → loop breaks with no errors →
                // sign proceeds and the provider's pointers/modifiers are silently
                // dropped. Block instead so the cm-sign-error banner surfaces.
                if (!enrichRes.ok) { blocked = true; break; }
              } catch (enrichErr) {
                console.error('enrich-charges fetch failed:', enrichErr);
                blocked = true; // network failure — block sign rather than drop enrichment silently
                break;
              }
              const pending = (enrichData.errors || []).some(e =>
                e.reason === 'billing_line_item_not_found' || e.reason === 'no_assessment_resolved'
              );
              if (!pending) break; // every charge resolved (or only non-transient errors remain)
              await new Promise(resolve => setTimeout(resolve, 700)); // let the commit effects apply
            }
            // Treat remaining errors after retries as blocking — same early-return
            // as the 422-blocked branch. Two cases:
            //   billing_line_item_not_found — BLI never materialized within retry window
            //   no_assessment_resolved      — BLI found but Assessment codings not yet
            //                                 populated (timing race); provider linked the
            //                                 charge so this is NOT advisory-only
            // Advisory-only 0-pointer charges never reach this point: the backend emits
            // a clear (no error) for them, so they don't contribute to this list.
            const enrichStillPending = (enrichData.errors || []).some(e =>
              e.reason === 'billing_line_item_not_found' || e.reason === 'no_assessment_resolved'
            );
            if (blocked || enrichStillPending) {
              // Ensure the cm-sign-error banner renders even when the block came from
              // a transport failure (5xx/network) that carries no per-charge errors —
              // otherwise sign would silently halt with no explanation.
              const blockingErrors = (enrichData.errors && enrichData.errors.length)
                ? enrichData.errors
                : [{ command_uuid: '', reason: 'enrichment_unavailable' }];
              setChargeErrors(blockingErrors);
              setApproved(false);
              setConfirming(false);
              saveSummaryToCache(noteData, updatedCommands, false, { recommendations: updatedRecommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });
              setInserting(false);
              return;
            }
            if (enrichData.errors && enrichData.errors.length) console.warn('enrich-charges partial errors', enrichData.errors);
          }
        }

        // CACHE_FLIP_UNCONDITIONAL_ON_APPROVE_SUCCESS - KOALA-5485 cache-flip regression:
        // the approved=true cache write must fire UNCONDITIONALLY on the success branch,
        // NOT gated on `data.attempted.length > 0`. Two paths reach here with zero
        // attempted entries:
        //   (1) Amend-mode Save with zero edits in any editable section - the amend
        //       branch already cached approved=true at line ~1294, but if there are
        //       NO amend edits at all (empty-note approval), neither branch wrote
        //       approved=true to cache. Without this unconditional write, setApproved(true)
        //       updates React state in memory but the cache holds approved=false;
        //       a page reload would revert the UI to pre-approval.
        //   (2) Fresh approval crash-recovery: if the user crashes before this
        //       point with a successful insert but empty attempted (rare but possible
        //       for command types that don't surface attempted entries), the cache
        //       must reflect approved=true so reload doesn't lose the approval.
        // Pinned by `test_summary_js_cache_flip_to_approved_true_is_unconditional_on_success`.
        // KOALA_5634_STAMP_RECOMMENDATIONS_ON_APPROVE: persist `updatedRecommendations`
        // (with command_uuid + already_documented stamped on the accepted recs) — not
        // the stale closure `recommendations`. Otherwise a page reload restores the
        // pre-stamp state and the very next syncNoteCommands duplicates every accepted
        // rec under ADDITIONAL COMMANDS.
        saveSummaryToCache(noteData, updatedCommands, true, {
          recommendations: updatedRecommendations, unmatched_conditions: unmatchedConditions,
          diagnosis_suggestions: diagnosisSuggestions,
          selected_template_name: selectedTemplate?.name || null, mode,
        });
        const hasPrescriptions = workingCommands.some(c => c.display && RX_SET.has(c.command_type))
          || recommendations.some(c => c.display && !c.rejected && RX_SET.has(c.command_type));
        logEvent('APPROVE_COMPLETE', { insertedCount: allInsertable.length, effectCount: data.inserted, hasPendingMetadata: (data.metadata_pending?.length || 0) > 0, amendEditCount: amendAttempted.length });
        // Verify commands were actually created (include Add Now items + amend-edit NEW uuids).
        const amendVerifyEntries = amendAttempted.map(a => ({
          command_uuid: a.new_command_uuid,
          command_type: a.command_type,
          display: a.display || '',
        }));
        const allAttempted = [...addNowAttemptedRef.current, ...(data.attempted || []), ...amendVerifyEntries];
        if (allAttempted.length > 0) {
          try {
            const verifyRes = await fetch(`${API_BASE}/verify-commands`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ note_uuid: noteId, attempted: allAttempted }),
            });
            const verifyData = await verifyRes.json();
            const failedCount = verifyData.failed?.length || 0;
            const verifiedCount = verifyData.verified?.length || 0;
            const vResult = failedCount > 0
              ? { ok: false, verified: verifyData.verified || [], failed: verifyData.failed }
              : { ok: true, verified: verifyData.verified || [], failed: [] };
            setVerificationResult(vResult);
            if (failedCount > 0) {
              logEvent('COMMANDS_FAILED', { failed: verifyData.failed });
            } else {
              logEvent('COMMANDS_VERIFIED', { total: verifiedCount });
            }
          } catch (verifyErr) {
            console.error('Verification failed:', verifyErr);
          }
        }
        setApproved(true);
        // if (!hasPrescriptions) {
        //   try {
        //     await fetch(`${API_BASE}/sign-note`, {
        //       method: 'POST',
        //       headers: { 'Content-Type': 'application/json' },
        //       body: JSON.stringify({ note_uuid: noteId }),
        //     });
        //     logEvent('NOTE_SIGNED');
        //   } catch (signErr) {
        //     console.error('Failed to sign note:', signErr);
        //   }
        // }
        const port = window.__canvasPort && window.__canvasPort();
        if (port) port.postMessage({ type: 'CLOSE_MODAL' });
      }
    } catch (err) {
      // Network/parsing failure on /insert-commands. If amend already
      // succeeded we persist the re-stamped state so retry doesn't
      // re-submit voided uuids as amends.
      if (amendAttempted.length > 0) {
        setError('Amendments saved; some commands failed to insert. Retry.');
      } else {
        setError('Failed to insert commands');
      }
      setApproved(false);
      setConfirming(false);
      saveSummaryToCache(noteData, workingCommands, false, { recommendations, unmatched_conditions: unmatchedConditions, diagnosis_suggestions: diagnosisSuggestions, selected_template_name: selectedTemplate?.name || null, mode });
      logEvent('APPROVE_ERROR', { error: 'Failed to insert commands', amendAttempted: amendAttempted.length });
    } finally {
      setInserting(false);
    }
  }, [commands, chargeMatrixDiagnoses, recommendations, noteId, noteData, saveSummaryToCache, unmatchedConditions, diagnosisSuggestions, canEdit, inserting]);

  const handleAddNow = useCallback(async (command, isRecommendation, index) => {
    if (!canEdit) return;
    // Mirror handleInsert's entry-clear so a panel from a prior blocked click
    // doesn't persist across a subsequent successful Add Now.
    setValidationError(null);
    logEvent('ADD_NOW', { commandType: command.command_type, isRecommendation, index });
    // Mark as adding to show spinner and prevent double-clicks.
    const setAdding = (flag) => {
      if (isRecommendation) {
        setRecommendations(prev => prev.map((rec, i) => i === index ? { ...rec, _adding: flag } : rec));
      } else {
        setCommands(prev => prev.map((cmd, i) => i === index ? { ...cmd, _adding: flag } : cmd));
      }
    };
    // Client-side gate: don't ship incomplete commands to the server. The
    // server still validates, but failing fast gives instant feedback and
    // keeps the audit log clean of avoidable VALIDATION_FAILED events. Use
    // the same getAcceptedRecFailureReason helper as the Approve filter so
    // Rx and refer gates stay in sync across all three submit paths.
    const _addNowReason = getAcceptedRecFailureReason(command);
    if (_addNowReason) {
      logEvent('ADD_NOW_BLOCKED', { commandType: command.command_type, reason: _addNowReason, index });
      setValidationError([
        {
          command_type: command.command_type,
          display: (command.display || '').slice(0, 80),
          errors: [_validationErrorMessage(command, _addNowReason, 'adding')],
          _context: 'adding',
        },
      ]);
      return;
    }
    setAdding(true);
    try {
      const { _template_inserted, ...payload } = command;
      const res = await fetch(`${API_BASE}/insert-commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note_uuid: noteId, commands: [payload] }),
      });
      const data = await res.json();
      if (data.error) {
        setAdding(false);
        // Mirror handleInsert's branching so non-validation server errors
        // (auth 403, "Invalid JSON", etc.) surface as a banner instead of
        // silently leaving the spinner stopped with no user feedback.
        if (data.validation_errors) {
          // Tag entries with _context: 'adding' so the panel header reads
          // "Please fix before adding:" rather than the default approve wording.
          setValidationError(data.validation_errors.map(v => ({ ...v, _context: 'adding' })));
        } else {
          setError(data.error);
        }
        logEvent('ADD_NOW_ERROR', { commandType: command.command_type, index, error: data.error, validation_errors: data.validation_errors });
        return;
      }
      // Phase 2: insert metadata if needed (e.g. alert_facility).
      if (data.metadata_pending && data.metadata_pending.length > 0) {
        try {
          await fetch(`${API_BASE}/insert-metadata`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note_uuid: noteId, pending: data.metadata_pending }),
          });
        } catch (metaErr) { console.error('Add Now metadata failed:', metaErr); }
      }
      // Track attempted entry for verification merge with Approve All.
      const attemptedEntry = data.attempted && data.attempted[0];
      if (attemptedEntry) {
        addNowAttemptedRef.current.push(attemptedEntry);
      }
      if (isRecommendation) {
        // KOALA_5634_RECOMMENDATIONS_REF: commitRecommendations() primes the ref
        // synchronously so the next syncNoteCommands (typically NOTE_TAB_CHANGE
        // on the freshly-inserted command) sees the new command_uuid in
        // recommendationsRef.current and skips the matching fetched row. Without
        // the prime, the just-added rec would re-appear under ADDITIONAL COMMANDS
        // as a from_the_note duplicate. Same race class as cache-load and
        // approve-success; same fix via the shared helper.
        commitRecommendations(prev => prev.map((rec, i) =>
          i === index ? { ...rec, already_documented: true, accepted: true, _added_now: true, _adding: false, command_uuid: attemptedEntry?.command_uuid || null } : rec
        ));
      } else {
        setCommands(prev => prev.map((cmd, i) =>
          i === index ? { ...cmd, already_documented: true, _added_now: true, _adding: false, command_uuid: attemptedEntry?.command_uuid || null } : cmd
        ));
      }
      logEvent('ADD_NOW_SUCCESS', { commandType: command.command_type, index });
    } catch (err) {
      console.error('Add Now failed:', err);
      // Mirror handleInsert's catch: surface a banner so a network failure
      // (offline, plugin-runner restart, non-JSON 5xx) doesn't leave the
      // spinner stopped with no user feedback.
      setError('Failed to add command');
      setAdding(false);
      logEvent('ADD_NOW_ERROR', { commandType: command.command_type, index, error: String(err) });
    }
  }, [noteId, canEdit]);


  const commandBySectionKey = buildCommandBySectionKey(commands);
  const adHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_ad_hoc');
  const objectiveAdHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_objective_ad_hoc');
  const historyAdHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_history_ad_hoc');
  const subjectiveAdHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_subjective_ad_hoc');
  const chargeAdHocCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === '_charges_ad_hoc');
  // Commands synced from the note body that have no Scribe-side section
  // mapping render in a dedicated bottom block.
  const fromTheNoteCommands = commands
    .map((cmd, index) => ({ command: cmd, index }))
    .filter(entry => entry.command.section_key === FROM_THE_NOTE_SECTION);

  const insertableCount = commands.filter(c => {
    if (c.command_type === 'diagnose') return c.data?.icd10_code && c.data?.accepted && c.display;
    return !c.already_documented && c.display;
  }).length
    + recommendations.filter(c => c.accepted && !c.already_documented && c.display).length;
  const RX_TYPES = new Set(['prescribe', 'refill', 'adjust_prescription']);
  const hasRxCommands = commands.some(c => c.display && RX_TYPES.has(c.command_type))
    || recommendations.some(c => c.display && !c.rejected && RX_TYPES.has(c.command_type));
  // Accept and Sign is only offered once the user has committed to a flow
  // and reached its natural completion point. Manual mode shows it as soon
  // as the user opts in (so they can sign with empty / template-only fields
  // if that's what they want). AI mode requires recording to be finalized
  // AND the note to have been generated — we don't want a half-finished
  // transcript or an in-flight LLM call to be signable.
  const aiFlowComplete = mode === 'ai' && recording.finalized && noteData !== null;
  const showFooter = canEdit && (mode === 'manual' || aiFlowComplete);

  const INCOMPLETE_LABELS = { diagnose: 'diagnose', imaging_order: 'imaging order', prescribe: 'prescription', refer: 'referral', lab_order: 'lab order' };
  // Module-scope `isRxIncomplete` is the single source of truth — see top of file.
  const _isRxIncomplete = isRxIncomplete;
  const _isLabIncomplete = (d) => !d.lab_partner || !d.tests_order_codes || d.tests_order_codes.length === 0;
  const _isImagingIncomplete = (d) => !d.image_code || !d.service_provider || !d.ordering_provider_id || !d.diagnosis_codes || d.diagnosis_codes.length === 0;
  const _isReferIncomplete = (d) => !d.service_provider || !d.clinical_question || !d.notes_to_specialist || !d.diagnosis_codes || d.diagnosis_codes.length === 0;
  const incompleteTypes = [];
  for (const c of commands) {
    if (c.already_documented) continue;
    if (c.command_type === 'imaging_order' && c.display && _isImagingIncomplete(c.data)) {
      if (!incompleteTypes.includes('imaging_order')) incompleteTypes.push('imaging_order');
    }
    if ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && c.display && _isRxIncomplete(c.data)) {
      if (!incompleteTypes.includes('prescribe')) incompleteTypes.push('prescribe');
    }
    if (c.command_type === 'lab_order' && c.display && _isLabIncomplete(c.data)) {
      if (!incompleteTypes.includes('lab_order')) incompleteTypes.push('lab_order');
    }
    if (c.command_type === 'refer' && c.display && _isReferIncomplete(c.data)) {
      if (!incompleteTypes.includes('refer')) incompleteTypes.push('refer');
    }
  }
  for (const c of recommendations) {
    if (c.already_documented || !c.display || c.rejected) continue;
    if ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && _isRxIncomplete(c.data)) {
      if (!incompleteTypes.includes('prescribe')) incompleteTypes.push('prescribe');
    }
    if (c.command_type === 'refer' && _isReferIncomplete(c.data)) {
      if (!incompleteTypes.includes('refer')) incompleteTypes.push('refer');
    }
  }
  const incompleteCount = commands.filter(c =>
    !c.already_documented && c.display && (
      (c.command_type === 'imaging_order' && _isImagingIncomplete(c.data)) ||
      ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && _isRxIncomplete(c.data)) ||
      (c.command_type === 'lab_order' && _isLabIncomplete(c.data)) ||
      (c.command_type === 'refer' && _isReferIncomplete(c.data))
    )
  ).length + recommendations.filter(c =>
    !c.already_documented && c.display && !c.rejected && (
      ((c.command_type === 'prescribe' || c.command_type === 'refill' || c.command_type === 'adjust_prescription') && _isRxIncomplete(c.data)) ||
      (c.command_type === 'refer' && _isReferIncomplete(c.data))
    )
  ).length;
  const UNDECIDED_LABELS = { diagnose: 'diagnosis', medication_statement: 'medication', allergy: 'allergy', prescribe: 'prescription', refill: 'prescription', adjust_prescription: 'prescription', refer: 'referral' };
  const undecidedTypes = [];
  for (const c of commands) {
    if (!c.already_documented && c.display && c.command_type === 'diagnose' && !c.data.accepted && !c.data.rejected) {
      if (!undecidedTypes.includes(c.command_type)) undecidedTypes.push(c.command_type);
    }
  }
  for (const c of recommendations) {
    if (!c.already_documented && c.display && !c.accepted && !c.rejected) {
      if (!undecidedTypes.includes(c.command_type)) undecidedTypes.push(c.command_type);
    }
  }
  const undecidedRecommendationCount = commands.filter(c =>
    !c.already_documented && c.display && c.command_type === 'diagnose' && !c.data.accepted && !c.data.rejected
  ).length + recommendations.filter(c =>
    !c.already_documented && c.display && !c.accepted && !c.rejected
  ).length;
  const hasUnsavedEdits = editingFields.size > 0;

  // Ensure sections with ad-hoc buttons are always present even if Nabla omits them.
  const ENSURE_KEYS = new Map([
    ['vitals', { key: 'vitals', title: 'Vitals', text: '' }],
    ['current_medications', { key: 'current_medications', title: 'Meds Discussed', text: '' }],
    ['allergies', { key: 'allergies', title: 'Allergies Discussed', text: '' }],
    ['past_medical_history', { key: 'past_medical_history', title: 'Past Medical History', text: '' }],
    ['past_surgical_history', { key: 'past_surgical_history', title: 'Past Surgical History', text: '' }],
    ['family_history', { key: 'family_history', title: 'Family History', text: '' }],
    ['lab_results', { key: 'lab_results', title: 'Lab Results', text: '' }],
    ['imaging_results', { key: 'imaging_results', title: 'Imaging Results', text: '' }],
    ['physical_exam', { key: 'physical_exam', title: 'Physical Exam', text: '' }],
  ]);
  const effectiveSections = (() => {
    const base = noteData ? noteData.sections : SKELETON_SECTIONS;
    const existing = new Set(base.map(s => s.key.toLowerCase()));
    const missing = [...ENSURE_KEYS.entries()].filter(([k]) => !existing.has(k)).map(([, v]) => v);
    return missing.length > 0 ? [...base, ...missing] : base;
  })();
  const isRecording = recording.status === 'recording' || recording.status === 'paused';
  // Suppress "Recording in progress" / "Paused" labels (and the recording dot)
  // once a note has been generated or the transcript was finalized — at that
  // point the transcript is a static record, not a live capture.
  const transcriptHeaderIsLive = isRecording && !noteData && !recording.finalized;
  const showTopControls = canEdit && !noteData && !isRecording && !recording.finalized && !generating && mode === null;

  // Unified progress display: "Finalizing transcript" is step 0 of a sequence
  // that continues through the server-driven generate pipeline. Showing one
  // bar that ticks across all 6 steps gives the user a clear sense of motion
  // during the speaker-attribution wait + LLM run rather than a long stretch
  // of dead "Finalizing..." text followed by a separate progress bar.
  const isFinalizing = recording.status === 'finishing';
  const isInGenerationPipeline = generating || (recording.finalized && mode === 'ai' && !noteData);
  const showProgressBanner = isFinalizing || isInGenerationPipeline;
  let progressIndex = 0;
  let progressLabel = FINALIZE_LABEL;
  if (!isFinalizing && isInGenerationPipeline) {
    const serverStep = Math.max(progress.step, 0);
    progressIndex = serverStep + 1; // +1 because finalize occupies index 0
    progressLabel = PROGRESS_STEPS[serverStep] || PROGRESS_STEPS[0];
  }
  const progressPct = Math.max(((progressIndex + 1) / TOTAL_PROGRESS_STEPS) * 100, 5);

  return html`
    <div class=${`summary-container${!canEdit && !approved ? ' summary-container--readonly' : ''}`}>
      ${isAuthor && isNoteEditable && wasFinalized && html`
        <div class=${`summary-status-pill summary-status-pill--${approved ? 'finalized' : 'amending'}`} role="status" aria-live="polite">
          <svg class="summary-status-pill-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            ${approved
              ? html`<polyline points="20 6 9 17 4 12"/>`
              : html`<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>`
            }
          </svg>
          <span class="summary-status-pill-text">
            ${approved ? 'Charting finalized' : 'Editing charting'}
          </span>
          ${approved && html`
            <button class="summary-status-pill-btn" onClick=${handleMakeChanges}>
              Make changes
            </button>
          `}
        </div>
      `}
      ${readOnlyReason === 'locked' && html`
        <div class="readonly-banner" role="status" aria-live="polite">
          <svg class="readonly-banner-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <span>Scribe documentation is incomplete. Click <strong>Amend</strong> in the note footer to finish.</span>
        </div>
      `}
      ${readOnlyReason === 'non_author' && html`
        <div class="readonly-banner" role="status" aria-live="polite">
          <svg class="readonly-banner-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>Read-only — only the note author can edit the Scribe tab.</span>
        </div>
      `}
      ${canEdit && html`
        <div class="unified-top-bar">
          ${templates.length > 0 && html`
            <select
              class="template-select"
              onChange=${handleSelectTemplate}
              value=${selectedTemplate ? selectedTemplate.name : ''}
              disabled=${approved || generating || noteData !== null || mode !== null}
            >
              <option value="">Select Visit Type</option>
              ${templates.map(t => html`<option key=${t.name} value=${t.name}>${t.name}</option>`)}
            </select>
          `}
          ${showTopControls && html`
            ${!manualModeOnly && html`
              <button class="start-ai-btn" onClick=${handleStartAI} disabled=${!selectedTemplate}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="8" /></svg>
                Start AI Scribe
              </button>
            `}
            <button class="start-manual-btn" onClick=${handleStartManual} disabled=${!selectedTemplate}>
              Manual
            </button>
          `}
          ${isRecording && html`
            <div class="recording-controls-inline">
              ${recording.status === 'recording'
                ? html`<button class="control-btn" onClick=${recording.pauseRecording} title="Pause">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <rect x="6" y="5" width="4" height="14" rx="1" />
                      <rect x="14" y="5" width="4" height="14" rx="1" />
                    </svg>
                    Pause
                  </button>`
                : html`<button class="control-btn" onClick=${recording.resumeRecording} title="Resume">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <polygon points="6,4 20,12 6,20" />
                    </svg>
                    Resume
                  </button>`}
              <${FinishRecordingButton} onFinish=${recording.finishRecording} />
            </div>
          `}
          ${false && debugMode && noteData && !approved && !generating && !isRecording && html`
            <button class="regenerate-btn" onClick=${handleGenerate} disabled=${!selectedTemplate}>
              Regenerate${!selectedTemplate ? ' (select visit type)' : ''}
            </button>
          `}
          ${recommendations.length > 0 && html`
            <label class="hide-rejected-label hide-rejected-label--top-bar" onClick=${() => setHideRejected(prev => !prev)}>
              Hide Rejected Recommendations
              <div class="toggle-switch${hideRejected ? ' on' : ''}">
                <div class="toggle-knob" />
              </div>
            </label>
          `}
        </div>
      `}
      ${(isRecording || recording.entries.length > 0) && html`
        <div class="transcript-panel">
          <button class="transcript-panel-header ${transcriptHeaderIsLive ? '' : 'finalized'}" onClick=${() => setTranscriptCollapsed(prev => !prev)}>
            <div class="transcript-panel-status ${transcriptHeaderIsLive ? '' : 'finalized'}">
              ${transcriptHeaderIsLive && recording.status === 'recording' && html`
                <span class="recording-dot recording-dot-live"
                  style=${{
                    transform: `scale(${1 + Math.min(recording.audioLevel * 8, 1)})`,
                    opacity: 0.6 + Math.min(recording.audioLevel * 6, 0.4),
                  }}
                ></span>
              `}
              ${transcriptHeaderIsLive && recording.status === 'paused' && html`<span class="recording-dot recording-dot-paused"></span>`}
              <span>${transcriptHeaderIsLive
                ? (recording.status === 'paused' ? 'Paused' : 'Recording in progress')
                : 'Transcript'}</span>
              ${!transcriptHeaderIsLive && html`<span class="transcript-entry-count">(${recording.entries.filter(e => e.is_final).length})</span>`}
            </div>
            <span class="transcript-panel-toggle">${transcriptCollapsed ? 'Show' : 'Hide'}</span>
          </button>
          ${showSavedToast && html`<div class="transcript-saved-toast">Transcript saved</div>`}
          ${!transcriptCollapsed && html`
            <div class="transcript-panel-body" ref=${transcriptBodyRef}>
              ${recording.entries.length > 0
                ? html`
                  <div class="transcript-list">
                    ${recording.entries.map((entry, i) => html`
                      <${TranscriptEntry}
                        key=${entry.item_id || i}
                        ...${entry}
                        providerName=${providerName}
                        providerPhotoUrl=${providerPhotoUrl}
                        patientName=${patientName}
                      />
                    `)}
                  </div>
                `
                : html`<p class="transcript-placeholder">Transcript will appear here as you speak...</p>`}
            </div>
          `}
        </div>
      `}
      ${recording.micPrompting && html`
        <div class="mic-prompting-banner">
          <div class="mic-prompting-spinner" />
          <span>Waiting for microphone permission…</span>
        </div>
      `}
      ${recording.micBlocked && html`
        <div class="mic-blocked-banner">
          <div class="mic-blocked-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="#c0392b">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
              <line x1="3" y1="3" x2="21" y2="21" stroke="#c0392b" stroke-width="2"/>
            </svg>
          </div>
          <div class="mic-blocked-content">
            <strong>Microphone Access Blocked</strong>
            <p>Microphone permission is required to record. Tap the button below to allow access.</p>
          </div>
          <div class="mic-blocked-actions">
            <button class="mic-blocked-btn mic-blocked-btn-refresh" onClick=${() => recording.retryMicPermission()}>Enable Microphone</button>
          </div>
        </div>
      `}
      ${recording.connectionLost && recording.status === 'recording' && html`
        <div class="connection-lost-warning">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink: 0;">
            <path d="M24 8.98C20.93 5.9 16.69 4 12 4S3.07 5.9 0 8.98L12 21 24 8.98zM2.92 9.07C5.51 7.08 8.67 6 12 6s6.49 1.08 9.08 3.07l-1.43 1.43C17.5 8.94 14.86 8 12 8s-5.5.94-7.65 2.51L2.92 9.07zM12 18l-6.22-6.22C7.84 10.14 9.82 9.25 12 9.25s4.16.89 6.22 2.53L12 18z"/>
            <line x1="4" y1="4" x2="20" y2="20" stroke="currentColor" stroke-width="2"/>
          </svg>
          Connection lost — reconnecting. Audio is being buffered locally.
        </div>
      `}
      ${recording.silenceWarning && recording.status === 'recording' && html`
        <div class="silence-warning">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink: 0;">
            <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
          </svg>
          No audio detected — check your microphone permissions and make sure it is not muted
        </div>
      `}
      ${recording.error && html`<p class="error" style="padding: 0 16px;">${recording.error}</p>`}
      ${showProgressBanner && html`
        <div class="summary-generating-banner">
          <div class="generating-bar" style="width: ${progressPct}%" />
          <span class="generating-label">${progressLabel}...</span>
        </div>
      `}
      ${canEdit && !noteData && !generating && recording.finalized && mode === 'ai' && html`
        <div class="summary-generate-banner">
          <p class="summary-banner-description">Recording complete. Generate a structured summary from your transcript.</p>
          <button class="generate-btn" onClick=${handleGenerate}>Generate Summary</button>
        </div>
      `}
      ${error && html`<p class="error" style="padding: 0 16px;">${error}</p>`}
      <div class=${`summary-body${inserting ? ' summary-body--inserting' : ''}`}>
        ${renderSoapGroups(effectiveSections, commandBySectionKey, handleEdit, handleDelete, {
          adHocCommands,
          objectiveAdHocCommands,
          historyAdHocCommands,
          subjectiveAdHocCommands,
          chargeAdHocCommands,
          assignees,
          onAddTask: canEdit ? handleAddTask : null,
          onAddOrder: canEdit ? handleAddOrder : null,
          onAddPlan: canEdit ? handleAddPlan : null,
          onAddVitals: canEdit ? handleAddVitals : null,
          onAddMedication: canEdit ? handleAddMedication : null,
          onAddAllergy: canEdit ? handleAddAllergy : null,
          onAddStopMedication: canEdit ? handleAddStopMedication : null,
          onAddRemoveAllergy: canEdit ? handleAddRemoveAllergy : null,
          onAddResolveCondition: canEdit ? handleAddResolveCondition : null,
          onAddHistory: canEdit ? handleAddHistory : null,
          onAddQuestionnaire: canEdit ? handleAddQuestionnaire : null,
          onAddCharge: canEdit ? handleAddTemplateCharge : null,
          searchCharges,
          suggestedCharges: selectedTemplate?.charges || [],
          onAddTemplateCharge: canEdit ? handleAddTemplateCharge : null,
          onRemoveChargeByCpt: canEdit ? handleRemoveChargeByCpt : null,
          templateCharges: selectedTemplate ? (selectedTemplate.charges || []) : [],
          readOnly: !canEdit,
          isAmending: wasFinalized && !approved,
          sectionConditions,
          patientId,
          noteId,
          staffId,
          staffName,
          recommendations,
          onEditRecommendation: handleEditRecommendation,
          onDeleteRecommendation: handleDeleteRecommendation,
          onAcceptRecommendation: handleAcceptRecommendation,
          onRejectRecommendation: handleRejectRecommendation,
          onAddCondition: canEdit ? handleAddCondition : null,
          unmatchedConditions,
          diagnosisSuggestions,
          onAddNow: (canEdit && !(wasFinalized && !approved)) ? handleAddNow : null,
          hideRejected,
          alertFacilityEnabled,
          onEditingChange: handleEditingChange,
          questionnaireScores: collectQuestionnaireScores(commands),
          chargeMatrixDiagnoses,
          noteDiagnoses,
          chargeMatrixCharges,
          onToggleChargePointer: canEdit ? onToggleChargePointer : null,
          onReorderDiagnoses: canEdit ? onReorderDiagnoses : null,
          onAddChargeModifier: canEdit ? onAddChargeModifier : null,
          onRemoveChargeModifier: canEdit ? onRemoveChargeModifier : null,
          onSetChargeComment: canEdit ? onSetChargeComment : null,
          onClearChargeComment: canEdit ? onClearChargeComment : null,
          onRemoveChargeByUuid: canEdit ? onRemoveChargeByUuid : null,
          examTemplates: templates,
          onCarryForwardExam: handleCarryForwardExam,
        })}
        ${fromTheNoteCommands.length > 0 && html`
          <div class="summary-section from-the-note-section">
            <div class="section-header">
              <span class="section-title">ADDITIONAL COMMANDS</span>
            </div>
            <div class="section-body">
              ${fromTheNoteCommands.map(entry => html`
                <div class="content-block from-the-note-item command-locked" key=${entry.command.command_uuid || entry.index}>
                  <svg class="command-row-icon-lock" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                  </svg>
                  <div class="from-the-note-label">${entry.command.label || humanizeCommandType(entry.command.command_type)}</div>
                  ${(entry.command.details || []).map(d => html`
                    <div class="from-the-note-detail" key=${d.label}>
                      <span class="from-the-note-detail-label">${d.label}:</span>
                      <span class="from-the-note-detail-value">${d.value}</span>
                    </div>
                  `)}
                </div>
              `)}
            </div>
          </div>
        `}
      </div>
      ${verificationResult && html`<${VerificationSummary} result=${verificationResult} />`}
      ${validationError && html`
        <div class="validation-error">
          <strong>${(Array.isArray(validationError) && validationError.some(v => v._context === 'adding')) ? 'Please fix before adding:' : 'Please fix before approving:'}</strong>
          <ul>
            ${(Array.isArray(validationError) ? validationError : [{ display: '', errors: [validationError] }]).map(v => html`
              ${v.errors.map(e => html`<li key=${e}><strong>${v.display || v.command_type}</strong>: ${e}</li>`)}
            `)}
          </ul>
        </div>
      `}
      ${showFooter && html`
        <div class="summary-footer">
          ${inserting ? html`
            <div class="approve-progress">
              <div class="approve-spinner" />
              <span>Inserting ${insertableCount} ${insertableCount === 1 ? 'command' : 'commands'} into note...</span>
            </div>
          ` : confirming ? html`
            <div class="approve-confirm-block">
              ${hasUnsavedEdits && html`
                <div class="summary-footer-warning">
                  ${editingFields.size} unsaved ${editingFields.size === 1 ? 'edit' : 'edits'} \u2014 save or cancel to continue.
                </div>
              `}
              <button class="insert-btn confirm" disabled=${hasUnsavedEdits} onClick=${handleInsert}>${wasFinalized ? (hasRxCommands ? 'Confirm: Save changes and review prescriptions' : 'Confirm: Save changes') : (hasRxCommands ? 'Confirm: Accept and review prescriptions' : 'Confirm: Accept and sign')}</button>
              <button class="approve-cancel" onClick=${() => setConfirming(false)}>Cancel</button>
            </div>
          ` : html`
            <div class="approve-block">
              ${incompleteCount > 0 && html`
                <div class="summary-footer-warning">
                  ${incompleteCount} incomplete ${incompleteCount === 1 ? 'item' : 'items'} must be fixed or removed before approving: ${incompleteTypes.map(t => INCOMPLETE_LABELS[t]).join(', ')}
                </div>
              `}
              ${undecidedRecommendationCount > 0 && html`
                <div class="summary-footer-warning">
                  ${undecidedRecommendationCount} ${undecidedRecommendationCount === 1 ? 'recommendation needs' : 'recommendations need'} a decision, ${undecidedRecommendationCount === 1 ? 'it has' : 'they have'} not been accepted nor rejected: ${undecidedTypes.map(t => UNDECIDED_LABELS[t] || t).join(', ')}
                </div>
              `}
              ${hasUnsavedEdits && html`
                <div class="summary-footer-warning">
                  ${editingFields.size} unsaved ${editingFields.size === 1 ? 'edit' : 'edits'} \u2014 save or cancel to continue.
                </div>
              `}
              ${!canSignCharges(chargeMatrixCharges) && html`
                <div class="summary-footer-warning">Some charges have no linked diagnosis — you can still sign, but consider linking them for cleaner billing.</div>
              `}
              ${(chargeErrors && chargeErrors.length)
                ? html`<div class="summary-footer-warning cm-sign-error">Some charges could not be saved (${chargeErrors.length}). Please review the charges and try again.</div>`
                : null}
              <button class="insert-btn" disabled=${undecidedRecommendationCount > 0 || hasUnsavedEdits} onClick=${() => setConfirming(true)}>${wasFinalized ? (hasRxCommands ? 'Save changes and review prescriptions' : 'Save changes') : (hasRxCommands ? 'Accept and review prescriptions' : 'Accept and sign')}</button>
              ${!wasFinalized && html`<div class="approve-warning">This action is permanent and cannot be undone.</div>`}
            </div>
          `}
        </div>
      `}
    </div>
  `;
}
