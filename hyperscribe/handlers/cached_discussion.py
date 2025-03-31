from __future__ import annotations

from datetime import datetime, timedelta

from hyperscribe.handlers.constants import Constants
from hyperscribe.structures.instruction import Instruction


# ATTENTION temporary structure while waiting for a better solution
class CachedDiscussion:
    CACHED: dict[str, CachedDiscussion] = {}

    def __init__(self, note_uuid: str) -> None:
        self.created: datetime = datetime.now()
        self.updated: datetime = self.created
        self.count: int = 1
        self.note_uuid = note_uuid
        self.previous_instructions: list[Instruction] = []

    def add_one(self) -> None:
        self.updated = datetime.now()
        self.count = self.count + 1

    def creation_day(self) -> str:
        return self.created.date().isoformat()

    @classmethod
    def get_discussion(cls, note_uuid: str) -> CachedDiscussion:
        if note_uuid not in cls.CACHED:
            cls.CACHED[note_uuid] = CachedDiscussion(note_uuid)
        return cls.CACHED[note_uuid]

    @classmethod
    def clear_cache(cls) -> None:
        oldest = datetime.now() - timedelta(minutes=Constants.DISCUSSION_CACHED_DURATION)
        keys = list(cls.CACHED.keys())
        for note_uuid in keys:
            if cls.CACHED[note_uuid].updated < oldest:
                del cls.CACHED[note_uuid]
