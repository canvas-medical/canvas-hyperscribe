from __future__ import annotations

from canvas_sdk.caching.plugins import get_cache
from canvas_sdk.effects import Effect


class StopAndGo:
    def __init__(self, note_uuid: str) -> None:
        self.note_uuid = note_uuid
        self._is_running: bool = False
        self._is_paused: bool = False
        self._is_ended: bool = False
        self._cycle: int = 1
        self._paused_effects: list[Effect] = []

    def is_running(self) -> bool:
        return self._is_running

    def is_paused(self) -> bool:
        return self._is_paused

    def is_ended(self) -> bool:
        return self._is_ended

    def cycle(self) -> int:
        return self._cycle

    def paused_effects(self) -> list[Effect]:
        return self._paused_effects

    def set_running(self, is_running: bool) -> None:
        self._is_running = is_running

    def set_paused(self, is_paused: bool) -> None:
        self._is_paused = is_paused

    def set_ended(self, is_ended: bool) -> None:
        self._is_ended = is_ended

    def set_cycle(self, cycle: int) -> None:
        self._cycle = cycle

    def add_paused_effect(self, effect: Effect) -> None:
        self._paused_effects.append(effect)

    def reset_paused_effect(self) -> None:
        self._paused_effects = []

    def save(self) -> None:
        get_cache().set(f"stopAndGo:{self.note_uuid}", self.to_json())

    def to_json(self) -> dict:
        return {
            "noteUuid": self.note_uuid,
            "isRunning": self._is_running,
            "isPaused": self._is_paused,
            "isEnded": self._is_ended,
            "cycle": self._cycle,
            "pausedEffects": [{"type": effect.type, "payload": effect.payload} for effect in self._paused_effects],
        }

    @classmethod
    def get(cls, note_uuid: str) -> StopAndGo:
        if cached := get_cache().get(f"stopAndGo:{note_uuid}"):
            return StopAndGo.load_from_json(cached)
        return StopAndGo(note_uuid)

    @classmethod
    def load_from_json(cls, dictionary: dict) -> StopAndGo:
        result = StopAndGo(dictionary["noteUuid"])
        result._is_running = dictionary["isRunning"]
        result._is_paused = dictionary["isPaused"]
        result._is_ended = dictionary["isEnded"]
        result._cycle = dictionary["cycle"]
        result._paused_effects = [
            Effect(type=effect["type"], payload=effect["payload"]) for effect in dictionary["pausedEffects"]
        ]
        return result
