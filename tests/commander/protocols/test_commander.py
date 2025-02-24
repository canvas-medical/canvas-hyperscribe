import json
from datetime import datetime, timezone
from unittest.mock import patch, call, MagicMock

import requests
from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.v1.data import TaskComment, Note, Command
from logger import log

from commander.protocols.commander import CachedDiscussion, Audio, Commander
from commander.protocols.structures.instruction import Instruction
from commander.protocols.structures.json_extract import JsonExtract
from commander.protocols.structures.line import Line
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey
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
        "SECRET_TEXT_VENDOR": "VendorTextLLM",
        "SECRET_TEXT_KEY": "KeyTextLLM",
        "SECRET_AUDIO_VENDOR": "VendorAudioLLM",
        "SECRET_AUDIO_KEY": "KeyAudioLLM",
        "SECRET_SCIENCE_HOST": "ScienceHost",
        "SECRET_ONTOLOGIES_HOST": "OntologiesHost",
        "SECRET_PRE_SHARED_KEY": "PreSharedKey",
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
def test_compute(compute_audio, task_comment_db, note_db, info):
    mock_comment = MagicMock()
    mock_note = MagicMock()

    def reset_mocks():
        compute_audio.reset_mock()
        task_comment_db.reset_mock()
        note_db.reset_mock()
        info.reset_mock()
        mock_comment.reset_mock()
        mock_note.reset_mock()

    secrets = {
        "VendorTextLLM": "theTextVendor",
        "VendorAudioLLM": "theAudioVendor",
    }
    event = Event(EventRequest(target="taskUuid"))
    tested = Commander(event, secrets)

    # the task comment is not related to the Audio plugin
    compute_audio.side_effect = []
    mock_comment.id = "commentUuid"
    mock_comment.task.id = "taskUuid"
    mock_comment.task.labels.all.side_effect = [["label1", "label2"]]
    mock_comment.task.labels.filter.return_value.first.side_effect = [""]
    task_comment_db.get.side_effect = [mock_comment]

    result = tested.compute()
    assert result == []

    assert compute_audio.mock_calls == []
    calls = [call.get(id='taskUuid')]
    assert task_comment_db.mock_calls == calls
    assert note_db.mock_calls == []
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
    task_comment_db.get.side_effect = [mock_comment]

    mock_note.provider.id = "providerUuid"
    mock_note.patient.id = "patientUuid"
    note_db.get.side_effect = [mock_note]

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
    assert task_comment_db.mock_calls == calls
    calls = [
        call("--> comment: commentUuid (task: taskUuid, labels: ['label1', 'label2'])"),
        call('Text: theTextVendor - Audio: theAudioVendor'),
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
    task_comment_db.get.side_effect = [mock_comment]

    mock_note.provider.id = "providerUuid"
    mock_note.patient.id = "patientUuid"
    note_db.get.side_effect = [mock_note]

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
    assert task_comment_db.mock_calls == calls
    calls = [
        call("--> comment: commentUuid (task: taskUuid, labels: ['label1', 'label2'])"),
        call('Text: theTextVendor - Audio: theAudioVendor'),
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


@patch('commander.protocols.commander.LimitedCache')
@patch('commander.protocols.commander.AudioInterpreter')
@patch('commander.protocols.commander.CachedDiscussion')
@patch('commander.protocols.commander.Auditor')
@patch.object(Commander, 'audio2commands')
@patch.object(Commander, 'existing_commands_to_instructions')
@patch.object(Commander, 'retrieve_audios')
@patch.object(log, "info")
def test_compute_audio(
        info,
        retrieve_audios,
        existing_commands_to_instructions,
        audio2commands,
        auditor,
        cached_discussion,
        audio_interpreter,
        limited_cache,
):
    def reset_mocks():
        info.reset_mock()
        retrieve_audios.reset_mock()
        existing_commands_to_instructions.reset_mock()
        audio2commands.reset_mock()
        auditor.reset_mock()
        cached_discussion.reset_mock()
        audio_interpreter.reset_mock()
        limited_cache.reset_mock()

    secrets = {
        "AudioHost": "theAudioHost",
        "KeyTextLLM": "theKeyTextLLM",
        "VendorTextLLM": "theVendorTextLLM",
        "KeyAudioLLM": "theKeyAudioLLM",
        "VendorAudioLLM": "theVendorAudioLLM",
        "ScienceHost": "theScienceHost",
        "OntologiesHost": "theOntologiesHost",
        "PreSharedKey": "thePreSharedKey",
        "AllowCommandUpdates": "yes",
    }
    event = Event(EventRequest(target="taskUuid"))

    # no more audio
    retrieve_audios.side_effect = [[]]
    existing_commands_to_instructions.side_effect = []
    audio2commands.side_effect = []
    auditor.side_effect = []
    cached_discussion.side_effect = []
    audio_interpreter.side_effect = []
    limited_cache.side_effect = []

    tested = Commander(event, secrets)
    result = tested.compute_audio("patientUuid", "noteUuid", "providerUuid", 3)
    expected = (False, [])
    assert result == expected

    calls = [call('--> audio chunks: 0')]
    assert info.mock_calls == calls
    calls = [call('theAudioHost', 'patientUuid', 'noteUuid', 3)]
    assert retrieve_audios.mock_calls == calls
    assert existing_commands_to_instructions.mock_calls == []
    assert audio2commands.mock_calls == []
    assert auditor.mock_calls == []
    calls = [call.clear_cache()]
    assert cached_discussion.mock_calls == calls
    assert audio_interpreter.mock_calls == []
    assert limited_cache.mock_calls == []
    reset_mocks()

    # audios retrieved
    instructions = [
        Instruction(uuid='uuidA', instruction='theInstructionA', information='theInformationA', is_new=False, is_updated=False),
        Instruction(uuid='uuidB', instruction='theInstructionB', information='theInformationB', is_new=False, is_updated=False),
        Instruction(uuid='uuidC', instruction='theInstructionC', information='theInformationC', is_new=True, is_updated=False),
    ]
    exp_settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        science_host='theScienceHost',
        ontologies_host='theOntologiesHost',
        pre_shared_key='thePreSharedKey',
    )
    discussion = CachedDiscussion("noteUuid")
    discussion.count = 2
    discussion.previous_instructions = instructions[2:]
    retrieve_audios.side_effect = [[b"audio1", b"audio2"]]
    existing_commands_to_instructions.side_effect = [instructions]
    audio2commands.side_effect = [
        (
            [
                Instruction(uuid='uuidA', instruction='theInstructionA', information='theInformationA', is_new=False, is_updated=True),
                Instruction(uuid='uuidB', instruction='theInstructionB', information='theInformationB', is_new=True, is_updated=False),
                Instruction(uuid='uuidC', instruction='theInstructionC', information='theInformationC', is_new=True, is_updated=False),
            ],
            [
                Effect(type="LOG", payload="Log1"),
                Effect(type="LOG", payload="Log2"),
                Effect(type="LOG", payload="Log3"),
            ],
        )
    ]
    auditor.side_effect = ["AuditorInstance"]
    cached_discussion.get_discussion.side_effect = [discussion]
    audio_interpreter.side_effect = ["AudioInterpreterInstance"]
    limited_cache.side_effect = ["LimitedCacheInstance"]
    tested = Commander(event, secrets)
    result = tested.compute_audio("patientUuid", "noteUuid", "providerUuid", 3)
    expected = (
        True, [
            Effect(type="LOG", payload="Log1"),
            Effect(type="LOG", payload="Log2"),
            Effect(type="LOG", payload="Log3"),
        ])
    assert result == expected

    assert discussion.count == 3
    previous = [
        Instruction(uuid='uuidA', instruction='theInstructionA', information='theInformationA', is_new=False, is_updated=True),
        Instruction(uuid='uuidB', instruction='theInstructionB', information='theInformationB', is_new=True, is_updated=False),
        Instruction(uuid='uuidC', instruction='theInstructionC', information='theInformationC', is_new=True, is_updated=False),
    ]
    assert discussion.previous_instructions == previous

    calls = [
        call('--> audio chunks: 2'),
        call('<===  note: noteUuid ===>'),
        call("instructions: ["
             "Instruction(uuid='uuidA', instruction='theInstructionA', information='theInformationA', is_new=False, is_updated=True), "
             "Instruction(uuid='uuidB', instruction='theInstructionB', information='theInformationB', is_new=True, is_updated=False), "
             "Instruction(uuid='uuidC', instruction='theInstructionC', information='theInformationC', is_new=True, is_updated=False)]"),
        call('<-------->'),
        call('command: LOG'),
        call('Log1'),
        call('command: LOG'),
        call('Log2'),
        call('command: LOG'),
        call('Log3'),
        call('<=== END ===>'),
    ]
    assert info.mock_calls == calls
    calls = [call('theAudioHost', 'patientUuid', 'noteUuid', 3)]
    assert retrieve_audios.mock_calls == calls
    calls = [call('AudioInterpreterInstance', instructions[2:])]
    assert existing_commands_to_instructions.mock_calls == calls
    calls = [call('AuditorInstance', [b'audio1', b'audio2'], 'AudioInterpreterInstance', instructions)]
    assert audio2commands.mock_calls == calls
    calls = [call()]
    assert auditor.mock_calls == calls
    calls = [
        call.clear_cache(),
        call.get_discussion('noteUuid'),
    ]
    assert cached_discussion.mock_calls == calls
    calls = [call(exp_settings, "LimitedCacheInstance", "patientUuid", "noteUuid", "providerUuid")]
    assert audio_interpreter.mock_calls == calls
    calls = [call("patientUuid")]
    assert limited_cache.mock_calls == calls
    reset_mocks()


@patch.object(Commander, 'update_commands_from')
@patch.object(Commander, 'new_commands_from')
@patch.object(log, "info")
def test_audio2commands(info, new_commands_from, update_commands_from):
    mock_auditor = MagicMock()
    mock_chatter = MagicMock()

    def reset_mocks():
        info.reset_mock()
        new_commands_from.reset_mock()
        update_commands_from.reset_mock()
        mock_auditor.reset_mock()
        mock_chatter.reset_mock()

    tested = Commander

    transcript = [
        {"speaker": "speaker1", "text": "textA"},
        {"speaker": "speaker2", "text": "textB"},
        {"speaker": "speaker1", "text": "textC"},
    ]
    audios = [b"audio1", b"audio2"]
    previous = [
        Instruction(
            uuid="uuidA",
            instruction="theInstructionA",
            information="theInformationA",
            is_new=True,
            is_updated=False,
        ),
    ]
    # all good
    new_commands_from.side_effect = [[Effect(type="LOG", payload="Log1"), Effect(type="LOG", payload="Log2")]]
    update_commands_from.side_effect = [[Effect(type="LOG", payload="Log3")]]
    mock_chatter.combine_and_speaker_detection.side_effect = [
        JsonExtract(has_error=False, error="", content=transcript),
    ]
    mock_chatter.detect_instructions.side_effect = [
        [
            {"uuid": "uuidA", "instruction": "theInstructionA", "information": "theInformationA", "isNew": False, "isUpdated": True},
            {"uuid": "uuidB", "instruction": "theInstructionB", "information": "theInformationB", "isNew": True, "isUpdated": False},
            {"uuid": "uuidC", "instruction": "theInstructionC", "information": "theInformationC", "isNew": True, "isUpdated": False},
        ],
    ]

    result = tested.audio2commands(mock_auditor, audios, mock_chatter, previous)
    expected = (
        [
            Instruction(
                uuid="uuidA",
                instruction="theInstructionA",
                information="theInformationA",
                is_new=False,
                is_updated=True,
            ),
            Instruction(
                uuid="uuidB",
                instruction="theInstructionB",
                information="theInformationB",
                is_new=True,
                is_updated=False,
            ),
            Instruction(
                uuid="uuidC",
                instruction="theInstructionC",
                information="theInformationC",
                is_new=True,
                is_updated=False,
            ),
        ],
        [
            Effect(type="LOG", payload="Log1"),
            Effect(type="LOG", payload="Log2"),
            Effect(type="LOG", payload="Log3"),
        ])
    assert result == expected

    calls = [
        call('--> transcript back and forth: 3'),
        call('--> instructions: 3'),
    ]
    assert info.mock_calls == calls
    calls = [
        call(
            mock_auditor,
            mock_chatter,
            [
                Instruction(uuid='uuidA', instruction='theInstructionA', information='theInformationA', is_new=False, is_updated=True),
                Instruction(uuid='uuidB', instruction='theInstructionB', information='theInformationB', is_new=True, is_updated=False),
                Instruction(uuid='uuidC', instruction='theInstructionC', information='theInformationC', is_new=True, is_updated=False),
            ],
            {
                'uuidA': Instruction(uuid='uuidA', instruction='theInstructionA', information='theInformationA', is_new=True, is_updated=False),
            },
        ),
    ]
    assert new_commands_from.mock_calls == calls
    assert update_commands_from.mock_calls == calls
    calls = [
        call.identified_transcript(
            [b'audio1', b'audio2'],
            [
                Line(speaker='speaker1', text='textA'),
                Line(speaker='speaker2', text='textB'),
                Line(speaker='speaker1', text='textC'),
            ],
        ),
        call.found_instructions(
            [
                Line(speaker='speaker1', text='textA'),
                Line(speaker='speaker2', text='textB'),
                Line(speaker='speaker1', text='textC'),
            ],
            [
                Instruction(uuid='uuidA', instruction='theInstructionA', information='theInformationA', is_new=False, is_updated=True),
                Instruction(uuid='uuidB', instruction='theInstructionB', information='theInformationB', is_new=True, is_updated=False),
                Instruction(uuid='uuidC', instruction='theInstructionC', information='theInformationC', is_new=True, is_updated=False),
            ],
        )
    ]
    assert mock_auditor.mock_calls == calls
    calls = [
        call.combine_and_speaker_detection([b'audio1', b'audio2']),
        call.detect_instructions(
            [
                Line(speaker='speaker1', text='textA'),
                Line(speaker='speaker2', text='textB'),
                Line(speaker='speaker1', text='textC'),
            ],
            previous,
        ),
    ]
    assert mock_chatter.mock_calls == calls
    reset_mocks()
    # --- transcript has error
    new_commands_from.side_effect = [[Effect(type="LOG", payload="Log1"), Effect(type="LOG", payload="Log2")]]
    update_commands_from.side_effect = [[Effect(type="LOG", payload="Log3")]]
    mock_chatter.combine_and_speaker_detection.side_effect = [
        JsonExtract(has_error=True, error="theError", content=transcript),
    ]
    mock_chatter.detect_instructions.side_effect = []

    result = tested.audio2commands(mock_auditor, audios, mock_chatter, previous)
    expected = (previous, [])
    assert result == expected

    calls = [
        call('--> transcript encountered: theError'),
    ]
    assert info.mock_calls == calls
    assert new_commands_from.mock_calls == []
    assert update_commands_from.mock_calls == []
    calls = [
        call.combine_and_speaker_detection([b'audio1', b'audio2']),
    ]
    assert mock_chatter.mock_calls == calls
    reset_mocks()


@patch("commander.protocols.commander.time")
@patch.object(log, "info")
def test_new_commands_from(info, time):
    auditor = MagicMock()
    chatter = MagicMock()
    mock_commands = [
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        info.reset_mock()
        time.reset_mock()
        auditor.reset_mock()
        chatter.reset_mock()
        for a_command in mock_commands:
            a_command.reset_mock()

    instructions = [
        Instruction(uuid='uuidA', instruction='theInstructionA', information='theInformationA', is_new=False, is_updated=True),
        Instruction(uuid='uuidB', instruction='theInstructionB', information='theInformationB', is_new=True, is_updated=False),
        Instruction(uuid='uuidC', instruction='theInstructionC', information='theInformationC', is_new=True, is_updated=False),
        Instruction(uuid='uuidD', instruction='theInstructionD', information='theInformationD', is_new=True, is_updated=False),
        Instruction(uuid='uuidE', instruction='theInstructionE', information='theInformationE', is_new=True, is_updated=False),
    ]

    tested = Commander
    # no new instruction
    past_uuids = {
        "uuidA": instructions[0],
        "uuidB": instructions[1],
        "uuidC": instructions[2],
        "uuidD": instructions[3],
        "uuidE": instructions[4],
    }
    time.side_effect = [111.110, 111.219]
    chatter.create_sdk_command_parameters.side_effect = []
    chatter.create_sdk_command_from.side_effect = []
    for mock_command in mock_commands:
        mock_command.originate.side_effect = []

    result = tested.new_commands_from(auditor, chatter, instructions, past_uuids)
    assert result == []
    calls = [
        call('--> new instructions: 0'),
        call('--> new commands: 0'),
        call('DURATION NEW: 108'),
    ]
    assert info.mock_calls == calls
    calls = [call(), call()]
    assert time.mock_calls == calls
    calls = [
        call.computed_parameters([]),
        call.computed_commands([], []),
    ]
    assert auditor.mock_calls == calls
    assert chatter.mock_calls == []
    for mock_command in mock_commands:
        assert mock_command.mock_calls == []
    reset_mocks()

    # with new instructions
    past_uuids = {
        "uuidA": instructions[0],
    }
    time.side_effect = [111.110, 111.357]
    chatter.create_sdk_command_parameters.side_effect = [
        (instructions[1], {"params": "instruction1"}),
        (instructions[2], None),
        (instructions[3], {"params": "instruction3"}),
        (instructions[4], {"params": "instruction4"}),
    ]
    chatter.create_sdk_command_from.side_effect = [
        mock_commands[0],
        mock_commands[1],
        None,
    ]
    for idx, mock_command in enumerate(mock_commands):
        mock_command.originate.side_effect = [Effect(type="LOG", payload=f"Log{idx}")]

    result = tested.new_commands_from(auditor, chatter, instructions, past_uuids)
    expected = [
        Effect(type="LOG", payload="Log0"),
        Effect(type="LOG", payload="Log1"),
    ]
    assert result == expected
    calls = [
        call('--> new instructions: 4'),
        call('--> new commands: 3'),
        call('DURATION NEW: 246'),
    ]
    assert info.mock_calls == calls
    calls = [call(), call()]
    assert time.mock_calls == calls
    calls = [
        call.computed_parameters(
            [
                (instructions[1], {'params': 'instruction1'}),
                (instructions[3], {'params': 'instruction3'}),
                (instructions[4], {'params': 'instruction4'}),
            ]
        ),
        call.computed_commands(
            [
                (instructions[1], {'params': 'instruction1'}),
                (instructions[3], {'params': 'instruction3'}),
                (instructions[4], {'params': 'instruction4'}),
            ],
            mock_commands,
        ),
    ]
    assert auditor.mock_calls == calls
    calls = [
        call.create_sdk_command_parameters(instructions[1]),
        call.create_sdk_command_parameters(instructions[2]),
        call.create_sdk_command_parameters(instructions[3]),
        call.create_sdk_command_parameters(instructions[4]),
        call.create_sdk_command_from(instructions[1], {'params': 'instruction1'}),
        call.create_sdk_command_from(instructions[3], {'params': 'instruction3'}),
        call.create_sdk_command_from(instructions[4], {'params': 'instruction4'}),
    ]
    assert chatter.mock_calls == calls
    calls = [
        call.originate(),
    ]
    for mock_command in mock_commands:
        assert mock_command.mock_calls == calls
    reset_mocks()


@patch("commander.protocols.commander.time")
@patch.object(log, "info")
def test_update_commands_from(info, time):
    auditor = MagicMock()
    chatter = MagicMock()
    mock_commands = [
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        info.reset_mock()
        time.reset_mock()
        auditor.reset_mock()
        chatter.reset_mock()
        for a_command in mock_commands:
            a_command.reset_mock()

    instructions = [
        Instruction(uuid='uuidA', instruction='theInstructionX', information='theInformationA', is_new=False, is_updated=True),
        Instruction(uuid='uuidB', instruction='theInstructionX', information='theInformationB', is_new=False, is_updated=True),
        Instruction(uuid='uuidC', instruction='theInstructionY', information='theInformationC', is_new=False, is_updated=True),
        Instruction(uuid='uuidD', instruction='theInstructionY', information='theInformationD', is_new=False, is_updated=True),
        Instruction(uuid='uuidE', instruction='theInstructionY', information='theInformationE', is_new=True, is_updated=False),
        Instruction(uuid='uuidF', instruction='theInstructionY', information='theInformationF', is_new=True, is_updated=False),
    ]
    chatter.note_uuid = "noteUuid"
    chatter.patient_id = "patientUuid"

    tested = Commander
    # all new instructions
    past_uuids = {}
    time.side_effect = [111.110, 111.357]
    chatter.create_sdk_command_parameters.side_effect = []
    chatter.create_sdk_command_from.side_effect = []
    for mock_command in mock_commands:
        mock_command.originate.side_effect = []

    result = tested.update_commands_from(auditor, chatter, instructions, past_uuids)
    assert result == []
    calls = [
        call('--> updated instructions: 0'),
        call('--> updated commands: 0'),
        call('DURATION UPDATE: 246'),
    ]
    assert info.mock_calls == calls
    calls = [call(), call()]
    assert time.mock_calls == calls
    calls = [
        call.computed_parameters([]),
        call.computed_commands([], []),
    ]
    assert auditor.mock_calls == calls
    assert chatter.mock_calls == []
    for mock_command in mock_commands:
        assert mock_command.mock_calls == []
    reset_mocks()

    # updated instructions
    past_uuids = {
        "uuidA": Instruction(uuid='uuidA', instruction='theInstructionX', information='changedA', is_new=False, is_updated=True),
        "uuidB": instructions[1],
        "uuidC": instructions[2],
        "uuidD": Instruction(uuid='uuidD', instruction='theInstructionY', information='changedD', is_new=False, is_updated=True),
        "uuidE": Instruction(uuid='uuidE', instruction='theInstructionY', information='changedE', is_new=True, is_updated=False),
        "uuidF": Instruction(uuid='uuidF', instruction='theInstructionY', information='changedE', is_new=True, is_updated=False),
    }
    time.side_effect = [111.110, 111.451]
    chatter.create_sdk_command_parameters.side_effect = [
        (instructions[0], {"params": "instruction0"}),
        (instructions[3], {"params": "instruction3"}),
        (instructions[4], None),
        (instructions[5], {"params": "instruction5"}),
    ]
    chatter.create_sdk_command_from.side_effect = [
        mock_commands[0],
        mock_commands[1],
        None,
    ]
    for idx, mock_command in enumerate(mock_commands):
        mock_command.edit.side_effect = [Effect(type="LOG", payload=f"Log{idx}")]

    result = tested.update_commands_from(auditor, chatter, instructions, past_uuids)
    expected = [
        Effect(type="LOG", payload="Log0"),
        Effect(type="LOG", payload="Log1"),
    ]
    assert result == expected
    calls = [
        call('--> updated instructions: 4'),
        call('--> updated commands: 3'),
        call('DURATION UPDATE: 340'),
    ]
    assert info.mock_calls == calls
    calls = [call(), call()]
    assert time.mock_calls == calls
    calls = [
        call.computed_parameters(
            [
                (instructions[0], {'params': 'instruction0'}),
                (instructions[3], {'params': 'instruction3'}),
                (instructions[5], {'params': 'instruction5'}),
            ]
        ),
        call.computed_commands(
            [
                (instructions[0], {'params': 'instruction0'}),
                (instructions[3], {'params': 'instruction3'}),
                (instructions[5], {'params': 'instruction5'}),
            ],
            mock_commands,
        ),
    ]
    assert auditor.mock_calls == calls
    calls = [
        call.create_sdk_command_parameters(instructions[0]),
        call.create_sdk_command_parameters(instructions[3]),
        call.create_sdk_command_parameters(instructions[4]),
        call.create_sdk_command_parameters(instructions[5]),
        call.create_sdk_command_from(instructions[0], {'params': 'instruction0'}),
        call.create_sdk_command_from(instructions[3], {'params': 'instruction3'}),
        call.create_sdk_command_from(instructions[5], {'params': 'instruction5'}),
    ]
    assert chatter.mock_calls == calls
    calls = [
        call.edit(),
    ]
    for mock_command in mock_commands:
        assert mock_command.mock_calls == calls
    reset_mocks()


@patch.object(Command, "objects")
@patch.object(Note, "objects")
def test_map_instruction2command_uuid(note_db, command_db):
    chatter = MagicMock()

    def reset_mocks():
        note_db.reset_mock()
        command_db.reset_mock()
        chatter.reset_mock()

    instructions = [
        Instruction(uuid='uuidA', instruction='theInstructionX', information='theInformationA', is_new=False, is_updated=True),
        Instruction(uuid='uuidB', instruction='theInstructionX', information='theInformationB', is_new=False, is_updated=True),
        Instruction(uuid='uuidC', instruction='theInstructionY', information='theInformationC', is_new=False, is_updated=True),
        Instruction(uuid='uuidD', instruction='theInstructionY', information='theInformationD', is_new=False, is_updated=True),
        Instruction(uuid='uuidE', instruction='theInstructionY', information='theInformationE', is_new=True, is_updated=False),
    ]
    chatter.note_uuid = "noteUuid"
    chatter.patient_id = "patientUuid"

    tested = Commander
    # only new instructions
    past_uuids = {}
    note_db.get.side_effect = [Note(dbid=751)]
    command_db.filter.return_value.order_by.side_effect = [
        [
            Command(id="uuid1", schema_key="canvas_command_X"),
            Command(id="uuid2", schema_key="canvas_command_X"),
            Command(id="uuid3", schema_key="canvas_command_Y"),
            Command(id="uuid4", schema_key="canvas_command_Y"),
            Command(id="uuid5", schema_key="canvas_command_Y"),
        ],
    ]
    chatter.schema_key2instruction.side_effect = [
        {
            "canvas_command_X": "theInstructionX",
            "canvas_command_Y": "theInstructionY",
        },
    ]

    result = tested.map_instruction2command_uuid(chatter, past_uuids)
    assert result == {}
    calls = [call.get(id='noteUuid')]
    assert note_db.mock_calls == calls
    calls = [
        call.filter(patient__id='patientUuid', note_id=751, origination_source='plugin', state='staged'),
        call.filter().order_by("schema_key", "dbid"),
    ]
    assert command_db.mock_calls == calls
    calls = [call.schema_key2instruction()]
    assert chatter.mock_calls == calls
    reset_mocks()

    # updated instructions
    past_uuids = {
        "uuidA": Instruction(uuid='uuidA', instruction='theInstructionX', information='changedA', is_new=False, is_updated=True),
        "uuidB": instructions[1],
        "uuidC": instructions[2],
        "uuidD": Instruction(uuid='uuidD', instruction='theInstructionY', information='changedD', is_new=False, is_updated=True),
        "uuidE": Instruction(uuid='uuidE', instruction='theInstructionY', information='changedE', is_new=True, is_updated=False),
    }
    note_db.get.side_effect = [Note(dbid=751)]
    command_db.filter.return_value.order_by.side_effect = [
        [
            Command(id="uuid1", schema_key="canvas_command_X"),
            Command(id="uuid2", schema_key="canvas_command_X"),
            Command(id="uuid3", schema_key="canvas_command_Y"),
            Command(id="uuid4", schema_key="canvas_command_Y"),
            Command(id="uuid5", schema_key="canvas_command_Y"),
        ],
    ]
    chatter.schema_key2instruction.side_effect = [
        {
            "canvas_command_X": "theInstructionX",
            "canvas_command_Y": "theInstructionY",
        },
    ]

    result = tested.map_instruction2command_uuid(chatter, past_uuids)
    expected = {
        "uuidA": "uuid1",
        "uuidB": "uuid2",
        "uuidC": "uuid3",
        "uuidD": "uuid4",
        "uuidE": "uuid5",
    }
    assert result == expected
    calls = [call.get(id='noteUuid')]
    assert note_db.mock_calls == calls
    calls = [
        call.filter(patient__id='patientUuid', note_id=751, origination_source='plugin', state='staged'),
        call.filter().order_by("schema_key", "dbid"),
    ]
    assert command_db.mock_calls == calls
    reset_mocks()


@patch.object(Command, "objects")
@patch.object(Note, "objects")
def test_existing_commands_to_instructions(note_db, command_db):
    chatter = MagicMock()

    def reset_mocks():
        note_db.reset_mock()
        command_db.reset_mock()
        chatter.reset_mock()

    chatter.note_uuid = "noteUuid"
    chatter.patient_id = "patientUuid"

    tested = Commander
    # only new instructions
    note_db.get.side_effect = [Note(dbid=751)]
    command_db.filter.return_value.order_by.side_effect = [
        [
            Command(id="uuid1", schema_key="canvas_command_X"),
            Command(id="uuid2", schema_key="canvas_command_X"),
            Command(id="uuid3", schema_key="canvas_command_Y"),
            Command(id="uuid4", schema_key="canvas_command_Y"),
            Command(id="uuid5", schema_key="canvas_command_Y"),
        ],
    ]
    chatter.schema_key2instruction.side_effect = [
        {
            "canvas_command_X": "theInstructionX",
            "canvas_command_Y": "theInstructionY",
        },
    ]

    result = tested.existing_commands_to_instructions(chatter, [])
    expected = [
        Instruction(uuid='uuid1', instruction='theInstructionX', information='', is_new=False, is_updated=False),
        Instruction(uuid='uuid2', instruction='theInstructionX', information='', is_new=False, is_updated=False),
        Instruction(uuid='uuid3', instruction='theInstructionY', information='', is_new=False, is_updated=False),
        Instruction(uuid='uuid4', instruction='theInstructionY', information='', is_new=False, is_updated=False),
        Instruction(uuid='uuid5', instruction='theInstructionY', information='', is_new=False, is_updated=False),
    ]
    assert result == expected
    calls = [call.get(id='noteUuid')]
    assert note_db.mock_calls == calls
    calls = [
        call.filter(patient__id='patientUuid', note_id=751, state='staged'),
        call.filter().order_by("schema_key", "dbid"),
    ]
    assert command_db.mock_calls == calls
    calls = [call.schema_key2instruction()]
    assert chatter.mock_calls == calls
    reset_mocks()

    # updated instructions
    note_db.get.side_effect = [Note(dbid=751)]
    command_db.filter.return_value.order_by.side_effect = [
        [
            Command(id="uuid1", schema_key="canvas_command_X", data={"narrative": "theNarrative1", "comment": "theComment1"}),
            Command(id="uuid2", schema_key="canvas_command_X", data={"narrative": "theNarrative2", "comment": "theComment2"}),
            Command(id="uuid3", schema_key="canvas_command_Y", data={"narrative": "theNarrative3", "comment": "theComment3"}),
            Command(id="uuid4", schema_key="canvas_command_Y", data={"narrative": "theNarrative4", "comment": "theComment4"}),
            Command(id="uuid5", schema_key="canvas_command_Y", data={"narrative": "theNarrative5", "comment": "theComment5"}),
            Command(id="uuid6", schema_key="hpi", data={"narrative": "theNarrative6", "comment": "theComment6"}),
            Command(id="uuid7", schema_key="reasonForVisit", data={"narrative": "theNarrative7", "comment": "theComment7"}),
        ],
    ]
    chatter.schema_key2instruction.side_effect = [
        {
            "canvas_command_X": "theInstructionX",
            "canvas_command_Y": "theInstructionY",
            "hpi": "HistoryOfPresentIllness",
            "reasonForVisit": "ReasonForVisit",
        },
    ]
    instructions = [
        Instruction(uuid='uuidA', instruction='theInstructionX', information='theInformationA', is_new=True, is_updated=True),
        Instruction(uuid='uuidB', instruction='theInstructionY', information='theInformationD', is_new=True, is_updated=True),
        Instruction(uuid='uuidC', instruction='theInstructionY', information='theInformationE', is_new=True, is_updated=True),
    ]

    result = tested.existing_commands_to_instructions(chatter, instructions)
    expected = [
        Instruction(uuid='uuid1', instruction='theInstructionX', information='theInformationA', is_new=False, is_updated=False),
        Instruction(uuid='uuid2', instruction='theInstructionX', information='', is_new=False, is_updated=False),
        Instruction(uuid='uuid3', instruction='theInstructionY', information='theInformationD', is_new=False, is_updated=False),
        Instruction(uuid='uuid4', instruction='theInstructionY', information='theInformationE', is_new=False, is_updated=False),
        Instruction(uuid='uuid5', instruction='theInstructionY', information='', is_new=False, is_updated=False),
        Instruction(uuid='uuid6', instruction='HistoryOfPresentIllness', information='theNarrative6', is_new=False, is_updated=False),
        Instruction(uuid='uuid7', instruction='ReasonForVisit', information='theComment7', is_new=False, is_updated=False),
    ]
    assert result == expected
    calls = [call.get(id='noteUuid')]
    assert note_db.mock_calls == calls
    calls = [
        call.filter(patient__id='patientUuid', note_id=751, state='staged'),
        call.filter().order_by("schema_key", "dbid"),
    ]
    assert command_db.mock_calls == calls
    reset_mocks()
