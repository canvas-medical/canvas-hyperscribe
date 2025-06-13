from datetime import datetime, timezone
from unittest.mock import patch, call

from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.structures.instruction import Instruction


@patch("hyperscribe.libraries.cached_sdk.datetime", wraps=datetime)
def test___init__(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 6, 12, 14, 33, 21, 123456, tzinfo=timezone.utc)
    mock_datetime.now.side_effect = [date_0]

    tested = CachedSdk("theNoteUuid")
    assert tested.created == date_0
    assert tested.updated == date_0
    assert tested.cycle == 1
    assert tested.note_uuid == "theNoteUuid"
    assert tested.previous_instructions == []
    assert tested.previous_transcript == ""

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls
    reset_mocks()


@patch.object(CachedSdk, "save")
@patch("hyperscribe.libraries.cached_sdk.datetime", wraps=datetime)
def test_set_cycle(mock_datetime, cache_save):
    def reset_mocks():
        mock_datetime.reset_mock()
        cache_save.reset_mock()

    dates = [
        datetime(2025, 6, 12, 14, 33, 21, 123456, tzinfo=timezone.utc),
        datetime(2025, 6, 12, 14, 33, 32, 123456, tzinfo=timezone.utc),
    ]
    mock_datetime.now.side_effect = dates
    tested = CachedSdk("theNoteUuid")
    assert tested.created == dates[0]
    assert tested.updated == dates[0]
    assert tested.cycle == 1

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls
    assert cache_save.mock_calls == []
    reset_mocks()

    tested.set_cycle(5)
    assert tested.created == dates[0]
    assert tested.updated == dates[1]
    assert tested.cycle == 5

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls
    calls = [call()]
    assert cache_save.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.libraries.cached_sdk.datetime", wraps=datetime)
def test_creation_day(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 6, 12, 14, 33, 21, 123456, tzinfo=timezone.utc)
    mock_datetime.now.side_effect = [date_0]

    tested = CachedSdk("theNoteUuid")
    expected = "2025-06-12"
    result = tested.creation_day()
    assert result == expected

    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.libraries.cached_sdk.get_cache")
def test_save(get_cache):
    def reset_mocks():
        get_cache.reset_mock()

    tested = CachedSdk("theNoteUuid")
    tested.created = datetime(2025, 6, 12, 14, 33, 21, 123456, tzinfo=timezone.utc)
    tested.updated = datetime(2025, 6, 12, 14, 33, 37, 123456, tzinfo=timezone.utc)
    tested.cycle = 7
    tested.previous_instructions = [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=True,
            is_updated=False,
        )
    ]
    tested.previous_transcript = "the last words"

    tested.save()

    calls = [
        call(),
        call().set(
            'theNoteUuid',
            {
                'created': '2025-06-12T14:33:21.123456+00:00',
                'updated': '2025-06-12T14:33:37.123456+00:00',
                'cycle': 7,
                'note_uuid': 'theNoteUuid',
                'previous_instructions': [
                    {
                        'uuid': 'uuid1',
                        'index': 0,
                        'instruction': 'theInstruction1',
                        'information': 'theInformation1',
                        'isNew': False,
                        'isUpdated': True,
                    },
                    {
                        'uuid': 'uuid2',
                        'index': 1,
                        'instruction': 'theInstruction2',
                        'information': 'theInformation2',
                        'isNew': True,
                        'isUpdated': False,
                    },
                ],
                'previous_transcript': 'the last words',
            }),
    ]
    assert get_cache.mock_calls == calls
    reset_mocks()


def test_to_json():
    tested = CachedSdk("theNoteUuid")
    tested.created = datetime(2025, 6, 12, 14, 33, 21, 123456, tzinfo=timezone.utc)
    tested.updated = datetime(2025, 6, 12, 14, 33, 37, 123456, tzinfo=timezone.utc)
    tested.cycle = 7
    tested.previous_instructions = [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=True,
            is_updated=False,
        )
    ]
    tested.previous_transcript = "the last words"

    result = tested.to_json()
    expected = {
        'created': '2025-06-12T14:33:21.123456+00:00',
        'updated': '2025-06-12T14:33:37.123456+00:00',
        'cycle': 7,
        'note_uuid': 'theNoteUuid',
        'previous_instructions': [
            {
                'uuid': 'uuid1',
                'index': 0,
                'instruction': 'theInstruction1',
                'information': 'theInformation1',
                'isNew': False,
                'isUpdated': True,
            },
            {
                'uuid': 'uuid2',
                'index': 1,
                'instruction': 'theInstruction2',
                'information': 'theInformation2',
                'isNew': True,
                'isUpdated': False,
            },
        ],
        'previous_transcript': 'the last words',
    }
    assert result == expected


