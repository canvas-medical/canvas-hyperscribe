from __future__ import annotations

from typing import NamedTuple


class IdentificationParameters(NamedTuple):
    patient_uuid: str
    note_uuid: str
    provider_uuid: str
    canvas_instance: str
