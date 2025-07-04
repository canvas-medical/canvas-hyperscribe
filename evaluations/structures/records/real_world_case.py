from datetime import datetime
from typing import NamedTuple


class RealWorldCase(NamedTuple):
    case_id: int
    customer_identifier: str = ""
    patient_note_hash: str = ""
    topical_exchange_identifier: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    audio_llm_vendor: str = ""
    audio_llm_name: str = ""
    id: int = 0
