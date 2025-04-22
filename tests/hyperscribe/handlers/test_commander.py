import json
from datetime import datetime, timezone
from unittest.mock import patch, call, MagicMock

import requests
from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.v1.data import TaskComment, Note, Command, TaskLabel
from logger import log

from hyperscribe.handlers.cached_discussion import CachedDiscussion
from hyperscribe.handlers.commander import Audio, Commander
from hyperscribe.handlers.implemented_commands import ImplementedCommands
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import is_constant


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
    # with error
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
        "LABEL_ENCOUNTER_COPILOT": "Encounter Copilot",
        "MAX_AUDIOS": 1,
        "MEMORY_LOG_LABEL": "main",
        "RESPONDS_TO": ["TASK_COMMENT_CREATED"],
    }
    assert is_constant(tested, constants)


@patch("hyperscribe.handlers.commander.MemoryLog")
@patch.object(log, "info")
@patch.object(Note, "objects")
@patch.object(TaskComment, "objects")
@patch.object(Commander, "compute_audio")
def test_compute(compute_audio, task_comment_db, note_db, info, memory_log):
    mock_comment = MagicMock()
    mock_note = MagicMock()

    def reset_mocks():
        compute_audio.reset_mock()
        task_comment_db.reset_mock()
        note_db.reset_mock()
        info.reset_mock()
        memory_log.reset_mock()
        mock_comment.reset_mock()
        mock_note.reset_mock()

    task_labels = [
        TaskLabel(name="label1"),
        TaskLabel(name="label2"),
    ]
    identification = IdentificationParameters(
        patient_uuid='patientUuid',
        note_uuid='noteUuid',
        provider_uuid='providerUuid',
        canvas_instance='theTestEnv',
    )
    secrets = {
        "VendorTextLLM": "theTextVendor",
        "VendorAudioLLM": "theAudioVendor",
    }
    event = Event(EventRequest(target="taskUuid"))
    environment = {"CUSTOMER_IDENTIFIER": "theTestEnv"}
    tested = Commander(event, secrets, environment)

    # the task comment is not related to the Audio plugin
    compute_audio.side_effect = []
    mock_comment.id = "commentUuid"
    mock_comment.task.id = "taskUuid"
    mock_comment.task.labels.all.side_effect = [task_labels]
    mock_comment.task.labels.filter.return_value.first.side_effect = [""]
    task_comment_db.get.side_effect = [mock_comment]

    result = tested.compute()
    assert result == []

    assert compute_audio.mock_calls == []
    calls = [call.get(id='taskUuid')]
    assert task_comment_db.mock_calls == calls
    assert note_db.mock_calls == []
    calls = [call("--> comment: commentUuid (task: taskUuid, labels: label1/label2)")]
    assert info.mock_calls == calls
    assert memory_log.mock_calls == []
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
    mock_comment.task.labels.all.side_effect = [task_labels]
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

    calls = [call(identification, 1)]
    assert compute_audio.mock_calls == calls
    calls = [call.get(id='taskUuid')]
    assert task_comment_db.mock_calls == calls
    calls = [
        call("--> comment: commentUuid (task: taskUuid, labels: label1/label2)"),
        call("audio was present => go to next iteration (2)"),
    ]
    assert info.mock_calls == calls
    calls = [
        call(identification, 'main'),
        call().output('Text: theTextVendor - Audio: theAudioVendor'),
        call.end_session('noteUuid'),
    ]
    assert memory_log.mock_calls == calls
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
    mock_comment.task.labels.all.side_effect = [task_labels]
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

    calls = [call(identification, 1)]
    assert compute_audio.mock_calls == calls
    calls = [call.get(id='taskUuid')]
    assert task_comment_db.mock_calls == calls
    calls = [
        call("--> comment: commentUuid (task: taskUuid, labels: label1/label2)"),
        call("audio was NOT present => stop the task"),
    ]
    assert info.mock_calls == calls
    calls = [
        call(identification, 'main'),
        call().output('Text: theTextVendor - Audio: theAudioVendor'),
        call.end_session('noteUuid'),
    ]
    assert memory_log.mock_calls == calls
    calls = [
        call.task.labels.all(),
        call.task.labels.filter(name='Encounter Copilot'),
        call.task.labels.filter().first()
    ]
    assert mock_comment.mock_calls == calls
    assert mock_note.mock_calls == []
    reset_mocks()


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


