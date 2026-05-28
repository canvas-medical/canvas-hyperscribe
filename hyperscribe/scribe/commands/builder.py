from __future__ import annotations

import json
import uuid
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.effects import Effect
from canvas_sdk.v1.data.note import Note
from logger import log
from pydantic import ValidationError

from hyperscribe.scribe.backend.models import CommandProposal
from hyperscribe.scribe.commands.adjust_prescription import AdjustPrescriptionParser
from hyperscribe.scribe.commands.allergy import AllergyParser
from hyperscribe.scribe.commands.assess import AssessParser
from hyperscribe.scribe.commands.base import CommandParser
from hyperscribe.scribe.commands.chart_review import ChartReviewParser
from hyperscribe.scribe.commands.diagnose import DiagnoseParser
from hyperscribe.scribe.commands.family_history import FamilyHistoryParser
from hyperscribe.scribe.commands.history_review import HistoryReviewParser
from hyperscribe.scribe.commands.hpi import HpiParser
from hyperscribe.scribe.commands.image_results import ImageResultsParser
from hyperscribe.scribe.commands.imaging_order import ImagingOrderParser
from hyperscribe.scribe.commands.lab_order import LabOrderParser
from hyperscribe.scribe.commands.lab_results import LabResultsParser
from hyperscribe.scribe.commands.medical_history import MedicalHistoryParser
from hyperscribe.scribe.commands.medication_statement import MedicationParser
from hyperscribe.scribe.commands.perform import PerformParser
from hyperscribe.scribe.commands.physical_exam import PhysicalExamParser
from hyperscribe.scribe.commands.plan import PlanParser
from hyperscribe.scribe.commands.prescription import PrescriptionParser
from hyperscribe.scribe.commands.questionnaire import QuestionnaireParser
from hyperscribe.scribe.commands.refer import ReferParser
from hyperscribe.scribe.commands.refill import RefillParser
from hyperscribe.scribe.commands.remove_allergy import RemoveAllergyParser
from hyperscribe.scribe.commands.resolve_condition import ResolveConditionParser
from hyperscribe.scribe.commands.rfv import RfvParser
from hyperscribe.scribe.commands.ros import RosParser
from hyperscribe.scribe.commands.stop_medication import StopMedicationParser
from hyperscribe.scribe.commands.surgical_history import SurgicalHistoryParser
from hyperscribe.scribe.commands.task import TaskParser
from hyperscribe.scribe.commands.vitals import VitalsParser


_BUILDERS: dict[str, CommandParser] = {
    "adjust_prescription": AdjustPrescriptionParser(),
    "allergy": AllergyParser(),
    "assess": AssessParser(),
    "chart_review": ChartReviewParser(),
    "diagnose": DiagnoseParser(),
    "familyHistory": FamilyHistoryParser(),
    "history_review": HistoryReviewParser(),
    "hpi": HpiParser(),
    "imaging_order": ImagingOrderParser(),
    "imaging_results": ImageResultsParser(),
    "lab_order": LabOrderParser(),
    "lab_results": LabResultsParser(),
    "medicalHistory": MedicalHistoryParser(),
    "medication_statement": MedicationParser(),
    "perform": PerformParser(),
    "physical_exam": PhysicalExamParser(),
    "plan": PlanParser(),
    "prescribe": PrescriptionParser(),
    "questionnaire": QuestionnaireParser(),
    "refer": ReferParser(),
    "refill": RefillParser(),
    "remove_allergy": RemoveAllergyParser(),
    "resolve_condition": ResolveConditionParser(),
    "rfv": RfvParser(),
    "ros": RosParser(),
    "stop_medication": StopMedicationParser(),
    "surgicalHistory": SurgicalHistoryParser(),
    "task": TaskParser(),
    "vitals": VitalsParser(),
}


def annotate_duplicates(proposals: list[CommandProposal], note_uuid: str) -> None:
    """Delegate duplicate annotation to each command parser."""
    if not note_uuid:
        return
    try:
        note = Note.objects.select_related("patient").get(id=note_uuid)
    except Note.DoesNotExist:
        return
    for builder in _BUILDERS.values():
        builder.annotate_duplicates(proposals, note)


