from datetime import datetime, UTC
from typing import LiteralString

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.records.synthetic_case import SyntheticCase as SyntheticCaseRecord


class SyntheticCase(Postgres):
    def upsert(self, case: SyntheticCaseRecord) -> SyntheticCaseRecord:
        params = {
            "now": datetime.now(UTC),
            "case_id": case.case_id,
            "category": case.category,
            "turn_total": case.turn_total,
            "speaker_sequence": self.constant_dumps(case.speaker_sequence),
            "clinician_to_patient_turn_ratio": case.clinician_to_patient_turn_ratio,
            "mood": [mood.value for mood in case.mood],
            "pressure": case.pressure.value,
            "clinician_style": case.clinician_style.value,
            "patient_style": case.patient_style.value,
            "turn_buckets": case.turn_buckets.value,
            "text_llm_vendor": case.text_llm_vendor,
            "text_llm_name": case.text_llm_name,
            "temperature": case.temperature,
        }

        sql: LiteralString = 'SELECT "id" FROM "synthetic_case" WHERE "case_id" = %(case_id)s'
        involved_id: int | None = None
        for record in self._select(sql, {"case_id": case.case_id}):
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
                    "text_llm_vendor" = %(text_llm_vendor)s,
                    "text_llm_name" = %(text_llm_name)s,
                    "temperature"   = %(temperature)s
                WHERE "id" = %(id)s
            """
            break
        else:
            sql = """
                INSERT INTO "synthetic_case" (
                    "created", "updated", "case_id", "category", "turn_total", "speaker_sequence",
                    "clinician_to_patient_turn_ratio", "mood", "pressure",
                    "clinician_style", "patient_style", "turn_buckets",
                    "text_llm_vendor", "text_llm_name", "temperature"
                )
                VALUES (
                    %(now)s, %(now)s, %(case_id)s, %(category)s, %(turn_total)s, %(speaker_sequence)s,
                    %(clinician_to_patient_turn_ratio)s, %(mood)s, %(pressure)s,
                    %(clinician_style)s, %(patient_style)s, %(turn_buckets)s,
                    %(text_llm_vendor)s, %(text_llm_name)s, %(temperature)s
                )
                RETURNING id
            """

        return SyntheticCaseRecord(
            id=self._alter(sql, params, involved_id),
            case_id=case.case_id,
            category=case.category,
            turn_total=case.turn_total,
            speaker_sequence=case.speaker_sequence,
            clinician_to_patient_turn_ratio=case.clinician_to_patient_turn_ratio,
            mood=case.mood,
            pressure=case.pressure,
            clinician_style=case.clinician_style,
            patient_style=case.patient_style,
            turn_buckets=case.turn_buckets,
            duration=case.duration,
            text_llm_vendor=case.text_llm_vendor,
            text_llm_name=case.text_llm_name,
            temperature=case.temperature,
        )
