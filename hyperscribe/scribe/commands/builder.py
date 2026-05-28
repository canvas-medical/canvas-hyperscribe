from __future__ import annotations

import json
import time
import uuid
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.effects import Effect
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.note import Note
from logger import log
from pydantic import ValidationError

from hyperscribe.scribe.backend.models import CommandProposal
from hyperscribe.scribe.commands.adjust_prescription import AdjustPrescriptionParser
from hyperscribe.scribe.commands.allergy import AllergyParser
from hyperscribe.scribe.commands.assess import AssessParser
from hyperscribe.scribe.commands.base import CommandParser
from hyperscribe.scribe.commands.carry_forward import carry_forward_assess_background
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


def prefill_assess_backgrounds(proposals: list[dict[str, Any]], note_uuid: str) -> None:
    """Pre-fill ``background`` on assess proposals from the most recent prior
    signed Assessment for the same (patient, condition).

    Mutates ``proposals[i]["data"]["background"]`` in place. Skips silently
    when the note can't be loaded, when no assess proposals are present, or
    when the lookup fails — the carry-forward is a convenience, not a
    correctness gate; a missing background just means the provider types it
    fresh.

    Called from ``session_view`` parallel to ``annotate_duplicates`` rather
    than from inside ``build_effects`` so that the side-effect (mutating
    ``proposals``) is visible at the same layer as the other proposal
    transformations. See ``carry_forward_assess_background`` for the
    per-(patient, condition) scoping rationale.
    """
    if not note_uuid:
        return
    assess_proposals = [p for p in proposals if p.get("command_type") == "assess"]
    if not assess_proposals:
        return
    try:
        # ``ValueError`` covers a malformed UUID passed as ``note_uuid`` (e.g.
        # an LLM-injected non-uuid string). Django raises before reaching the
        # SQL layer, and the carry-forward contract is best-effort — silently
        # skip rather than propagate up into the request handler.
        note = Note.objects.select_related("patient").get(id=note_uuid)
    except (Note.DoesNotExist, ValueError):
        return
    for proposal in assess_proposals:
        data = proposal.get("data")
        if not isinstance(data, dict):
            continue
        carry_forward_assess_background(data, note)


def prefill_assess_backgrounds_for_proposals(proposals: list[CommandProposal], note_uuid: str) -> None:
    """``CommandProposal``-shaped variant of :func:`prefill_assess_backgrounds`.

    Identical contract and side effect: mutates ``proposal.data["background"]``
    in place for every assess proposal whose (patient, condition) has a prior
    signed Assessment. Exists as a parallel callable because the upstream
    callers in ``session_view`` (``/extract-commands``, ``/recommend-commands``,
    ``post_generate_summary`` step 2, and the recommend branch within it) hold
    ``list[CommandProposal]`` at the same point ``annotate_duplicates`` is
    invoked. Hoisting the dict conversion just to call the dict-shaped helper
    would break the symmetric placement (parallel to ``annotate_duplicates``)
    the carry-forward design relies on.

    Same defensive skips: empty ``note_uuid``, no assess proposals, note lookup
    failure, malformed UUID.
    """
    if not note_uuid:
        return
    assess_proposals = [p for p in proposals if p.command_type == "assess"]
    if not assess_proposals:
        return
    try:
        note = Note.objects.select_related("patient").get(id=note_uuid)
    except (Note.DoesNotExist, ValueError):
        return
    for proposal in assess_proposals:
        # CommandProposal.data is typed dict[str, Any] (see backend/models.py),
        # so we skip the isinstance guard that the dict-shaped sibling uses for
        # defensive parsing of untrusted JSON.
        carry_forward_assess_background(proposal.data, note)


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


_METADATA_DB_WAIT_ATTEMPTS = 6
_METADATA_DB_WAIT_INTERVAL_SECONDS = 0.25


