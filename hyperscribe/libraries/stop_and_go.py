from __future__ import annotations

from datetime import UTC, datetime
from time import sleep

from canvas_sdk.caching.plugins import get_cache
from canvas_sdk.effects import Effect
from logger import log

from hyperscribe.libraries.constants import Constants


class StopAndGo:
    def __init__(self, note_uuid: str) -> None:
        self.note_uuid = note_uuid
        self._created = datetime.now(UTC)
        self._is_running: bool = False
        self._is_paused: bool = False
        self._is_ended: bool = False
        self._cycle: int = 0
        self._paused_effects: list[Effect] = []
        self._waiting_cycles: list[int] = []
        self._delay: int = 0  # seconds to wait when set

    def created(self) -> datetime:
        return self._created

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

    def set_running(self, is_running: bool) -> StopAndGo:
        self._is_running = is_running
        return self

    def set_paused(self, is_paused: bool) -> StopAndGo:
        self._is_paused = is_paused
        return self

    def set_ended(self, is_ended: bool) -> StopAndGo:
        self._is_ended = is_ended
        return self

    def set_cycle(self, cycle: int) -> StopAndGo:
        self._cycle = cycle
        return self

    def add_paused_effects(self, effects: list[Effect]) -> StopAndGo:
        self._paused_effects.extend(effects)
        return self

    def reset_paused_effect(self) -> StopAndGo:
        self._paused_effects = []
        return self

    def add_waiting_cycle(self) -> StopAndGo:
        next_cycle = self._cycle + 1
        if self._waiting_cycles:
            next_cycle = self._waiting_cycles[-1] + 1
        self._waiting_cycles.append(next_cycle)

        if self._is_running and len(self._waiting_cycles) >= Constants.STUCK_SESSION_WAITING_CYCLES_THRESHOLD:
            self._is_running = False
            log.warning(
                f"Stuck session detected for note {self.note_uuid}: "
                f"cycle={self.cycle()}, "
                f"waiting={self.waiting_cycles()}, "
                f"created={self.created().isoformat()}"
            )

        return self

    def consume_next_waiting_cycles(self, save: bool) -> bool:
        if self._waiting_cycles:
            self._cycle = self._waiting_cycles.pop(0)
            if save:
                self.save()
            return True
        return False

    def waiting_cycles(self) -> list[int]:
        return self._waiting_cycles

    def set_delay(self) -> StopAndGo:
        self._delay = 1  # arbitrary number of seconds (e.g., to let the backend process the effects)
        return self

    def consume_delay(self) -> None:
        if self._delay > 0:
            sleep(self._delay)
        self._delay = 0

    def save(self) -> None:
        get_cache().set(f"stopAndGo:{self.note_uuid}", self.to_json())

    def to_json(self) -> dict:
        return {
            "noteUuid": self.note_uuid,
            "created": self._created.isoformat(),
            "isRunning": self._is_running,
            "isPaused": self._is_paused,
            "isEnded": self._is_ended,
            "cycle": self._cycle,
            "pausedEffects": [{"type": effect.type, "payload": effect.payload} for effect in self._paused_effects],
            "waitingCycles": self._waiting_cycles,
            "delay": self._delay,
        }

    @classmethod
    def get(cls, note_uuid: str) -> StopAndGo:
        if cached := get_cache().get(f"stopAndGo:{note_uuid}"):
            return StopAndGo.load_from_json(cached)
        return StopAndGo(note_uuid)

    @classmethod
    def load_from_json(cls, dictionary: dict) -> StopAndGo:
        result = StopAndGo(dictionary["noteUuid"])
        result._created = datetime.fromisoformat(dictionary["created"])
        result._is_running = dictionary["isRunning"]
        result._is_paused = dictionary["isPaused"]
        result._is_ended = dictionary["isEnded"]
        result._cycle = dictionary["cycle"]
        result._paused_effects = [
            Effect(type=effect["type"], payload=effect["payload"]) for effect in dictionary["pausedEffects"]
        ]
        result._waiting_cycles = dictionary["waitingCycles"]
        result._delay = dictionary["delay"]
        return result
