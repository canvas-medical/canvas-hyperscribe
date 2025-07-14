#PLACEHOLDER FOR NOW–COPIES CASE.PY HEAVILY AND WILL BE EDITED, JUST BEING USED AS PLACEHOLDER TO TEST PIPELINE.
from datetime import datetime, UTC
from typing import LiteralString

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.records.synthetic_case import SyntheticCase as Record


class SyntheticCase(Postgres):
    def get_case_id(self, case_id: int) -> int:
        sql: LiteralString = 'SELECT "id" FROM "synthetic_case" WHERE "case_id" = %(case_id)s'
        for record in self._select(sql, {"case_id": case_id}):
            return int(record["id"])
        return 0

    def get_synthetic_case(self, case_id: int) -> Record:
        sql: LiteralString = """
            SELECT "id", "case_id", "category", "turn_total", "speaker_sequence",
                   "clinician_to_patient_turn_ratio", "mood", "pressure",
                   "clinician_style", "patient_style", "turn_buckets", "duration",
                   "audio_llm_vendor", "audio_llm_name"
            FROM "synthetic_case"
            WHERE "case_id" = %(case_id)s
        """
        for record in self._select(sql, {"case_id": case_id}):
            return Record.load_record(record)
        raise ValueError(f"No synthetic_case found for case_id={case_id}")

    def upsert(self, sc: Record) -> Record:
        params = {
            "now": datetime.now(UTC),
            "case_id": sc.case_id,
            "category": sc.category,
            "turn_total": sc.turn_total,
            "speaker_sequence": self.constant_dumps(sc.speaker_sequence),
            "clinician_to_patient_turn_ratio": sc.clinician_to_patient_turn_ratio,
            "mood": sc.mood.value,
            "pressure": sc.pressure.value,
            "clinician_style": sc.clinician_style.value,
            "patient_style": sc.patient_style.value,
            "turn_buckets": sc.turn_buckets.value,
            "duration": sc.duration,
            "text_llm_vendor": sc.text_llm_vendor,
            "text_llm_name": sc.text_llm_name,
        }

        sql: LiteralString = 'SELECT "id" FROM "synthetic_case" WHERE "case_id" = %(case_id)s'
        involved_id: int | None = None

        for record in self._select(sql, {"case_id": sc.case_id}):
            involved_id = record["id"]
            params["id"] = involved_id
            sql = """
                UPDATE "synthetic_case"
                SET "updated" = %(now)s,
                    "category" = %(category)s,
                    "turn_total" = %(turn_total)s,
                    "speaker_sequence" = %(speaker_sequence)s,
                    "clinician_to_patient_turn_ratio" = %(clinician_to_patient_turn_ratio)s,
                    "mood" = %(mood)s,
                    "pressure" = %(pressure)s,
                    "clinician_style" = %(clinician_style)s,
                    "patient_style" = %(patient_style)s,
                    "turn_buckets" = %(turn_buckets)s,
                    "duration" = %(duration)s,
                    "text_llm_vendor" = %(text_llm_vendor)s,
                    "text_llm_name" = %(text_llm_name)s
                WHERE "id" = %(id)s
            """
            break
        else:
            sql = """
                INSERT INTO "synthetic_case"
                    ("created", "updated", "case_id", "category", "turn_total", "speaker_sequence",
                    "clinician_to_patient_turn_ratio", "mood", "pressure", "clinician_style",
                    "patient_style", "turn_buckets", "duration", "text_llm_vendor", "text_llm_name")
                VALUES
                    (%(now)s, %(now)s, %(case_id)s, %(category)s, %(turn_total)s, %(speaker_sequence)s,
                    %(clinician_to_patient_turn_ratio)s, %(mood)s, %(pressure)s, %(clinician_style)s,
                    %(patient_style)s, %(turn_buckets)s, %(duration)s, %(text_llm_vendor)s, %(text_llm_name)s)
                RETURNING id
            """

        return Record(
            id=self._alter(sql, params, involved_id),
            case_id=sc.case_id,
            category=sc.category,
            turn_total=sc.turn_total,
            speaker_sequence=sc.speaker_sequence,
            clinician_to_patient_turn_ratio=sc.clinician_to_patient_turn_ratio,
            mood=sc.mood,
            pressure=sc.pressure,
            clinician_style=sc.clinician_style,
            patient_style=sc.patient_style,
            turn_buckets=sc.turn_buckets,
            duration=sc.duration,
            text_llm_vendor=sc.text_llm_vendor,
            text_llm_name=sc.text_llm_name,
        )

