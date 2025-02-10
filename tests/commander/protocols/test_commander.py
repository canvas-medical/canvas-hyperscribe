import json
from datetime import datetime, timezone
from unittest.mock import patch, call, MagicMock

import requests
from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.v1.data import TaskComment, Note
from logger import log

from commander.protocols.commander import CachedDiscussion, Audio, Commander
from tests.helper import is_constant


@patch("commander.protocols.commander.datetime", wraps=datetime)
def test___init__(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    now = datetime(2025, 2, 4, 7, 48, 21, tzinfo=timezone.utc)
    mock_datetime.now.side_effect = [now]

    tested = CachedDiscussion("noteUuid")
    assert tested.updated == now
    assert tested.count == 1
    assert tested.note_uuid == "noteUuid"
    assert tested.previous_instructions == []
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    reset_mocks()

    CachedDiscussion.CACHED = {}


@patch("commander.protocols.commander.datetime", wraps=datetime)
def test_add_one(mock_datetime):
    def reset_mocks():
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 2, 4, 7, 48, 21, tzinfo=timezone.utc)
    date_1 = datetime(2025, 2, 4, 7, 48, 33, tzinfo=timezone.utc)
    mock_datetime.now.side_effect = [date_0, date_1]

    tested = CachedDiscussion("noteUuid")
    assert tested.updated == date_0
    assert tested.count == 1
    assert tested.note_uuid == "noteUuid"
    assert tested.previous_instructions == []
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    reset_mocks()

    tested.add_one()
    assert tested.updated == date_1
    assert tested.count == 2
    assert tested.note_uuid == "noteUuid"
    assert tested.previous_instructions == []
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    reset_mocks()

    CachedDiscussion.CACHED = {}


def test_get_discussion():
    tested = CachedDiscussion
    assert CachedDiscussion.CACHED == {}

    result = tested.get_discussion("noteUuid")
    assert isinstance(result, CachedDiscussion)
    assert CachedDiscussion.CACHED == {"noteUuid": result}

    result2 = tested.get_discussion("noteUuid")
    assert result == result2
    assert CachedDiscussion.CACHED == {"noteUuid": result}

    CachedDiscussion.CACHED = {}


@patch("commander.protocols.commander.datetime", wraps=datetime)
def test_clear_cache(mock_datetime):
    date_0 = datetime(2025, 2, 4, 7, 18, 21, tzinfo=timezone.utc)
    date_1 = datetime(2025, 2, 4, 7, 18, 33, tzinfo=timezone.utc)
    date_2 = datetime(2025, 2, 4, 7, 28, 21, tzinfo=timezone.utc)
    date_3 = datetime(2025, 2, 4, 7, 48, 27, tzinfo=timezone.utc)
    date_4 = datetime(2025, 2, 4, 7, 48, 37, tzinfo=timezone.utc)
    date_5 = datetime(2025, 2, 4, 7, 58, 37, tzinfo=timezone.utc)

    tested = CachedDiscussion

    mock_datetime.now.side_effect = [date_0]
    result0 = tested.get_discussion("noteUuid0")
    mock_datetime.now.side_effect = [date_1]
    result1 = tested.get_discussion("noteUuid1")
    mock_datetime.now.side_effect = [date_2]
    result2 = tested.get_discussion("noteUuid2")

    print("-------")
    print({k: i.updated for k, i in tested.CACHED.items()})
    print("-------")

    mock_datetime.now.side_effect = [date_2]
    tested.clear_cache()
    expected = {
        "noteUuid0": result0,
        "noteUuid1": result1,
        "noteUuid2": result2,
    }
    assert CachedDiscussion.CACHED == expected

    mock_datetime.now.side_effect = [date_3]
    tested.clear_cache()
    expected = {
        "noteUuid1": result1,
        "noteUuid2": result2,
    }
    assert CachedDiscussion.CACHED == expected

    mock_datetime.now.side_effect = [date_4]
    tested.clear_cache()
    expected = {
        "noteUuid2": result2,
    }
    assert CachedDiscussion.CACHED == expected

    mock_datetime.now.side_effect = [date_5]
    tested.clear_cache()
    assert CachedDiscussion.CACHED == {}

    CachedDiscussion.CACHED = {}


