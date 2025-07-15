from datetime import datetime, timezone
from unittest.mock import patch, call

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.datastores.postgres.real_world_case import RealWorldCase
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.records.real_world_case import RealWorldCase as Record
from tests.helper import compare_sql


def helper_instance() -> RealWorldCase:
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return RealWorldCase(credentials)


def test_class():
    assert issubclass(RealWorldCase, Postgres)


@patch("evaluations.datastores.postgres.real_world_case.datetime", wraps=datetime)
@patch.object(RealWorldCase, "_alter")
@patch.object(RealWorldCase, "_select")
def test_upsert(select, alter, mock_datetime):
    def reset_mock():
        select.reset_mock()
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 7, 4, 6, 11, 4, 805952, tzinfo=timezone.utc)
    case = Record(
        case_id=741,
        customer_identifier="theCustomerIdentifier",
        patient_note_hash="thePatientNoteHash",
        topical_exchange_identifier="theTopicalExchangeIdentifier",
        publishable=True,
        start_time=31.25,
        end_time=74.36,
        duration=43.11,
        audio_llm_vendor="theAudioLlmVendor",
        audio_llm_name="theAudioLlmName",
        id=333,
    )
    expected = Record(
        case_id=741,
        customer_identifier="theCustomerIdentifier",
        patient_note_hash="thePatientNoteHash",
        topical_exchange_identifier="theTopicalExchangeIdentifier",
        publishable=True,
        start_time=31.25,
        end_time=74.36,
        duration=43.11,
        audio_llm_vendor="theAudioLlmVendor",
        audio_llm_name="theAudioLlmName",
        id=351,
    )

    tested = helper_instance()
    # insert
    select.side_effect = [[]]
    alter.side_effect = [351]
    mock_datetime.now.side_effect = [date_0]

    result = tested.upsert(case)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    exp_sql = 'SELECT "id" FROM "real_world_case" WHERE "case_id"=%(case_id)s'
    assert compare_sql(sql, exp_sql)
    exp_params = {"case_id": 741}
    assert params == exp_params
    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = ('INSERT INTO "real_world_case" ("created", "updated", "case_id", "customer_identifier", '
               ' "patient_note_hash", "topical_exchange_identifier", "publishable", "start_time", "end_time", '
               ' "duration", "audio_llm_vendor", "audio_llm_name") '
               'VALUES (%(now)s, %(now)s, %(case_id)s, %(customer_identifier)s, '
               ' %(patient_note_hash)s, %(topical_exchange_identifier)s, %(publishable)s, %(start_time)s, %(end_time)s, '
               ' %(duration)s, %(audio_llm_vendor)s, %(audio_llm_name)s) '
               'RETURNING id')
    assert compare_sql(sql, exp_sql)
    exp_params = {
        'audio_llm_name': 'theAudioLlmName',
        'audio_llm_vendor': 'theAudioLlmVendor',
        'case_id': 741,
        'customer_identifier': 'theCustomerIdentifier',
        'duration': 43.11,
        'end_time': 74.36,
        'now': date_0,
        'patient_note_hash': 'thePatientNoteHash',
        'start_time': 31.25,
        'topical_exchange_identifier': 'theTopicalExchangeIdentifier',
        'publishable': True,
    }
    assert params == exp_params
    assert involved_id is None
    reset_mock()

    # update
    select.side_effect = [[{"id": 147}]]
    alter.side_effect = [351]
    mock_datetime.now.side_effect = [date_0]

    result = tested.upsert(case)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    exp_sql = 'SELECT "id" FROM "real_world_case" WHERE "case_id"=%(case_id)s'
    assert compare_sql(sql, exp_sql)
    exp_params = {"case_id": 741}
    assert params == exp_params
    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = ('UPDATE "real_world_case" SET "updated"=%(now)s, "customer_identifier"=%(customer_identifier)s, '
               ' "patient_note_hash"=%(patient_note_hash)s, "topical_exchange_identifier"=%(topical_exchange_identifier)s, '
               ' "publishable"=%(publishable)s, "start_time"=%(start_time)s, "end_time"=%(end_time)s, "duration"=%(duration)s, '
               ' "audio_llm_vendor"=%(audio_llm_vendor)s, "audio_llm_name"=%(audio_llm_name)s '
               'WHERE "id" = %(id)s AND ( '
               ' "customer_identifier" <> %(customer_identifier)s OR '
               ' "patient_note_hash" <> %(patient_note_hash)s OR '
               ' "topical_exchange_identifier" <> %(topical_exchange_identifier)s OR '
               ' "publishable" <> %(publishable)s OR '
               ' "start_time" <> %(start_time)s OR '
               ' "end_time" <> %(end_time)s OR '
               ' "duration" <> %(duration)s OR '
               ' "audio_llm_vendor" <> %(audio_llm_vendor)s OR '
               ' "audio_llm_name" <> %(audio_llm_name)s)')
    assert compare_sql(sql, exp_sql)
    exp_params = {
        'audio_llm_name': 'theAudioLlmName',
        'audio_llm_vendor': 'theAudioLlmVendor',
        'case_id': 741,
        'customer_identifier': 'theCustomerIdentifier',
        'duration': 43.11,
        'end_time': 74.36,
        'id': 147,
        'now': date_0,
        'patient_note_hash': 'thePatientNoteHash',
        'start_time': 31.25,
        'topical_exchange_identifier': 'theTopicalExchangeIdentifier',
        'publishable': True,
    }
    assert params == exp_params
    assert involved_id == 147
    reset_mock()