@patch('hyperscribe.handlers.commander.AwsS3')
@patch('hyperscribe.handlers.commander.MemoryLog')
@patch('hyperscribe.handlers.commander.LimitedCache')
@patch('hyperscribe.handlers.commander.AudioInterpreter')
@patch('hyperscribe.handlers.commander.CachedDiscussion')
@patch('hyperscribe.handlers.commander.Auditor')
@patch.object(Command, "objects")
@patch.object(Commander, 'existing_commands_to_coded_items')
@patch.object(Commander, 'existing_commands_to_instructions')
@patch.object(Commander, 'audio2commands')
@patch.object(Commander, 'retrieve_audios')
def test_compute_audio(
        retrieve_audios,
        audio2commands,
        existing_commands_to_instructions,
        existing_commands_to_coded_items,
        command_db,
        auditor,
        cached_discussion,
        audio_interpreter,
        limited_cache,
        memory_log,
        aws_s3,
):
    def reset_mocks():
        retrieve_audios.reset_mock()
        audio2commands.reset_mock()
        existing_commands_to_instructions.reset_mock()
        existing_commands_to_coded_items.reset_mock()
        command_db.reset_mock()
        auditor.reset_mock()
        cached_discussion.reset_mock()
        audio_interpreter.reset_mock()
        limited_cache.reset_mock()
        memory_log.reset_mock()
        aws_s3.reset_mock()

    secrets = {
        "AudioHost": "theAudioHost",
        "KeyTextLLM": "theKeyTextLLM",
        "VendorTextLLM": "theVendorTextLLM",
        "KeyAudioLLM": "theKeyAudioLLM",
        "VendorAudioLLM": "theVendorAudioLLM",
        "ScienceHost": "theScienceHost",
        "OntologiesHost": "theOntologiesHost",
        "PreSharedKey": "thePreSharedKey",
        "StructuredReasonForVisit": "yes",
        "AwsKey": "theKey",
        "AwsSecret": "theSecret",
        "AwsRegion": "theRegion",
        "AwsBucket": "theBucket",
    }
    event = Event(EventRequest(target="taskUuid"))
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    # no more audio
    retrieve_audios.side_effect = [[]]
    audio2commands.side_effect = []
    existing_commands_to_instructions.side_effect = []
    existing_commands_to_coded_items.side_effect = []
    command_db.filter.return_value.order_by.side_effect = []
    auditor.side_effect = []
    cached_discussion.side_effect = []
    audio_interpreter.side_effect = []
    limited_cache.side_effect = []
    aws_s3.return_value.is_ready.side_effect = []

    tested = Commander(event, secrets)
    result = tested.compute_audio(identification, 3)
    expected = (False, [])
    assert result == expected

    calls = [
        call(identification, 'main'),
        call().output('--> audio chunks: 0'),
    ]
    assert memory_log.mock_calls == calls
    calls = [call('theAudioHost', 'patientUuid', 'noteUuid', 3)]
    assert retrieve_audios.mock_calls == calls
    assert audio2commands.mock_calls == []
    assert existing_commands_to_instructions.mock_calls == []
    assert existing_commands_to_coded_items.mock_calls == []
    assert command_db.mock_calls == []
    assert auditor.mock_calls == []
    calls = [call.clear_cache()]
    assert cached_discussion.mock_calls == calls
    assert audio_interpreter.mock_calls == []
    assert limited_cache.mock_calls == []
    assert aws_s3.mock_calls == []
    reset_mocks()

    # audios retrieved
    for is_ready in [True, False]:
        instructions = [
            Instruction(
                uuid='uuidA',
                instruction='theInstructionA',
                information='theInformationA',
                is_new=False,
                is_updated=False,
                audits=["lineA"],
            ),
            Instruction(
                uuid='uuidB',
                instruction='theInstructionB',
                information='theInformationB',
                is_new=False,
                is_updated=False,
                audits=["lineB"],
            ),
            Instruction(
                uuid='uuidC',
                instruction='theInstructionC',
                information='theInformationC',
                is_new=True,
                is_updated=False,
                audits=["lineC"],
            ),
        ]
        exp_instructions = [
            Instruction(
                uuid='uuidA',
                instruction='theInstructionA',
                information='theInformationA',
                is_new=False,
                is_updated=True,
                audits=["lineA"],
            ),
            Instruction(
                uuid='uuidB',
                instruction='theInstructionB',
                information='theInformationB',
                is_new=True,
                is_updated=False,
                audits=["lineB"],
            ),
            Instruction(
                uuid='uuidC',
                instruction='theInstructionC',
                information='theInformationC',
                is_new=True,
                is_updated=False,
                audits=["lineC"],
            ),
        ]
        exp_effects = [
            Effect(type="LOG", payload="Log1"),
            Effect(type="LOG", payload="Log2"),
            Effect(type="LOG", payload="Log3"),
        ]
        exp_settings = Settings(
            llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
            llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
            science_host='theScienceHost',
            ontologies_host='theOntologiesHost',
            pre_shared_key='thePreSharedKey',
            structured_rfv=True,
        )
        exp_aws_s3_credentials = AwsS3Credentials(aws_key='theKey', aws_secret='theSecret', region='theRegion', bucket='theBucket')
        discussion = CachedDiscussion("noteUuid")
        discussion.created = datetime(2025, 3, 10, 23, 59, 7, tzinfo=timezone.utc)
        discussion.updated = datetime(2025, 3, 11, 0, 3, 17, tzinfo=timezone.utc)
        discussion.count = 7
        discussion.previous_instructions = instructions[2:]
        retrieve_audios.side_effect = [[b"audio1", b"audio2"]]
        audio2commands.side_effect = [(exp_instructions, exp_effects)]
        existing_commands_to_instructions.side_effect = [instructions]
        existing_commands_to_coded_items.side_effect = ["stagedCommands"]
        command_db.filter.return_value.order_by.side_effect = ["QuerySetCommands"]
        auditor.side_effect = ["AuditorInstance"]
        cached_discussion.get_discussion.side_effect = [discussion]
        audio_interpreter.side_effect = ["AudioInterpreterInstance"]
        limited_cache.side_effect = ["LimitedCacheInstance"]
        aws_s3.return_value.is_ready.side_effect = [is_ready]
        memory_log.end_session.side_effect = ["flushedMemoryLog"]
        tested = Commander(event, secrets)
        result = tested.compute_audio(identification, 3)
        expected = (True, exp_effects)
        assert result == expected

        assert discussion.count == 8
        assert discussion.previous_instructions == exp_instructions

        calls = [
            call(identification, 'main'),
            call().output('--> audio chunks: 2'),
            call().output('<===  note: noteUuid ===>'),
            call().output('Structured RfV: True'),
            call().output('instructions:'),
            call().output('- theInstructionA (uuidA, new/updated: False/True): theInformationA'),
            call().output('- theInstructionB (uuidB, new/updated: True/False): theInformationB'),
            call().output('- theInstructionC (uuidC, new/updated: True/False): theInformationC'),
            call().output('<-------->'),
            call().output('command: LOG'),
            call().output('Log1'),
            call().output('command: LOG'),
            call().output('Log2'),
            call().output('command: LOG'),
            call().output('Log3'),
            call().output('<=== END ===>'),
        ]
        if is_ready:
            calls.append(call().output('--> log path: canvasInstance/2025-03-10/patientUuid-noteUuid/07.log'))
            calls.append(call.end_session('noteUuid'))
        assert memory_log.mock_calls == calls
        calls = [call('theAudioHost', 'patientUuid', 'noteUuid', 3)]
        assert retrieve_audios.mock_calls == calls
        calls = [call('AuditorInstance', [b'audio1', b'audio2'], 'AudioInterpreterInstance', instructions)]
        assert audio2commands.mock_calls == calls
        calls = [call('QuerySetCommands', instructions[2:])]
        assert existing_commands_to_instructions.mock_calls == calls
        calls = [call('QuerySetCommands')]
        assert existing_commands_to_coded_items.mock_calls == calls
        calls = [
            call.filter(patient__id='patientUuid', note__id='noteUuid', state='staged'),
            call.filter().order_by("dbid"),
        ]
        assert command_db.mock_calls == calls
        calls = [call()]
        assert auditor.mock_calls == calls
        calls = [
            call.clear_cache(),
            call.get_discussion('noteUuid'),
        ]
        assert cached_discussion.mock_calls == calls
        calls = [call(exp_settings, exp_aws_s3_credentials, "LimitedCacheInstance", identification)]
        assert audio_interpreter.mock_calls == calls
        calls = [call("patientUuid", "stagedCommands")]
        assert limited_cache.mock_calls == calls
        calls = [
            call(AwsS3Credentials(aws_key='theKey', aws_secret='theSecret', region='theRegion', bucket='theBucket')),
            call().__bool__(),
            call().is_ready(),
        ]
        if is_ready:
            calls.append(call().upload_text_to_s3('canvasInstance/2025-03-10/patientUuid-noteUuid/07.log', "flushedMemoryLog"))
        assert aws_s3.mock_calls == calls
        reset_mocks()


