from __future__ import annotations

from datetime import datetime, timedelta, UTC

from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.instruction import Instruction

# ATTENTION temporary structure while waiting for a better solution
CACHED: dict[str, CachedDiscussion] = {}


class CachedDiscussion:

    def __init__(self, note_uuid: str) -> None:
        self.created: datetime = datetime.now(UTC)
        self.updated: datetime = self.created
        self.cycle: int = 1
        self.note_uuid = note_uuid
        self.previous_instructions: list[Instruction] = []
        self.previous_transcript: str = ""

    def set_cycle(self, cycle: int) -> None:
        self.updated = datetime.now(UTC)
        self.cycle = cycle

    def creation_day(self) -> str:
        return self.created.date().isoformat()

    @classmethod
    def get_discussion(cls, note_uuid: str) -> CachedDiscussion:
        if note_uuid not in CACHED:
            CACHED[note_uuid] = CachedDiscussion(note_uuid)
        return CACHED[note_uuid]

    @classmethod
    def clear_cache(cls) -> None:
        oldest = datetime.now(UTC) - timedelta(minutes=Constants.DISCUSSION_CACHED_DURATION)
        keys = list(CACHED.keys())
        for note_uuid in keys:
            if CACHED[note_uuid].updated < oldest:
                del CACHED[note_uuid]
