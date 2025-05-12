from __future__ import annotations

from datetime import datetime, UTC
from typing import NamedTuple


class CommentBody(NamedTuple):
    chunk_index: int
    note_id: str
    patient_id: str
    created: datetime
    finished: datetime | None

    def to_dict(self) -> dict:
        return {
            "chunk_index": self.chunk_index,
            "note_id": self.note_id,
            "patient_id": self.patient_id,
            "created": self.created.isoformat(),
            "finished": self.finished.isoformat() if isinstance(self.finished, datetime) else None,
        }

    @classmethod
    def load_from_json(cls, data: dict) -> CommentBody:
        return cls(
            chunk_index=data["chunk_index"],
            note_id=data["note_id"],
            patient_id=data.get("patient_id", ""),
            created=datetime.fromisoformat(created) if (created := data.get("created")) else datetime.now(UTC),
            finished=datetime.fromisoformat(finished) if (finished := data.get("finished")) else None,
        )
