from datetime import datetime, timezone
from unittest.mock import patch, call

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.datastores.postgres.synthetic_case import SyntheticCase
from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle
from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood
from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle
from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.records.synthetic_case import SyntheticCase as SyntheticCaseRecord
from tests.helper import compare_sql


def helper_instance() -> SyntheticCase:
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return SyntheticCase(credentials)


def test_class():
    assert issubclass(SyntheticCase, Postgres)


@patch("evaluations.datastores.postgres.synthetic_case.datetime", wraps=datetime)
@patch.object(SyntheticCase, "_alter")
@patch.object(SyntheticCase, "_select")
def test_upsert(select, alter, mock_datetime):
    def reset_mock():
        select.reset_mock()
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 7, 4, 6, 11, 4, 805952, tzinfo=timezone.utc)
    case = SyntheticCaseRecord(
        case_id=123,
        category="theCategory",
        turn_total=4,
        speaker_sequence=["Clinician", "Patient", "Patient", "Clinician"],
        clinician_to_patient_turn_ratio=1.0,
        mood=[SyntheticCaseMood.PATIENT_FRUSTRATED],
        pressure=SyntheticCasePressure.TIME_PRESSURE,
        clinician_style=SyntheticCaseClinicianStyle.CAUTIOUS_INQUISITIVE,
        patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        turn_buckets=SyntheticCaseTurnBuckets.MEDIUM,
        duration=65.0,
        text_llm_vendor="VendorX",
        text_llm_name="ModelY",
        id=123,
    )

    expected = SyntheticCaseRecord(
        case_id=123,
        category="theCategory",
        turn_total=4,
        speaker_sequence=["Clinician", "Patient", "Patient", "Clinician"],
        clinician_to_patient_turn_ratio=1.0,
        mood=[SyntheticCaseMood.PATIENT_FRUSTRATED],
        pressure=SyntheticCasePressure.TIME_PRESSURE,
        clinician_style=SyntheticCaseClinicianStyle.CAUTIOUS_INQUISITIVE,
        patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        turn_buckets=SyntheticCaseTurnBuckets.MEDIUM,
        duration=65.0,
        text_llm_vendor="VendorX",
        text_llm_name="ModelY",
        id=23,
    )

    tested = helper_instance()

    # insert
    select.side_effect = [[]]
    alter.side_effect = [23]
    mock_datetime.now.side_effect = [date_0]

    result = tested.upsert(case)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    exp_sql = 'SELECT "id" FROM "synthetic_case" WHERE "case_id" = %(case_id)s'
    assert compare_sql(sql, exp_sql)
    exp_params = {"case_id": 123}
    assert params == exp_params

    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = """
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

    assert compare_sql(sql, exp_sql)
    exp_params = {
        "now": date_0,
        "case_id": 123,
        "category": "theCategory",
        "turn_total": 4,
        "speaker_sequence": '["Clinician","Patient","Patient","Clinician"]',
        "clinician_to_patient_turn_ratio": 1.0,
        "mood": [SyntheticCaseMood.PATIENT_FRUSTRATED],
        "pressure": SyntheticCasePressure.TIME_PRESSURE,
        "clinician_style": SyntheticCaseClinicianStyle.CAUTIOUS_INQUISITIVE,
        "patient_style": SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        "turn_buckets": SyntheticCaseTurnBuckets.MEDIUM,
        "text_llm_vendor": "VendorX",
        "text_llm_name": "ModelY",
        "temperature": 1.0,
    }
    assert params == exp_params
    assert involved_id is None
    reset_mock()

    # update
    select.side_effect = [[{"id": 777}]]
    alter.side_effect = [23]
    mock_datetime.now.side_effect = [date_0]

    result = tested.upsert(case)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    exp_sql = 'SELECT "id" FROM "synthetic_case" WHERE "case_id" = %(case_id)s'
    assert compare_sql(sql, exp_sql)
    exp_params = {"case_id": 123}
    assert params == exp_params

    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = (
        'UPDATE "synthetic_case" SET "updated" = %(now)s, "category" = %(category)s, "turn_total" = %(turn_total)s, '
        '"speaker_sequence" = %(speaker_sequence)s, '
        '"clinician_to_patient_turn_ratio" = %(clinician_to_patient_turn_ratio)s, '
        '"mood" = %(mood)s, "pressure" = %(pressure)s, "clinician_style" = %(clinician_style)s, '
        '"patient_style" = %(patient_style)s, "turn_buckets" = %(turn_buckets)s, '
        '"text_llm_vendor" = %(text_llm_vendor)s, "text_llm_name" = %(text_llm_name)s, "temperature" = %(temperature)s '
        'WHERE "id" = %(id)s'
    )
    assert compare_sql(sql, exp_sql)
    exp_params = {
        "now": date_0,
        "id": 777,
        "case_id": 123,
        "category": "theCategory",
        "turn_total": 4,
        "speaker_sequence": '["Clinician","Patient","Patient","Clinician"]',
        "clinician_to_patient_turn_ratio": 1.0,
        "mood": [SyntheticCaseMood.PATIENT_FRUSTRATED],
        "pressure": SyntheticCasePressure.TIME_PRESSURE,
        "clinician_style": SyntheticCaseClinicianStyle.CAUTIOUS_INQUISITIVE,
        "patient_style": SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        "turn_buckets": SyntheticCaseTurnBuckets.MEDIUM,
        "text_llm_vendor": "VendorX",
        "text_llm_name": "ModelY",
        "temperature": 1.0,
    }
    assert involved_id == 777
    assert params == exp_params
    reset_mock()
