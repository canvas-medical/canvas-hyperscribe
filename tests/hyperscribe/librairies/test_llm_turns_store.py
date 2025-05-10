import json
from datetime import timezone, datetime
from unittest.mock import patch, call

from requests import Response

import hyperscribe.libraries.llm_turns_store as llm_turns_store
from hyperscribe.libraries.cached_discussion import CachedDiscussion
from hyperscribe.libraries.llm_turns_store import LlmTurnsStore
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.aws_s3_object import AwsS3Object
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.llm_turn import LlmTurn


def helper_instance() -> LlmTurnsStore:
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    s3_credentials = AwsS3Credentials(
        aws_key='theKey',
        aws_secret='theSecret',
        region='theRegion',
        bucket='theBucket',
    )
    return LlmTurnsStore(s3_credentials, identification, "2025-05-08", 7)


def test_end_session():
    tested = LlmTurnsStore
    #
    mock_discussion = {}
    with patch.object(llm_turns_store, "DISCUSSIONS", mock_discussion):
        tested.end_session("noteUuid_2")
        assert mock_discussion == {}

    #
    mock_discussion = {
        "noteUuid_1": {
            1: {"key_1": 2, "key_2": 3},
            2: {"key_1": 1, "key_3": 1},
        },
        "noteUuid_2": {
            1: {"key_1": 2, "key_2": 3},
            2: {"key_1": 1, "key_3": 1},
        },
        "noteUuid_3": {
            1: {"key_1": 2, "key_2": 3},
            2: {"key_1": 1, "key_3": 1},
        },
        "noteUuid_4": {},
    }
    with patch.object(llm_turns_store, "DISCUSSIONS", mock_discussion):
        tested.end_session("noteUuid_2")
        assert mock_discussion == {
            "noteUuid_1": {
                1: {"key_1": 2, "key_2": 3},
                2: {"key_1": 1, "key_3": 1},
            },
            "noteUuid_3": {
                1: {"key_1": 2, "key_2": 3},
                2: {"key_1": 1, "key_3": 1},
            },
            "noteUuid_4": {},
        }


@patch.object(CachedDiscussion, "get_discussion")
def test_instance(get_discussion):
    def reset_mocks():
        get_discussion.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    s3_credentials = AwsS3Credentials(
        aws_key='theKey',
        aws_secret='theSecret',
        region='theRegion',
        bucket='theBucket',
    )
    cached = CachedDiscussion("theNoteUuid")
    cached.created = datetime(2025, 5, 7, 23, 59, 37, tzinfo=timezone.utc)
    cached.updated = datetime(2025, 5, 7, 0, 38, 21, tzinfo=timezone.utc)
    cached.cycle = 7
    get_discussion.side_effect = [cached]

    tested = LlmTurnsStore
    result = tested.instance(s3_credentials, identification)
    assert isinstance(result, LlmTurnsStore)
    assert result.s3_credentials == s3_credentials
    assert result.identification == identification
    assert result.creation_day == "2025-05-07"
    assert result.cycle == 7

    calls = [call("noteUuid")]
    assert get_discussion.mock_calls == calls
    reset_mocks()


def test___init__():
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    s3_credentials = AwsS3Credentials(
        aws_key='theKey',
        aws_secret='theSecret',
        region='theRegion',
        bucket='theBucket',
    )
    tested = LlmTurnsStore(s3_credentials, identification, "2025-05-08", 7)
    assert tested.s3_credentials == s3_credentials
    assert tested.identification == identification
    assert tested.creation_day == "2025-05-08"
    assert tested.cycle == 7


