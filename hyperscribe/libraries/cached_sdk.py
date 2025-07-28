from __future__ import annotations

from datetime import datetime, UTC

from canvas_sdk.caching.plugins import get_cache

from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.line import Line

# ATTENTION the SDK cache is limited to the plugin environment
CACHED: dict[str, dict] = {}


class CachedSdk:
    def __init__(self, note_uuid: str) -> None:
        self.created: datetime = datetime.now(UTC)
        self.updated: datetime = self.created
        self.cycle: int = 1
        self.note_uuid = note_uuid
        self.previous_instructions: list[Instruction] = []
        self.previous_transcript: list[Line] = []

    def set_cycle(self, cycle: int) -> None:
        self.updated = datetime.now(UTC)
        self.cycle = cycle
        self.save()

    def creation_day(self) -> str:
        return self.created.date().isoformat()

    def save(self) -> None:
        sdk_cache = get_cache()
        if sdk_cache is None:
            CACHED[self.note_uuid] = self.to_json()
        else:
            sdk_cache.set(self.note_uuid, self.to_json())

    def to_json(self) -> dict:
        return {
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "cycle": self.cycle,
            "note_uuid": self.note_uuid,
            "previous_instructions": [instruction.to_json(False) for instruction in self.previous_instructions],
            "previous_transcript": [line.to_json() for line in self.previous_transcript],
        }

    @classmethod
    def get_discussion(cls, note_uuid: str) -> CachedSdk:
        sdk_cache = get_cache()
        if sdk_cache is None:
            sdk_cache = CACHED

        if cached := sdk_cache.get(note_uuid):
            return CachedSdk.load_from_json(cached)
        return CachedSdk(note_uuid)

    @classmethod
    def load_from_json(cls, dictionary: dict) -> CachedSdk:
        result = CachedSdk(dictionary["note_uuid"])
        result.created = datetime.fromisoformat(dictionary["created"])
        result.updated = datetime.fromisoformat(dictionary["updated"])
        result.cycle = dictionary["cycle"]
        result.previous_instructions = Instruction.load_from_json(dictionary["previous_instructions"])
        result.previous_transcript = Line.load_from_json(dictionary["previous_transcript"])
        return result
