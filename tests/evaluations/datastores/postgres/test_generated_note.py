from datetime import datetime, timezone
from unittest.mock import patch, call

from evaluations.datastores.postgres.generated_note import GeneratedNote
from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.records.generated_note import GeneratedNote as Record
from tests.helper import compare_sql


def helper_instance() -> GeneratedNote:
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return GeneratedNote(credentials)


def test_class():
    assert issubclass(GeneratedNote, Postgres)


@patch("evaluations.datastores.postgres.generated_note.datetime", wraps=datetime)
@patch.object(GeneratedNote, "_alter")
def test_insert(alter, mock_datetime):
    def reset_mock():
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 7, 4, 6, 11, 4, 805952, tzinfo=timezone.utc)
    case = Record(
        case_id=741,
        cycle_duration=35,
        cycle_count=7,
        cycle_transcript_overlap=57,
        text_llm_vendor="theTextLlmVendor",
        text_llm_name="theTextLlmName",
        note_json=["note1", "note2"],
        hyperscribe_version="theHyperscribeVersion",
        staged_questionnaires={"case": "staged_questionnaires"},
        transcript2instructions={"case": "transcript2instructions"},
        instruction2parameters={"case": "instruction2parameters"},
        parameters2command={"case": "parameters2command"},
        failed=True,
        errors={"case": "errors"},
        id=333,
    )
    expected = Record(
        case_id=741,
        cycle_duration=35,
        cycle_count=7,
        cycle_transcript_overlap=57,
        text_llm_vendor="theTextLlmVendor",
        text_llm_name="theTextLlmName",
        note_json=["note1", "note2"],
        hyperscribe_version="theHyperscribeVersion",
        staged_questionnaires={"case": "staged_questionnaires"},
        transcript2instructions={"case": "transcript2instructions"},
        instruction2parameters={"case": "instruction2parameters"},
        parameters2command={"case": "parameters2command"},
        failed=True,
        errors={"case": "errors"},
        id=351,
    )

    tested = helper_instance()

    alter.side_effect = [351]
    mock_datetime.now.side_effect = [date_0]

    result = tested.insert(case)
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls

    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = ('INSERT INTO "generated_note" ("created", "updated", "case_id", "cycle_duration", "cycle_count", '
               ' "cycle_transcript_overlap", "text_llm_vendor", "text_llm_name", "note_json", "hyperscribe_version", '
               ' "staged_questionnaires", "transcript2instructions", "instruction2parameters", '
               ' "parameters2command", "failed", "errors") '
               'VALUES (%(now)s, %(now)s, %(case_id)s, %(cycle_duration)s, %(cycle_count)s, '
               ' %(cycle_transcript_overlap)s, %(text_llm_vendor)s, %(text_llm_name)s, %(note_json)s, %(hyperscribe_version)s, '
               ' %(staged_questionnaires)s, %(transcript2instructions)s, %(instruction2parameters)s, '
               ' %(parameters2command)s, %(failed)s, %(errors)s) '
               'RETURNING id')
    assert compare_sql(sql, exp_sql)
    exp_params = {
        'case_id': 741,
        'cycle_count': 7,
        'cycle_duration': 35,
        'cycle_transcript_overlap': 57,
        'errors': '{"case": "errors"}',
        'failed': True,
        'hyperscribe_version': 'theHyperscribeVersion',
        'instruction2parameters': '{"case": "instruction2parameters"}',
        'note_json': '["note1", "note2"]',
        'now': date_0,
        'parameters2command': '{"case": "parameters2command"}',
        'staged_questionnaires': '{"case": "staged_questionnaires"}',
        'text_llm_name': 'theTextLlmName',
        'text_llm_vendor': 'theTextLlmVendor',
        'transcript2instructions': '{"case": "transcript2instructions"}',
    }
    assert params == exp_params
    assert involved_id is None
    reset_mock()