@patch.object(LlmTurnsStore, "store_document")
def test_store(store_document):
    def reset_mocks():
        store_document.reset_mock()

    tested = helper_instance()
    mock_discussion = {}
    with patch.object(llm_turns_store, "DISCUSSIONS", mock_discussion):
        #
        tested.store(
            "theInstruction",
            3,
            [
                LlmTurn(role="system", text=["line 1"]),
                LlmTurn(role="user", text=["line 2"]),
                LlmTurn(role="model", text=["line 3"]),
                LlmTurn(role="user", text=["line 4"]),
                LlmTurn(role="model", text=["line 5"]),
            ]
        )
        expected = {
            'noteUuid': {
                7: {
                    'theInstruction_03': 1,
                },
            },
        }
        assert mock_discussion == expected
        calls = [
            call(
                'theInstruction_03_00.json',
                [
                    {'role': 'system', 'text': ['line 1']},
                    {'role': 'user', 'text': ['line 2']},
                    {'role': 'model', 'text': ['line 3']},
                    {'role': 'user', 'text': ['line 4']},
                    {'role': 'model', 'text': ['line 5']},
                ],
            )
        ]
        assert store_document.mock_calls == calls
        reset_mocks()
        #
        tested.store(
            "theInstruction",
            3,
            [
                LlmTurn(role="system", text=["line 1"]),
                LlmTurn(role="user", text=["line 2"]),
            ]
        )
        expected = {
            'noteUuid': {
                7: {
                    'theInstruction_03': 2,
                },
            },
        }
        assert mock_discussion == expected

        calls = [
            call(
                'theInstruction_03_01.json',
                [
                    {'role': 'system', 'text': ['line 1']},
                    {'role': 'user', 'text': ['line 2']},
                ],
            )
        ]
        assert store_document.mock_calls == calls
        reset_mocks()
        #
        tested.store(
            "otherInstruction",
            3,
            [
                LlmTurn(role="system", text=["line 1"]),
                LlmTurn(role="user", text=["line 2"]),
            ]
        )
        expected = {
            'noteUuid': {
                7: {
                    'theInstruction_03': 2,
                    'otherInstruction_03': 1,
                },
            },
        }
        assert mock_discussion == expected

        calls = [
            call(
                'otherInstruction_03_00.json',
                [
                    {'role': 'system', 'text': ['line 1']},
                    {'role': 'user', 'text': ['line 2']},
                ],
            )
        ]
        assert store_document.mock_calls == calls
        reset_mocks()
        #
        tested.store(
            "subZeroInstruction",
            -1,
            [
                LlmTurn(role="system", text=["line 1"]),
                LlmTurn(role="user", text=["line 2"]),
            ]
        )
        expected = {
            'noteUuid': {
                7: {
                    'theInstruction_03': 2,
                    'otherInstruction_03': 1,
                    'subZeroInstruction': 1,
                },
            },
        }
        assert mock_discussion == expected

        calls = [
            call(
                'subZeroInstruction_00.json',
                [
                    {'role': 'system', 'text': ['line 1']},
                    {'role': 'user', 'text': ['line 2']},
                ],
            )
        ]
        assert store_document.mock_calls == calls
        reset_mocks()


