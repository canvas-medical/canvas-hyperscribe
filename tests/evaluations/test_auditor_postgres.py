from inspect import getsource
from unittest.mock import patch, call

from evaluations.auditor_postgres import AuditorPostgres
from evaluations.auditor_store import AuditorStore
from evaluations.datastores.postgres.generated_note import GeneratedNote as GeneratedNoteStore


def helper_instance(mock_generated_note_store) -> AuditorPostgres:
    result = AuditorPostgres("theCase", 7, 333)
    mock_generated_note_store.reset_mock()
    return result


def test_class():
    tested = AuditorPostgres
    assert issubclass(tested, AuditorStore)


@patch('evaluations.auditor_postgres.GeneratedNoteStore')
@patch('evaluations.auditor_postgres.HelperEvaluation')
def test___init__(helper, generated_note_store):
    def reset_mocks():
        helper.reset_mock()
        generated_note_store.reset_mock()

    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    generated_note_store.side_effect = ["theGeneratedStore"]
    tested = AuditorPostgres("theCase", 7, 333)
    assert tested.case == "theCase"
    assert tested.cycle == 7
    assert tested.generated_note_id == 333
    assert tested.store == "theGeneratedStore"

    calls = [call.postgres_credentials()]
    assert helper.mock_calls == calls
    calls = [call('thePostgresCredentials')]
    assert generated_note_store.mock_calls == calls
    reset_mocks()


def test_upsert_audio():
    tested = AuditorPostgres("theCase", 7, 333)
    source = getsource(tested.upsert_audio)
    # Remove the function definition line and whitespace
    lines = source.split('\n')
    body_lines = [line.strip() for line in lines[1:] if line.strip()]

    # Should only contain ellipsis
    assert len(body_lines) == 1
    assert body_lines[0] == '...  # TODO record the audio in the database'

    # force the execution
    assert tested.upsert_audio("theLabel", b"audio1") is None


@patch.object(GeneratedNoteStore, 'update_fields')
def test_upsert_json(update_fields):
    def reset_mocks():
        update_fields.reset_mock()

    tested = AuditorPostgres("theCase", 7, 333)
    tested.upsert_json("theLabel", {"key": "value"})

    calls = [
        call(333, {'theLabel': {'key': 'value'}}),
    ]
    assert update_fields.mock_calls == calls
    reset_mocks()


@patch.object(GeneratedNoteStore, 'get_field')
def test_get_json(get_field):
    def reset_mocks():
        get_field.reset_mock()

    get_field.side_effect = [{'key': 'value'}]
    tested = AuditorPostgres("theCase", 7, 333)
    result = tested.get_json("theLabel")
    expected = {'key': 'value'}
    assert result == expected

    calls = [
        call(333, "theLabel"),
    ]
    assert get_field.mock_calls == calls
    reset_mocks()


@patch.object(GeneratedNoteStore, 'update_fields')
def test_finalize(update_fields):
    def reset_mocks():
        update_fields.reset_mock()

    tested = AuditorPostgres("theCase", 7, 333)
    tested.finalize(["error1", "error2"])

    calls = [
        call(333, {
            'cycle_count': 7,
            'note_json': [],
            'failed': True,
            'errors': ['error1', 'error2'],
        }),
    ]
    assert update_fields.mock_calls == calls
    reset_mocks()
