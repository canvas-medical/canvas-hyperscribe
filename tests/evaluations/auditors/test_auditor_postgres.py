from inspect import getsource
from unittest.mock import patch, call, MagicMock

from evaluations.auditors.auditor_postgres import AuditorPostgres
from evaluations.auditors.auditor_store import AuditorStore
from evaluations.structures.enums.case_status import CaseStatus
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.records.case import Case as CaseRecord
from evaluations.structures.records.generated_note import GeneratedNote as GeneratedNoteRecord
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> AuditorPostgres:
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        science_host='theScienceHost',
        ontologies_host='theOntologiesHost',
        pre_shared_key='thePreSharedKey',
        structured_rfv=True,
        audit_llm=True,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
    )
    s3_credentials = AwsS3Credentials(
        aws_key='theKey',
        aws_secret='theSecret',
        region='theRegion',
        bucket='theBucket',
    )
    psql_credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return AuditorPostgres("theCase", 7, settings, s3_credentials, psql_credentials)


def test_class():
    tested = AuditorPostgres
    assert issubclass(tested, AuditorStore)


def test___init__():
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        science_host='theScienceHost',
        ontologies_host='theOntologiesHost',
        pre_shared_key='thePreSharedKey',
        structured_rfv=True,
        audit_llm=True,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
    )
    s3_credentials = AwsS3Credentials(
        aws_key='theKey',
        aws_secret='theSecret',
        region='theRegion',
        bucket='theBucket',
    )
    psql_credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    tested = AuditorPostgres("theCase", 7, settings, s3_credentials, psql_credentials)
    assert tested.case == "theCase"
    assert tested.cycle == 7
    assert tested.cycle_key == "cycle_007"
    assert tested.s3_credentials == s3_credentials
    assert tested.settings == settings
    assert tested.postgres_credentials == psql_credentials


@patch('evaluations.auditors.auditor_postgres.CaseStore')
def test_case_id(case_store):
    def reset_mocks():
        case_store.reset_mock()

    tested = helper_instance()

    case_store.return_value.get_id.side_effect = [25]
    result = tested.case_id()
    expected = 25
    assert result == expected

    calls = [
        call(tested.postgres_credentials),
        call().get_id('theCase'),
    ]
    assert case_store.mock_calls == calls
    reset_mocks()

    case_store.side_effect = []
    result = tested.case_id()
    expected = 25
    assert result == expected

    assert case_store.mock_calls == []
    reset_mocks()


@patch('evaluations.auditors.auditor_postgres.GeneratedNoteStore')
@patch.object(AuditorPostgres, 'case_id')
def test_generated_note_id(case_id, generated_note_store):
    mock_settings = MagicMock()

    def reset_mocks():
        case_id.reset_mock()
        generated_note_store.reset_mock()
        mock_settings.reset_mock()

    tested = helper_instance()
    tested.settings = mock_settings

    #
    mock_settings.llm_text.vendor = "theTextVendor"
    mock_settings.llm_text_model.side_effect = ["theTextModel"]
    case_id.side_effect = [47]
    generated_note_store.return_value.insert.side_effect = [GeneratedNoteRecord(case_id=111, id=333)]

    result = tested.generated_note_id()
    expected = 333
    assert result == expected

    calls = [call()]
    assert case_id.mock_calls == calls
    calls = [
        call(tested.postgres_credentials),
        call().insert(GeneratedNoteRecord(
            case_id=47,
            cycle_duration=0,
            cycle_count=0,
            cycle_transcript_overlap=100,
            text_llm_vendor='theTextVendor',
            text_llm_name='theTextModel',
            note_json=[],
            hyperscribe_version='',
            staged_questionnaires={},
            transcript2instructions={},
            instruction2parameters={},
            parameters2command={},
            failed=True,
            errors={},
            id=0,
        )),
    ]
    assert generated_note_store.mock_calls == calls
    calls = [call.llm_text_model()]
    assert mock_settings.mock_calls == calls
    reset_mocks()

    #
    mock_settings.llm_text_model.side_effect = []
    case_id.side_effect = []
    generated_note_store.return_value.insert.side_effect = []

    result = tested.generated_note_id()
    expected = 333
    assert result == expected

    assert case_id.mock_calls == []
    assert generated_note_store.mock_calls == []
    assert mock_settings.mock_calls == []
    reset_mocks()