@patch.object(log, "info")
@patch.object(requests, "get")
def test_get_audio(get, info):
    def reset_mocks():
        get.reset_mock()
        info.reset_mock()

    tested = Audio
    # no error
    get.return_value.status_code = 200
    get.return_value.content = b"theResponse"
    result = tested.get_audio("theUrl")
    assert result == b"theResponse"
    calls = [call('theUrl', timeout=300)]
    assert get.mock_calls == calls
    calls = [
        call(' ---> audio url: theUrl'),
        call('           code: 200'),
        call('        content: 11'),
    ]
    assert info.mock_calls == calls
    reset_mocks()
    # with erro
    get.return_value.status_code = 202
    get.return_value.content = b"theResponse"
    result = tested.get_audio("theUrl")
    assert result == b""
    calls = [call('theUrl', timeout=300)]
    assert get.mock_calls == calls
    calls = [
        call(' ---> audio url: theUrl'),
        call('           code: 202'),
        call('        content: 11'),
    ]
    assert info.mock_calls == calls
    reset_mocks()


def test_constants():
    tested = Commander
    constants = {
        "SECRET_OPENAI_KEY": "OpenAIKey",
        "SECRET_SCIENCE_HOST": "ScienceHost",
        "SECRET_ONTOLOGIES_HOST": "OntologiesHost",
        "SECRET_PRE_SHARED_KEY": "PreSharedKey",
        "SECRET_ALLOW_COMMAND_UPDATES": "AllowCommandUpdates",
        "SECRET_AUDIO_HOST": "AudioHost",
        "LABEL_ENCOUNTER_COPILOT": "Encounter Copilot",
        "MAX_AUDIOS": 1,
        "RESPONDS_TO": ["TASK_COMMENT_CREATED"],
    }
    assert is_constant(tested, constants)


@patch.object(Audio, "get_audio")
def test_retrieve_audios(get_audio):
    def reset_mocks():
        get_audio.reset_mock()

    tested = Commander

    # no more audio
    get_audio.side_effect = [b""]
    result = tested.retrieve_audios("theHost", "patientUuid", "noteUuid", 3)
    assert result == []
    calls = [call('theHost/audio/patientUuid/noteUuid/3')]
    assert get_audio.mock_calls == calls
    reset_mocks()

    # some audio
    with patch.object(Commander, "MAX_AUDIOS", 3):
        get_audio.side_effect = [b"call 1", b"call 2", b"call 3", b"call 4"]
        result = tested.retrieve_audios("theHost", "patientUuid", "noteUuid", 3)
        assert result == [
            b'call 2',
            b'call 3',
            b'call 1',
        ]
        calls = [
            call('theHost/audio/patientUuid/noteUuid/3'),
            call('theHost/audio/patientUuid/noteUuid/1'),
            call('theHost/audio/patientUuid/noteUuid/2'),
        ]
        assert get_audio.mock_calls == calls
        reset_mocks()


