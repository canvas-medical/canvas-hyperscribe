from datetime import datetime, UTC
from typing import LiteralString

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.records.real_world_case import RealWorldCase as Record


class RealWorldCase(Postgres):
    def upsert(self, case: Record) -> Record:
        params = {
            "now": datetime.now(UTC),
            "case_id": case.case_id,
            "customer_identifier": case.customer_identifier,
            "patient_note_hash": case.patient_note_hash,
            "topical_exchange_identifier": case.topical_exchange_identifier,
            "publishable": case.publishable,
            "start_time": case.start_time,
            "end_time": case.end_time,
            "duration": case.duration,
            "audio_llm_vendor": case.audio_llm_vendor,
            "audio_llm_name": case.audio_llm_name,
        }
        sql: LiteralString = 'SELECT "id" FROM "real_world_case" WHERE "case_id"=%(case_id)s'
        involved_id: int | None = None
        for record in self._select(sql, {"case_id": case.case_id}):
            involved_id = record["id"]
            params["id"] = record["id"]
            sql = """
                  UPDATE "real_world_case"
                  SET "updated"=%(now)s,
                      "customer_identifier"=%(customer_identifier)s,
                      "patient_note_hash"=%(patient_note_hash)s,
                      "topical_exchange_identifier"=%(topical_exchange_identifier)s,
                      "publishable"=%(publishable)s,
                      "start_time"=%(start_time)s,
                      "end_time"=%(end_time)s,
                      "duration"=%(duration)s,
                      "audio_llm_vendor"=%(audio_llm_vendor)s,
                      "audio_llm_name"=%(audio_llm_name)s
                  WHERE "id" = %(id)s
                    AND (
                      "customer_identifier" <> %(customer_identifier)s OR
                      "patient_note_hash" <> %(patient_note_hash)s OR
                      "topical_exchange_identifier" <> %(topical_exchange_identifier)s OR
                      "publishable" <> %(publishable)s OR
                      "start_time" <> %(start_time)s OR
                      "end_time" <> %(end_time)s OR
                      "duration" <> %(duration)s OR
                      "audio_llm_vendor" <> %(audio_llm_vendor)s OR
                      "audio_llm_name" <> %(audio_llm_name)s)"""
            break
        else:
            sql = """
                  INSERT INTO "real_world_case" ("created", "updated", "case_id", "customer_identifier",
                                                 "patient_note_hash", "topical_exchange_identifier", "publishable",
                                                 "start_time", "end_time", "duration", "audio_llm_vendor",
                                                 "audio_llm_name")
                  VALUES (%(now)s, %(now)s, %(case_id)s, %(customer_identifier)s,
                          %(patient_note_hash)s, %(topical_exchange_identifier)s, %(publishable)s,
                          %(start_time)s, %(end_time)s, %(duration)s, %(audio_llm_vendor)s,
                          %(audio_llm_name)s) RETURNING id"""

        return Record(
            id=self._alter(sql, params, involved_id),
            case_id=case.case_id,
            customer_identifier=case.customer_identifier,
            patient_note_hash=case.patient_note_hash,
            topical_exchange_identifier=case.topical_exchange_identifier,
            publishable=case.publishable,
            start_time=case.start_time,
            end_time=case.end_time,
            duration=case.duration,
            audio_llm_vendor=case.audio_llm_vendor,
            audio_llm_name=case.audio_llm_name,
        )
