from __future__ import annotations

from canvas_sdk.caching.plugins import get_cache


class StopAndGo:
    def __init__(self, note_uuid: str) -> None:
        self.note_uuid = note_uuid
        self.is_paused: bool = False
        self.is_ended: bool = False
        self.cycle: int = 1

    def save(self) -> None:
        get_cache().set(f"stopAndGo:{self.note_uuid}", self.to_json())

    def to_json(self) -> dict:
        return {
            "noteUuid": self.note_uuid,
            "isPaused": self.is_paused,
            "isEnded": self.is_ended,
            "cycle": self.cycle,
        }

    @classmethod
    def get(cls, note_uuid: str) -> StopAndGo:
        if cached := get_cache().get(f"stopAndGo:{note_uuid}"):
            return StopAndGo.load_from_json(cached)
        return StopAndGo(note_uuid)

    @classmethod
    def load_from_json(cls, dictionary: dict) -> StopAndGo:
        result = StopAndGo(dictionary["noteUuid"])
        result.is_paused = dictionary["isPaused"]
        result.is_ended = dictionary["isEnded"]
        result.cycle = dictionary["cycle"]
        return result