@patch.object(log, "info")
@patch.object(Note, "objects")
@patch.object(TaskComment, "objects")
@patch.object(Commander, "compute_audio")
def test_compute(compute_audio, task_comment, note, info):
    mock_comment = MagicMock()
    mock_note = MagicMock()

    def reset_mocks():
        compute_audio.reset_mock()
        task_comment.reset_mock()
        note.reset_mock()
        info.reset_mock()
        mock_comment.reset_mock()
        mock_note.reset_mock()

    secrets = {}
    event = Event(EventRequest(target="taskUuid"))
    tested = Commander(event, secrets)

    # the task comment is not related to the Audio plugin
    compute_audio.side_effect = []
    mock_comment.id = "commentUuid"
    mock_comment.task.id = "taskUuid"
    mock_comment.task.labels.all.side_effect = [["label1", "label2"]]
    mock_comment.task.labels.filter.return_value.first.side_effect = [""]
    task_comment.get.side_effect = [mock_comment]

    result = tested.compute()
    assert result == []

    assert compute_audio.mock_calls == []
    calls = [call.get(id='taskUuid')]
    assert task_comment.mock_calls == calls
    assert note.mock_calls == []
    calls = [call("--> comment: commentUuid (task: taskUuid, labels: ['label1', 'label2'])")]
    assert info.mock_calls == calls
    calls = [
        call.task.labels.all(),
        call.task.labels.filter(name='Encounter Copilot'),
        call.task.labels.filter().first()
    ]
    assert mock_comment.mock_calls == calls
    assert mock_note.mock_calls == []
    reset_mocks()

    # the task is related to the Audio plugin
    # -- with more audio
    compute_audio.side_effect = [(True, [Effect(type="LOG", payload="SomePayload")])]
    mock_comment.id = "commentUuid"
    mock_comment.body = json.dumps({"chunk_index": 1, "note_id": "noteUuid"})
    mock_comment.task.id = "taskUuid"
    mock_comment.task.labels.all.side_effect = [["label1", "label2"]]
    mock_comment.task.labels.filter.return_value.first.side_effect = ["aTask"]
    task_comment.get.side_effect = [mock_comment]

    mock_note.provider.id = "providerUuid"
    mock_note.patient.id = "patientUuid"
    note.get.side_effect = [mock_note]

    result = tested.compute()
    expected = [
        Effect(
            type="LOG",
            payload="SomePayload",
        ),
        Effect(
            type="CREATE_TASK_COMMENT",
            payload='{"data": {'
                    '"task": {"id": "taskUuid"}, '
                    '"body": "{\\"note_id\\": \\"noteUuid\\", \\"patient_id\\": \\"patientUuid\\", \\"chunk_index\\": 2}"}}',
        ),
    ]
    assert result == expected

    calls = [call('patientUuid', 'noteUuid', 'providerUuid', 1)]
    assert compute_audio.mock_calls == calls
    calls = [call.get(id='taskUuid')]
    assert task_comment.mock_calls == calls
    calls = [
        call("--> comment: commentUuid (task: taskUuid, labels: ['label1', 'label2'])"),
        call('audio was present => go to next iteration (2)'),
    ]
    assert info.mock_calls == calls
    calls = [
        call.task.labels.all(),
        call.task.labels.filter(name='Encounter Copilot'),
        call.task.labels.filter().first()
    ]
    assert mock_comment.mock_calls == calls
    assert mock_note.mock_calls == []
    reset_mocks()
    # -- no more audio
    compute_audio.side_effect = [(False, [])]
    mock_comment.id = "commentUuid"
    mock_comment.body = json.dumps({"chunk_index": 1, "note_id": "noteUuid"})
    mock_comment.task.id = "taskUuid"
    mock_comment.task.labels.all.side_effect = [["label1", "label2"]]
    mock_comment.task.labels.filter.return_value.first.side_effect = ["aTask"]
    task_comment.get.side_effect = [mock_comment]

    mock_note.provider.id = "providerUuid"
    mock_note.patient.id = "patientUuid"
    note.get.side_effect = [mock_note]

    result = tested.compute()
    expected = [
        Effect(
            type="UPDATE_TASK",
            payload="{\"data\": {\"id\": \"taskUuid\", \"status\": \"COMPLETED\"}}",
        ),
    ]
    assert result == expected

    calls = [call('patientUuid', 'noteUuid', 'providerUuid', 1)]
    assert compute_audio.mock_calls == calls
    calls = [call.get(id='taskUuid')]
    assert task_comment.mock_calls == calls
    calls = [
        call("--> comment: commentUuid (task: taskUuid, labels: ['label1', 'label2'])"),
        call('audio was NOT present => stop the task'),
    ]
    assert info.mock_calls == calls
    calls = [
        call.task.labels.all(),
        call.task.labels.filter(name='Encounter Copilot'),
        call.task.labels.filter().first()
    ]
    assert mock_comment.mock_calls == calls
    assert mock_note.mock_calls == []
    reset_mocks()


def test_allow_command_updates():
    event = Event(EventRequest())

    tests = [
        ({}, False),
        ({"AllowCommandUpdates": "yes"}, True),
        ({"AllowCommandUpdates": "YES"}, True),
        ({"AllowCommandUpdates": "y"}, True),
        ({"AllowCommandUpdates": "Y"}, True),
        ({"AllowCommandUpdates": "1"}, True),
        ({"AllowCommandUpdates": "0"}, False),
        ({"AllowCommandUpdates": "anything"}, False),
    ]
    for secrets, expected in tests:
        tested = Commander(event, secrets)
        result = tested.allow_command_updates()
        assert result is expected
