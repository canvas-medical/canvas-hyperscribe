from datetime import datetime, UTC

from logger import log


class MemoryLog:
    ENTRIES: dict[str, dict[str, list[str]]] = {}

    @classmethod
    def begin_session(cls, note_uuid: str) -> None:
        if note_uuid not in cls.ENTRIES:
            cls.ENTRIES[note_uuid] = {}

    @classmethod
    def end_session(cls, note_uuid: str) -> str:
        if note_uuid not in cls.ENTRIES:
            return ""
        return "\n".join([
            "\n".join(l)
            for l in sorted(
                [e for e in cls.ENTRIES.pop(note_uuid).values() if e],
                key=lambda v: v[0],
            )
        ])

    def __init__(self, note_uuid: str, label: str) -> None:
        self.note_uuid = note_uuid
        self.label = label
        if self.note_uuid not in self.ENTRIES:
            self.ENTRIES[self.note_uuid] = {}
        if label not in self.ENTRIES[self.note_uuid]:
            self.ENTRIES[self.note_uuid][self.label] = []

    def log(self, message: str) -> None:
        self.ENTRIES[self.note_uuid][self.label].append(f"{datetime.now(UTC).isoformat()}: {message}")

    def output(self, message: str) -> None:
        self.log(message)
        log.info(message)

    def logs(self) -> str:
        return "\n".join(self.ENTRIES[self.note_uuid][self.label])