def _wait_for_command_in_note(command_uuid: str, note_uuid: str) -> bool:
    """Poll the DB for a just-committed command, scoped to a specific note.

    Phase 1 returns the originate/commit effects with the API response; Canvas
    then applies them asynchronously. The SDK's upsert_metadata runs a *synchronous*
    DB existence check at effect-build time (see canvas_sdk.effects.command_metadata.base),
    so without this wait the second request often races phase 1 and the validator
    raises before any effect leaves the plugin.

    The query filters on BOTH `id=command_uuid` AND `note__id=note_uuid` so the
    same retry serves two concerns simultaneously: visibility (race tolerance)
    and authorization (per-item note scoping). Foreign command_uuids never
    appear in this scoped filter and are correctly rejected after the retry
    cap. Race-delayed legitimate commands appear once Canvas finishes applying
    phase-1's commit effects.

    The .exists() call is wrapped defensively: a transient ORM exception
    (connection drop, transaction abort, pool exhaustion) on a single check
    must NOT escape and 500 the whole /insert-metadata batch. A ValidationError
    (e.g. malformed UUID string from a direct API caller) is treated identically
    to "not visible" so a bad input can't crash a legitimate batch. Treat any
    failure as "not yet visible" and retry through the existing cap; if every
    retry hits the same fault, return False so the caller's per-item
    try/except path drops just that one item with a logged warning instead
    of taking down every alert_facility write in the batch.
    """
    for attempt in range(_METADATA_DB_WAIT_ATTEMPTS):
        try:
            visible = Command.objects.filter(id=command_uuid, note__id=note_uuid).exists()
        except Exception:
            log.exception(
                "metadata: existence check failed for %s in note %s (attempt %d)",
                command_uuid,
                note_uuid,
                attempt,
            )
            visible = False
        if visible:
            if attempt > 0:
                log.info("metadata: command %s visible after %d retries", command_uuid, attempt)
            return True
        time.sleep(_METADATA_DB_WAIT_INTERVAL_SECONDS)
    return False


def build_metadata_effects(
    pending: list[dict[str, Any]], note_uuid: str
) -> tuple[list[Effect], int]:
    """Phase 2: build upsert_metadata effects for commands that exist on the
    authorized note.

    The per-item `_wait_for_command_in_note` check serves as both the
    visibility wait (race tolerance for phase-1's async commit application)
    and the per-item authorization check (the command must belong to
    `note_uuid`). A foreign command_uuid will never appear in the scoped
    filter and is rejected after the retry cap; a race-delayed legitimate
    command will appear once Canvas catches up and proceeds normally.

    The authorized `note_uuid` is also what's passed to `build_stub` —
    each item's `note_uuid` field is ignored as a defense-in-depth measure
    against a client trying to smuggle a different note_uuid into the
    downstream SDK call.

    Each item is processed defensively: if the command is not yet visible
    after a bounded wait, or if the SDK's upsert validation fails for any
    reason, we log and skip rather than 500'ing the entire batch.

    Returns `(effects, rejected_count)`. `rejected_count` is the number of
    items dropped due to visibility/scope failure, malformed input, or SDK
    exceptions — used by the API layer for audit observability.
    """
    effects: list[Effect] = []
    rejected = 0
    for item in pending:
        command_type = item.get("command_type", "")
        command_uuid = str(item.get("command_uuid", ""))
        metadata = item.get("metadata", {}) or {}

        builder = _BUILDERS.get(command_type)
        if builder is None:
            log.warning("metadata: unknown command_type=%r (uuid=%s)", command_type, command_uuid)
            rejected += 1
            continue
        if not command_uuid or not metadata:
            log.warning("metadata: skipping malformed item: %r", item)
            rejected += 1
            continue

        if not _wait_for_command_in_note(command_uuid, note_uuid):
            log.warning(
                "metadata: command %s (%s) not visible in note %s after %d attempts; "
                "skipping upsert of %s",
                command_uuid,
                command_type,
                note_uuid,
                _METADATA_DB_WAIT_ATTEMPTS,
                list(metadata.keys()),
            )
            rejected += 1
            continue

        try:
            # Always use the authorized note_uuid, never the item's. This
            # decouples the downstream build_stub call from any client-supplied
            # note_uuid that might disagree with the authorized one.
            command = builder.build_stub(command_uuid, note_uuid)
            for key, value in metadata.items():
                effects.append(command.upsert_metadata(key, value))
                log.info(
                    "metadata: queued upsert command=%s type=%s key=%s value=%s",
                    command_uuid,
                    command_type,
                    key,
                    value,
                )
        except Exception:
            log.exception(
                "metadata: upsert_metadata failed for command=%s type=%s keys=%s",
                command_uuid,
                command_type,
                list(metadata.keys()),
            )
            rejected += 1
    return effects, rejected