def validate_proposals(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate all proposals. Returns list of {command_type, display, errors} for failures."""
    validation_errors: list[dict[str, Any]] = []
    for proposal in proposals:
        builder = _BUILDERS.get(proposal.get("command_type", ""))
        if builder is None:
            continue
        errors = builder.validate(proposal.get("data", {}))
        if errors:
            validation_errors.append(
                {
                    "command_type": proposal.get("command_type", ""),
                    "display": (proposal.get("display") or "")[:80],
                    "errors": errors,
                }
            )
    return validation_errors


def _build_unvalidated_metadata_effect(command: _BaseCommand, key: str, value: str) -> Effect:
    """Construct UPSERT_COMMAND_METADATA directly. The SDK helper
    validates Command.objects.filter(...).exists() at Python build time,
    which fails before originate has been applied. Canvas processes effects
    sequentially, so originate (STAGED) -> metadata (apply-time check passes)
    -> commit (COMMITTED with metadata attached) all in one response.

    Note: `Effect` is imported from `canvas_sdk.effects` (which re-exports the
    protobuf class) rather than the raw `canvas_generated.messages.effects_pb2`
    path, because the plugin-runner sandbox allowlists the former but not the
    latter."""
    return Effect(
        type="UPSERT_COMMAND_METADATA",
        payload=json.dumps(
            {
                "data": {
                    "schema_key": command.Meta.key,
                    "command_id": str(command.command_uuid),
                    "key": key,
                    "value": value,
                },
            }
        ),
    )


def _format_pydantic_errors(exc: ValidationError) -> list[str]:
    """Render pydantic errors as actionable one-liners for the provider UI.

    The rendered message names the failing field and states the constraint in plain
    English. Raw ``input`` values are **never** echoed except when they are explicit
    PHI-safe scalars (``int``/``float``/``bool``/``None``); any other type — string,
    list, dict, model — is omitted entirely. This matters because ``build_errors``
    is persisted to the ``VALIDATION_FAILED`` audit log by ``session_view`` and
    returned in the HTTP response body, both of which are HIPAA-sensitive sinks
    when the LLM emits free-text content into a numeric/enum field.
    """
    messages: list[str] = []
    for err in exc.errors():
        # INVARIANT: ``loc`` parts are developer-defined field names from the scribe
        # SDK command models, not LLM/user input — safe to render in clinician-facing
        # error UI and to persist to the VALIDATION_FAILED audit log. Pydantic
        # surfaces dict keys into ``loc`` for ``dict[K, V]``-typed fields; do NOT add
        # ``dict[str, X]``-typed fields to scribe command models without sanitizing,
        # or the LLM-supplied keys will leak into ``loc`` and through this renderer.
        loc = ".".join(str(part) for part in err.get("loc", ())) or "value"
        err_type = err.get("type", "")
        ctx = err.get("ctx", {}) or {}
        input_value = err.get("input")
        if err_type == "greater_than_equal" and "ge" in ctx:
            messages.append(f"{loc} must be greater than or equal to {ctx['ge']} ({_render_input(input_value)})")
        elif err_type == "less_than_equal" and "le" in ctx:
            messages.append(f"{loc} must be less than or equal to {ctx['le']} ({_render_input(input_value)})")
        elif err_type == "greater_than" and "gt" in ctx:
            messages.append(f"{loc} must be greater than {ctx['gt']} ({_render_input(input_value)})")
        elif err_type == "less_than" and "lt" in ctx:
            messages.append(f"{loc} must be less than {ctx['lt']} ({_render_input(input_value)})")
        elif err_type == "string_too_long" and "max_length" in ctx:
            messages.append(f"{loc} must be at most {ctx['max_length']} characters")
        elif err_type == "string_too_short" and "min_length" in ctx:
            messages.append(f"{loc} must be at least {ctx['min_length']} characters")
        elif err_type == "missing":
            messages.append(f"{loc} is required")
        elif err_type in ("value_error", "assertion_error"):
            # Latent defense: custom ``@field_validator`` decorators (none today in
            # ``hyperscribe/scribe/commands/``) raise ``ValueError(f"... {x} ...")``,
            # and Pydantic embeds the raw input into ``msg`` for these types — a PHI
            # vector via the ``else:`` fallback. Surface only the field name.
            messages.append(f"{loc}: invalid value")
        else:
            # Fallback for unmapped pydantic types (int_type/int_parsing/bool_type/
            # etc.). Keep the pydantic message but only echo input when it's a
            # PHI-safe scalar; otherwise omit entirely.
            msg = err.get("msg", "Invalid value")
            if isinstance(input_value, (int, float, bool)) or input_value is None:
                messages.append(f"{loc}: {msg} (currently {input_value!r})")
            else:
                messages.append(f"{loc}: {msg}")
    return messages


def _render_input(value: Any) -> str:
    """Render an ``input`` value for inclusion in an error message.

    For the if/elif branches above, the constraint is on a numeric field and the
    value is expected to be a number — but the LLM can emit free text into a
    numeric field, in which case the value is unsafe to echo (PHI risk). Anything
    that isn't an explicit PHI-safe scalar collapses to ``"currently invalid"``.
    """
    if isinstance(value, (int, float, bool)) or value is None:
        return f"currently {value}"
    return "currently invalid"


# Friendly command-type labels used as the ``display`` prefix on build_errors,
# so the UI renders e.g. "Vitals: pulse must be greater than or equal to 30
# (currently 8)" instead of dumping the raw input free-text as the prefix.
_BUILD_ERROR_LABELS: dict[str, str] = {
    "vitals": "Vitals",
}


def build_effects(
    proposals: list[dict[str, Any]],
    note_uuid: str,
    feature_flags: dict[str, bool] | None = None,
) -> tuple[list[Effect], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert selected command proposals into Canvas SDK Effects.

    Each command is originated individually so a single failure doesn't
    take down unrelated commands. Effect order in the returned list is:

        originate_A, originate_B, ...,
        metadata_A, metadata_B, ...,    # only when pending_metadata is non-empty
        commit_A,   commit_B,   ...,

    Canvas processes effects sequentially, so by the time a metadata effect
    runs the corresponding originate effect has populated the Command row
    in the DB; by the time the commit effect runs, the metadata row is
    already attached to the (still STAGED) command.

    Returns (effects, metadata_pending, attempted, build_errors). When a
    proposal fails SDK construction (e.g. a vital outside its pydantic range),
    that single command is skipped and a structured error in the same shape as
    ``validate_proposals`` is appended to ``build_errors``; sibling commands
    still produce effects. ``metadata_pending`` is always empty now (metadata
    is emitted inline); kept in the signature so the legacy ``/insert-metadata``
    pathway continues to be a no-op without requiring a separate route change.
    """
    built: list[tuple[CommandParser, _BaseCommand, dict[str, Any]]] = []
    build_errors: list[dict[str, Any]] = []
    for proposal in proposals:
        command_type = proposal.get("command_type", "")
        builder = _BUILDERS.get(command_type)
        if builder is None:
            continue
        # Resolve the user-facing label once per proposal. The LLM-supplied
        # ``display`` is untrusted free text and may contain PHI when the model
        # echoes raw field content; prefer the friendly label from
        # ``_BUILD_ERROR_LABELS`` for any command type we render error UI for.
        display = _BUILD_ERROR_LABELS.get(command_type) or (proposal.get("display") or "")[:80]
        try:
            command = builder.build(proposal.get("data", {}), note_uuid, str(uuid.uuid4()))
        except ValidationError as exc:
            build_errors.append(
                {
                    "command_type": command_type,
                    "display": display,
                    "errors": _format_pydantic_errors(exc),
                }
            )
            continue
        except ValueError:
            # Non-pydantic value coercion error. Today the only path that lands
            # here is the enum coercion in vitals.py:70 for an LLM-supplied
            # free-text ``blood_pressure_position_and_site``. We deliberately do
            # NOT include ``str(exc)`` because Python's standard enum
            # ``ValueError`` embeds the raw input verbatim ("'<raw>' is not a
            # valid <EnumName>"), and that string is persisted to the
            # VALIDATION_FAILED audit log by session_view — a HIPAA leak sink
            # when the raw input is free-text PHI. But we DO surface the field
            # name (developer-defined, PHI-safe) so the clinician sees which
            # field is wrong and can re-prompt; a bare generic message is
            # unactionable. If another command type starts raising plain
            # ``ValueError`` from ``build()``, this hardcoded field name will
            # become misleading — add a per-command-type lookup at that point.
            build_errors.append(
                {
                    "command_type": command_type,
                    "display": display,
                    "errors": ["blood_pressure_position_and_site: invalid value"],
                }
            )
            continue
        built.append((builder, command, proposal))

    if not built:
        return [], [], [], build_errors

    effects: list[Effect] = []
    for _, command, _ in built:
        effects.append(command.originate())

    for builder, command, proposal in built:
        meta = builder.pending_metadata(command, proposal, feature_flags)
        if not meta:
            continue
        for key, value in (meta.get("metadata") or {}).items():
            effects.append(_build_unvalidated_metadata_effect(command, key, value))

    for builder, command, proposal in built:
        effects.extend(builder.post_originate_effects(command, proposal))

    attempted = [
        {
            "command_uuid": str(command.command_uuid),
            "command_type": builder.command_type,
            "display": (proposal.get("display") or "")[:80],
        }
        for builder, command, proposal in built
    ]

    return effects, [], attempted, build_errors


def build_metadata_effects(pending: list[dict[str, Any]]) -> list[Effect]:
    """Phase 2: build upsert_metadata effects for commands that now exist in the DB."""
    effects: list[Effect] = []
    for item in pending:
        builder = _BUILDERS.get(item.get("command_type", ""))
        if builder is None:
            continue
        command = builder.build_stub(item["command_uuid"], item["note_uuid"])
        for key, value in item.get("metadata", {}).items():
            effects.append(command.upsert_metadata(key, value))
    return effects


# ----------------------------------------------------------------------
# Amendment edit path (KOALA-5485)
#
# When a provider clicks "Make changes" after approving the scribe note,
# they can edit the content of already-documented sections. The sections in
# EDITABLE_AMEND_SECTIONS support content edits during amendment; sections
# outside the allowlist stay locked.
#
# The allowlist covers EVERY ``_BUILDERS`` command_type EXCEPT clinical
# orders (prescribe, refill, adjust_prescription, refer, imaging_order,
# lab_order) and questionnaires. Orders have downstream external workflow
# implications (pharmacy dispatch, referral letters, lab tickets) that make
# void+recreate unsafe in this context. Questionnaire amendment is a future
# ticket: its insert flow is ``originate + edit + commit`` (the edit applies
# responses), which doesn't fit any of the three buckets below; a dedicated
# 4-effect route would be needed.
#
# This constant is mirrored in:
#   - hyperscribe/scribe/static/summary.js (EDITABLE_AMEND_SECTIONS)
#   - hyperscribe/scribe/static/soap-group.js (EDITABLE_AMEND_SECTIONS)
# Keep all three in sync (single-sourcing is a planned follow-up ticket).
#
# Three routes, picked per-proposal by section_key:
#   1) DIRECT_EDIT (RFV / chief_complaint) - emit EDIT only, reuse uuid.
#      RFV is the only section whose home-app interpreter wires EDIT but
#      NOT COMMIT or ENTER_IN_ERROR. The command stays STAGED forever, so
#      EDIT works and EIE would silently no-op (state corruption).
#   2) CUSTOM_COMMAND_ROUTED (_ros, physical_exam, _chart_review,
#      _history_review, lab_results, imaging_results) - emit
#      EnterInError(old) + Originate(new). ALL CustomCommand subclasses share
#      Meta.key "customCommand" (forcibly set by __init_subclass__), so their
#      constantized_key is "CUSTOM_COMMAND". The Canvas SDK only declares
#      ORIGINATE_CUSTOM_COMMAND_COMMAND and ENTER_IN_ERROR_CUSTOM_COMMAND_COMMAND
#      in the protobuf enum - calling .commit() raises
#      ValueError("unknown enum label \"COMMIT_CUSTOM_COMMAND_COMMAND\"")
#      at Python build time. home-app's OriginateCustomCommand interpreter
#      auto-commits unconditionally after originate, so no explicit commit
#      effect is needed (and would crash).
#   3) VOID_RECREATE (everything else: HPI, vitals, allergies, current_meds,
#      structured PMH/PSH/PFH, plan/A&P diagnose/assess, charges, tasks,
#      stop_med, remove_allergy, resolve_condition, and the ad-hoc buckets
#      where these commands originate before being saved). Emit
#      EnterInError(old) + Originate(new) + Commit(new). Dedicated SDK
#      command classes have their constantized key wired into both the SDK
#      proto AND home-app interpreters for all three effects.
# ----------------------------------------------------------------------

EDITABLE_AMEND_SECTIONS: frozenset[str] = frozenset(
    {
        # DIRECT_EDIT bucket
        "chief_complaint",
        # CUSTOM_COMMAND_ROUTED bucket
        "_ros",
        "_history_review",
        "_chart_review",
        "physical_exam",
        "lab_results",
        "imaging_results",
        # VOID_RECREATE bucket - SOAP-section-anchored
        "history_of_present_illness",
        "current_medications",
        "allergies",
        "vitals",
        "past_medical_history",
        "past_surgical_history",
        "family_history",
        "assessment_and_plan",
        "plan",
        # VOID_RECREATE bucket - ad-hoc buckets (rows added during a session;
        # after approval+reload they retain these section_keys and may be
        # ``already_documented=true``)
        "_ad_hoc",
        "_objective_ad_hoc",
        "_history_ad_hoc",
        "_charges_ad_hoc",
    }
)

# Cross-repo invariant (NOT enforced in CI yet - follow-up ticket).
#
# The direct-EDIT path for chief_complaint (RFV) is load-bearing on home-app
# NOT wiring either of these interpreters:
#   * COMMIT_REASON_FOR_VISIT_COMMAND
#   * ENTER_IN_ERROR_REASON_FOR_VISIT_COMMAND
#
# As of this writing, the registry at
#   canvas-monorepo/home-app/plugin_io/interpreters/commands/__init__.py
# (around line 395) declares neither. That means RFV commands stay STAGED
# forever and ``EditCommandEffectInterpreter`` accepts edits. If a home-app PR
# adds either wiring, RFV becomes committable and the direct-EDIT path here
# silently breaks - the EDIT effect lands on a COMMITTED row and home-app
# rejects it with "Command must be staged in order to be edited."
#
# If you're adding to home-app's interpreter registry: revisit this carve-out.
# Either (a) drop chief_complaint from DIRECT_EDIT_SECTIONS and let it fall
# through to the void+recreate path below, or (b) confirm the new wiring
# preserves the STAGED-forever guarantee for RFV.
#
# Follow-up: a workflows/ CI job that asserts this invariant cross-repo on
# every home-app PR would catch the bug at the source instead of relying on
# this comment. Tracked separately.
DIRECT_EDIT_SECTIONS: frozenset[str] = frozenset({"chief_complaint"})

# Sections whose parser builds a CustomCommand instance. These cannot call
# .commit() (the COMMIT_CUSTOM_COMMAND_COMMAND enum does not exist), so the
# amend route is EnterInError(old) + Originate(new) only; home-app's
# OriginateCustomCommand interpreter auto-commits after originate.
#
# The parsers in this set ALL return ``CustomCommand(schema_key=...)`` rather
# than a dedicated SDK class:
#   * RosParser            -> CustomCommand("reviewOfSystems")
#   * HistoryReviewParser  -> CustomCommand("historyReview")
#   * ChartReviewParser    -> CustomCommand("chartReview")
#   * PhysicalExamParser   -> CustomCommand("physicalExam")
#   * LabResultsParser     -> CustomCommand("labResult")
#   * ImageResultsParser   -> CustomCommand("imageResult")
CUSTOM_COMMAND_ROUTED_SECTIONS: frozenset[str] = frozenset(
    {
        "_ros",
        "_history_review",
        "_chart_review",
        "physical_exam",
        "lab_results",
        "imaging_results",
    }
)

# Command types that MUST NEVER be amended via the void+recreate path,
# regardless of which section_key they land on.
#
# Three reasons a command_type lands here:
#
#   1. STRUCTURALLY IMPOSSIBLE: no COMMIT_*_COMMAND interpreter exists in
#      home-app, so the third effect of the EIE+Originate+Commit route
#      cannot execute. The Originate either dangles in STAGED forever or
#      home-app's plugin_runner_receiver rejects the Commit.
#
#   2. STRUCTURALLY AWKWARD: the command has no COMMIT_*_COMMAND
#      interpreter but DOES have an EnterInError interpreter, so EIE works
#      but the Originate+Commit half breaks. A 4-effect EIE+Originate+
#      Edit+Commit route (or equivalent) would be needed and isn't built.
#
#   3. POLICY EXCLUDED: the wiring exists end-to-end, but void+recreate is
#      the wrong abstraction for the workflow. Calling it after the command
#      has already triggered external action would either re-fire the
#      dispatch or leave the original in a half-cancelled state. A dedicated
#      "amend an order" workflow with explicit cancel/resend semantics is
#      the right shape; tracked separately.
#
#   4. DEFERRED: a workable route exists in principle but hasn't been built.
#      Questionnaire's insert flow is originate+edit+commit (the edit
#      applies responses to the staged command), so the amend route needs
#      4 effects (EIE+Originate+Edit+Commit) AND the question/response
#      state has to survive the recreate. Tracked as a follow-up.
#
# Mirrored intent: the JS allowlists omit `_subjective_ad_hoc` (questionnaire
# bucket) and `_recommended` (order recommendation bucket), but command_type
# is the authoritative gate because some commands (`prescribe`, `task`) can
# also be added via `_ad_hoc`. Section-key plus command-type together make
# the denial structural rather than relying on the frontend not to send the
# request.
#
# Keep the JS mirror (soap-group.js + summary.js) in sync with the same
# categorization comments until single-sourcing lands.
NON_EDITABLE_AMEND_COMMAND_TYPES: frozenset[str] = frozenset(
    {
        # 1. Structurally impossible (no COMMIT_*_COMMAND interpreter):
        #    Originate dangles in STAGED; pharmacy dispatch via SureScripts
        #    would also re-fire on a Commit if one existed.
        "prescribe",
        "refill",
        "adjust_prescription",
        # 2. Structurally awkward (EIE exists, no COMMIT - would need a
        #    4-effect amend route that isn't built yet):
        "refer",
        "imaging_order",
        # 3. Policy excluded (full home-app wiring exists; amend after the
        #    lab-partner ticket has been dispatched would create downstream
        #    confusion at the partner side - a cancel/resend workflow is
        #    the right shape):
        "lab_order",
        # 4. Deferred (4-effect EIE+Originate+Edit+Commit route + question/
        #    response state preservation needed):
        "questionnaire",
    }
)


def build_amend_edit_effects(
    proposals: list[dict[str, Any]],
    note_uuid: str,
) -> tuple[list[Effect], list[dict[str, Any]]]:
    """Build Canvas SDK Effects for amendment-mode edits of already-documented commands.

    Each proposal must carry the existing ``command_uuid`` and a ``section_key``
    in :data:`EDITABLE_AMEND_SECTIONS`. Proposals that fail either check are
    silently dropped and logged at WARN (defense in depth - we never trust a
    hand-crafted payload enough to invent a uuid or emit effects for a
    non-amendable section).

    Returns ``(effects, attempted)`` where ``attempted`` carries enough state
    for the API layer to (a) emit a structured audit-log entry and (b) let the
    frontend re-stamp ``ScribeSummary.commands`` with the new uuid after a
    void+recreate.
    """
    effects: list[Effect] = []
    attempted: list[dict[str, Any]] = []

    for proposal in proposals:
        section_key = proposal.get("section_key", "")
        command_type = proposal.get("command_type", "")
        old_command_uuid = proposal.get("command_uuid", "")

        if section_key not in EDITABLE_AMEND_SECTIONS:
            log.warning(
                "amend_edit_dropped: section_not_editable section_key=%s command_type=%s",
                section_key,
                command_type,
            )
            continue
        if command_type in NON_EDITABLE_AMEND_COMMAND_TYPES:
            # Orders (prescribe family + refer + imaging/lab order) and
            # questionnaires are categorically denied regardless of which
            # section_key the frontend ships, because the ad-hoc section_keys
            # (_ad_hoc, _objective_ad_hoc, ...) are shared with editable
            # command_types and the section-key check alone would let an
            # order ride through.
            log.warning(
                "amend_edit_dropped: command_type_not_editable section_key=%s command_type=%s",
                section_key,
                command_type,
            )
            continue
        if not old_command_uuid:
            log.warning(
                "amend_edit_dropped: missing_command_uuid section_key=%s command_type=%s",
                section_key,
                command_type,
            )
            continue
        builder = _BUILDERS.get(command_type)
        if builder is None:
            log.warning(
                "amend_edit_dropped: unknown_command_type section_key=%s command_type=%s",
                section_key,
                command_type,
            )
            continue

        data = proposal.get("data", {}) or {}

        if section_key in DIRECT_EDIT_SECTIONS:
            # RFV direct-edit path: keep the existing uuid, emit EDIT only.
            command = builder.build(data, note_uuid, old_command_uuid)
            effects.append(command.edit())
            attempted.append(
                {
                    "section_key": section_key,
                    "command_type": command_type,
                    "old_command_uuid": old_command_uuid,
                    "new_command_uuid": old_command_uuid,
                    "mode": "direct_edit",
                    "display": (proposal.get("display") or "")[:80],
                }
            )
            continue

        # EnterInError(old) + Originate(new). Two flavors:
        # - CustomCommand-routed: no explicit commit (home-app auto-commits).
        # - Dedicated SDK class: explicit Commit(new).
        old_command = builder.build(data, note_uuid, old_command_uuid)
        new_command_uuid = str(uuid.uuid4())
        new_command = builder.build(data, note_uuid, new_command_uuid)
        effects.append(old_command.enter_in_error())
        effects.append(new_command.originate())
        if section_key in CUSTOM_COMMAND_ROUTED_SECTIONS:
            mode = "void_recreate_custom"
        else:
            effects.append(new_command.commit())
            mode = "void_recreate"
        attempted.append(
            {
                "section_key": section_key,
                "command_type": command_type,
                "old_command_uuid": old_command_uuid,
                "new_command_uuid": new_command_uuid,
                "mode": mode,
                "display": (proposal.get("display") or "")[:80],
            }
        )

    return effects, attempted


def build_amend_delete_effects(
    proposals: list[dict[str, Any]],
    note_uuid: str,
) -> tuple[list[Effect], list[dict[str, Any]]]:
    """Build Canvas SDK Effects for amendment-mode deletes of already-documented commands.

    Driver: perform (charge) commands in the amend-mode checklist have no
    ChargeRow editor (they render as a checked label + checkbox), so the only
    way to amend a documented charge is to uncheck it. Without a dedicated
    delete route the uncheck silently no-ops in handleInsert: it's filtered
    out of the insertable list, and because the user didn't edit it, the
    ``_amend_edited`` tag is never set either, so the existing amend POST
    also drops it. The chart stays out of sync with the visible UI.

    Each proposal must carry the existing ``command_uuid`` and a ``section_key``
    in :data:`EDITABLE_AMEND_SECTIONS`. Proposals failing eligibility (missing
    uuid, section not in allowlist, command_type in denylist, unknown
    command_type) are silently dropped and logged at WARN - same defense-in-
    depth pattern as :func:`build_amend_edit_effects`.

    Only an ``enter_in_error`` effect is emitted per proposal - no Originate,
    no Commit. The frontend filters the deleted commands out of its working
    array after success; they do not flow into ``/insert-commands``.

    Returns ``(effects, attempted)`` where ``attempted`` carries enough state
    for the API layer to emit a structured audit-log entry. ``display`` is
    intentionally OMITTED from the attempted dict so that the AMEND_EXISTING_
    COMMANDS audit payload never gains a free-text channel for PHI through
    this codepath (the existing whitelist in session_view also defends).
    """
    effects: list[Effect] = []
    attempted: list[dict[str, Any]] = []

    for proposal in proposals:
        section_key = proposal.get("section_key", "")
        command_type = proposal.get("command_type", "")
        old_command_uuid = proposal.get("command_uuid", "")

        if section_key not in EDITABLE_AMEND_SECTIONS:
            log.warning(
                "amend_delete_dropped: section_not_editable section_key=%s command_type=%s",
                section_key,
                command_type,
            )
            continue
        if command_type in NON_EDITABLE_AMEND_COMMAND_TYPES:
            log.warning(
                "amend_delete_dropped: command_type_not_editable section_key=%s command_type=%s",
                section_key,
                command_type,
            )
            continue
        if not old_command_uuid:
            log.warning(
                "amend_delete_dropped: missing_command_uuid section_key=%s command_type=%s",
                section_key,
                command_type,
            )
            continue
        builder = _BUILDERS.get(command_type)
        if builder is None:
            log.warning(
                "amend_delete_dropped: unknown_command_type section_key=%s command_type=%s",
                section_key,
                command_type,
            )
            continue

        data = proposal.get("data", {}) or {}
        command = builder.build(data, note_uuid, old_command_uuid)
        effects.append(command.enter_in_error())
        # HIPAA: deliberately no ``display`` key - the audit-feeding shape
        # must remain free of PHI. The session_view whitelist
        # (_AMEND_AUDIT_ENTRY_KEYS) is the belt-and-suspenders backstop.
        attempted.append(
            {
                "section_key": section_key,
                "command_type": command_type,
                "command_uuid": old_command_uuid,
                "mode": "amend_delete",
            }
        )

    return effects, attempted