@patch('hyperscribe.handlers.commander.MemoryLog')
@patch.object(Commander, 'transcript2commands')
def test_audio2commands(transcript2commands, memory_log):
    mock_auditor = MagicMock()
    mock_chatter = MagicMock()

    def reset_mocks():
        transcript2commands.reset_mock()
        mock_auditor.reset_mock()
        mock_chatter.reset_mock()
        memory_log.reset_mock()

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
            audits=["lineA"],
        ),
    ]
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    # all good
    transcript2commands.side_effect = ["resultTranscript2commands"]
    mock_chatter.combine_and_speaker_detection.side_effect = [
        JsonExtract(has_error=False, error="", content=transcript),
    ]
    mock_chatter.identification = identification

    result = tested.audio2commands(mock_auditor, audios, mock_chatter, previous)
    expected = "resultTranscript2commands"
    assert result == expected

    calls = [
        call(identification, 'main'),
        call().output('--> transcript back and forth: 3'),
    ]
    assert memory_log.mock_calls == calls
    calls = [
        call(
            mock_auditor,
            [
                Line(speaker='speaker1', text='textA'),
                Line(speaker='speaker2', text='textB'),
                Line(speaker='speaker1', text='textC'),
            ],
            mock_chatter,
            [
                Instruction(
                    uuid='uuidA',
                    instruction='theInstructionA',
                    information='theInformationA',
                    audits=["lineA"],
                    is_new=True,
                    is_updated=False,
                ),
            ],
        ),
    ]
    assert transcript2commands.mock_calls == calls
    calls = [
        call.identified_transcript(
            [b'audio1', b'audio2'],
            [
                Line(speaker='speaker1', text='textA'),
                Line(speaker='speaker2', text='textB'),
                Line(speaker='speaker1', text='textC'),
            ],
        ),
    ]
    assert mock_auditor.mock_calls == calls
    calls = [
        call.combine_and_speaker_detection([b'audio1', b'audio2']),
    ]
    assert mock_chatter.mock_calls == calls
    reset_mocks()
    # --- transcript has error
    transcript2commands.side_effect = []
    mock_chatter.combine_and_speaker_detection.side_effect = [
        JsonExtract(has_error=True, error="theError", content=transcript),
    ]

    result = tested.audio2commands(mock_auditor, audios, mock_chatter, previous)
    expected = (previous, [])
    assert result == expected

    calls = [
        call(identification, 'main'),
        call().output('--> transcript encountered: theError'),
    ]
    assert memory_log.mock_calls == calls
    assert transcript2commands.mock_calls == []
    calls = [
        call.combine_and_speaker_detection([b'audio1', b'audio2']),
    ]
    assert mock_chatter.mock_calls == calls
    reset_mocks()


@patch.object(Commander, 'transcript2commands_questionnaires')
@patch.object(Commander, 'transcript2commands_common')
def test_transcript2command(transcript2commands_common, transcript2commands_questionnaires):
    mock_auditor = MagicMock()
    mock_chatter = MagicMock()

    def reset_mocks():
        transcript2commands_common.reset_mock()
        transcript2commands_questionnaires.reset_mock()
        mock_auditor.reset_mock()
        mock_chatter.reset_mock()

    tested = Commander

    transcript = [
        Line(speaker="speaker1", text="textA"),
        Line(speaker="speaker2", text="textB"),
        Line(speaker="speaker1", text="textC"),
    ]
    # only common instructions
    instructions = [
        Instruction(
            uuid="uuidA",
            instruction="theInstructionA",
            information="theInformationA",
            is_new=True,
            is_updated=False,
            audits=["lineA"],
        ),
        Instruction(
            uuid="uuidB",
            instruction="theInstructionB",
            information="theInformationB",
            is_new=False,
            is_updated=True,
            audits=["lineB"],
        ),
    ]
    transcript2commands_common.side_effect = [(["instruction1", "instruction2"], ["effect1", "effect2"])]
    transcript2commands_questionnaires.side_effect = [([], [])]

    result = tested.transcript2commands(mock_auditor, transcript, mock_chatter, instructions)
    expected = (["instruction1", "instruction2"], ["effect1", "effect2"])
    assert result == expected

    calls = [call(mock_auditor, transcript, mock_chatter, instructions)]
    assert transcript2commands_common.mock_calls == calls
    calls = [call(mock_auditor, transcript, mock_chatter, [])]
    assert transcript2commands_questionnaires.mock_calls == calls
    assert mock_auditor.mock_calls == []
    assert mock_chatter.mock_calls == []
    reset_mocks()

    # only questionnaire instructions
    instructions = [
        Instruction(
            uuid="uuidA",
            instruction="ReviewOfSystem",
            information="theInformationA",
            is_new=True,
            is_updated=False,
            audits=["lineA"],
        ),
        Instruction(
            uuid="uuidB",
            instruction="Questionnaire",
            information="theInformationB",
            is_new=False,
            is_updated=True,
            audits=["lineB"],
        ),
    ]
    transcript2commands_common.side_effect = [([], [])]
    transcript2commands_questionnaires.side_effect = [(["instruction1", "instruction2"], ["effect1", "effect2"])]

    result = tested.transcript2commands(mock_auditor, transcript, mock_chatter, instructions)
    expected = (["instruction1", "instruction2"], ["effect1", "effect2"])
    assert result == expected

    calls = [call(mock_auditor, transcript, mock_chatter, [])]
    assert transcript2commands_common.mock_calls == calls
    calls = [call(mock_auditor, transcript, mock_chatter, instructions)]
    assert transcript2commands_questionnaires.mock_calls == calls
    assert mock_auditor.mock_calls == []
    assert mock_chatter.mock_calls == []
    reset_mocks()

    # one common instruction and one questionnaire instruction
    instructions = [
        Instruction(
            uuid="uuidA",
            instruction="theInstructionA",
            information="theInformationA",
            is_new=True,
            is_updated=False,
            audits=["lineA"],
        ),
        Instruction(
            uuid="uuidB",
            instruction="Questionnaire",
            information="theInformationB",
            is_new=False,
            is_updated=True,
            audits=["lineB"],
        ),
    ]
    transcript2commands_common.side_effect = [(["instruction1"], ["effect1"])]
    transcript2commands_questionnaires.side_effect = [(["instruction2"], ["effect2"])]

    result = tested.transcript2commands(mock_auditor, transcript, mock_chatter, instructions)
    expected = (["instruction1", "instruction2"], ["effect1", "effect2"])
    assert result == expected

    calls = [call(mock_auditor, transcript, mock_chatter, instructions[:1])]
    assert transcript2commands_common.mock_calls == calls
    calls = [call(mock_auditor, transcript, mock_chatter, instructions[1:])]
    assert transcript2commands_questionnaires.mock_calls == calls
    assert mock_auditor.mock_calls == []
    assert mock_chatter.mock_calls == []
    reset_mocks()