@patch('evaluations.auditors.auditor_postgres.CaseStore')
def test_case_prepare(case_store):
    def reset_mocks():
        case_store.reset_mock()

    tested = helper_instance()

    # the case does not exist yet
    case_store.return_value.get_id.side_effect = [0]
    case_store.return_value.upsert.side_effect = [CaseRecord(id=117, name="theCase")]

    tested.case_prepare()

    calls = [
        call(tested.postgres_credentials),
        call().get_id('theCase'),
        call().upsert(CaseRecord(
            name='theCase',
            transcript={},
            limited_chart={},
            profile='theCase',
            validation_status=CaseStatus.GENERATION,
            batch_identifier='',
            tags={},
            id=0,
        )),
    ]
    assert case_store.mock_calls == calls
    reset_mocks()

    # the case already exists
    case_store.return_value.get_id.side_effect = [145]
    case_store.return_value.upsert.side_effect = []

    tested.case_prepare()

    calls = [
        call(tested.postgres_credentials),
        call().get_id('theCase'),
        call().update_fields(145, {'validation_status': CaseStatus.GENERATION}),
    ]
    assert case_store.mock_calls == calls
    reset_mocks()


@patch('evaluations.auditors.auditor_postgres.CaseStore')
@patch.object(AuditorPostgres, 'case_id')
def test_case_update_limited_cache(case_id, case_store):
    def reset_mocks():
        case_id.reset_mock()
        case_store.reset_mock()

    case_id.side_effect = [145]

    tested = helper_instance()
    tested.case_update_limited_cache({"limited": "cache"})

    calls = [call()]
    assert case_id.mock_calls == calls
    calls = [
        call(tested.postgres_credentials),
        call().update_fields(145, {"limited_chart": {"limited": "cache"}}),
    ]
    assert case_store.mock_calls == calls
    reset_mocks()


@patch('evaluations.auditors.auditor_postgres.GeneratedNoteStore')
@patch.object(AuditorPostgres, 'summarized_generated_commands')
@patch.object(AuditorPostgres, 'generated_note_id')
def test_case_finalize(generated_note_id, summarized_generated_commands, generated_note_store):
    def reset_mocks():
        generated_note_id.reset_mock()
        summarized_generated_commands.reset_mock()
        generated_note_store.reset_mock()

    generated_note_id.side_effect = [137]
    summarized_generated_commands.side_effect = [{"summarized": "commands"}]

    tested = helper_instance()
    tested.case_finalize({"error1": "value1", "error2": "value2"})

    calls = [call()]
    assert generated_note_id.mock_calls == calls
    calls = [call()]
    assert summarized_generated_commands.mock_calls == calls
    calls = [
        call(tested.postgres_credentials),
        call().update_fields(
            137,
            {
                'cycle_count': 7,
                'note_json': {'summarized': 'commands'},
                'failed': True,
                'errors': {"error1": "value1", "error2": "value2"},
            },
        ),
    ]
    assert generated_note_store.mock_calls == calls
    reset_mocks()


def test_upsert_audio():
    tested = helper_instance()
    source = getsource(tested.upsert_audio)
    # Remove the function definition line and whitespace
    lines = source.split('\n')
    body_lines = [line.strip() for line in lines[1:] if line.strip()]

    # Should only contain ellipsis
    assert len(body_lines) == 1
    assert body_lines[0] == '...  # TODO record the audio in the database'

    # force the execution
    assert tested.upsert_audio("theLabel", b"audio1") is None