@patch("hyperscribe.libraries.cached_sdk.datetime", wraps=datetime)
@patch("hyperscribe.libraries.cached_sdk.get_cache")
def test_get_discussion(get_cache, mock_datetime):
    def reset_mocks():
        get_cache.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 6, 12, 14, 33, 51, 123456, tzinfo=timezone.utc)
    date_1 = datetime(2025, 6, 12, 14, 33, 21, 123456, tzinfo=timezone.utc)
    date_2 = datetime(2025, 6, 12, 14, 33, 37, 123456, tzinfo=timezone.utc)

    tested = CachedSdk

    # key exists
    get_cache.side_effect = [{
        'theNoteUuid': {
            'created': '2025-06-12T14:33:21.123456+00:00',
            'updated': '2025-06-12T14:33:37.123456+00:00',
            'cycle': 7,
            'note_uuid': 'theNoteUuid',
            'previous_instructions': [
                {
                    'uuid': 'uuid1',
                    'index': 0,
                    'instruction': 'theInstruction1',
                    'information': 'theInformation1',
                    'isNew': False,
                    'isUpdated': True,
                },
                {
                    'uuid': 'uuid2',
                    'index': 1,
                    'instruction': 'theInstruction2',
                    'information': 'theInformation2',
                    'isNew': True,
                    'isUpdated': False,
                },
            ],
            'previous_transcript': 'the last words',
        },
    }]
    mock_datetime.now.side_effect = [date_0]
    result = tested.get_discussion("theNoteUuid")
    assert isinstance(result, CachedSdk)
    assert result.created == date_1
    assert result.updated == date_2
    assert result.cycle == 7
    assert result.previous_instructions == [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=True,
            is_updated=False,
        )
    ]
    assert result.previous_transcript == "the last words"

    calls = [call()]
    assert get_cache.mock_calls == calls
    calls = [
        call.now(timezone.utc),
        call.fromisoformat('2025-06-12T14:33:21.123456+00:00'),
        call.fromisoformat('2025-06-12T14:33:37.123456+00:00'),
    ]
    assert mock_datetime.mock_calls == calls
    reset_mocks()

    # key does not exist
    get_cache.side_effect = [{}]
    mock_datetime.now.side_effect = [date_0]
    result = tested.get_discussion("theNoteUuid")
    assert isinstance(result, CachedSdk)
    assert result.created == date_0
    assert result.updated == date_0
    assert result.cycle == 1
    assert result.previous_instructions == []
    assert result.previous_transcript == ""

    calls = [call()]
    assert get_cache.mock_calls == calls
    calls = [call.now(timezone.utc)]
    assert mock_datetime.mock_calls == calls
    reset_mocks()


def test_load_from_json():
    date_1 = datetime(2025, 6, 12, 14, 33, 21, 123456, tzinfo=timezone.utc)
    date_2 = datetime(2025, 6, 12, 14, 33, 37, 123456, tzinfo=timezone.utc)
    tested = CachedSdk
    result = tested.load_from_json({
        'created': '2025-06-12T14:33:21.123456+00:00',
        'updated': '2025-06-12T14:33:37.123456+00:00',
        'cycle': 7,
        'note_uuid': 'theNoteUuid',
        'previous_instructions': [
            {
                'uuid': 'uuid1',
                'index': 0,
                'instruction': 'theInstruction1',
                'information': 'theInformation1',
                'isNew': False,
                'isUpdated': True,
            },
            {
                'uuid': 'uuid2',
                'index': 1,
                'instruction': 'theInstruction2',
                'information': 'theInformation2',
                'isNew': True,
                'isUpdated': False,
            },
        ],
        'previous_transcript': 'the last words',
    })
    assert isinstance(result, CachedSdk)
    assert result.created == date_1
    assert result.updated == date_2
    assert result.cycle == 7
    assert result.previous_instructions == [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=True,
            is_updated=False,
        )
    ]
    assert result.previous_transcript == "the last words"