@patch.object(Commander, 'store_audits')
@patch('hyperscribe.handlers.commander.MemoryLog')
@patch("hyperscribe.handlers.commander.time")
def test_transcript2commands_common(time, memory_log, store_audits):
    mock_auditor = MagicMock()
    mock_chatter = MagicMock()
    mock_commands = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        time.reset_mock()
        memory_log.reset_mock()
        store_audits.reset_mock()
        mock_auditor.reset_mock()
        mock_chatter.reset_mock()
        for a_command in mock_commands:
            a_command.reset_mock()

    tested = Commander

    transcript = [
        Line(speaker="speaker1", text="textA"),
        Line(speaker="speaker2", text="textB"),
        Line(speaker="speaker1", text="textC"),
    ]
    previous_instructions = [
        Instruction(uuid='uuidA', instruction='theInstructionA', information='theInformationA', is_new=False, is_updated=True, audits=[]),
        Instruction(uuid='uuidB', instruction='theInstructionB', information='theInformationB', is_new=False, is_updated=False, audits=[]),
    ]
    exp_instructions = [
        Instruction(uuid='uuidA', instruction='theInstructionA', information='changedInformationA', is_new=False, is_updated=True, audits=[]),
        Instruction(uuid='uuidB', instruction='theInstructionB', information='theInformationB', is_new=False, is_updated=False, audits=[]),
        Instruction(uuid='uuidC', instruction='theInstructionC', information='theInformationC', is_new=True, is_updated=False, audits=[]),
        Instruction(uuid='uuidD', instruction='theInstructionD', information='theInformationD', is_new=True, is_updated=False, audits=[]),
        Instruction(uuid='uuidE', instruction='theInstructionE', information='theInformationE', is_new=True, is_updated=False, audits=[]),
        Instruction(uuid='uuidF', instruction='theInstructionF', information='theInformationF', is_new=True, is_updated=False, audits=[]),
    ]
    instructions_with_parameters = [
        InstructionWithParameters(
            uuid='uuidA',
            instruction='theInstructionA',
            information='changedInformationA',
            is_new=False,
            is_updated=True,
            audits=["lineA"],
            parameters={"params": "instruction0"},
        ),
        # B is unchanged
        None,  # C results with None
        InstructionWithParameters(
            uuid='uuidD',
            instruction='theInstructionD',
            information='theInformationD',
            is_new=True,
            is_updated=False,
            audits=["lineD"],
            parameters={"params": "instruction3"},
        ),
        InstructionWithParameters(
            uuid='uuidE',
            instruction='theInstructionE',
            information='theInformationE',
            is_new=True,
            is_updated=False,
            audits=["lineE"],
            parameters={"params": "instruction4"},
        ),
        InstructionWithParameters(
            uuid='uuidF',
            instruction='theInstructionF',
            information='theInformationF',
            is_new=True,
            is_updated=False,
            audits=["lineF"],
            parameters={"params": "instruction5"},
        ),
    ]
    instructions_with_commands = [
        InstructionWithCommand(
            uuid='uuidA',
            instruction='theInstructionA',
            information='changedInformationA',
            is_new=False,
            is_updated=True,
            audits=["lineA"],
            parameters={"params": "instruction0"},
            command=mock_commands[0],
        ),
        InstructionWithCommand(
            uuid='uuidD',
            instruction='theInstructionD',
            information='theInformationD',
            is_new=True,
            is_updated=False,
            audits=["lineD"],
            parameters={"params": "instruction3"},
            command=mock_commands[1],
        ),
        None,  # E
        InstructionWithCommand(
            uuid='uuidF',
            instruction='theInstructionF',
            information='theInformationF',
            is_new=True,
            is_updated=False,
            audits=["lineF"],
            parameters={"params": "instruction5"},
            command=mock_commands[2],
        ),
    ]
    tests = [
        # -- simulated note
        ("_NoteUuid", [], []),  # -- simulated note
        # -- 'real' note
        ("noteUuid", [
            Effect(type="LOG", payload="Log1"),
            Effect(type="LOG", payload="Log2"),
            Effect(type="LOG", payload="Log3"),
        ], [
             call.edit(),
             call.originate(),
             call.originate(),
         ]),
    ]
    for note_uuid, exp_effects, command_calls in tests:
        identification = IdentificationParameters(
            patient_uuid="patientUuid",
            note_uuid=note_uuid,
            provider_uuid="providerUuid",
            canvas_instance="canvasInstance",
        )
        mock_chatter.identification = identification
        mock_chatter.aws_s3 = "awsS3"

        mock_chatter.detect_instructions.side_effect = [
            [
                {
                    "uuid": "uuidA",
                    "instruction": "theInstructionA",
                    "information": "changedInformationA",
                    "isNew": False,
                    "isUpdated": True,
                    "audits": ["lineA"],
                },
                {
                    "uuid": "uuidB",
                    "instruction": "theInstructionB",
                    "information": "theInformationB",
                    "isNew": False,
                    "isUpdated": False,
                    "audits": ["lineB"],
                },
                {
                    "uuid": "uuidC",
                    "instruction": "theInstructionC",
                    "information": "theInformationC",
                    "isNew": True,
                    "isUpdated": False,
                    "audits": ["lineC"],
                },
                {
                    "uuid": "uuidD",
                    "instruction": "theInstructionD",
                    "information": "theInformationD",
                    "isNew": True,
                    "isUpdated": False,
                    "audits": ["lineD"],
                },
                {
                    "uuid": "uuidE",
                    "instruction": "theInstructionE",
                    "information": "theInformationE",
                    "isNew": True,
                    "isUpdated": False,
                    "audits": ["lineE"],
                },
                {
                    "uuid": "uuidF",
                    "instruction": "theInstructionF",
                    "information": "theInformationF",
                    "isNew": True,
                    "isUpdated": False,
                    "audits": ["lineF"],
                },
            ],
        ]
        mock_chatter.create_sdk_command_parameters.side_effect = instructions_with_parameters
        mock_chatter.create_sdk_command_from.side_effect = instructions_with_commands

        mock_commands[0].edit.side_effect = [Effect(type="LOG", payload="Log1")]
        mock_commands[1].edit.side_effect = []
        mock_commands[2].edit.side_effect = []
        mock_commands[0].originate.side_effect = []
        mock_commands[1].originate.side_effect = [Effect(type="LOG", payload="Log2")]
        mock_commands[2].originate.side_effect = [Effect(type="LOG", payload="Log3")]

        time.side_effect = [111.110, 111.219]

        result = tested.transcript2commands_common(mock_auditor, transcript, mock_chatter, previous_instructions)
        expected = (exp_instructions, exp_effects)
        assert result[0] == expected[0]

        exp_instructions_w_parameters = [instructions_with_parameters[i] for i in [0, 2, 3, 4]]
        exp_instructions_w_commands = [instructions_with_commands[i] for i in [0, 1, 3]]
        calls = [
            call(identification, 'main'),
            call().output('--> instructions: 6'),
            call().output('--> computed instructions: 5'),
            call().output('--> computed commands: 4'),
            call().output('DURATION COMMONS: 108'),
        ]
        assert memory_log.mock_calls == calls
        calls = [call("awsS3", identification, "audit_common_commands", exp_instructions_w_commands)]
        assert store_audits.mock_calls == calls
        calls = [call(), call()]
        assert time.mock_calls == calls
        calls = [
            call.found_instructions(transcript, previous_instructions, expected[0]),
            call.computed_parameters(exp_instructions_w_parameters),
            call.computed_commands(exp_instructions_w_commands),
        ]
        assert mock_auditor.mock_calls == calls
        calls = [
            call.detect_instructions(transcript, previous_instructions),
            call.create_sdk_command_parameters(exp_instructions[0]),
            call.create_sdk_command_parameters(exp_instructions[2]),
            call.create_sdk_command_parameters(exp_instructions[3]),
            call.create_sdk_command_parameters(exp_instructions[4]),
            call.create_sdk_command_parameters(exp_instructions[5]),
            call.create_sdk_command_from(exp_instructions_w_parameters[0]),
            call.create_sdk_command_from(exp_instructions_w_parameters[1]),
            call.create_sdk_command_from(exp_instructions_w_parameters[2]),
            call.create_sdk_command_from(exp_instructions_w_parameters[3]),
        ]
        assert mock_chatter.mock_calls == calls
        for idx, command_call in enumerate(command_calls):
            calls = [command_call]
            assert mock_commands[idx].mock_calls == calls

        reset_mocks()