@patch("hyperscribe.libraries.llm_turns_store.AwsS3")
def test_store_document(aws_s3):
    def reset_mocks():
        aws_s3.reset_mock()

    document = [
        {'role': 'system', 'text': ['line 1']},
        {'role': 'user', 'text': ['line 2']},
        {'role': 'model', 'text': ['line 3']},
    ]

    tested = helper_instance()
    # S3 not ready
    aws_s3.return_value.is_ready.side_effect = [False]
    tested.store_document("theInstruction", document)
    calls = [
        call(tested.s3_credentials),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()

    # S3 is ready
    aws_s3.return_value.is_ready.side_effect = [True]
    tested.store_document("theInstruction", document)
    calls = [
        call(tested.s3_credentials),
        call().is_ready(),
        call().upload_text_to_s3(
            'canvasInstance/llm_turns/2025-05-08/noteUuid/07/theInstruction',
            '[\n'
            '  {\n    "role": "system",\n    "text": [\n      "line 1"\n    ]\n  },\n'
            '  {\n    "role": "user",\n    "text": [\n      "line 2"\n    ]\n  },\n'
            '  {\n    "role": "model",\n    "text": [\n      "line 3"\n    ]\n  }'
            '\n]',
        ),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.libraries.llm_turns_store.AwsS3")
def test_stored_document(aws_s3):
    def reset_mocks():
        aws_s3.reset_mock()

    document = [
        {'role': 'system', 'text': ['line 1']},
        {'role': 'user', 'text': ['line 2']},
        {'role': 'model', 'text': ['line 3']},
    ]

    tested = helper_instance()
    # S3 not ready
    aws_s3.return_value.is_ready.side_effect = [False]
    aws_s3.return_value.access_s3_object.side_effect = []
    result = tested.stored_document("theName")
    assert result == []
    calls = [
        call(tested.s3_credentials),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()

    # S3 is ready
    # -- response not 200
    response = Response()
    response.status_code = 500
    aws_s3.return_value.is_ready.side_effect = [True]
    aws_s3.return_value.access_s3_object.side_effect = [response]
    result = tested.stored_document("theName")
    assert result == []
    calls = [
        call(tested.s3_credentials),
        call().is_ready(),
        call().access_s3_object('canvasInstance/llm_turns/2025-05-08/noteUuid/07/theName'),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()
    # -- response not 200
    response = Response()
    response.status_code = 200
    response._content = json.dumps(document).encode()
    aws_s3.return_value.is_ready.side_effect = [True]
    aws_s3.return_value.access_s3_object.side_effect = [response]
    result = tested.stored_document("theName")
    assert result == document
    calls = [
        call(tested.s3_credentials),
        call().is_ready(),
        call().access_s3_object('canvasInstance/llm_turns/2025-05-08/noteUuid/07/theName'),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.libraries.llm_turns_store.AwsS3")
def test_stored_documents(aws_s3):
    def reset_mocks():
        aws_s3.reset_mock()

    a_date = datetime(2025, 5, 8, 5, 27, 45, tzinfo=timezone.utc)

    tested = helper_instance()
    # S3 not ready
    aws_s3.return_value.is_ready.side_effect = [False]
    aws_s3.return_value.list_s3_objects.side_effect = []
    aws_s3.return_value.access_s3_object.side_effect = []
    result = [d for d in tested.stored_documents()]
    assert result == []
    calls = [
        call(tested.s3_credentials),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()
    # S3 is ready
    # -- no document
    aws_s3.return_value.is_ready.side_effect = [True]
    aws_s3.return_value.list_s3_objects.side_effect = [[]]
    aws_s3.return_value.access_s3_object.side_effect = []
    result = [d for d in tested.stored_documents()]
    assert result == []
    calls = [
        call(tested.s3_credentials),
        call().is_ready(),
        call().list_s3_objects('canvasInstance/llm_turns/2025-05-08/noteUuid/07'),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()
    # -- with documents
    aws_s3.return_value.is_ready.side_effect = [True]
    aws_s3.return_value.list_s3_objects.side_effect = [[
        AwsS3Object(
            key="canvasInstance/llm_turns/2025-05-08/noteUuid/07/theInstruction_01_01.json",
            last_modified=a_date,
            size=4785236,
        ),
        AwsS3Object(
            key="canvasInstance/llm_turns/2025-05-08/noteUuid/07/theInstruction_01_00.json",
            last_modified=a_date,
            size=4785236,
        ),
        AwsS3Object(
            key="canvasInstance/llm_turns/2025-05-08/noteUuid/07/theInstruction_00_01.json",
            last_modified=a_date,
            size=4785236,
        ),
        AwsS3Object(
            key="canvasInstance/llm_turns/2025-05-08/noteUuid/07/transcript2instructions_01.json",
            last_modified=a_date,
            size=4785236,
        ),
    ]]
    responses = [Response(), Response(), Response(), Response()]
    responses[0].status_code = 200
    responses[0]._content = json.dumps({"key": "document0"}).encode()
    responses[1].status_code = 200
    responses[1]._content = json.dumps({"key": "document1"}).encode()
    responses[2].status_code = 500
    responses[2]._content = json.dumps({"key": "document2"}).encode()
    responses[3].status_code = 200
    responses[3]._content = json.dumps({"key": "document3"}).encode()

    aws_s3.return_value.access_s3_object.side_effect = responses
    result = [d for d in tested.stored_documents()]
    expected = [
        ('transcript2instructions_01', {'key': 'document0'}),
        ('theInstruction_00_01', {'key': 'document1'}),
        ('theInstruction_01_01', {'key': 'document3'}),
    ]
    assert result == expected
    calls = [
        call(tested.s3_credentials),
        call().is_ready(),
        call().list_s3_objects('canvasInstance/llm_turns/2025-05-08/noteUuid/07'),
        call().access_s3_object('canvasInstance/llm_turns/2025-05-08/noteUuid/07/transcript2instructions_01.json'),
        call().access_s3_object('canvasInstance/llm_turns/2025-05-08/noteUuid/07/theInstruction_00_01.json'),
        call().access_s3_object('canvasInstance/llm_turns/2025-05-08/noteUuid/07/theInstruction_01_00.json'),
        call().access_s3_object('canvasInstance/llm_turns/2025-05-08/noteUuid/07/theInstruction_01_01.json'),
    ]
    assert aws_s3.mock_calls == calls
    reset_mocks()


def test_store_path():
    tested = helper_instance()
    result = tested.store_path()
    expected = "canvasInstance/llm_turns/2025-05-08/noteUuid/07"
    assert result == expected


def test_s3_path_sort():
    tested = LlmTurnsStore
    tests = [
        ('canvasInstance/llm_turns/2025-05-08/noteUuid/07/transcript2instructions_00.json', (-1, 0)),
        ('canvasInstance/llm_turns/2025-05-08/noteUuid/07/transcript2instructions_01.json', (-1, 1)),
        ('canvasInstance/llm_turns/2025-05-08/noteUuid/07/theInstruction_00_00.json', (0, 0)),
        ('canvasInstance/llm_turns/2025-05-08/noteUuid/07/theInstruction_00_01.json', (0, 1)),
        ('canvasInstance/llm_turns/2025-05-08/noteUuid/07/theInstruction_01_00.json', (1, 0)),
        ('canvasInstance/llm_turns/2025-05-08/noteUuid/07/theInstruction_01_01.json', (1, 1)),
        ('canvasInstance/llm_turns/2025-05-08/noteUuid/07/impossible.json', (999, 999)),
    ]
    for s3_path, expected in tests:
        result = tested.s3_path_sort(s3_path)
        assert result == expected, f"---> {s3_path}"


def test_decompose():
    tested = LlmTurnsStore
    tests = [
        ('transcript2instructions_00', ("transcript2instructions", 0)),
        ('transcript2instructions_01', ("transcript2instructions", 1)),
        ('theInstruction_00_00', ("theInstruction_00", 0)),
        ('theInstruction_00_01', ("theInstruction_00", 1)),
        ('theInstruction_01_00', ("theInstruction_01", 0)),
        ('theInstruction_01_01', ("theInstruction_01", 1)),
    ]
    for step, expected in tests:
        result = tested.decompose(step)
        assert result == expected, f"---> {step}"


def test_indexed_instruction():
    tested = LlmTurnsStore
    tests = [
        ("theInstruction", 0, "theInstruction_00"),
        ("theInstruction", 3, "theInstruction_03"),
        ("theInstruction", 12, "theInstruction_12"),
        ("theInstruction", 112, "theInstruction_112"),
    ]
    for instruction, index, expected in tests:
        result = tested.indexed_instruction(instruction, index)
        assert result == expected, f"---> {instruction} {index}"