@patch("evaluations.datastores.postgres.generated_note.datetime", wraps=datetime)
@patch.object(GeneratedNote, "_alter")
def test_update_fields(alter, mock_datetime):
    def reset_mock():
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 7, 4, 6, 11, 4, 805952, tzinfo=timezone.utc)

    tests = [
        # no field
        ({}, 0, "", {}),
        # unknown field
        ({"unknown": "field"}, 0, "", {}),
        # regular field
        (
            {"failed": True},
            1,
            'UPDATE "generated_note" '
            'SET "updated"=%(now)s, "failed" = %(failed)s '
            'WHERE "id" = %(id)s AND ("failed"<>%(failed)s)',
            {'failed': True, 'id': 347, 'now': date_0}
        ),
        # json field
        (
            {"parameters2command": {"key": "data"}},
            1,
            'UPDATE "generated_note" '
            'SET "updated"=%(now)s, "parameters2command" = %(parameters2command)s '
            'WHERE "id" = %(id)s AND ("parameters2command"::jsonb<>%(parameters2command)s::jsonb)',
            {'parameters2command': '{"key": "data"}', 'id': 347, 'now': date_0}
        ),
        # several fields
        (
            {"instruction2parameters": {"key1": "data1"}, "staged_questionnaires": {"key2": "data2"}, "cycle_count": 11,
             "text_llm_name": "theTextLlmName"},
            1,
            ' UPDATE "generated_note" '
            'SET "updated"=%(now)s, "instruction2parameters" = %(instruction2parameters)s, '
            '"staged_questionnaires" = %(staged_questionnaires)s, "cycle_count" = %(cycle_count)s, '
            '"text_llm_name" = %(text_llm_name)s '
            'WHERE "id" = %(id)s AND ("instruction2parameters"::jsonb<>%(instruction2parameters)s::jsonb '
            'OR "staged_questionnaires"::jsonb<>%(staged_questionnaires)s::jsonb '
            'OR "cycle_count"<>%(cycle_count)s '
            'OR "text_llm_name"<>%(text_llm_name)s)',
            {
                'cycle_count': 11,
                'id': 347,
                'instruction2parameters': '{"key1": "data1"}',
                'now': date_0,
                'staged_questionnaires': '{"key2": "data2"}',
                'text_llm_name': 'theTextLlmName',

            }
        ),
    ]

    tested = helper_instance()
    for updates, exp_count, exp_sql, exp_params in tests:
        mock_datetime.now.side_effect = [date_0]

        tested.update_fields(347, updates)

        assert len(alter.mock_calls) == exp_count
        if exp_count > 0:
            sql, params, involved_id = alter.mock_calls[0].args
            assert compare_sql(sql, exp_sql)
            assert params == exp_params
            assert involved_id == 347
        reset_mock()


@patch.object(GeneratedNote, "_select")
def test_get_field(select):
    def reset_mock():
        select.reset_mock()

    tests = [
        # unknown field
        ("unknown", [], {}, 0, "", {}),
        # regular field
        ("failed", [], {}, 0, "", {}),
        # list field
        ("note_json", [], {}, 0, "", {}),
        # dict field
        # -- no record
        (
            "parameters2command",
            [],
            {},
            1,
            'SELECT "parameters2command" FROM "generated_note" WHERE "id" = %(id)s',
            {'id': 347}
        ),
        # -- record
        (
            "parameters2command",
            [{"parameters2command": {"key": "data"}}],
            {"key": "data"},
            1,
            'SELECT "parameters2command" FROM "generated_note" WHERE "id" = %(id)s',
            {'id': 347}
        ),
    ]

    tested = helper_instance()
    for field, records, expected, exp_count, exp_sql, exp_params in tests:
        select.side_effect = [records]

        result = tested.get_field(347, field)
        assert result == expected

        assert len(select.mock_calls) == exp_count
        if exp_count > 0:
            sql, params = select.mock_calls[0].args
            assert compare_sql(sql, exp_sql)
            assert params == exp_params
        reset_mock()