@patch.object(Commander, 'store_audits')
@patch('hyperscribe.handlers.commander.MemoryLog')
@patch("hyperscribe.handlers.commander.time")
def test_transcript2commands_questionnaires(time, memory_log, store_audits):
    auditor = MagicMock()
    chatter = MagicMock()
    mock_commands = [
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        time.reset_mock()
        memory_log.reset_mock()
        store_audits.reset_mock()
        auditor.reset_mock()
        chatter.reset_mock()
        for a_command in mock_commands:
            a_command.reset_mock()

    transcript = [
        Line(speaker="speaker1", text="textA"),
        Line(speaker="speaker2", text="textB"),
        Line(speaker="speaker1", text="textC"),
    ]

    instructions = [
        Instruction(uuid='uuidA', instruction='theInstructionA', information='theInformationA', is_new=False, is_updated=True, audits=["lineA"]),
        Instruction(uuid='uuidB', instruction='theInstructionB', information='theInformationB', is_new=True, is_updated=False, audits=["lineB"]),
        Instruction(uuid='uuidC', instruction='theInstructionC', information='theInformationC', is_new=False, is_updated=False, audits=["lineC"]),
        Instruction(uuid='uuidD', instruction='theInstructionD', information='theInformationD', is_new=True, is_updated=True, audits=["lineD"]),
        Instruction(uuid='uuidE', instruction='theInstructionE', information='theInformationE', is_new=True, is_updated=True, audits=["lineE"]),
    ]
    instructions_with_commands = [
        None,
        InstructionWithCommand(
            uuid='uuidB',
            instruction='theInstructionB',
            information='theInformationB',
            is_new=False,
            is_updated=False,
            audits=["lineB1", "lineB2"],
            parameters={},
            command=mock_commands[0],
        ),
        InstructionWithCommand(
            uuid='uuidC',
            instruction='theInstructionC',
            information='theInformationC',
            is_new=False,
            is_updated=True,
            audits=["lineC1", "lineC2"],
            parameters={},
            command=mock_commands[1],
        ),
        None,
        None,
    ]

    updated = [
        Instruction(
            uuid='uuidB',
            instruction='theInstructionB',
            information='theInformationB',
            is_new=False,
            is_updated=False,
            audits=["lineB1", "lineB2"],
        ),
        Instruction(
            uuid='uuidC',
            instruction='theInstructionC',
            information='theInformationC',
            is_new=False,
            is_updated=True,
            audits=["lineC1", "lineC2"],
        ),
    ]
    effects = [
        Effect(type="LOG", payload="Log0"),
        Effect(type="LOG", payload="Log1"),
    ]

    tested = Commander
    # no instruction
    result = tested.transcript2commands_questionnaires(auditor, transcript, chatter, [])
    expected = ([], [])
    assert result == expected
    assert memory_log.mock_calls == []
    assert store_audits.mock_calls == []
    assert time.mock_calls == []
    assert auditor.mock_calls == []
    assert chatter.mock_calls == []
    for mock_command in mock_commands:
        assert mock_command.mock_calls == []
    reset_mocks()

    # with instructions
    tests = [
        # -- simulated note
        ("_NoteUuid", (updated, []), []),  # -- simulated note
        # -- 'real' note
        ("noteUuid", (updated, effects), [call.edit()]),
    ]
    for note_uuid, expected, command_calls in tests:
        identification = IdentificationParameters(
            patient_uuid="patientUuid",
            note_uuid=note_uuid,
            provider_uuid="providerUuid",
            canvas_instance="canvasInstance",
        )
        chatter.identification = identification
        chatter.aws_s3 = "awsS3"
        time.side_effect = [111.110, 111.357]
        chatter.update_questionnaire.side_effect = instructions_with_commands
        for idx, mock_command in enumerate(mock_commands):
            mock_command.edit.side_effect = [Effect(type="LOG", payload=f"Log{idx}")]

        result = tested.transcript2commands_questionnaires(auditor, transcript, chatter, instructions)
        assert result == expected
        calls = [
            call(identification, 'main'),
            call().output('DURATION QUESTIONNAIRES: 246'),
        ]
        assert memory_log.mock_calls == calls
        calls = [call(
            "awsS3",
            identification,
            "audit_update_questionnaires",
            updated,
        )]
        assert store_audits.mock_calls == calls
        calls = [call(), call()]
        assert time.mock_calls == calls
        calls = [call.computed_questionnaires(transcript, instructions, instructions_with_commands[1:3])]
        assert auditor.mock_calls == calls
        calls = [
            call.update_questionnaire(transcript, instructions[0]),
            call.update_questionnaire(transcript, instructions[1]),
            call.update_questionnaire(transcript, instructions[2]),
            call.update_questionnaire(transcript, instructions[3]),
            call.update_questionnaire(transcript, instructions[4]),
        ]
        assert chatter.mock_calls == calls
        for mock_command in mock_commands:
            assert mock_command.mock_calls == command_calls
        reset_mocks()


@patch.object(Commander, 'store_audits')
@patch('hyperscribe.handlers.commander.MemoryLog')
@patch("hyperscribe.handlers.commander.time")
def test_new_commands_from(time, memory_log, store_audits):
    auditor = MagicMock()
    chatter = MagicMock()
    mock_commands = [
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        time.reset_mock()
        memory_log.reset_mock()
        store_audits.reset_mock()
        auditor.reset_mock()
        chatter.reset_mock()
        for a_command in mock_commands:
            a_command.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    instructions = [
        Instruction(uuid='uuidA', instruction='theInstructionA', information='theInformationA', is_new=False, is_updated=True, audits=["lineA"]),
        Instruction(uuid='uuidB', instruction='theInstructionB', information='theInformationB', is_new=True, is_updated=False, audits=["lineB"]),
        Instruction(uuid='uuidC', instruction='theInstructionC', information='theInformationC', is_new=True, is_updated=False, audits=["lineC"]),
        Instruction(uuid='uuidD', instruction='theInstructionD', information='theInformationD', is_new=True, is_updated=False, audits=["lineD"]),
        Instruction(uuid='uuidE', instruction='theInstructionE', information='theInformationE', is_new=True, is_updated=False, audits=["lineE"]),
    ]
    instructions_with_parameters = [
        InstructionWithParameters(
            uuid='uuidB',
            instruction='theInstructionB',
            information='theInformationB',
            is_new=True,
            is_updated=False,
            audits=["lineB"],
            parameters={"params": "instruction1"},
        ),
        None,
        InstructionWithParameters(
            uuid='uuidD',
            instruction='theInstructionD',
            information='theInformationD',
            is_new=True,
            is_updated=False,
            audits=["lineD"],
            parameters={"params": "instruction3"},
        ),
        InstructionWithParameters(
            uuid='uuidE',
            instruction='theInstructionE',
            information='theInformationE',
            is_new=True,
            is_updated=False,
            audits=["lineE"],
            parameters={"params": "instruction4"},
        ),
    ]
    instructions_with_commands = [
        InstructionWithCommand(
            uuid='uuidB',
            instruction='theInstructionB',
            information='theInformationB',
            is_new=True,
            is_updated=False,
            audits=["lineB"],
            parameters={"params": "instruction1"},
            command=mock_commands[0],
        ),
        InstructionWithCommand(
            uuid='uuidD',
            instruction='theInstructionD',
            information='theInformationD',
            is_new=True,
            is_updated=False,
            audits=["lineD"],
            parameters={"params": "instruction3"},
            command=mock_commands[1],
        ),
        None,
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
    chatter.identification = identification
    chatter.aws_s3 = "awsS3"
    for mock_command in mock_commands:
        mock_command.originate.side_effect = []

    result = tested.new_commands_from(auditor, chatter, instructions, past_uuids)
    assert result == []
    calls = [
        call(identification, 'main'),
        call().output('--> new instructions: 0'),
        call().output('--> new commands: 0'),
        call().output('DURATION NEW: 108'),
    ]
    assert memory_log.mock_calls == calls
    calls = [call("awsS3", identification, "audit_new_commands", [])]
    assert store_audits.mock_calls == calls
    calls = [call(), call()]
    assert time.mock_calls == calls
    calls = [
        call.computed_parameters([]),
        call.computed_commands([]),
    ]
    assert auditor.mock_calls == calls
    assert chatter.mock_calls == []
    for mock_command in mock_commands:
        assert mock_command.mock_calls == []
    reset_mocks()

    # with new instructions
    tests = [
        # -- simulated note
        ("_NoteUuid", [], []),  # -- simulated note
        # -- 'real' note
        ("noteUuid", [Effect(type="LOG", payload="Log0"), Effect(type="LOG", payload="Log1")], [call.originate()]),
    ]
    for note_uuid, expected, command_calls in tests:
        identification = IdentificationParameters(
            patient_uuid="patientUuid",
            note_uuid=note_uuid,
            provider_uuid="providerUuid",
            canvas_instance="canvasInstance",
        )
        chatter.identification = identification
        past_uuids = {
            "uuidA": instructions[0],
        }
        time.side_effect = [111.110, 111.357]
        chatter.create_sdk_command_parameters.side_effect = instructions_with_parameters
        chatter.create_sdk_command_from.side_effect = instructions_with_commands
        for idx, mock_command in enumerate(mock_commands):
            mock_command.originate.side_effect = [Effect(type="LOG", payload=f"Log{idx}")]

        result = tested.new_commands_from(auditor, chatter, instructions, past_uuids)
        assert result == expected
        calls = [
            call(identification, 'main'),
            call().output('--> new instructions: 4'),
            call().output('--> new commands: 3'),
            call().output('DURATION NEW: 246'),
        ]
        assert memory_log.mock_calls == calls
        calls = [call(
            "awsS3",
            identification,
            "audit_new_commands",
            [
                instructions_with_commands[0],
                instructions_with_commands[1],
            ],
        )]
        assert store_audits.mock_calls == calls
        calls = [call(), call()]
        assert time.mock_calls == calls
        calls = [
            call.computed_parameters(
                [
                    instructions_with_parameters[0],
                    instructions_with_parameters[2],
                    instructions_with_parameters[3],
                ]
            ),
            call.computed_commands(
                [
                    instructions_with_commands[0],
                    instructions_with_commands[1],
                ],
            ),
        ]
        assert auditor.mock_calls == calls
        calls = [
            call.create_sdk_command_parameters(instructions[1]),
            call.create_sdk_command_parameters(instructions[2]),
            call.create_sdk_command_parameters(instructions[3]),
            call.create_sdk_command_parameters(instructions[4]),
            call.create_sdk_command_from(instructions_with_parameters[0]),
            call.create_sdk_command_from(instructions_with_parameters[2]),
            call.create_sdk_command_from(instructions_with_parameters[3]),
        ]
        assert chatter.mock_calls == calls
        for mock_command in mock_commands:
            assert mock_command.mock_calls == command_calls
        reset_mocks()


@patch.object(Commander, 'store_audits')
@patch('hyperscribe.handlers.commander.MemoryLog')
@patch("hyperscribe.handlers.commander.time")
def test_update_commands_from(time, memory_log, store_audits):
    auditor = MagicMock()
    chatter = MagicMock()
    mock_commands = [
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        time.reset_mock()
        memory_log.reset_mock()
        store_audits.reset_mock()
        auditor.reset_mock()
        chatter.reset_mock()
        for a_command in mock_commands:
            a_command.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    instructions = [
        Instruction(uuid='uuidA', instruction='theInstructionX', information='theInformationA', is_new=False, is_updated=True, audits=["lineA"]),
        Instruction(uuid='uuidB', instruction='theInstructionX', information='theInformationB', is_new=False, is_updated=True, audits=["lineB"]),
        Instruction(uuid='uuidC', instruction='theInstructionY', information='theInformationC', is_new=False, is_updated=True, audits=["lineC"]),
        Instruction(uuid='uuidD', instruction='theInstructionY', information='theInformationD', is_new=False, is_updated=True, audits=["lineD"]),
        Instruction(uuid='uuidE', instruction='theInstructionY', information='theInformationE', is_new=True, is_updated=False, audits=["lineE"]),
        Instruction(uuid='uuidF', instruction='theInstructionY', information='theInformationF', is_new=True, is_updated=False, audits=["lineF"]),
    ]
    instructions_with_parameters = [
        InstructionWithParameters(
            uuid='uuidB',
            instruction='theInstructionB',
            information='theInformationB',
            is_new=True,
            is_updated=False,
            audits=["lineB"],
            parameters={"params": "instruction1"},
        ),
        None,
        InstructionWithParameters(
            uuid='uuidD',
            instruction='theInstructionD',
            information='theInformationD',
            is_new=True,
            is_updated=False,
            audits=["lineD"],
            parameters={"params": "instruction3"},
        ),
        InstructionWithParameters(
            uuid='uuidE',
            instruction='theInstructionE',
            information='theInformationE',
            is_new=True,
            is_updated=False,
            audits=["lineE"],
            parameters={"params": "instruction4"},
        ),
    ]
    instructions_with_commands = [
        InstructionWithCommand(
            uuid='uuidB',
            instruction='theInstructionB',
            information='theInformationB',
            is_new=True,
            is_updated=False,
            audits=["lineB"],
            parameters={"params": "instruction1"},
            command=mock_commands[0],
        ),
        InstructionWithCommand(
            uuid='uuidD',
            instruction='theInstructionD',
            information='theInformationD',
            is_new=True,
            is_updated=False,
            audits=["lineD"],
            parameters={"params": "instruction3"},
            command=mock_commands[1],
        ),
        None,
    ]
    chatter.identification = identification
    chatter.aws_s3 = "awsS3"

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
        call(identification, 'main'),
        call().output('--> updated instructions: 0'),
        call().output('--> updated commands: 0'),
        call().output('DURATION UPDATE: 246'),
    ]
    assert memory_log.mock_calls == calls
    calls = [call("awsS3", identification, "audit_updated_commands", [])]
    assert store_audits.mock_calls == calls
    calls = [call(), call()]
    assert time.mock_calls == calls
    calls = [
        call.computed_parameters([]),
        call.computed_commands([]),
    ]
    assert auditor.mock_calls == calls
    assert chatter.mock_calls == []
    for mock_command in mock_commands:
        assert mock_command.mock_calls == []
    reset_mocks()

    # updated instructions
    tests = [
        # -- simulated note
        ("_NoteUuid", [], []),  # -- simulated note
        # -- 'real' note
        ("noteUuid", [Effect(type="LOG", payload="Log0"), Effect(type="LOG", payload="Log1")], [call.edit()]),
    ]
    for note_uuid, expected, command_calls in tests:
        identification = IdentificationParameters(
            patient_uuid="patientUuid",
            note_uuid=note_uuid,
            provider_uuid="providerUuid",
            canvas_instance="canvasInstance",
        )
        chatter.identification = identification
        past_uuids = {
            "uuidA": Instruction(uuid='uuidA', instruction='theInstructionX', information='changedA', is_new=False, is_updated=True,
                                 audits=["lineA"]),
            "uuidB": instructions[1],
            "uuidC": instructions[2],
            "uuidD": Instruction(uuid='uuidD', instruction='theInstructionY', information='changedD', is_new=False, is_updated=True,
                                 audits=["lineD"]),
            "uuidE": Instruction(uuid='uuidE', instruction='theInstructionY', information='changedE', is_new=True, is_updated=False,
                                 audits=["lineE"]),
            "uuidF": Instruction(uuid='uuidF', instruction='theInstructionY', information='changedE', is_new=True, is_updated=False,
                                 audits=["lineF"]),
        }
        time.side_effect = [111.110, 111.451]
        chatter.create_sdk_command_parameters.side_effect = instructions_with_parameters
        chatter.create_sdk_command_from.side_effect = instructions_with_commands
        for idx, mock_command in enumerate(mock_commands):
            mock_command.edit.side_effect = [Effect(type="LOG", payload=f"Log{idx}")]

        result = tested.update_commands_from(auditor, chatter, instructions, past_uuids)
        assert result == expected
        calls = [
            call(identification, 'main'),
            call().output('--> updated instructions: 4'),
            call().output('--> updated commands: 3'),
            call().output('DURATION UPDATE: 340'),
        ]
        assert memory_log.mock_calls == calls
        calls = [call(
            "awsS3",
            identification,
            "audit_updated_commands",
            [
                instructions_with_commands[0],
                instructions_with_commands[1],
            ],
        )]
        assert store_audits.mock_calls == calls
        calls = [call(), call()]
        assert time.mock_calls == calls
        calls = [
            call.computed_parameters(
                [
                    instructions_with_parameters[0],
                    instructions_with_parameters[2],
                    instructions_with_parameters[3],
                ]
            ),
            call.computed_commands(
                [
                    instructions_with_commands[0],
                    instructions_with_commands[1],
                ],
            ),
        ]
        assert auditor.mock_calls == calls
        calls = [
            call.create_sdk_command_parameters(instructions[0]),
            call.create_sdk_command_parameters(instructions[3]),
            call.create_sdk_command_parameters(instructions[4]),
            call.create_sdk_command_parameters(instructions[5]),
            call.create_sdk_command_from(instructions_with_parameters[0]),
            call.create_sdk_command_from(instructions_with_parameters[2]),
            call.create_sdk_command_from(instructions_with_parameters[3]),
        ]
        assert chatter.mock_calls == calls
        for mock_command in mock_commands:
            assert mock_command.mock_calls == command_calls
        reset_mocks()


@patch.object(ImplementedCommands, "schema_key2instruction")
def test_existing_commands_to_instructions(schema_key2instruction):
    def reset_mocks():
        schema_key2instruction.reset_mock()

    tested = Commander
    # only new instructions
    current_commands = [
        Command(id="uuid1", schema_key="canvas_command_X"),
        Command(id="uuid2", schema_key="canvas_command_X"),
        Command(id="uuid3", schema_key="canvas_command_Y"),
        Command(id="uuid4", schema_key="canvas_command_Y"),
        Command(id="uuid5", schema_key="canvas_command_Y"),
    ]
    schema_key2instruction.side_effect = [
        {
            "canvas_command_X": "theInstructionX",
            "canvas_command_Y": "theInstructionY",
        },
    ]

    result = tested.existing_commands_to_instructions(current_commands, [])
    expected = [
        Instruction(uuid='uuid1', instruction='theInstructionX', information='', is_new=False, is_updated=False, audits=[]),
        Instruction(uuid='uuid2', instruction='theInstructionX', information='', is_new=False, is_updated=False, audits=[]),
        Instruction(uuid='uuid3', instruction='theInstructionY', information='', is_new=False, is_updated=False, audits=[]),
        Instruction(uuid='uuid4', instruction='theInstructionY', information='', is_new=False, is_updated=False, audits=[]),
        Instruction(uuid='uuid5', instruction='theInstructionY', information='', is_new=False, is_updated=False, audits=[]),
    ]
    assert result == expected
    calls = [call()]
    assert schema_key2instruction.mock_calls == calls
    reset_mocks()

    # updated instructions
    current_commands = [
        Command(id="uuid0", schema_key="canvas_command_Z", data={"narrative": "theNarrative0", "comment": "theComment0"}),
        Command(id="uuid1", schema_key="canvas_command_X", data={"narrative": "theNarrative1", "comment": "theComment1"}),
        Command(id="uuid3", schema_key="canvas_command_Y", data={"narrative": "theNarrative3", "comment": "theComment3"}),
        Command(id="uuid4", schema_key="canvas_command_Y", data={"narrative": "theNarrative4", "comment": "theComment4"}),
        Command(id="uuid2", schema_key="canvas_command_X", data={"narrative": "theNarrative2", "comment": "theComment2"}),
        Command(id="uuid5", schema_key="canvas_command_Y", data={"narrative": "theNarrative5", "comment": "theComment5"}),
        Command(id="uuid6", schema_key="hpi", data={"narrative": "theNarrative6", "comment": "theComment6"}),
        Command(id="uuid7", schema_key="reasonForVisit", data={"narrative": "theNarrative7", "comment": "theComment7"}),
        Command(id="uuid8", schema_key="exam", data={"questionnaire": {"extra": {"pk": 123, "name": "thePhysicalExam", "questions": []}}}),
        Command(id="uuid9", schema_key="questionnaire", data={"questionnaire": {"extra": {"pk": 234, "name": "theQuestionnaire", "questions": []}}}),
        Command(id="uuid10", schema_key="ros", data={"questionnaire": {"extra": {"pk": 125, "name": "theReviewOfSystem", "questions": []}}}),
        Command(id="uuid11", schema_key="structuredAssessment",
                data={"questionnaire": {"extra": {"pk": 222, "name": "theStructuredAssessment", "questions": []}}}),
    ]
    schema_key2instruction.side_effect = [
        {
            "canvas_command_Z": "theInstructionZ",
            "canvas_command_X": "theInstructionX",
            "canvas_command_Y": "theInstructionY",
            "hpi": "HistoryOfPresentIllness",
            "reasonForVisit": "ReasonForVisit",
            "exam": "PhysicalExam",
            "questionnaire": "Questionnaire",
            "ros": "ReviewOfSystem",
            "structuredAssessment": "StructuredAssessment",
        },
    ]
    instructions = [
        Instruction(uuid='uuidA', instruction='theInstructionX', information='theInformationA', is_new=True, is_updated=True, audits=["lineA"]),
        Instruction(uuid='uuidB', instruction='theInstructionY', information='theInformationD', is_new=True, is_updated=True, audits=["lineB"]),
        Instruction(uuid='uuidC', instruction='theInstructionY', information='theInformationE', is_new=True, is_updated=True, audits=["lineC"]),
    ]

    result = tested.existing_commands_to_instructions(current_commands, instructions)
    expected = [
        Instruction(
            uuid='uuid0',
            instruction='theInstructionZ',
            information='',
            is_new=False,
            is_updated=False,
            audits=[],
        ),
        Instruction(
            uuid='uuid1',
            instruction='theInstructionX',
            information='theInformationA',
            is_new=False,
            is_updated=False,
            audits=[],
        ),
        Instruction(
            uuid='uuid3',
            instruction='theInstructionY',
            information='theInformationD',
            is_new=False,
            is_updated=False,
            audits=[],
        ),
        Instruction(
            uuid='uuid4',
            instruction='theInstructionY',
            information='theInformationE',
            is_new=False,
            is_updated=False,
            audits=[],
        ),
        Instruction(
            uuid='uuid2',
            instruction='theInstructionX',
            information='',
            is_new=False,
            is_updated=False,
            audits=[],
        ),
        Instruction(
            uuid='uuid5',
            instruction='theInstructionY',
            information='',
            is_new=False,
            is_updated=False,
            audits=[],
        ),
        Instruction(
            uuid='uuid6',
            instruction='HistoryOfPresentIllness',
            information='theNarrative6',
            is_new=False,
            is_updated=False,
            audits=[],
        ),
        Instruction(
            uuid='uuid7',
            instruction='ReasonForVisit',
            information='theComment7',
            is_new=False,
            is_updated=False,
            audits=[],
        ),
        Instruction(
            uuid='uuid8',
            instruction='PhysicalExam',
            information='{"name": "thePhysicalExam", "dbid": 123, "questions": []}',
            is_new=False,
            is_updated=False,
            audits=[],
        ),
        Instruction(
            uuid='uuid9',
            instruction='Questionnaire',
            information='{"name": "theQuestionnaire", "dbid": 234, "questions": []}',
            is_new=False,
            is_updated=False,
            audits=[],
        ),
        Instruction(
            uuid='uuid10',
            instruction='ReviewOfSystem',
            information='{"name": "theReviewOfSystem", "dbid": 125, "questions": []}',
            is_new=False,
            is_updated=False,
            audits=[],
        ),
        Instruction(
            uuid='uuid11',
            instruction='StructuredAssessment',
            information='{"name": "theStructuredAssessment", "dbid": 222, "questions": []}',
            is_new=False,
            is_updated=False,
            audits=[],
        ),
    ]
    assert result == expected
    calls = [call()]
    assert schema_key2instruction.mock_calls == calls
    reset_mocks()


@patch.object(ImplementedCommands, "command_list")
def test_existing_commands_to_coded_items(command_list):
    mock_commands = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        command_list.reset_mock()

    tested = Commander
    current_commands = [
        Command(id="uuid1", schema_key="canvas_command_X", data={"key1": "value1"}),
        Command(id="uuid2", schema_key="canvas_command_X", data={"key2": "value2"}),
        Command(id="uuid3", schema_key="canvas_command_Y", data={"key3": "value3"}),
        Command(id="uuid4", schema_key="canvas_command_Y", data={"key4": "value4"}),
        Command(id="uuid5", schema_key="canvas_command_Y", data={"key5": "value5"}),
        Command(id="uuid6", schema_key="canvas_command_A", data={"key6": "value6"}),
    ]
    command_list.side_effect = [mock_commands] * 6

    mock_commands[0].schema_key.return_value = "canvas_command_X"
    mock_commands[1].schema_key.return_value = "canvas_command_Y"
    mock_commands[2].schema_key.return_value = "canvas_command_Z"

    mock_commands[0].staged_command_extract.side_effect = [
        CodedItem(label="label1", code="code1", uuid=""),
        None,
    ]
    mock_commands[1].staged_command_extract.side_effect = [
        CodedItem(label="label3", code="code3", uuid=""),
        CodedItem(label="label4", code="code4", uuid=""),
        CodedItem(label="label5", code="code5", uuid=""),
    ]
    mock_commands[2].staged_command_extract.side_effect = []

    result = tested.existing_commands_to_coded_items(current_commands)
    expected = {
        'canvas_command_X': [
            CodedItem(uuid='uuid1', label='label1', code='code1'),
        ],
        'canvas_command_Y': [
            CodedItem(uuid='uuid3', label='label3', code='code3'),
            CodedItem(uuid='uuid4', label='label4', code='code4'),
            CodedItem(uuid='uuid5', label='label5', code='code5'),
        ],
    }

    assert result == expected
    calls = [call()] * 6
    assert command_list.mock_calls == calls
    calls = [
        call.schema_key(),
        call.staged_command_extract({'key1': 'value1'}),
        call.schema_key(),
        call.staged_command_extract({'key2': 'value2'}),
        call.schema_key(),
        call.schema_key(),
        call.schema_key(),
        call.schema_key(),
    ]
    assert mock_commands[0].mock_calls == calls
    calls = [
        call.schema_key(),
        call.staged_command_extract({'key3': 'value3'}),
        call.schema_key(),
        call.staged_command_extract({'key4': 'value4'}),
        call.schema_key(),
        call.staged_command_extract({'key5': 'value5'}),
        call.schema_key(),
    ]
    assert mock_commands[1].mock_calls == calls
    calls = [call.schema_key()]
    assert mock_commands[2].mock_calls == calls
    reset_mocks()


@patch.object(CachedDiscussion, "get_discussion")
@patch("hyperscribe.handlers.commander.AwsS3")
def test_store_audits(aws_s3, get_discussion):
    def reset_mocks():
        aws_s3.reset_mock()
        get_discussion.reset_mock()

    credentials = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
    instructions = [
        Instruction(
            uuid='uuidA',
            instruction='theInstructionA',
            information='theInformationA',
            is_new=False,
            is_updated=False,
            audits=["lineA", "lineB"],
        ),
        Instruction(
            uuid='uuidB',
            instruction='theInstructionB',
            information='theInformationB',
            is_new=False,
            is_updated=False,
            audits=["lineC"],
        ),
        Instruction(
            uuid='uuidC',
            instruction='theInstructionC',
            information='theInformationC',
            is_new=True,
            is_updated=False,
            audits=["lineD", "lineE", "lineF"],
        ),
    ]
    identification = IdentificationParameters(
        patient_uuid="thePatientUuid",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    )
    tested = Commander
    #
    aws_s3.return_value.is_ready.side_effect = [False]
    get_discussion.side_effect = []
    tested.store_audits(credentials, identification, "theLabel", instructions)
    calls = [
        call(credentials),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    assert get_discussion.mock_calls == []
    reset_mocks()
    #
    cached = CachedDiscussion("theNoteUuid")
    cached.created = datetime(2025, 4, 11, 23, 59, 37, tzinfo=timezone.utc)
    cached.updated = datetime(2025, 4, 12, 0, 38, 21, tzinfo=timezone.utc)
    cached.count = 7

    aws_s3.return_value.is_ready.side_effect = [True]
    get_discussion.side_effect = [cached]
    tested.store_audits(credentials, identification, "theLabel", instructions)
    calls = [
        call(credentials),
        call().is_ready(),
        call().upload_text_to_s3(
            'theCanvasInstance/2025-04-11/partials/theNoteUuid/06/theLabel.log',
            '--- theInstructionA (uuidA) ---\n'
            'lineA\n'
            'lineB\n'
            '--- theInstructionB (uuidB) ---\n'
            'lineC\n'
            '--- theInstructionC (uuidC) ---\n'
            'lineD\n'
            'lineE\n'
            'lineF\n'
            '-- EOF ---'),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call('theNoteUuid')]
    assert get_discussion.mock_calls == calls
    reset_mocks()
