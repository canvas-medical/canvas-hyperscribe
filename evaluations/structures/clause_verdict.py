from __future__ import annotations

from typing import Any, NamedTuple

PROVENANCE_TEMPLATE = "template"
PROVENANCE_ENCOUNTER = "encounter"
PROVENANCE_BLENDED = "blended"
PROVENANCE_UNKNOWN = "unknown"


class ClauseVerdict(NamedTuple):
    """One atomic clinical assertion pulled out of a merged exam row, with a ruling on
    where its wording came from and whether the transcript actually establishes it."""

    row: str
    assertion: str
    provenance: str
    supported: bool
    transcript_citation: str
    contradicted_by: str
    note: str

    def to_json(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "assertion": self.assertion,
            "provenance": self.provenance,
            "supported": self.supported,
            "transcript_citation": self.transcript_citation,
            "contradicted_by": self.contradicted_by,
            "note": self.note,
        }

    @classmethod
    def load_from_json(cls, data: list[dict]) -> list[ClauseVerdict]:
        return [
            cls(
                row=str(item.get("row", "")),
                assertion=str(item.get("assertion", "")),
                provenance=str(item.get("provenance", PROVENANCE_UNKNOWN)),
                supported=bool(item.get("supported", False)),
                transcript_citation=str(item.get("transcript_citation", "") or ""),
                contradicted_by=str(item.get("contradicted_by", "") or ""),
                note=str(item.get("note", "") or ""),
            )
            for item in data
        ]
