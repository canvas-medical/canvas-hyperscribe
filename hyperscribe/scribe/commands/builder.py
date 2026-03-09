from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.history_present_illness import HistoryOfPresentIllnessCommand
from canvas_sdk.commands.commands.plan import PlanCommand
from canvas_sdk.commands.commands.reason_for_visit import ReasonForVisitCommand
from canvas_sdk.effects import Effect


def _build_hpi(data: dict[str, Any], note_uuid: str) -> _BaseCommand:
    return HistoryOfPresentIllnessCommand(
        narrative=str(data.get("narrative", "")),
        note_uuid=note_uuid,
    )


def _build_plan(data: dict[str, Any], note_uuid: str) -> _BaseCommand:
    return PlanCommand(
        narrative=str(data.get("narrative", "")),
        note_uuid=note_uuid,
    )


def _build_rfv(data: dict[str, Any], note_uuid: str) -> _BaseCommand:
    return ReasonForVisitCommand(
        comment=str(data.get("comment", "")),
        note_uuid=note_uuid,
    )


_BUILDERS = {
    "hpi": _build_hpi,
    "plan": _build_plan,
    "rfv": _build_rfv,
}


def build_effects(proposals: list[dict[str, Any]], note_uuid: str) -> list[Effect]:
    """Convert selected command proposals into Canvas SDK Effects."""
    effects: list[Effect] = []
    for proposal in proposals:
        builder = _BUILDERS.get(proposal.get("command_type", ""))
        if builder is None:
            continue
        command = builder(proposal.get("data", {}), note_uuid)
        effects.append(command.originate())
    return effects