@patch('evaluations.auditors.auditor_postgres.GeneratedNoteStore')
@patch('evaluations.auditors.auditor_postgres.CaseStore')
@patch.object(AuditorPostgres, 'generated_note_id')
@patch.object(AuditorPostgres, 'case_id')
def test_upsert_json(case_id, generated_note_id, case_store, generated_note_store):
    def reset_mocks():
        case_id.reset_mock()
        generated_note_id.reset_mock()
        case_store.reset_mock()
        generated_note_store.reset_mock()

    tested = helper_instance()

    # update the transcript
    case_id.side_effect = [144, 137]
    generated_note_id.side_effect = []
    case_store.return_value.get_transcript.side_effect = [{
        "cycle_004": [Line(speaker="aSpeaker", text="aText")]
    }]

    tested.upsert_json("audio2transcript", {"cycle_007": [{"speaker": "theSpeaker", "text": "theText"}]})

    calls = [call(), call()]
    assert case_id.mock_calls == calls
    assert generated_note_id.mock_calls == []
    calls = [
        call(tested.postgres_credentials),
        call().get_transcript(144),
        call().update_fields(137, {
            'transcript': {
                'cycle_004': [{'speaker': 'aSpeaker', 'text': 'aText'}],
                'cycle_007': [{'speaker': 'theSpeaker', 'text': 'theText'}],
            },
        }),
    ]
    assert case_store.mock_calls == calls
    assert generated_note_store.mock_calls == []
    reset_mocks()

    # update another field
    case_id.side_effect = []
    generated_note_id.side_effect = [521]
    case_store.return_value.get_transcript.side_effect = []

    tested.upsert_json("another_field", {"cycle_007": [{"key": "data"}]})

    assert case_id.mock_calls == []
    calls = [call()]
    assert generated_note_id.mock_calls == calls
    assert case_store.mock_calls == []
    calls = [
        call(tested.postgres_credentials),
        call().update_fields(521, {'another_field': {'cycle_007': [{'key': 'data'}]}}),
    ]
    assert generated_note_store.mock_calls == calls
    reset_mocks()


@patch('evaluations.auditors.auditor_postgres.GeneratedNoteStore')
@patch.object(AuditorPostgres, 'generated_note_id')
def test_get_json(generated_note_id, generated_note_store):
    def reset_mocks():
        generated_note_id.reset_mock()
        generated_note_store.reset_mock()

    generated_note_id.side_effect = [333]
    generated_note_store.return_value.get_field.side_effect = [{'key': 'value'}]
    tested = helper_instance()
    result = tested.get_json("theLabel")
    expected = {'key': 'value'}
    assert result == expected

    calls = [call()]
    assert generated_note_id.mock_calls == calls
    calls = [
        call(tested.postgres_credentials),
        call().get_field(333, "theLabel"),
    ]
    assert generated_note_store.mock_calls == calls
    reset_mocks()


@patch('evaluations.auditors.auditor_postgres.CaseStore')
@patch.object(AuditorPostgres, 'case_id')
def test_limited_chart(case_id, case_store):
    def reset_mocks():
        case_id.reset_mock()
        case_store.reset_mock()

    case_id.side_effect = [333]
    case_store.return_value.get_limited_chart.side_effect = [{'key': 'value'}]
    tested = helper_instance()
    result = tested.limited_chart()
    expected = {'key': 'value'}
    assert result == expected

    calls = [call()]
    assert case_id.mock_calls == calls
    calls = [
        call(tested.postgres_credentials),
        call().get_limited_chart(333),
    ]
    assert case_store.mock_calls == calls
    reset_mocks()


@patch.object(AuditorPostgres, 'full_transcript')
def test_transcript(full_transcript):
    def reset_mocks():
        full_transcript.reset_mock()

    full_transcript.side_effect = [{'cycle_007': [Line(speaker="aSpeaker", text="aText")]}]
    tested = helper_instance()
    result = tested.transcript()
    expected = [Line(speaker="aSpeaker", text="aText")]
    assert result == expected

    calls = [call()]
    assert full_transcript.mock_calls == calls
    reset_mocks()

    full_transcript.side_effect = [{'cycle_006': [Line(speaker="aSpeaker", text="aText")]}]
    tested = helper_instance()
    result = tested.transcript()
    expected = []
    assert result == expected

    calls = [call()]
    assert full_transcript.mock_calls == calls
    reset_mocks()


@patch('evaluations.auditors.auditor_postgres.CaseStore')
@patch.object(AuditorPostgres, 'case_id')
def test_full_transcript(case_id, case_store):
    def reset_mocks():
        case_id.reset_mock()
        case_store.reset_mock()

    case_id.side_effect = [333]
    case_store.return_value.get_transcript.side_effect = [{'cycle_001': [Line(speaker="aSpeaker", text="aText")]}]
    tested = helper_instance()
    result = tested.full_transcript()
    expected = {'cycle_001': [Line(speaker="aSpeaker", text="aText")]}
    assert result == expected

    calls = [call()]
    assert case_id.mock_calls == calls
    calls = [
        call(tested.postgres_credentials),
        call().get_transcript(333),
    ]
    assert case_store.mock_calls == calls
    reset_mocks()
