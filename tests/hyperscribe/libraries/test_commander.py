from datetime import datetime, timezone
from unittest.mock import patch, call, MagicMock

import pytest
from canvas_generated.messages.effects_pb2 import Effect
from canvas_sdk.v1.data import Command

from hyperscribe.libraries.audio_client import AudioClient, CachedAudioSession
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.commander import Commander
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.line import Line
from hyperscribe.structures.progress_message import ProgressMessage
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import is_constant


@pytest.fixture
def the_audio_client() -> AudioClient:
    return AudioClient.for_operation("https://theAudioServer.com", "theTestEnv", "theAudioHostSharedSecret")


@pytest.fixture
def the_session() -> CachedAudioSession:
    return CachedAudioSession("theSessionId", "theUserToken", "theLoggedInUserId")


def test_constants():
    tested = Commander
    constants = {"MAX_PREVIOUS_AUDIOS": 0}
    assert is_constant(tested, constants)


@patch("hyperscribe.libraries.commander.AwsS3")
@patch("hyperscribe.libraries.commander.ProgressDisplay")
@patch("hyperscribe.libraries.commander.MemoryLog")
@patch("hyperscribe.libraries.commander.LimitedCache")
@patch("hyperscribe.libraries.commander.AudioInterpreter")
@patch("hyperscribe.libraries.commander.AuditorLive")
@patch.object(AudioClient, "get_audio_chunk")
@patch.object(CachedSdk, "save")
@patch.object(CachedSdk, "get_discussion")
@patch.object(Command, "objects")
@patch.object(Commander, "existing_commands_to_coded_items")
@patch.object(Commander, "existing_commands_to_instructions")
@patch.object(Commander, "audio2commands")
def test_compute_audio(
    audio2commands,
    existing_commands_to_instructions,
    existing_commands_to_coded_items,
    command_db,
    cache_get_discussion,
    cache_save,
    mock_get_audio_chunk,
    auditor_live,
    audio_interpreter,
    limited_cache,
    memory_log,
    progress,
    aws_s3,
    the_audio_client,
    the_session,
):
    def reset_mocks():
        audio2commands.reset_mock()
        existing_commands_to_instructions.reset_mock()
        existing_commands_to_coded_items.reset_mock()
        command_db.reset_mock()
        auditor_live.reset_mock()
        cache_get_discussion.reset_mock()
        cache_save.reset_mock()
        audio_interpreter.reset_mock()
        limited_cache.reset_mock()
        memory_log.reset_mock()
        progress.reset_mock()
        aws_s3.reset_mock()
        mock_get_audio_chunk.reset_mock()

    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    aws_s3_credentials = AwsS3Credentials(
        aws_key="theKey",
        aws_secret="theSecret",
        region="theRegion",
        bucket="theBucket",
    )
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        structured_rfv=True,
        audit_llm=False,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=7,
        hierarchical_detection_threshold=5,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=["Command1", "Command2", "Command3"]),
        staffers_policy=AccessPolicy(policy=False, items=["31", "47"]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    # no more audio
    audio2commands.side_effect = []
    existing_commands_to_instructions.side_effect = []
    existing_commands_to_coded_items.side_effect = []
    command_db.filter.return_value.order_by.side_effect = []
    auditor_live.side_effect = []
    cache_get_discussion.side_effect = []
    audio_interpreter.side_effect = []
    limited_cache.side_effect = []
    aws_s3.return_value.is_ready.side_effect = []

    tested = Commander
    mock_get_audio_chunk.side_effect = [b""]
    result = tested.compute_audio(identification, settings, aws_s3_credentials, the_audio_client, 3)
    expected = (False, [])
    assert result == expected

    calls = [call.instance(identification, "main", aws_s3_credentials), call.instance().output("--> audio chunks: 0")]
    assert memory_log.mock_calls == calls
    assert audio2commands.mock_calls == []
    assert existing_commands_to_instructions.mock_calls == []
    assert existing_commands_to_coded_items.mock_calls == []
    assert command_db.mock_calls == []
    assert auditor_live.mock_calls == []
    assert cache_get_discussion.mock_calls == []
    assert cache_save.mock_calls == []
    assert audio_interpreter.mock_calls == []
    assert limited_cache.mock_calls == []
    assert progress.mock_calls == []
    assert aws_s3.mock_calls == []
    calls = [call(identification.patient_uuid, identification.note_uuid, 3)]
    assert mock_get_audio_chunk.mock_calls == calls
    reset_mocks()

    # audios retrieved
    for is_ready in [True, False]:
        instructions = [
            Instruction(
                uuid="uuidA",
                index=0,
                instruction="theInstructionA",
                information="theInformationA",
                is_new=False,
                is_updated=False,
            ),
            Instruction(
                uuid="uuidB",
                index=1,
                instruction="theInstructionB",
                information="theInformationB",
                is_new=False,
                is_updated=False,
            ),
            Instruction(
                uuid="uuidC",
                index=2,
                instruction="theInstructionC",
                information="theInformationC",
                is_new=True,
                is_updated=False,
            ),
        ]
        exp_instructions = [
            Instruction(
                uuid="uuidA",
                index=0,
                instruction="theInstructionA",
                information="theInformationA",
                is_new=False,
                is_updated=True,
            ),
            Instruction(
                uuid="uuidB",
                index=1,
                instruction="theInstructionB",
                information="theInformationB",
                is_new=True,
                is_updated=False,
            ),
            Instruction(
                uuid="uuidC",
                index=2,
                instruction="theInstructionC",
                information="theInformationC",
                is_new=True,
                is_updated=False,
            ),
        ]
        exp_effects = [
            Effect(type="LOG", payload="Log1"),
            Effect(type="LOG", payload="Log2"),
            Effect(type="LOG", payload="Log3"),
        ]

        discussion = CachedSdk("noteUuid")
        discussion.created = datetime(2025, 3, 10, 23, 59, 7, tzinfo=timezone.utc)
        discussion.updated = datetime(2025, 3, 11, 0, 3, 17, tzinfo=timezone.utc)
        discussion.cycle = 7
        discussion.previous_instructions = instructions[2:]
        discussion.previous_transcript = [Line(speaker="speaker0", text="some text", start=0.0, end=2.1)]
        audio2commands.side_effect = [(exp_instructions, exp_effects, "other last words.")]
        existing_commands_to_instructions.side_effect = [instructions]
        existing_commands_to_coded_items.side_effect = ["stagedCommands"]
        command_db.filter.return_value.order_by.side_effect = ["QuerySetCommands"]
        auditor_live.side_effect = ["AuditorInstance"]
        cache_get_discussion.side_effect = [discussion]
        audio_interpreter.side_effect = ["AudioInterpreterInstance"]
        limited_cache.side_effect = ["LimitedCacheInstance"]
        aws_s3.return_value.is_ready.side_effect = [is_ready]
        memory_log.end_session.side_effect = ["flushedMemoryLog"]
        tested = Commander
        mock_get_audio_chunk.side_effect = [b"raw-audio-bytes"]
        result = tested.compute_audio(identification, settings, aws_s3_credentials, the_audio_client, 3)
        expected = (True, exp_effects)
        assert result == expected

        assert discussion.cycle == 3
        assert discussion.previous_instructions == exp_instructions
        assert discussion.previous_transcript == "other last words."

        calls = [
            call.instance(identification, "main", aws_s3_credentials),
            call.instance().output("--> audio chunks: 1"),
            call.instance().output("<===  note: noteUuid ===>"),
            call.instance().output("Structured RfV: True"),
            call.instance().output("Audit LLM Decisions: False"),
            call.instance().output("instructions:"),
            call.instance().output("- theInstructionA #00 (uuidA, new/updated: False/True): theInformationA"),
            call.instance().output("- theInstructionB #01 (uuidB, new/updated: True/False): theInformationB"),
            call.instance().output("- theInstructionC #02 (uuidC, new/updated: True/False): theInformationC"),
            call.instance().output("<-------->"),
            call.instance().output("command: LOG"),
            call.instance().output("Log1"),
            call.instance().output("command: LOG"),
            call.instance().output("Log2"),
            call.instance().output("command: LOG"),
            call.instance().output("Log3"),
            call.instance().output("<=== END ===>"),
        ]
        if is_ready:
            calls.append(
                call.instance().output(
                    "--> log path: hyperscribe-canvasInstance/finals/2025-03-10/patientUuid-noteUuid/03.log",
                ),
            )
            calls.append(call.end_session("noteUuid"))
        assert memory_log.mock_calls == calls
        calls = [
            call(
                "AuditorInstance",
                [b"raw-audio-bytes"],
                "AudioInterpreterInstance",
                instructions,
                [Line(speaker="speaker0", text="some text", start=0.0, end=2.1)],
            )
        ]
        assert audio2commands.mock_calls == calls
        calls = [call("QuerySetCommands", instructions[2:])]
        assert existing_commands_to_instructions.mock_calls == calls
        calls = [call("QuerySetCommands", AccessPolicy(policy=False, items=["Command1", "Command2", "Command3"]), True)]
        assert existing_commands_to_coded_items.mock_calls == calls
        calls = [
            call.filter(patient__id="patientUuid", note__id="noteUuid", state="staged"),
            call.filter().order_by("dbid"),
        ]
        assert command_db.mock_calls == calls
        calls = [call(3, settings, aws_s3_credentials, identification)]
        assert auditor_live.mock_calls == calls
        calls = [call("noteUuid")]
        assert cache_get_discussion.mock_calls == calls
        calls = [call(), call()]
        assert cache_save.mock_calls == calls
        calls = [call(settings, aws_s3_credentials, "LimitedCacheInstance", identification)]
        assert audio_interpreter.mock_calls == calls
        calls = [call("patientUuid", "providerUuid", "stagedCommands")]
        assert limited_cache.mock_calls == calls
        calls = [
            call.send_to_user(
                identification,
                settings,
                [ProgressMessage(message="starting the cycle 3...", section="events:4")],
            )
        ]
        assert progress.mock_calls == calls
        calls = [
            call(AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")),
            call().__bool__(),
            call().is_ready(),
        ]
        if is_ready:
            calls.append(
                call().upload_text_to_s3(
                    "hyperscribe-canvasInstance/finals/2025-03-10/patientUuid-noteUuid/03.log",
                    "flushedMemoryLog",
                ),
            )
        assert aws_s3.mock_calls == calls
        calls = [call(identification.patient_uuid, identification.note_uuid, 3)]
        assert mock_get_audio_chunk.mock_calls == calls
        reset_mocks()


@patch("hyperscribe.libraries.commander.ProgressDisplay")
@patch("hyperscribe.libraries.commander.MemoryLog")
@patch.object(Line, "tail_of")
@patch.object(Commander, "transcript2commands")
def test_audio2commands(transcript2commands, tail_of, memory_log, progress):
    mock_auditor = MagicMock()
    mock_chatter = MagicMock()

    def reset_mocks():
        transcript2commands.reset_mock()
        tail_of.reset_mock()
        mock_auditor.reset_mock()
        mock_chatter.reset_mock()
        memory_log.reset_mock()
        progress.reset_mock()

    tested = Commander

    audios = [b"audio1", b"audio2"]
    previous = [
        Instruction(
            uuid="uuidA",
            index=0,
            instruction="theInstructionA",
            information="theInformationA",
            is_new=True,
            is_updated=False,
        ),
    ]
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        structured_rfv=True,
        audit_llm=True,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=7,
        hierarchical_detection_threshold=5,
        send_progress=True,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    lines = [
        Line(speaker="speaker", text="last words 1", start=0.0, end=1.3),
        Line(speaker="speaker", text="last words 2", start=1.3, end=2.5),
        Line(speaker="speaker", text="last words 3", start=2.5, end=3.6),
    ]

    text = " ".join([f"word{i:02d}" for i in range(4)])

    transcript = [
        {"speaker": "speaker1", "text": f"{text} textA.", "start": 0.0, "end": 1.3},
        {"speaker": "speaker2", "text": f"{text} textB.", "start": 1.3, "end": 2.5},
        {"speaker": "speaker1", "text": f"{text} textC.", "start": 2.5, "end": 3.6},
    ]
    # all good
    transcript2commands.side_effect = [("instructions", "effects")]
    tail_of.side_effect = [lines]
    mock_chatter.combine_and_speaker_detection.side_effect = [
        JsonExtract(has_error=False, error="", content=transcript),
    ]
    mock_chatter.identification = identification
    mock_chatter.s3_credentials = "s3Credentials"
    mock_chatter.settings = settings

    result = tested.audio2commands(
        mock_auditor,
        audios,
        mock_chatter,
        previous,
        [Line(speaker="speaker0", text="some text", start=0.0, end=2.1)],
    )
    expected = ("instructions", "effects", lines)
    assert result == expected

    calls = [
        call.instance(identification, "main", "s3Credentials"),
        call.instance().output("--> transcript back and forth: 3"),
    ]
    assert memory_log.mock_calls == calls
    calls = [
        call.send_to_user(
            identification,
            settings,
            [
                ProgressMessage(
                    message="["
                    '{"speaker": "speaker1", "text": "word00 word01 word02 word03 textA.", "start": 0.0, "end": 1.3}, '
                    '{"speaker": "speaker2", "text": "word00 word01 word02 word03 textB.", "start": 1.3, "end": 2.5}, '
                    '{"speaker": "speaker1", "text": "word00 word01 word02 word03 textC.", "start": 2.5, "end": 3.6}]',
                    section="transcript",
                )
            ],
        )
    ]
    assert progress.mock_calls == calls
    calls = [
        call(
            mock_auditor,
            [
                Line(speaker="speaker1", text=f"{text} textA.", start=0.0, end=1.3),
                Line(speaker="speaker2", text=f"{text} textB.", start=1.3, end=2.5),
                Line(speaker="speaker1", text=f"{text} textC.", start=2.5, end=3.6),
            ],
            mock_chatter,
            [
                Instruction(
                    uuid="uuidA",
                    index=0,
                    instruction="theInstructionA",
                    information="theInformationA",
                    is_new=True,
                    is_updated=False,
                ),
            ],
        ),
    ]
    assert transcript2commands.mock_calls == calls
    calls = [
        call(
            [
                Line(speaker="speaker1", text=f"{text} textA.", start=0.0, end=1.3),
                Line(speaker="speaker2", text=f"{text} textB.", start=1.3, end=2.5),
                Line(speaker="speaker1", text=f"{text} textC.", start=2.5, end=3.6),
            ],
            37,
        ),
    ]
    assert tail_of.mock_calls == calls
    calls = [
        call.identified_transcript(
            [b"audio1", b"audio2"],
            [
                Line(speaker="speaker1", text=f"{text} textA.", start=0.0, end=1.3),
                Line(speaker="speaker2", text=f"{text} textB.", start=1.3, end=2.5),
                Line(speaker="speaker1", text=f"{text} textC.", start=2.5, end=3.6),
            ],
        ),
    ]
    assert mock_auditor.mock_calls == calls
    calls = [
        call.combine_and_speaker_detection(
            [b"audio1", b"audio2"],
            [Line(speaker="speaker0", text="some text", start=0.0, end=2.1)],
        )
    ]
    assert mock_chatter.mock_calls == calls
    reset_mocks()

    # --- transcript has error
    transcript2commands.side_effect = []
    tail_of.side_effect = []
    mock_chatter.combine_and_speaker_detection.side_effect = [
        JsonExtract(has_error=True, error="theError", content=transcript),
    ]

    result = tested.audio2commands(
        mock_auditor,
        audios,
        mock_chatter,
        previous,
        [Line(speaker="speaker0", text="some text", start=0.0, end=2.1)],
    )
    expected = (previous, [], [])
    assert result == expected

    calls = [
        call.instance(identification, "main", "s3Credentials"),
        call.instance().output("--> transcript encountered: theError"),
    ]
    assert memory_log.mock_calls == calls
    assert transcript2commands.mock_calls == []
    assert tail_of.mock_calls == []
    calls = [
        call.combine_and_speaker_detection(
            [b"audio1", b"audio2"],
            [Line(speaker="speaker0", text="some text", start=0.0, end=2.1)],
        )
    ]
    assert mock_chatter.mock_calls == calls
    reset_mocks()


@patch.object(Commander, "transcript2commands_questionnaires")
@patch.object(Commander, "transcript2commands_common")
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
        Line(speaker="speaker1", text="textA", start=0.0, end=2.1),
        Line(speaker="speaker2", text="textB", start=2.1, end=4.8),
        Line(speaker="speaker1", text="textC", start=4.8, end=5.7),
    ]
    # only common instructions
    instructions = [
        Instruction(
            uuid="uuidA",
            index=0,
            instruction="theInstructionA",
            information="theInformationA",
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuidB",
            index=1,
            instruction="theInstructionB",
            information="theInformationB",
            is_new=False,
            is_updated=True,
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
            index=0,
            instruction="ReviewOfSystem",
            information="theInformationA",
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuidB",
            index=1,
            instruction="Questionnaire",
            information="theInformationB",
            is_new=False,
            is_updated=True,
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
            index=0,
            instruction="theInstructionA",
            information="theInformationA",
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuidB",
            index=1,
            instruction="Questionnaire",
            information="theInformationB",
            is_new=False,
            is_updated=True,
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


@patch("hyperscribe.libraries.commander.ProgressDisplay")
@patch("hyperscribe.libraries.commander.MemoryLog")
@patch("hyperscribe.libraries.commander.time")
def test_transcript2commands_common(time, memory_log, progress):
    mock_auditor = MagicMock()
    mock_chatter = MagicMock()
    mock_commands = [MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        time.reset_mock()
        memory_log.reset_mock()
        progress.reset_mock()
        mock_auditor.reset_mock()
        mock_chatter.reset_mock()
        for a_command in mock_commands:
            a_command.reset_mock()

    tested = Commander

    transcript = [
        Line(speaker="speaker1", text="textA", start=0.0, end=2.1),
        Line(speaker="speaker2", text="textB", start=2.1, end=4.8),
        Line(speaker="speaker1", text="textC", start=4.8, end=5.7),
    ]
    previous_instructions = [
        Instruction(
            uuid="uuidA",
            index=0,
            instruction="theInstructionA",
            information="theInformationA",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuidB",
            index=1,
            instruction="theInstructionB",
            information="theInformationB",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuidF",
            index=2,
            instruction="theInstructionA",
            information="theInformationF",
            is_new=False,
            is_updated=True,
        ),
    ]
    exp_instructions = [
        Instruction(
            uuid="uuidA",
            index=1,
            instruction="theInstructionA",
            information="changedInformationA",
            is_new=False,
            is_updated=True,
        ).set_previous_information("theInformationA"),
        Instruction(
            uuid="uuidB",
            index=2,
            instruction="theInstructionB",
            information="theInformationB",
            is_new=False,
            is_updated=False,
        ).set_previous_information("theInformationB"),
        Instruction(
            uuid="uuidF",
            index=3,
            instruction="theInstructionA",
            information="changedInformationF",
            is_new=False,
            is_updated=True,
        ).set_previous_information("theInformationF"),
        Instruction(
            uuid="uuidC",
            index=4,
            instruction="theInstructionC",
            information="theInformationC",
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuidD",
            index=5,
            instruction="theInstructionD",
            information="theInformationD",
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuidE",
            index=6,
            instruction="theInstructionD",
            information="theInformationE",
            is_new=True,
            is_updated=False,
        ),
    ]
    instructions_with_parameters = [
        InstructionWithParameters(
            uuid="uuidA",
            index=1,
            instruction="theInstructionA",
            information="changedInformationA",
            is_new=False,
            is_updated=True,
            parameters={"params": "instruction0"},
        ),
        # B is unchanged
        InstructionWithParameters(
            uuid="uuidF",
            index=3,
            instruction="theInstructionA",
            information="changedInformationF",
            is_new=False,
            is_updated=True,
            parameters={"params": "instruction5"},
        ),
        None,  # C results with None
        InstructionWithParameters(
            uuid="uuidD",
            index=5,
            instruction="theInstructionD",
            information="theInformationD",
            is_new=True,
            is_updated=False,
            parameters={"params": "instruction3"},
        ),
        InstructionWithParameters(
            uuid="uuidE",
            index=6,
            instruction="theInstructionD",
            information="theInformationE",
            is_new=True,
            is_updated=False,
            parameters={"params": "instruction4"},
        ),
    ]
    instructions_with_commands = [
        InstructionWithCommand(
            uuid="uuidA",
            index=1,
            instruction="theInstructionA",
            information="changedInformationA",
            is_new=False,
            is_updated=True,
            parameters={"params": "instruction0"},
            command=mock_commands[0],
        ),
        InstructionWithCommand(
            uuid="uuidF",
            index=3,
            instruction="theInstructionA",
            information="changedInformationF",
            is_new=False,
            is_updated=True,
            parameters={"params": "instruction5"},
            command=mock_commands[1],
        ),
        InstructionWithCommand(
            uuid="uuidD",
            index=5,
            instruction="theInstructionD",
            information="theInformationD",
            is_new=True,
            is_updated=False,
            parameters={"params": "instruction3"},
            command=mock_commands[2],
        ),
        None,  # E
    ]

    effects = [
        Effect(type="LOG", payload="Log1"),
        Effect(type="LOG", payload="Log2"),
        Effect(type="LOG", payload="Log3"),
    ]
    command_calls = [call.edit(), call.edit(), call.originate()]
    tests = [
        # -- simulated note
        (True, [], []),
        # -- 'real' note
        (False, effects, command_calls),
    ]
    for is_local_data, exp_effects, exp_command_calls in tests:
        identification = IdentificationParameters(
            patient_uuid="patientUuid",
            note_uuid="noteUuid",
            provider_uuid="providerUuid",
            canvas_instance="canvasInstance",
        )
        settings = Settings(
            llm_text=VendorKey(vendor="textVendor", api_key="textAPIKey"),
            llm_audio=VendorKey(vendor="audioVendor", api_key="audioAPIKey"),
            structured_rfv=True,
            audit_llm=True,
            reasoning_llm=False,
            custom_prompts=[],
            is_tuning=False,
            api_signing_key="theApiSigningKey",
            max_workers=7,
            hierarchical_detection_threshold=5,
            send_progress=False,
            commands_policy=AccessPolicy(policy=False, items=["Command1", "Command2", "Command3"]),
            staffers_policy=AccessPolicy(policy=False, items=["31", "47"]),
            trial_staffers_policy=AccessPolicy(policy=True, items=[]),
            cycle_transcript_overlap=37,
        )
        mock_chatter.is_local_data = is_local_data
        mock_chatter.identification = identification
        mock_chatter.settings = settings
        mock_chatter.s3_credentials = "awsS3"

        mock_chatter.detect_instructions.side_effect = [
            [
                {
                    "uuid": "uuidA",
                    "instruction": "theInstructionA",
                    "information": "changedInformationA",
                    "isNew": False,
                    "isUpdated": True,
                },
                {
                    "uuid": "uuidB",
                    "instruction": "theInstructionB",
                    "information": "theInformationB",
                    "isNew": False,
                    "isUpdated": False,
                },
                {
                    "uuid": "uuidF",
                    "instruction": "theInstructionA",
                    "information": "changedInformationF",
                    "isNew": False,
                    "isUpdated": True,
                },
                {
                    "uuid": "uuidC",
                    "instruction": "theInstructionC",
                    "information": "theInformationC",
                    "isNew": True,
                    "isUpdated": False,
                },
                {
                    "uuid": "uuidD",
                    "instruction": "theInstructionD",
                    "information": "theInformationD",
                    "isNew": True,
                    "isUpdated": False,
                },
                {
                    "uuid": "uuidE",
                    "instruction": "theInstructionD",
                    "information": "theInformationE",
                    "isNew": True,
                    "isUpdated": False,
                },
            ],
        ]
        mock_chatter.create_sdk_command_parameters.side_effect = instructions_with_parameters
        mock_chatter.create_sdk_command_from.side_effect = instructions_with_commands

        mock_commands[0].edit.side_effect = [Effect(type="LOG", payload="Log1")]
        mock_commands[1].edit.side_effect = [Effect(type="LOG", payload="Log2")]
        mock_commands[2].edit.side_effect = []
        mock_commands[0].originate.side_effect = []
        mock_commands[1].originate.side_effect = []
        mock_commands[2].originate.side_effect = [Effect(type="LOG", payload="Log3")]

        time.side_effect = [111.110, 111.219]

        result = tested.transcript2commands_common(mock_auditor, transcript, mock_chatter, previous_instructions)
        expected = (exp_instructions, exp_effects)
        assert result[0] == expected[0]
        assert result[1] == expected[1]

        exp_instructions_w_parameters = [instructions_with_parameters[i] for i in [0, 1, 3, 4]]
        exp_instructions_w_commands = [instructions_with_commands[i] for i in [0, 1, 2]]
        calls = [
            call.instance(identification, "main", "awsS3"),
            call.instance().output("--> instructions: 6"),
            call.instance().output("--> computed instructions: 5"),
            call.instance().output("--> computed commands: 4"),
            call.instance().output("DURATION COMMONS: 108"),
        ]
        assert memory_log.mock_calls == calls
        calls = [
            call.send_to_user(
                identification,
                settings,
                [
                    ProgressMessage(
                        message="instructions detection: "
                        "new: theInstructionC: 1, theInstructionD: 2, "
                        "updated: theInstructionA: 2, "
                        "total: 6",
                        section="events:4",
                    )
                ],
            ),
            call.send_to_user(
                identification,
                settings,
                [ProgressMessage(message="parameters computation done (4)", section="events:4")],
            ),
            call.send_to_user(
                identification,
                settings,
                [ProgressMessage(message="commands generation done (3)", section="events:4")],
            ),
        ]
        assert progress.mock_calls == calls
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
        for idx, command_call in enumerate(exp_command_calls):
            calls = [command_call]
            assert mock_commands[idx].mock_calls == calls

        reset_mocks()

    # no new instruction, no updates
    previous_instructions = [
        Instruction(
            uuid="uuidA",
            index=0,
            instruction="theInstructionA",
            information="theInformationA",
            is_new=False,
            is_updated=False,
        ).set_previous_information("theInformationA"),
        Instruction(
            uuid="uuidB",
            index=1,
            instruction="theInstructionB",
            information="theInformationB",
            is_new=False,
            is_updated=False,
        ).set_previous_information("theInformationB"),
        Instruction(
            uuid="uuidF",
            index=2,
            instruction="theInstructionA",
            information="theInformationF",
            is_new=False,
            is_updated=False,
        ).set_previous_information("theInformationF"),
    ]
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textAPIKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioAPIKey"),
        structured_rfv=True,
        audit_llm=True,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=7,
        hierarchical_detection_threshold=5,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=["Command1", "Command2", "Command3"]),
        staffers_policy=AccessPolicy(policy=False, items=["31", "47"]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    mock_chatter.identification = identification
    mock_chatter.settings = settings
    mock_chatter.s3_credentials = "awsS3"

    mock_chatter.detect_instructions.side_effect = [
        [
            {
                "uuid": "uuidA",
                "instruction": "theInstructionA",
                "information": "theInformationA",
                "isNew": False,
                "isUpdated": False,
            },
            {
                "uuid": "uuidB",
                "instruction": "theInstructionB",
                "information": "theInformationB",
                "isNew": False,
                "isUpdated": False,
            },
            {
                "uuid": "uuidF",
                "instruction": "theInstructionA",
                "information": "theInformationF",
                "isNew": False,
                "isUpdated": False,
            },
        ],
    ]
    mock_chatter.create_sdk_command_parameters.side_effect = instructions_with_parameters
    mock_chatter.create_sdk_command_from.side_effect = instructions_with_commands

    mock_commands[0].edit.side_effect = []
    mock_commands[1].edit.side_effect = []
    mock_commands[2].edit.side_effect = []
    mock_commands[0].originate.side_effect = []
    mock_commands[1].originate.side_effect = []
    mock_commands[2].originate.side_effect = []

    time.side_effect = [111.110, 111.219]

    result = tested.transcript2commands_common(mock_auditor, transcript, mock_chatter, previous_instructions)
    expected = (previous_instructions, [])
    assert result[0] == expected[0]
    assert result[1] == expected[1]

    exp_instructions_w_parameters = []
    exp_instructions_w_commands = []
    calls = [
        call.instance(identification, "main", "awsS3"),
        call.instance().output("--> instructions: 3"),
        call.instance().output("--> computed instructions: 0"),
        call.instance().output("--> computed commands: 0"),
        call.instance().output("DURATION COMMONS: 108"),
    ]
    assert memory_log.mock_calls == calls
    calls = [
        call.send_to_user(
            identification,
            settings,
            [ProgressMessage(message="instructions detection: total: 3", section="events:4")],
        ),
        call.send_to_user(
            identification,
            settings,
            [ProgressMessage(message="parameters computation done (0)", section="events:4")],
        ),
        call.send_to_user(
            identification,
            settings,
            [ProgressMessage(message="commands generation done (0)", section="events:4")],
        ),
    ]
    assert progress.mock_calls == calls
    calls = [call(), call()]
    assert time.mock_calls == calls
    calls = [
        call.found_instructions(transcript, previous_instructions, expected[0]),
        call.computed_parameters(exp_instructions_w_parameters),
        call.computed_commands(exp_instructions_w_commands),
    ]
    assert mock_auditor.mock_calls == calls
    calls = [call.detect_instructions(transcript, previous_instructions)]
    assert mock_chatter.mock_calls == calls
    for mock_command in mock_commands:
        assert mock_command.mock_calls == []

    reset_mocks()


@patch("hyperscribe.libraries.commander.ProgressDisplay")
@patch("hyperscribe.libraries.commander.MemoryLog")
@patch("hyperscribe.libraries.commander.time")
def test_transcript2commands_questionnaires(time, memory_log, progress):
    auditor = MagicMock()
    chatter = MagicMock()
    mock_commands = [MagicMock(), MagicMock()]

    def reset_mocks():
        time.reset_mock()
        memory_log.reset_mock()
        progress.reset_mock()
        auditor.reset_mock()
        chatter.reset_mock()
        for a_command in mock_commands:
            a_command.reset_mock()

    transcript = [
        Line(speaker="speaker1", text="textA", start=0.0, end=2.1),
        Line(speaker="speaker2", text="textB", start=2.1, end=4.8),
        Line(speaker="speaker1", text="textC", start=4.8, end=5.7),
    ]

    instructions = [
        Instruction(
            uuid="uuidA",
            index=0,
            instruction="theInstructionA",
            information="theInformationA",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuidB",
            index=1,
            instruction="theInstructionB",
            information="theInformationB",
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuidC",
            index=2,
            instruction="theInstructionC",
            information="theInformationC",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuidD",
            index=3,
            instruction="theInstructionD",
            information="theInformationD",
            is_new=True,
            is_updated=True,
        ),
        Instruction(
            uuid="uuidE",
            index=4,
            instruction="theInstructionE",
            information="theInformationE",
            is_new=True,
            is_updated=True,
        ),
    ]
    instructions_with_commands = [
        None,
        InstructionWithCommand(
            uuid="uuidB",
            index=1,
            instruction="theInstructionB",
            information="theInformationB",
            is_new=False,
            is_updated=False,
            parameters={},
            command=mock_commands[0],
        ),
        InstructionWithCommand(
            uuid="uuidC",
            index=2,
            instruction="theInstructionC",
            information="theInformationC",
            is_new=False,
            is_updated=True,
            parameters={},
            command=mock_commands[1],
        ),
        None,
        None,
    ]

    updated = [
        Instruction(
            uuid="uuidB",
            index=1,
            instruction="theInstructionB",
            information="theInformationB",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuidC",
            index=2,
            instruction="theInstructionC",
            information="theInformationC",
            is_new=False,
            is_updated=True,
        ),
    ]
    effects = [Effect(type="LOG", payload="Log0"), Effect(type="LOG", payload="Log1")]

    tested = Commander
    # no instruction
    result = tested.transcript2commands_questionnaires(auditor, transcript, chatter, [])
    expected = ([], [])
    assert result == expected
    assert memory_log.mock_calls == []
    assert time.mock_calls == []
    calls = [call.computed_questionnaires(transcript, [], [])]
    assert auditor.mock_calls == calls
    assert chatter.mock_calls == []
    for mock_command in mock_commands:
        assert mock_command.mock_calls == []
    reset_mocks()

    # with instructions
    tests = [
        # -- simulated note
        (True, (updated, []), []),
        # -- 'real' note
        (False, (updated, effects), [call.edit()]),
    ]
    for is_local_data, expected, command_calls in tests:
        identification = IdentificationParameters(
            patient_uuid="patientUuid",
            note_uuid="noteUuid",
            provider_uuid="providerUuid",
            canvas_instance="canvasInstance",
        )
        settings = Settings(
            llm_text=VendorKey(vendor="textVendor", api_key="textAPIKey"),
            llm_audio=VendorKey(vendor="audioVendor", api_key="audioAPIKey"),
            structured_rfv=True,
            audit_llm=True,
            reasoning_llm=False,
            custom_prompts=[],
            is_tuning=False,
            api_signing_key="theApiSigningKey",
            max_workers=7,
            hierarchical_detection_threshold=5,
            send_progress=False,
            commands_policy=AccessPolicy(policy=False, items=["Command1", "Command2", "Command3"]),
            staffers_policy=AccessPolicy(policy=False, items=["31", "47"]),
            trial_staffers_policy=AccessPolicy(policy=True, items=[]),
            cycle_transcript_overlap=37,
        )
        chatter.is_local_data = is_local_data
        chatter.identification = identification
        chatter.settings = settings
        chatter.s3_credentials = "awsS3"
        time.side_effect = [111.110, 111.357]
        chatter.update_questionnaire.side_effect = instructions_with_commands
        for idx, mock_command in enumerate(mock_commands):
            mock_command.edit.side_effect = [Effect(type="LOG", payload=f"Log{idx}")]

        result = tested.transcript2commands_questionnaires(auditor, transcript, chatter, instructions)
        assert result == expected
        calls = [call.instance(identification, "main", "awsS3"), call.instance().output("DURATION QUESTIONNAIRES: 246")]
        assert memory_log.mock_calls == calls
        calls = [
            call.send_to_user(
                identification,
                settings,
                [ProgressMessage(message="questionnaires update done (2)", section="events:4")],
            )
        ]
        assert progress.mock_calls == calls
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


@patch("hyperscribe.libraries.commander.MemoryLog")
@patch("hyperscribe.libraries.commander.time")
def test_new_commands_from(time, memory_log):
    auditor = MagicMock()
    chatter = MagicMock()
    mock_commands = [MagicMock(), MagicMock()]

    def reset_mocks():
        time.reset_mock()
        memory_log.reset_mock()
        auditor.reset_mock()
        chatter.reset_mock()
        for a_command in mock_commands:
            a_command.reset_mock()

    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textAPIKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioAPIKey"),
        structured_rfv=True,
        audit_llm=True,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=7,
        hierarchical_detection_threshold=5,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=["Command1", "Command2", "Command3"]),
        staffers_policy=AccessPolicy(policy=False, items=["31", "47"]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    instructions = [
        Instruction(
            uuid="uuidA",
            index=0,
            instruction="theInstructionA",
            information="theInformationA",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuidB",
            index=1,
            instruction="theInstructionB",
            information="theInformationB",
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuidC",
            index=2,
            instruction="theInstructionC",
            information="theInformationC",
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuidD",
            index=3,
            instruction="theInstructionD",
            information="theInformationD",
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuidE",
            index=4,
            instruction="theInstructionE",
            information="theInformationE",
            is_new=True,
            is_updated=False,
        ),
    ]
    instructions_with_parameters = [
        InstructionWithParameters(
            uuid="uuidB",
            index=1,
            instruction="theInstructionB",
            information="theInformationB",
            is_new=True,
            is_updated=False,
            parameters={"params": "instruction1"},
        ),
        None,
        InstructionWithParameters(
            uuid="uuidD",
            index=3,
            instruction="theInstructionD",
            information="theInformationD",
            is_new=True,
            is_updated=False,
            parameters={"params": "instruction3"},
        ),
        InstructionWithParameters(
            uuid="uuidE",
            index=4,
            instruction="theInstructionE",
            information="theInformationE",
            is_new=True,
            is_updated=False,
            parameters={"params": "instruction4"},
        ),
    ]
    instructions_with_commands = [
        InstructionWithCommand(
            uuid="uuidB",
            index=1,
            instruction="theInstructionB",
            information="theInformationB",
            is_new=True,
            is_updated=False,
            parameters={"params": "instruction1"},
            command=mock_commands[0],
        ),
        InstructionWithCommand(
            uuid="uuidD",
            index=3,
            instruction="theInstructionD",
            information="theInformationD",
            is_new=True,
            is_updated=False,
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
    chatter.is_local_data = False
    chatter.identification = identification
    chatter.settings = settings
    chatter.s3_credentials = "awsS3"
    for mock_command in mock_commands:
        mock_command.originate.side_effect = []

    result = tested.new_commands_from(auditor, chatter, instructions, past_uuids)
    assert result == []
    calls = [
        call(identification, "main"),
        call().output("--> new instructions: 0"),
        call().output("--> new commands: 0"),
        call().output("DURATION NEW: 108"),
    ]
    assert memory_log.mock_calls == calls
    calls = [call(), call()]
    assert time.mock_calls == calls
    calls = [call.computed_parameters([]), call.computed_commands([])]
    assert auditor.mock_calls == calls
    assert chatter.mock_calls == []
    for mock_command in mock_commands:
        assert mock_command.mock_calls == []
    reset_mocks()

    # with new instructions
    tests = [
        # -- simulated note
        (True, [], []),  # -- simulated note
        # -- 'real' note
        (False, [Effect(type="LOG", payload="Log0"), Effect(type="LOG", payload="Log1")], [call.originate()]),
    ]
    for is_local_data, expected, command_calls in tests:
        identification = IdentificationParameters(
            patient_uuid="patientUuid",
            note_uuid="noteUuid",
            provider_uuid="providerUuid",
            canvas_instance="canvasInstance",
        )
        chatter.is_local_data = is_local_data
        chatter.identification = identification
        past_uuids = {"uuidA": instructions[0]}
        time.side_effect = [111.110, 111.357]
        chatter.create_sdk_command_parameters.side_effect = instructions_with_parameters
        chatter.create_sdk_command_from.side_effect = instructions_with_commands
        for idx, mock_command in enumerate(mock_commands):
            mock_command.originate.side_effect = [Effect(type="LOG", payload=f"Log{idx}")]

        result = tested.new_commands_from(auditor, chatter, instructions, past_uuids)
        assert result == expected
        calls = [
            call(identification, "main"),
            call().output("--> new instructions: 4"),
            call().output("--> new commands: 3"),
            call().output("DURATION NEW: 246"),
        ]
        assert memory_log.mock_calls == calls
        calls = [call(), call()]
        assert time.mock_calls == calls
        calls = [
            call.computed_parameters(
                [instructions_with_parameters[0], instructions_with_parameters[2], instructions_with_parameters[3]],
            ),
            call.computed_commands([instructions_with_commands[0], instructions_with_commands[1]]),
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


@patch("hyperscribe.libraries.commander.MemoryLog")
@patch("hyperscribe.libraries.commander.time")
def test_update_commands_from(time, memory_log):
    auditor = MagicMock()
    chatter = MagicMock()
    mock_commands = [MagicMock(), MagicMock()]

    def reset_mocks():
        time.reset_mock()
        memory_log.reset_mock()
        auditor.reset_mock()
        chatter.reset_mock()
        for a_command in mock_commands:
            a_command.reset_mock()

    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textAPIKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioAPIKey"),
        structured_rfv=True,
        audit_llm=True,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=7,
        hierarchical_detection_threshold=5,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=["Command1", "Command2", "Command3"]),
        staffers_policy=AccessPolicy(policy=False, items=["31", "47"]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    instructions = [
        Instruction(
            uuid="uuidA",
            index=0,
            instruction="theInstructionX",
            information="theInformationA",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuidB",
            index=1,
            instruction="theInstructionX",
            information="theInformationB",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuidC",
            index=2,
            instruction="theInstructionY",
            information="theInformationC",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuidD",
            index=3,
            instruction="theInstructionY",
            information="theInformationD",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuidE",
            index=4,
            instruction="theInstructionY",
            information="theInformationE",
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuidF",
            index=5,
            instruction="theInstructionY",
            information="theInformationF",
            is_new=True,
            is_updated=False,
        ),
    ]
    instructions_with_parameters = [
        InstructionWithParameters(
            uuid="uuidB",
            index=1,
            instruction="theInstructionB",
            information="theInformationB",
            is_new=True,
            is_updated=False,
            parameters={"params": "instruction1"},
        ),
        None,
        InstructionWithParameters(
            uuid="uuidD",
            index=2,
            instruction="theInstructionD",
            information="theInformationD",
            is_new=True,
            is_updated=False,
            parameters={"params": "instruction3"},
        ),
        InstructionWithParameters(
            uuid="uuidE",
            index=3,
            instruction="theInstructionE",
            information="theInformationE",
            is_new=True,
            is_updated=False,
            parameters={"params": "instruction4"},
        ),
    ]
    instructions_with_commands = [
        InstructionWithCommand(
            uuid="uuidB",
            index=1,
            instruction="theInstructionB",
            information="theInformationB",
            is_new=True,
            is_updated=False,
            parameters={"params": "instruction1"},
            command=mock_commands[0],
        ),
        InstructionWithCommand(
            uuid="uuidD",
            index=3,
            instruction="theInstructionD",
            information="theInformationD",
            is_new=True,
            is_updated=False,
            parameters={"params": "instruction3"},
            command=mock_commands[1],
        ),
        None,
    ]
    chatter.is_local_data = False
    chatter.identification = identification
    chatter.settings = settings
    chatter.s3_credentials = "awsS3"

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
        call(identification, "main"),
        call().output("--> updated instructions: 0"),
        call().output("--> updated commands: 0"),
        call().output("DURATION UPDATE: 246"),
    ]
    assert memory_log.mock_calls == calls
    calls = [call(), call()]
    assert time.mock_calls == calls
    calls = [call.computed_parameters([]), call.computed_commands([])]
    assert auditor.mock_calls == calls
    assert chatter.mock_calls == []
    for mock_command in mock_commands:
        assert mock_command.mock_calls == []
    reset_mocks()

    # updated instructions
    tests = [
        # -- simulated note
        (True, [], []),  # -- simulated note
        # -- 'real' note
        (False, [Effect(type="LOG", payload="Log0"), Effect(type="LOG", payload="Log1")], [call.edit()]),
    ]
    for is_local_data, expected, command_calls in tests:
        identification = IdentificationParameters(
            patient_uuid="patientUuid",
            note_uuid="noteUuid",
            provider_uuid="providerUuid",
            canvas_instance="canvasInstance",
        )
        chatter.is_local_data = is_local_data
        chatter.identification = identification
        past_uuids = {
            "uuidA": Instruction(
                uuid="uuidA",
                index=0,
                instruction="theInstructionX",
                information="changedA",
                is_new=False,
                is_updated=True,
            ),
            "uuidB": instructions[1],
            "uuidC": instructions[2],
            "uuidD": Instruction(
                uuid="uuidD",
                index=1,
                instruction="theInstructionY",
                information="changedD",
                is_new=False,
                is_updated=True,
            ),
            "uuidE": Instruction(
                uuid="uuidE",
                index=2,
                instruction="theInstructionY",
                information="changedE",
                is_new=True,
                is_updated=False,
            ),
            "uuidF": Instruction(
                uuid="uuidF",
                index=3,
                instruction="theInstructionY",
                information="changedE",
                is_new=True,
                is_updated=False,
            ),
        }
        time.side_effect = [111.110, 111.451]
        chatter.create_sdk_command_parameters.side_effect = instructions_with_parameters
        chatter.create_sdk_command_from.side_effect = instructions_with_commands
        for idx, mock_command in enumerate(mock_commands):
            mock_command.edit.side_effect = [Effect(type="LOG", payload=f"Log{idx}")]

        result = tested.update_commands_from(auditor, chatter, instructions, past_uuids)
        assert result == expected
        calls = [
            call(identification, "main"),
            call().output("--> updated instructions: 4"),
            call().output("--> updated commands: 3"),
            call().output("DURATION UPDATE: 340"),
        ]
        assert memory_log.mock_calls == calls
        calls = [call(), call()]
        assert time.mock_calls == calls
        calls = [
            call.computed_parameters(
                [instructions_with_parameters[0], instructions_with_parameters[2], instructions_with_parameters[3]],
            ),
            call.computed_commands([instructions_with_commands[0], instructions_with_commands[1]]),
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
        {"canvas_command_X": "theInstructionX", "canvas_command_Y": "theInstructionY"},
    ]

    result = tested.existing_commands_to_instructions(current_commands, [])
    expected = [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="theInstructionX",
            information="",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid2",
            index=1,
            instruction="theInstructionX",
            information="",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid3",
            index=2,
            instruction="theInstructionY",
            information="",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid4",
            index=3,
            instruction="theInstructionY",
            information="",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid5",
            index=4,
            instruction="theInstructionY",
            information="",
            is_new=False,
            is_updated=False,
        ),
    ]
    assert result == expected
    calls = [call()]
    assert schema_key2instruction.mock_calls == calls
    reset_mocks()

    # updated instructions
    current_commands = [
        Command(
            id="uuid0",
            schema_key="canvas_command_Z",
            data={"narrative": "theNarrative0", "comment": "theComment0"},
        ),
        Command(
            id="uuid1",
            schema_key="canvas_command_X",
            data={"narrative": "theNarrative1", "comment": "theComment1"},
        ),
        Command(
            id="uuid3",
            schema_key="canvas_command_Y",
            data={"narrative": "theNarrative3", "comment": "theComment3"},
        ),
        Command(
            id="uuid4",
            schema_key="canvas_command_Y",
            data={"narrative": "theNarrative4", "comment": "theComment4"},
        ),
        Command(
            id="uuid2",
            schema_key="canvas_command_X",
            data={"narrative": "theNarrative2", "comment": "theComment2"},
        ),
        Command(
            id="uuid5",
            schema_key="canvas_command_Y",
            data={"narrative": "theNarrative5", "comment": "theComment5"},
        ),
        Command(id="uuid6", schema_key="hpi", data={"narrative": "theNarrative6", "comment": "theComment6"}),
        Command(id="uuid7", schema_key="reasonForVisit", data={"narrative": "theNarrative7", "comment": "theComment7"}),
        Command(
            id="uuid8",
            schema_key="exam",
            data={"questionnaire": {"extra": {"pk": 123, "name": "thePhysicalExam", "questions": []}}},
        ),
        Command(
            id="uuid9",
            schema_key="questionnaire",
            data={"questionnaire": {"extra": {"pk": 234, "name": "theQuestionnaire", "questions": []}}},
        ),
        Command(
            id="uuid10",
            schema_key="ros",
            data={"questionnaire": {"extra": {"pk": 125, "name": "theReviewOfSystem", "questions": []}}},
        ),
        Command(
            id="uuid11",
            schema_key="structuredAssessment",
            data={"questionnaire": {"extra": {"pk": 222, "name": "theStructuredAssessment", "questions": []}}},
        ),
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
        Instruction(
            uuid="uuidA",
            index=0,
            instruction="theInstructionX",
            information="theInformationA",
            is_new=True,
            is_updated=True,
        ),
        Instruction(
            uuid="uuidB",
            index=1,
            instruction="theInstructionY",
            information="theInformationD",
            is_new=True,
            is_updated=True,
        ),
        Instruction(
            uuid="uuidC",
            index=2,
            instruction="theInstructionY",
            information="theInformationE",
            is_new=True,
            is_updated=True,
        ),
    ]

    result = tested.existing_commands_to_instructions(current_commands, instructions)
    expected = [
        Instruction(
            uuid="uuid0",
            index=0,
            instruction="theInstructionZ",
            information="",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid1",
            index=1,
            instruction="theInstructionX",
            information="theInformationA",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid3",
            index=3,
            instruction="theInstructionY",
            information="theInformationD",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid4",
            index=4,
            instruction="theInstructionY",
            information="theInformationE",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid2",
            index=2,
            instruction="theInstructionX",
            information="",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid5",
            index=5,
            instruction="theInstructionY",
            information="",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid6",
            index=6,
            instruction="HistoryOfPresentIllness",
            information="theNarrative6",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid7",
            index=7,
            instruction="ReasonForVisit",
            information="theComment7",
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid8",
            index=8,
            instruction="PhysicalExam",
            information='{"name": "thePhysicalExam", "dbid": 123, "questions": []}',
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid9",
            index=9,
            instruction="Questionnaire",
            information='{"name": "theQuestionnaire", "dbid": 234, "questions": []}',
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid10",
            index=10,
            instruction="ReviewOfSystem",
            information='{"name": "theReviewOfSystem", "dbid": 125, "questions": []}',
            is_new=False,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid11",
            index=11,
            instruction="StructuredAssessment",
            information='{"name": "theStructuredAssessment", "dbid": 222, "questions": []}',
            is_new=False,
            is_updated=False,
        ),
    ]
    assert result == expected
    calls = [call()]
    assert schema_key2instruction.mock_calls == calls
    reset_mocks()


@patch.object(ImplementedCommands, "command_list")
def test_existing_commands_to_coded_items(command_list):
    mock_commands = [MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        command_list.reset_mock()
        for c in mock_commands:
            c.reset_mock()

    tested = Commander
    current_commands = [
        Command(id="uuid1", schema_key="canvas_command_X", data={"key1": "value1"}),
        Command(id="uuid2", schema_key="canvas_command_X", data={"key2": "value2"}),
        Command(id="uuid3", schema_key="canvas_command_Y", data={"key3": "value3"}),
        Command(id="uuid4", schema_key="canvas_command_Y", data={"key4": "value4"}),
        Command(id="uuid5", schema_key="canvas_command_Y", data={"key5": "value5"}),
        Command(id="uuid6", schema_key="canvas_command_A", data={"key6": "value6"}),
    ]

    # all commands allowed
    command_list.side_effect = [mock_commands] * 6

    mock_commands[0].schema_key.return_value = "canvas_command_X"
    mock_commands[0].class_name.return_value = "CommandX"
    mock_commands[1].schema_key.return_value = "canvas_command_Y"
    mock_commands[1].class_name.return_value = "CommandY"
    mock_commands[2].schema_key.return_value = "canvas_command_Z"
    mock_commands[2].class_name.return_value = "CommandZ"

    mock_commands[0].staged_command_extract.side_effect = [CodedItem(label="label1", code="code1", uuid=""), None]
    mock_commands[1].staged_command_extract.side_effect = [
        CodedItem(label="label3", code="code3", uuid=""),
        CodedItem(label="label4", code="code4", uuid=""),
        CodedItem(label="label5", code="code5", uuid=""),
    ]
    mock_commands[2].staged_command_extract.side_effect = []

    policy = AccessPolicy(policy=True, items=["CommandX", "CommandY", "CommandZ"])
    result = tested.existing_commands_to_coded_items(current_commands, policy, True)
    expected = {
        "canvas_command_X": [CodedItem(uuid="uuid1", label="label1", code="code1")],
        "canvas_command_Y": [
            CodedItem(uuid="uuid3", label="label3", code="code3"),
            CodedItem(uuid="uuid4", label="label4", code="code4"),
            CodedItem(uuid="uuid5", label="label5", code="code5"),
        ],
    }
    assert result == expected
    calls = [call()] * 6
    assert command_list.mock_calls == calls
    calls = [
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key1": "value1"}),
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key2": "value2"}),
        call.class_name(),
        call.schema_key(),
        call.class_name(),
        call.schema_key(),
        call.class_name(),
        call.schema_key(),
        call.class_name(),
        call.schema_key(),
    ]
    assert mock_commands[0].mock_calls == calls
    calls = [
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key3": "value3"}),
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key4": "value4"}),
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key5": "value5"}),
        call.class_name(),
        call.schema_key(),
    ]
    assert mock_commands[1].mock_calls == calls
    calls = [call.class_name(), call.schema_key()]
    assert mock_commands[2].mock_calls == calls
    reset_mocks()

    # one command allowed
    command_list.side_effect = [mock_commands] * 6

    mock_commands[0].schema_key.return_value = "canvas_command_X"
    mock_commands[0].class_name.return_value = "CommandX"
    mock_commands[1].schema_key.return_value = "canvas_command_Y"
    mock_commands[1].class_name.return_value = "CommandY"
    mock_commands[2].schema_key.return_value = "canvas_command_Z"
    mock_commands[2].class_name.return_value = "CommandZ"

    mock_commands[0].staged_command_extract.side_effect = [CodedItem(label="label1", code="code1", uuid=""), None]
    mock_commands[1].staged_command_extract.side_effect = [
        CodedItem(label="label3", code="code3", uuid=""),
        CodedItem(label="label4", code="code4", uuid=""),
        CodedItem(label="label5", code="code5", uuid=""),
    ]
    mock_commands[2].staged_command_extract.side_effect = []

    policy = AccessPolicy(policy=True, items=["CommandX"])
    result = tested.existing_commands_to_coded_items(current_commands, policy, False)
    expected = {"canvas_command_X": [CodedItem(uuid="", label="label1", code="code1")]}
    assert result == expected
    calls = [call()] * 6
    assert command_list.mock_calls == calls
    calls = [
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key1": "value1"}),
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key2": "value2"}),
        call.class_name(),
        call.schema_key(),
        call.class_name(),
        call.schema_key(),
        call.class_name(),
        call.schema_key(),
        call.class_name(),
        call.schema_key(),
    ]
    assert mock_commands[0].mock_calls == calls
    calls = [call.class_name(), call.class_name(), call.class_name(), call.class_name()]
    assert mock_commands[1].mock_calls == calls
    assert mock_commands[2].mock_calls == calls
    reset_mocks()
