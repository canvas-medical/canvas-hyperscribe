from __future__ import annotations

from typing import NamedTuple


class IdentificationParameters(NamedTuple):
    patient_uuid: str
    note_uuid: str
    provider_uuid: str
    canvas_instance: str

    def canvas_host(self) -> str:
        result = f"https://{self.canvas_instance}"
        if self.canvas_instance == "local":
            result = "http://localhost:8000"
        return result
