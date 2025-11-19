from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, call

import pytest

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.line import Line
from hyperscribe.structures.model_spec import ModelSpec
from hyperscribe.structures.progress_message import ProgressMessage
from hyperscribe.structures.section_with_transcript import SectionWithTranscript
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import MockClass


def helper_instance(mocks, with_audit) -> tuple[AudioInterpreter, Settings, AwsS3Credentials, LimitedCache]:
    def reset_mocks():
        command_list.reset_mocks()

    with patch.object(ImplementedCommands, "command_list") as command_list:
        settings = Settings(
            llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
            llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
            structured_rfv=False,
            audit_llm=with_audit,
            reasoning_llm=False,
            custom_prompts=[],
            is_tuning=False,
            api_signing_key="theApiSigningKey",
            max_workers=3,
            hierarchical_detection_threshold=4,
            send_progress=False,
            commands_policy=AccessPolicy(policy=False, items=[]),
            staffers_policy=AccessPolicy(policy=False, items=[]),
            trial_staffers_policy=AccessPolicy(policy=True, items=[]),
            cycle_transcript_overlap=37,
        )
        aws_s3 = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
        if mocks:
            mocks[0].return_value.is_available.side_effect = [True]
            mocks[1].return_value.is_available.side_effect = [True]
            mocks[2].return_value.is_available.side_effect = [False]
            mocks[3].return_value.is_available.side_effect = [True]
            if len(mocks) > 4:
                mocks[4].return_value.is_available.side_effect = [True]

        command_list.side_effect = [mocks]

        cache = LimitedCache("patientUuid", "providerUuid", {})
        cache._demographic = "thePatientDemographic"
        identification = IdentificationParameters(
            patient_uuid="patientUuid",
            note_uuid="noteUuid",
            provider_uuid="providerUuid",
            canvas_instance="canvasInstance",
        )
        instance = AudioInterpreter(settings, aws_s3, cache, identification)
        calls = [call()]
        assert command_list.mock_calls == calls
        reset_mocks()

        return instance, settings, aws_s3, cache


@patch.object(ImplementedCommands, "command_list")
def test___init__(command_list):
    mocks = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        command_list.reset_mocks()
        for item in mocks:
            item.reset_mock()

    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        structured_rfv=False,
        audit_llm=False,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
        hierarchical_detection_threshold=5,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=["Command1", "Command2", "Command3"]),
        staffers_policy=AccessPolicy(policy=False, items=["31", "47"]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    aws_s3 = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")

    mocks[0].return_value.is_available.side_effect = [True]
    mocks[1].return_value.is_available.side_effect = [True]
    mocks[2].return_value.is_available.side_effect = [False]
    mocks[3].return_value.is_available.side_effect = [True]
    mocks[4].return_value.is_available.side_effect = [True]
    mocks[0].return_value.class_name.side_effect = ["CommandA", "CommandA"]
    mocks[1].return_value.class_name.side_effect = ["CommandB", "CommandB"]
    mocks[2].return_value.class_name.side_effect = ["CommandC", "CommandC"]
    mocks[3].return_value.class_name.side_effect = ["CommandD", "CommandD"]
    mocks[4].return_value.class_name.side_effect = ["CommandE", "CommandE"]
    command_list.side_effect = [mocks]

    cache = LimitedCache("patientUuid", "providerUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    instance = AudioInterpreter(settings, aws_s3, cache, identification)
    assert instance.settings == settings
    assert instance.s3_credentials == aws_s3
    assert instance.identification == identification
    assert instance.cache == cache

    calls = [call()]
    assert command_list.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call(settings, cache, identification),
            call().__bool__(),
            call().class_name(),
            call().is_available(),
        ]
        if idx != 2:
            calls.append(call().class_name())
        assert mock.mock_calls == calls
    reset_mocks()


def test_common_instructions():
    mocks = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        for item in mocks:
            item.reset_mock()

    tests = [
        ("AdjustPrescription", True),
        ("Allergy", True),
        ("Assess", True),
        ("CloseGoal", True),
        ("Diagnose", True),
        ("FamilyHistory", True),
        ("FollowUp", True),
        ("Goal", True),
        ("HistoryOfPresentIllness", True),
        ("ImagingOrder", True),
        ("Immunize", True),
        ("Instruct", True),
        ("LabOrder", True),
        ("MedicalHistory", True),
        ("Medication", True),
        ("Perform", True),
        ("PhysicalExam", False),
        ("Plan", True),
        ("Prescription", True),
        ("Questionnaire", False),
        ("ReasonForVisit", True),
        ("Refer", True),
        ("Refill", True),
        ("RemoveAllergy", True),
        ("ResolveCondition", True),
        ("ReviewOfSystem", False),
        ("StopMedication", True),
        ("StructuredAssessment", False),
        ("SurgeryHistory", True),
        ("Task", True),
        ("UpdateDiagnose", True),
        ("UpdateGoal", True),
        ("Vitals", True),
    ]
    for class_name, expected_present in tests:
        mocks[0].return_value.class_name.side_effect = [class_name, class_name]
        mocks[1].return_value.class_name.side_effect = ["Second", "Second"]
        mocks[2].return_value.class_name.side_effect = ["Third", "Third"]
        mocks[3].return_value.class_name.side_effect = ["Fourth", "Fourth"]
        mocks[4].return_value.class_name.side_effect = ["Fifth", "Fifth"]

        tested, settings, aws_credentials, cache = helper_instance(mocks, True)
        result = tested.common_instructions()
        expected = [mocks[1].return_value, mocks[3].return_value, mocks[4].return_value]

        if expected_present:
            expected.insert(0, mocks[0].return_value)

        assert result == expected
        for idx, mock in enumerate(mocks):
            calls = [
                call(settings, cache, tested.identification),
                call().__bool__(),
                call().class_name(),
                call().is_available(),
            ]
            if idx != 2:
                calls.append(call().class_name())
            assert mock.mock_calls == calls, f"---> {idx}"
        reset_mocks()


def test_instruction_constraints():
    mocks = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        for item in mocks:
            item.reset_mock()

    instructions = Instruction.load_from_json(
        [
            {"instruction": "Command1"},
            {"instruction": "Command2"},
            {"instruction": "Command3"},
            {"instruction": "Command4"},
            {"instruction": "Command5"},
        ],
    )

    tests = [
        ([0, 1, 2, 3], ["Constraints1", "Constraints4"]),
        ([0, 1, 2, 3, 4], ["Constraints1", "Constraints4", "Constraints5"]),
        ([0], ["Constraints1"]),
        ([2, 3], ["Constraints4"]),
    ]
    for list_idx, expected in tests:
        mocks[0].return_value.class_name.side_effect = ["Command1", "Command1"]
        mocks[1].return_value.class_name.side_effect = ["Command2", "Command2"]
        mocks[2].return_value.class_name.side_effect = ["Command3", "Command3"]
        mocks[3].return_value.class_name.side_effect = ["Command4", "Command4"]
        mocks[4].return_value.class_name.side_effect = ["Command5", "Command5"]
        mocks[0].return_value.instruction_constraints.side_effect = ["Constraints1"]
        mocks[1].return_value.instruction_constraints.side_effect = [""]
        mocks[2].return_value.instruction_constraints.side_effect = ["Constraints3"]
        mocks[3].return_value.instruction_constraints.side_effect = ["Constraints4"]
        mocks[4].return_value.instruction_constraints.side_effect = ["Constraints5"]

        tested, settings, aws_credentials, cache = helper_instance(mocks, True)
        result = tested.instruction_constraints([instructions[i] for i in list_idx])
        assert result == expected
        for idx, mock in enumerate(mocks):
            calls = [
                call(settings, cache, tested.identification),
                call().__bool__(),
                call().class_name(),
                call().is_available(),
            ]
            if idx != 2:
                calls.append(call().class_name())
                if idx in list_idx:
                    calls.append(call().instruction_constraints())
            assert mock.mock_calls == calls, f"---> {idx}"
        reset_mocks()


@patch.object(ImplementedCommands, "questionnaire_command_name_list")
def test_command_structures(questionnaire_command_name_list):
    mocks = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        questionnaire_command_name_list.reset_mock()
        for item in mocks:
            item.reset_mock()

    tests = [
        ("Second", "Second is a questionnaire", None, None),
        ("Sixth", "Sixth is not a known command", None, None),
        ("First", None, "Parameters1", 0),
        ("Fourth", None, "Parameters4", 3),
    ]
    for class_name, exp_error, expected, rank in tests:
        mocks[0].return_value.class_name.side_effect = ["First", "First"]
        mocks[1].return_value.class_name.side_effect = ["Second", "Second"]
        mocks[2].return_value.class_name.side_effect = ["Third", "Third"]
        mocks[3].return_value.class_name.side_effect = ["Fourth", "Fourth"]
        mocks[4].return_value.class_name.side_effect = ["Fifth", "Fifth"]
        mocks[0].return_value.command_parameters.side_effect = ["Parameters1"]
        mocks[1].return_value.command_parameters.side_effect = ["Parameters2"]
        mocks[2].return_value.command_parameters.side_effect = ["Parameters3"]
        mocks[3].return_value.command_parameters.side_effect = ["Parameters4"]
        mocks[4].return_value.command_parameters.side_effect = ["Parameters5"]
        questionnaire_command_name_list.side_effect = ["Second", "Fifth"]

        tested, settings, aws_credentials, cache = helper_instance(mocks, True)
        if exp_error:
            with pytest.raises(ValueError, match=exp_error):
                tested.command_structures(class_name)
        else:
            result = tested.command_structures(class_name)
            assert result == expected

        calls = [call()]
        assert questionnaire_command_name_list.mock_calls == calls
        for idx, mock in enumerate(mocks):
            calls = [
                call(settings, cache, tested.identification),
                call().__bool__(),
                call().class_name(),
                call().is_available(),
            ]
            if idx != 2:
                calls.append(call().class_name())
            if idx == rank:
                calls.append(call().command_parameters())
            assert mock.mock_calls == calls, f"---> {idx}"
        reset_mocks()


@patch.object(ImplementedCommands, "questionnaire_command_name_list")
def test_command_schema(questionnaire_command_name_list):
    mocks = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        questionnaire_command_name_list.reset_mock()
        for item in mocks:
            item.reset_mock()

    tests = [
        ("Second", "Second is a questionnaire", None, None),
        ("Sixth", "Sixth is not a known command", None, None),
        ("First", None, "Parameters1", 0),
        ("Fourth", None, "Parameters4", 3),
    ]
    for class_name, exp_error, expected, rank in tests:
        mocks[0].return_value.class_name.side_effect = ["First", "First"]
        mocks[1].return_value.class_name.side_effect = ["Second", "Second"]
        mocks[2].return_value.class_name.side_effect = ["Third", "Third"]
        mocks[3].return_value.class_name.side_effect = ["Fourth", "Fourth"]
        mocks[4].return_value.class_name.side_effect = ["Fifth", "Fifth"]
        mocks[0].return_value.command_parameters_schemas.side_effect = ["Parameters1"]
        mocks[1].return_value.command_parameters_schemas.side_effect = ["Parameters2"]
        mocks[2].return_value.command_parameters_schemas.side_effect = ["Parameters3"]
        mocks[3].return_value.command_parameters_schemas.side_effect = ["Parameters4"]
        mocks[4].return_value.command_parameters_schemas.side_effect = ["Parameters5"]
        questionnaire_command_name_list.side_effect = ["Second", "Fifth"]

        tested, settings, aws_credentials, cache = helper_instance(mocks, True)
        if exp_error:
            with pytest.raises(ValueError, match=exp_error):
                tested.command_schema(class_name)
        else:
            result = tested.command_schema(class_name)
            assert result == expected

        calls = [call()]
        assert questionnaire_command_name_list.mock_calls == calls
        for idx, mock in enumerate(mocks):
            calls = [
                call(settings, cache, tested.identification),
                call().__bool__(),
                call().class_name(),
                call().is_available(),
            ]
            if idx != 2:
                calls.append(call().class_name())
            if idx == rank:
                calls.append(call().command_parameters_schemas())
            assert mock.mock_calls == calls, f"---> {idx}"
        reset_mocks()


@patch.object(AudioInterpreter, "combine_and_speaker_detection_double_step")
@patch.object(AudioInterpreter, "combine_and_speaker_detection_single_step")
@patch("hyperscribe.libraries.audio_interpreter.MemoryLog")
@patch("hyperscribe.libraries.audio_interpreter.Helper")
def test_combine_and_speaker_detection(
    helper,
    memory_log,
    combine_and_speaker_detection_single_step,
    combine_and_speaker_detection_double_step,
):
    def reset_mocks():
        helper.reset_mock()
        memory_log.reset_mock()
        combine_and_speaker_detection_single_step.reset_mock()
        combine_and_speaker_detection_double_step.reset_mock()

    tested, settings, aws_credentials, cache = helper_instance([], True)
    audio_bytes = b"chunkAudio"
    lines = [
        Line(speaker="speaker", text="last words 1", start=0.0, end=1.3),
        Line(speaker="speaker", text="last words 2", start=1.3, end=2.5),
        Line(speaker="speaker", text="last words 3", start=2.5, end=3.6),
    ]

    tests = [
        (
            True,
            "single",
            [call(helper.audio2texter.return_value, lines)],
            [],
            [
                call.audio2texter(settings, memory_log.instance.return_value),
                call.audio2texter().add_audio(b"chunkAudio", "mp3"),
                call.audio2texter().support_speaker_identification(),
            ],
            [call.instance(tested.identification, "audio2transcript", aws_credentials)],
        ),
        (
            False,
            "double",
            [],
            [call(helper.audio2texter.return_value, helper.chatter.return_value, lines)],
            [
                call.audio2texter(settings, memory_log.instance.return_value),
                call.audio2texter().add_audio(b"chunkAudio", "mp3"),
                call.audio2texter().support_speaker_identification(),
                call.chatter(settings, memory_log.instance.return_value, ModelSpec.COMPLEX),
            ],
            [
                call.instance(tested.identification, "audio2transcript", aws_credentials),
                call.instance(tested.identification, "speakerDetection", aws_credentials),
            ],
        ),
    ]
    for identification, expected, exp_call_single, exp_calls_double, exp_call_helper, exp_call_memory_log in tests:
        helper.audio2texter.return_value.support_speaker_identification.side_effect = [identification]
        combine_and_speaker_detection_single_step.side_effect = ["single"]
        combine_and_speaker_detection_double_step.side_effect = ["double"]

        result = tested.combine_and_speaker_detection(audio_bytes, lines)
        assert result == expected

        assert helper.mock_calls == exp_call_helper
        assert memory_log.mock_calls == exp_call_memory_log
        assert combine_and_speaker_detection_single_step.mock_calls == exp_call_single
        assert combine_and_speaker_detection_double_step.mock_calls == exp_calls_double
        reset_mocks()


def test_combine_and_speaker_detection_double_step():
    transcriber = MagicMock()
    detector = MagicMock()

    def reset_mocks():
        transcriber.reset_mock()
        detector.reset_mock()

    lines = [
        Line(speaker="speaker1", text="last words 1", start=0.0, end=1.3),
        Line(speaker="speaker2", text="last words 2", start=1.3, end=2.5),
        Line(speaker="speaker3", text="last words 3", start=2.5, end=3.6),
    ]
    content = [
        {"speaker": "speaker_0", "text": "text 0", "start": 0.0, "end": 3.6},
        {"speaker": "speaker_1", "text": "text 1", "start": 3.6, "end": 4.7},
        {"speaker": "speaker_0", "text": "text 3", "start": 4.7, "end": 5.3},
    ]
    system_prompt = [
        "The conversation is in the medical context, and related to a visit of a patient with a healthcare provider.",
        "",
        "A recording is parsed in realtime and the transcription is reported for each speaker.",
        "Your task is to identify the speakers of the provided transcription.",
        "",
    ]
    user_prompts = {
        "noTailedTranscript": [
            "",
            "Your task is to identify the role of the voices (patient, clinician, nurse, parents...) "
            "in the conversation, if there is only one voice, or just only silence, assume this is the clinician.",
            "",
            "```csv",
            "speaker,text,start,end\nspeaker_0,text 0,0.0,3.6\nspeaker_1,text 1,3.6,4.7\nspeaker_0,text 3,4.7,5.3",
            "```",
            "",
            "Present your findings in a CSV format within a Markdown code block:",
            "```csv",
            "speaker,text,start,end\n"
            "Patient/Clinician/Nurse/Parent...,"
            "the verbatim transcription as reported in the transcription,"
            "the start as reported in the transcription,"
            "the end as reported in the transcription",
            "```",
            "",
        ],
        "withTailedTranscript": [
            "The previous segment finished with:\n"
            "```csv\n"
            "speaker,text,start,end\n"
            "speaker1,last words 1,0.0,1.3\n"
            "speaker2,last words 2,1.3,2.5\n"
            "speaker3,last words 3,2.5,3.6\n"
            "```\n",
            "Your task is to identify the role of the voices (patient, clinician, nurse, parents...) "
            "in the conversation, if there is only one voice, or just only silence, assume this is the clinician.",
            "",
            "```csv",
            "speaker,text,start,end\nspeaker_0,text 0,0.0,3.6\nspeaker_1,text 1,3.6,4.7\nspeaker_0,text 3,4.7,5.3",
            "```",
            "",
            "Present your findings in a CSV format within a Markdown code block:",
            "```csv",
            "speaker,text,start,end\n"
            "Patient/Clinician/Nurse/Parent...,"
            "the verbatim transcription as reported in the transcription,"
            "the start as reported in the transcription,"
            "the end as reported in the transcription",
            "```",
            "",
        ],
    }
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "speaker": {"type": "string", "minLength": 1},
                "text": {"type": "string", "minLength": 1},
                "start": {"type": "number", "default": 0.0},
                "end": {"type": "number", "default": 0.0},
            },
            "required": ["speaker", "text"],
            "additionalProperties": False,
        },
        "minItems": 1,
    }

    tested, settings, aws_credentials, cache = helper_instance([], True)
    # all good
    # -- no previous transcript
    transcriber.chat.side_effect = [JsonExtract(has_error=False, error="", content=[content])]
    detector.chat.side_effect = [JsonExtract(has_error=False, error="", content=[["theResult"]])]
    result = tested.combine_and_speaker_detection_double_step(transcriber, detector, [])
    expected = JsonExtract(error="", has_error=False, content=["theResult"])
    assert result == expected

    calls = [call.chat([])]
    assert transcriber.mock_calls == calls
    calls = [
        call.set_system_prompt(system_prompt),
        call.set_user_prompt(user_prompts["noTailedTranscript"]),
        call.chat(None),
    ]
    assert detector.mock_calls == calls
    reset_mocks()
    # -- with previous transcript
    transcriber.chat.side_effect = [JsonExtract(has_error=False, error="", content=[content])]
    detector.chat.side_effect = [JsonExtract(has_error=False, error="", content=[["theResult"]])]
    result = tested.combine_and_speaker_detection_double_step(transcriber, detector, lines)
    expected = JsonExtract(error="", has_error=False, content=["theResult"])
    assert result == expected

    calls = [call.chat([])]
    assert transcriber.mock_calls == calls
    calls = [
        call.set_system_prompt(system_prompt),
        call.set_user_prompt(user_prompts["withTailedTranscript"]),
        call.chat(None),
    ]
    assert detector.mock_calls == calls
    reset_mocks()

    # error on the detector
    transcriber.chat.side_effect = [JsonExtract(has_error=False, error="", content=[content])]
    detector.chat.side_effect = [JsonExtract(has_error=True, error="the error", content=[["theResult"]])]
    result = tested.combine_and_speaker_detection_double_step(transcriber, detector, lines)
    expected = JsonExtract(has_error=True, error="the error", content=["theResult"])
    assert result == expected

    calls = [call.chat([])]
    assert transcriber.mock_calls == calls
    calls = [
        call.set_system_prompt(system_prompt),
        call.set_user_prompt(user_prompts["withTailedTranscript"]),
        call.chat(None),
    ]
    assert detector.mock_calls == calls
    reset_mocks()

    # error on the transcriber
    transcriber.chat.side_effect = [JsonExtract(has_error=True, error="the error", content=[content])]
    detector.chat.side_effect = []
    result = tested.combine_and_speaker_detection_double_step(transcriber, detector, lines)
    expected = JsonExtract(has_error=True, error="the error", content=[content])
    assert result == expected

    calls = [call.chat([])]
    assert transcriber.mock_calls == calls
    assert detector.mock_calls == []
    reset_mocks()


def test_combine_and_speaker_detection_single_step():
    detector = MagicMock()

    def reset_mocks():
        detector.reset_mock()

    system_prompt = [
        "The conversation is in the medical context, and related to a visit of a patient with a healthcare provider.",
        "",
        "Your task is to transcribe what was said with maximum accuracy, capturing ALL clinical"
        "information including patient symptoms, medical history, medications, treatment plans"
        "and provider recommendations.",
        "Ensure complete documentation of patient-reported concerns and clinician instructions,"
        "as missing clinical details significantly impact care quality.",
        "",
    ]
    user_prompt = {
        "noTailedTranscript": [
            "The recording takes place in a medical setting, specifically related to a patient's visit with a "
            "clinician.",
            "",
            "These audio files contain recordings of a single visit.",
            "There is no overlap between the segments, so they should be regarded as a continuous flow and "
            "analyzed at once.",
            "",
            "Your task is to:",
            "1. label each voice if multiple voices are present.",
            "2. transcribe each speaker's words with maximum accuracy.",
            "",
            "Present your findings in a JSON format within a Markdown code block:",
            "```json",
            '[\n {\n  "voice": "voice_1/voice_2/.../voice_N",\n  "text": "the verbatim transcription of what the '
            'speaker said, or [silence] for silences"\n }\n]',
            "```",
            "",
            "Then, review the discussion from the top and distinguish the role of the voices (patient, clinician, "
            "nurse, parents...) in the conversation, if there is only one voice, or just only silence, "
            "assume this is the clinician",
            "",
            "Present your findings in a JSON format within a Markdown code block:",
            "```json",
            '[\n {\n  "speaker": "Patient/Clinician/Nurse/...",\n  "voice": "voice_1/voice_2/.../voice_N"\n }\n]',
            "```",
            "",
        ],
        "withTailedTranscript": [
            "The recording takes place in a medical setting, specifically related to a patient's visit with a "
            "clinician.",
            "",
            "These audio files contain recordings of a single visit.",
            "There is no overlap between the segments, so they should be regarded as a continuous flow and "
            "analyzed at once.",
            "The previous segment finished with:"
            "\n```json"
            "\n["
            '\n {\n  "speaker": "speaker",\n  "text": "last words 1",\n  "start": 0.0,\n  "end": 1.3\n },'
            '\n {\n  "speaker": "speaker",\n  "text": "last words 2",\n  "start": 1.3,\n  "end": 2.5\n },'
            '\n {\n  "speaker": "speaker",\n  "text": "last words 3",\n  "start": 2.5,\n  "end": 3.6\n }'
            "\n]"
            "\n```"
            "\n",
            "Your task is to:",
            "1. label each voice if multiple voices are present.",
            "2. transcribe each speaker's words with maximum accuracy.",
            "",
            "Present your findings in a JSON format within a Markdown code block:",
            "```json",
            '[\n {\n  "voice": "voice_1/voice_2/.../voice_N",\n  "text": "the verbatim transcription of what the '
            'speaker said, or [silence] for silences"\n }\n]',
            "```",
            "",
            "Then, review the discussion from the top and distinguish the role of the voices (patient, clinician, "
            "nurse, parents...) in the conversation, if there is only one voice, or just only silence, "
            "assume this is the clinician",
            "",
            "Present your findings in a JSON format within a Markdown code block:",
            "```json",
            '[\n {\n  "speaker": "Patient/Clinician/Nurse/...",\n  "voice": "voice_1/voice_2/.../voice_N"\n }\n]',
            "```",
            "",
        ],
    }
    schemas = [
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "voice": {"type": "string", "pattern": "^voice_[1-9]\\d*$"},
                    "text": {"type": "string", "minLength": 1},
                    "start": {"type": "number", "default": 0.0},
                    "end": {"type": "number", "default": 0.0},
                },
                "required": ["voice", "text"],
                "additionalProperties": False,
            },
            "minItems": 1,
        },
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string", "minLength": 1},
                    "voice": {"type": "string", "pattern": "^voice_[1-9]\\d*$"},
                },
                "required": ["speaker", "voice"],
                "additionalProperties": False,
            },
            "minItems": 1,
            "uniqueItems": True,
        },
    ]
    discussion = [
        {"voice": "voice_3", "text": "the text A"},
        {"voice": "voice_2", "text": "the text B"},
        {"voice": "voice_1", "text": "the text C"},
        {"voice": "voice_2", "text": "the text D"},
        {"voice": "voice_2", "text": "the text E"},
        {"voice": "voice_1", "text": "the text F"},
        {"voice": "voice_2", "text": "the text G"},
        {"voice": "voice_3", "text": "the text H"},
    ]
    speakers = [
        {"voice": "voice_1", "speaker": "doctor"},
        {"voice": "voice_2", "speaker": "patient"},
        {"voice": "voice_3", "speaker": "nurse"},
    ]
    conversation = [
        {"speaker": "nurse", "text": "the text A"},
        {"speaker": "patient", "text": "the text B"},
        {"speaker": "doctor", "text": "the text C"},
        {"speaker": "patient", "text": "the text D"},
        {"speaker": "patient", "text": "the text E"},
        {"speaker": "doctor", "text": "the text F"},
        {"speaker": "patient", "text": "the text G"},
        {"speaker": "nurse", "text": "the text H"},
    ]
    lines = [
        Line(speaker="speaker", text="last words 1", start=0.0, end=1.3),
        Line(speaker="speaker", text="last words 2", start=1.3, end=2.5),
        Line(speaker="speaker", text="last words 3", start=2.5, end=3.6),
    ]

    tested, settings, aws_credentials, cache = helper_instance([], True)
    # no error
    # -- all JSON
    detector.chat.side_effect = [
        JsonExtract(error="theError", has_error=False, content=[discussion, speakers]),
    ]
    result = tested.combine_and_speaker_detection_single_step(detector, [])
    expected = JsonExtract(error="", has_error=False, content=conversation)
    assert result == expected
    calls = [
        call.set_system_prompt(system_prompt),
        call.set_user_prompt(user_prompt["noTailedTranscript"]),
        call.chat(schemas),
    ]
    assert detector.mock_calls == calls
    reset_mocks()
    # -- only one JSON
    detector.chat.side_effect = [JsonExtract(error="theError", has_error=False, content=[discussion])]
    result = tested.combine_and_speaker_detection_single_step(detector, [])
    expected = JsonExtract(error="partial response", has_error=True, content=[discussion])
    assert result == expected
    calls = [
        call.set_system_prompt(system_prompt),
        call.set_user_prompt(user_prompt["noTailedTranscript"]),
        call.chat(schemas),
    ]
    assert detector.mock_calls == calls
    reset_mocks()
    # -- with some previous transcript
    detector.chat.side_effect = [
        JsonExtract(error="theError", has_error=False, content=[discussion, speakers]),
    ]
    result = tested.combine_and_speaker_detection_single_step(detector, lines)
    expected = JsonExtract(error="", has_error=False, content=conversation)
    assert result == expected
    calls = [
        call.set_system_prompt(system_prompt),
        call.set_user_prompt(user_prompt["withTailedTranscript"]),
        call.chat(schemas),
    ]
    assert detector.mock_calls == calls
    reset_mocks()

    # with error
    detector.chat.side_effect = [
        JsonExtract(error="theError", has_error=True, content=[discussion, speakers]),
    ]
    result = tested.combine_and_speaker_detection_single_step(detector, [])
    expected = JsonExtract(error="theError", has_error=True, content=[discussion, speakers])
    assert result == expected
    calls = [
        call.set_system_prompt(system_prompt),
        call.set_user_prompt(user_prompt["noTailedTranscript"]),
        call.chat(schemas),
    ]
    assert detector.mock_calls == calls
    reset_mocks()


@patch.object(AudioInterpreter, "detect_instructions_per_section")
@patch.object(AudioInterpreter, "detect_instructions_flat")
@patch.object(AudioInterpreter, "common_instructions")
def test_detect_instructions(common_instructions, detect_instructions_flat, detect_instructions_per_section):
    def reset_mocks():
        common_instructions.reset_mock()
        detect_instructions_flat.reset_mock()
        detect_instructions_per_section.reset_mock()

    tested, settings, aws_credentials, cache = helper_instance([], False)

    lines = [
        Line(speaker="speaker", text="last words 1", start=0.0, end=1.3),
        Line(speaker="speaker", text="last words 2", start=1.3, end=2.5),
        Line(speaker="speaker", text="last words 3", start=2.5, end=3.6),
    ]
    known_instructions = [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="theInstruction1",
            information="",
            is_new=True,
            is_updated=False,
            previous_information="thePreviousInformation1",
        ),
        Instruction(
            uuid="uuid2",
            index=1,
            instruction="theInstruction2",
            information="",
            is_new=True,
            is_updated=False,
            previous_information="thePreviousInformation2",
        ),
        Instruction(
            uuid="uuid3",
            index=2,
            instruction="theInstruction3",
            information="",
            is_new=True,
            is_updated=False,
            previous_information="thePreviousInformation3",
        ),
        Instruction(
            uuid="uuid4",
            index=3,
            instruction="theInstruction4",
            information="",
            is_new=True,
            is_updated=False,
            previous_information="thePreviousInformation4",
        ),
        Instruction(
            uuid="uuid5",
            index=4,
            instruction="theInstruction5",
            information="",
            is_new=True,
            is_updated=False,
            previous_information="thePreviousInformation5",
        ),
    ]

    tests = [
        (
            known_instructions[:3],
            "resultFlat",
            [call(lines, known_instructions[:3], "theCommonInstructions", "allAtOnce")],
            [],
        ),
        (
            known_instructions[:4],
            "resultPerSection",
            [],
            [call(lines, known_instructions[:4], "theCommonInstructions")],
        ),
    ]
    for instructions, expected, exp_calls_flat, exp_calls_per_section in tests:
        common_instructions.side_effect = ["theCommonInstructions"]
        detect_instructions_flat.side_effect = ["resultFlat"]
        detect_instructions_per_section.side_effect = ["resultPerSection"]

        result = tested.detect_instructions(lines, instructions)

        assert result == expected
        calls = [call()]
        assert common_instructions.mock_calls == calls
        assert detect_instructions_flat.mock_calls == exp_calls_flat
        assert detect_instructions_per_section.mock_calls == exp_calls_per_section
        reset_mocks()


@patch.object(MemoryLog, "instance")
@patch.object(Helper, "chatter")
@patch.object(AudioInterpreter, "json_schema_sections")
def test_detect_sections(json_schema, chatter, memory_log):
    mocks = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        json_schema.reset_mock()
        chatter.reset_mock()
        memory_log.reset_mock()
        for item in mocks:
            item.reset_mock()
        mocks[0].class_name.side_effect = ["First", "First"]
        mocks[1].class_name.side_effect = ["Second", "Second"]
        mocks[2].class_name.side_effect = ["Third", "Third"]
        mocks[3].class_name.side_effect = ["Fourth", "Fourth"]
        mocks[4].class_name.side_effect = ["Fifth", "Fifth"]
        mocks[0].note_section.side_effect = ["Assessment"]
        mocks[1].note_section.side_effect = ["Plan"]
        mocks[2].note_section.side_effect = ["Plan"]
        mocks[3].note_section.side_effect = ["Assessment"]
        mocks[4].note_section.side_effect = ["Plan"]

    reset_mocks()
    discussion = [
        Line(speaker="personA", text="the text 1", start=0.0, end=1.3),
        Line(speaker="personB", text="the text 2", start=1.3, end=2.5),
        Line(speaker="personA", text="the text 3", start=2.5, end=3.6),
    ]
    system_prompt = [
        "The conversation is in the context of a clinical encounter between patient and licensed healthcare provider.",
        "The user will submit a segment of the transcript of the visit of a patient with the healthcare provider.",
        "Your task is to identify in the transcript whether it includes information related to any of these sections:",
        "```text",
        "* Assessment: any evaluations, diagnoses, or impressions made by the provider about the patient's condition "
        "- linked commands: ['First', 'Fourth'].",
        "* History: any past information about the patient's medical, family, or social history that is not part of "
        "the current reason for visit"
        " - linked commands: [].",
        "* Objective: any measurable or observable data such as physical exam findings, test results, or vital signs"
        " - linked commands: [].",
        "* Plan: any intended future actions such as treatments, follow-ups, prescriptions, or referrals"
        " - linked commands: ['Second', 'Third', 'Fifth'].",
        "* Procedures: any actions that have already been performed on the patient during the encounter"
        " (e.g. immunizations, suturing)"
        " - linked commands: [].",
        "* Subjective: any information describing the patient's current concerns, symptoms, "
        "or the stated reason for visit (e.g. 'follow-up visit', 'check-up', 'here for cough', 'experiencing pain'"
        " - linked commands: [].",
        "```",
        "",
        "Your response must be in a JSON Markdown block and validated with the schema:",
        "```json",
        '"theJsonSchema"',
        "```",
        "",
    ]
    user_prompt = [
        "Below is the most recent segment of the transcript of the visit of a patient with a healthcare provider.",
        "What are the sections present in the transcript?",
        "```csv",
        "speaker,text,start,end\npersonA,the text 1,0.0,1.3\npersonB,the text 2,1.3,2.5\npersonA,the text 3,2.5,3.6",
        "```",
        "",
    ]

    tested, settings, aws_credentials, cache = helper_instance(mocks, False)

    json_schema.side_effect = ["theJsonSchema"]
    chatter.return_value.single_conversation.side_effect = [
        [
            {
                "section": "SectionX",
                "transcript": [
                    {"speaker": "personA", "text": "the text 1"},
                    {"speaker": "personB", "text": "the text 2"},
                ],
            },
            {
                "section": "SectionY",
                "transcript": [],
            },
            {
                "section": "SectionZ",
                "transcript": [
                    {"speaker": "personA", "text": "the text 3"},
                ],
            },
        ]
    ]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.detect_sections(discussion, mocks)
    expected = [
        SectionWithTranscript(
            section="SectionX",
            transcript=[
                Line(speaker="personA", text="the text 1"),
                Line(speaker="personB", text="the text 2"),
            ],
        ),
        SectionWithTranscript(section="SectionY", transcript=[]),
        SectionWithTranscript(
            section="SectionZ",
            transcript=[
                Line(speaker="personA", text="the text 3"),
            ],
        ),
    ]
    assert result == expected
    calls = [call(["Assessment", "History", "Objective", "Plan", "Procedures", "Subjective"])]
    assert json_schema.mock_calls == calls
    calls = [
        call(settings, "MemoryLogInstance", ModelSpec.COMPLEX),
        call().single_conversation(system_prompt, user_prompt, ["theJsonSchema"], None),
    ]
    assert chatter.mock_calls == calls
    calls = [call(tested.identification, "transcript2sections", aws_credentials)]
    assert memory_log.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call(settings, cache, tested.identification),
            call().__bool__(),
            call().class_name(),
            call().is_available(),
        ]
        if idx != 2:
            calls.extend(
                [
                    call().class_name(),
                    call().class_name().__hash__(),
                ]
            )
        calls.extend(
            [
                call.note_section(),
                call.class_name(),
            ]
        )
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()


@patch.object(AudioInterpreter, "detect_instructions_flat")
@patch.object(AudioInterpreter, "detect_sections")
def test_detect_instructions_per_section(detect_sections, detect_instructions_flat):
    mocks = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        detect_sections.reset_mock()
        detect_instructions_flat.reset_mock()
        for item in mocks:
            item.reset_mock()
        mocks[0].class_name.side_effect = ["First", "First"]
        mocks[1].class_name.side_effect = ["Second", "Second"]
        mocks[2].class_name.side_effect = ["Third", "Third"]
        mocks[3].class_name.side_effect = ["Fourth", "Fourth"]
        mocks[4].class_name.side_effect = ["Fifth", "Fifth"]
        mocks[0].note_section.return_value = "SectionX"
        mocks[1].note_section.return_value = "SectionZ"
        mocks[2].note_section.return_value = "SectionZ"
        mocks[3].note_section.return_value = "SectionX"
        mocks[4].note_section.return_value = "SectionY"

    reset_mocks()
    discussion = [
        Line(speaker="personA", text="the text 1"),
        Line(speaker="personB", text="the text 2"),
        Line(speaker="personA", text="the text 3"),
    ]
    transcript_sections = [
        SectionWithTranscript(
            section="SectionX",
            transcript=[
                Line(speaker="personA", text="the text 1"),
                Line(speaker="personB", text="the text 2"),
            ],
        ),
        SectionWithTranscript(
            section="SectionZ",
            transcript=[
                Line(speaker="personA", text="the text 3"),
            ],
        ),
    ]
    known_instructions = [
        Instruction(
            index=0,
            information="theInformation0",
            instruction="First",
            is_new=False,
            is_updated=False,
            uuid="uuidA",
            previous_information="thePreviousInformation1",
        ),
        Instruction(
            index=1,
            information="theInformation5",
            instruction="Fifth",
            is_new=False,
            is_updated=False,
            uuid="uuidA",
            previous_information="thePreviousInformation5",
        ),
    ]
    detected = [
        [
            Instruction(
                uuid="uuidA",
                index=0,
                instruction="First",
                information="theInformation1",
                is_new=True,
                is_updated=False,
                previous_information="",
            ),
            Instruction(
                uuid="uuidB",
                index=1,
                instruction="Second",
                information="theInformation2",
                is_new=True,
                is_updated=False,
                previous_information="",
            ),
        ],
        [
            Instruction(
                uuid="uuidA",
                index=0,
                instruction="Third",
                information="theInformation3",
                is_new=True,
                is_updated=False,
                previous_information="",
            ),
        ],
    ]

    tested, settings, aws_credentials, cache = helper_instance(mocks, False)

    # no known instruction
    detect_sections.side_effect = [transcript_sections]
    detect_instructions_flat.side_effect = detected

    result = tested.detect_instructions_per_section(discussion, [], mocks)
    expected = [
        Instruction(
            uuid="uuidA",
            index=0,
            instruction="First",
            information="theInformation1",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="uuidB",
            index=1,
            instruction="Second",
            information="theInformation2",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="instruction-002",
            index=2,
            instruction="Third",
            information="theInformation3",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
    ]
    assert result == expected

    calls = [call(discussion, mocks)]
    assert detect_sections.mock_calls == calls
    calls = [
        call(
            [Line(speaker="personA", text="the text 1"), Line(speaker="personB", text="the text 2")],
            [],
            [mocks[0], mocks[3]],
            "SectionX",
        ),
        call(
            [Line(speaker="personA", text="the text 3")],
            [],
            [mocks[1], mocks[2]],
            "SectionZ",
        ),
    ]
    assert detect_instructions_flat.mock_calls == calls
    reset_mocks()

    # with known instructions
    detect_sections.side_effect = [transcript_sections]
    detect_instructions_flat.side_effect = detected

    result = tested.detect_instructions_per_section(discussion, known_instructions, mocks)
    expected = [
        Instruction(
            uuid="uuidA",
            index=0,
            information="theInformation5",
            instruction="Fifth",
            is_new=False,
            is_updated=False,
            previous_information="thePreviousInformation5",
        ),
        Instruction(
            uuid="instruction-001",
            index=1,
            information="theInformation1",
            instruction="First",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="uuidB",
            index=2,
            information="theInformation2",
            instruction="Second",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="instruction-002",
            index=3,
            information="theInformation3",
            instruction="Third",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
    ]
    assert result == expected

    calls = [call(discussion, mocks)]
    assert detect_sections.mock_calls == calls
    calls = [
        call(
            [Line(speaker="personA", text="the text 1"), Line(speaker="personB", text="the text 2")],
            [known_instructions[0]],
            [mocks[0], mocks[3]],
            "SectionX",
        ),
        call(
            [Line(speaker="personA", text="the text 3")],
            [],
            [mocks[1], mocks[2]],
            "SectionZ",
        ),
    ]
    assert detect_instructions_flat.mock_calls == calls
    reset_mocks()


@patch.object(MemoryLog, "instance")
@patch.object(Helper, "chatter")
@patch.object(AudioInterpreter, "instruction_constraints")
def test_detect_instructions_flat(instruction_constraints, chatter, memory_log):
    mocks = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        instruction_constraints.reset_mock()
        chatter.reset_mock()
        memory_log.reset_mock()
        for item in mocks:
            item.reset_mock()
        mocks[0].class_name.side_effect = ["First", "First"]
        mocks[1].class_name.side_effect = ["Second", "Second"]
        mocks[2].class_name.side_effect = ["Third", "Third"]
        mocks[3].class_name.side_effect = ["Fourth", "Fourth"]
        mocks[4].class_name.side_effect = ["Fifth", "Fifth"]
        mocks[0].instruction_description.side_effect = ["Description1"]
        mocks[1].instruction_description.side_effect = ["Description2"]
        mocks[2].instruction_description.side_effect = ["Description3"]
        mocks[3].instruction_description.side_effect = ["Description4"]
        mocks[4].instruction_description.side_effect = ["Description5"]

    system_prompt = [
        "The conversation is in the context of a clinical encounter between patient and licensed healthcare provider.",
        "The user will submit the transcript of the visit of a patient with the healthcare provider.",
        "The user needs to extract and store the relevant information in their software using structured "
        "commands as described below.",
        "Your task is to help the user by identifying the relevant instructions and their linked information, "
        "regardless of their location in the transcript. Prioritize accuracy and completeness, as omitting"
        "significant clinical information compromises patient care.",
        "Prioritize and reward comprehensive capture of all health-related discussion. Focus on"
        "accurately documenting clinical information while naturally filtering non-medical content."
        "",
        "IMPORTANT: Carefully track attribution of all health information. Before documenting any symptom, "
        "condition, test result, or medical history, verify WHO it belongs to by examining pronouns, "
        "possessive markers, and context. Information about other people (family members, friends, "
        "coworkers, etc.) must NOT be attributed to the patient. When in doubt about attribution, "
        "review the surrounding context to confirm the subject of the health information.",
        "",
        "The instructions are limited to the following:",
        "```csv",
        "instruction,description",
        "First,Description1\nSecond,Description2\nThird,Description3\nFourth,Description4\nFifth,Description5",
        "```",
        "",
        "Your response must be in a CSV Markdown block like:",
        "```csv",
        "uuid,index,instruction,information,is_new,is_updated\n"
        "a unique identifier in this discussion,"
        "the 0-based appearance order of the instruction in this discussion,"
        "one of: 'First/Second/Third/Fourth/Fifth',"
        "all relevant information extracted from the discussion explaining and/or defining the instruction,"
        "the instruction is new to the discussion,"
        "the instruction is an update of an instruction previously identified in the discussion",
        "```",
        "",
    ]
    user_prompts = {
        "noKnownInstructions": [
            "Below is the most recent segment of the transcript of the visit of a patient with a healthcare provider.",
            "What are the instructions I need to add to my software to document the visit correctly?",
            "```csv",
            "speaker,text,start,end\n"
            "personA,the text 1,0.0,1.3\n"
            "personB,the text 2,1.3,2.5\n"
            "personA,the text 3,2.5,3.6",
            "```",
            "",
            "List all possible instructions as a text, and then, in a CSV markdown block, "
            "respond with the found instructions as requested",
            "",
        ],
        "withKnownInstructions": [
            "Below is the most recent segment of the transcript of the visit of a patient with a healthcare provider.",
            "What are the instructions I need to add to my software to document the visit correctly?",
            "```csv",
            "speaker,text,start,end\n"
            "personA,the text 1,0.0,1.3\n"
            "personB,the text 2,1.3,2.5\n"
            "personA,the text 3,2.5,3.6",
            "```",
            "",
            "List all possible instructions as a text, and then, in a CSV markdown block, "
            "respond with the found instructions as requested",
            "",
            "From among all previous segments of the transcript, the following instructions were identified:",
            "```csv",
            "uuid,index,instruction,information,is_new,is_updated\n"
            "theUuid1,0,theInstruction1,the information 1,True,False\n"
            "theUuid2,1,theInstruction2,the information 2,False,True",
            "```",
            "If there is information in the transcript that is relevant to a prior instruction deemed updatable, "
            "then you can use it to update the contents of the instruction rather than creating a new one.",
            "But, in all cases, you must provide each and every new, updated and unchanged instructions.",
        ],
        "constraints": [
            "Review your response and be sure to follow these constraints:",
            " * theConstraint1",
            " * theConstraint2",
            "",
            "First, review carefully your response against the constraints.",
            "Then, return the original CSV if it doesn't infringe the constraints.",
            "Or provide a corrected version to follow the constraints if needed.",
            "",
        ],
        "withMissingInstructions": [
            "Your response did not include the instructions identified before.",
            "Correct your response to provide, in the requested format, ALL new, updated and unchanged instructions.",
        ],
    }

    discussion = [
        Line(speaker="personA", text="the text 1", start=0.0, end=1.3),
        Line(speaker="personB", text="the text 2", start=1.3, end=2.5),
        Line(speaker="personA", text="the text 3", start=2.5, end=3.6),
    ]
    known_instructions = [
        Instruction(
            uuid="theUuid1",
            index=0,
            instruction="theInstruction1",
            information="the information 1",
            is_new=True,
            is_updated=False,
            previous_information="thePreviousInformation1",
        ),
        Instruction(
            uuid="theUuid2",
            index=1,
            instruction="theInstruction2",
            information="the information 2",
            is_new=False,
            is_updated=True,
            previous_information="thePreviousInformation2",
        ),
    ]
    instruction_constraints_calls = [
        call(
            [
                Instruction(
                    uuid="theUuid1",
                    index=0,
                    instruction="theInstruction1",
                    information="theInformation1",
                    is_new=True,
                    is_updated=False,
                    previous_information="",
                ),
                Instruction(
                    uuid="theUuid2",
                    index=1,
                    instruction="theInstruction2",
                    information="theInformation2",
                    is_new=True,
                    is_updated=False,
                    previous_information="",
                ),
                Instruction(
                    uuid="theUuid3",
                    index=2,
                    instruction="theInstruction3",
                    information="theInformation3",
                    is_new=True,
                    is_updated=False,
                    previous_information="",
                ),
            ]
        ),
    ]
    reset_mocks()

    tested, settings, aws_credentials, cache = helper_instance(mocks, False)
    # -- no known instruction
    # -- -- no error
    instruction_constraints.side_effect = [["theConstraint1", "theConstraint2"]]
    chatter.return_value.chat.side_effect = [
        JsonExtract(
            has_error=False,
            error="",
            content=[
                [
                    "uuid,index,instruction,information,is_new,is_updated",
                    "theUuid1,0,theInstruction1,theInformation1,true,false",
                    "theUuid2,1,theInstruction2,theInformation2,true,false",
                    "theUuid3,2,theInstruction3,theInformation3,true,false",
                ]
            ],
        ),
        JsonExtract(
            has_error=False,
            error="",
            content=[
                [
                    "uuid,index,instruction,information,is_new,is_updated",
                    "theUuid1,0,theInstruction1,theInformation1,true,false",
                    "theUuid2,1,theInstruction2,theInformation4,true,false",
                ]
            ],
        ),
    ]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.detect_instructions_flat(discussion, [], mocks, "theSection")
    expected = [
        Instruction(
            uuid="theUuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="theUuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation4",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
    ]
    assert result == expected
    assert instruction_constraints.mock_calls == instruction_constraints_calls
    calls = [
        call(settings, "MemoryLogInstance", ModelSpec.COMPLEX),
        call().set_system_prompt(system_prompt),
        call().set_user_prompt(user_prompts["noKnownInstructions"]),
        call().chat(None),
        call().set_model_prompt(
            [
                "```csv",
                "uuid,index,instruction,information,is_new,is_updated\n"
                "theUuid1,0,theInstruction1,theInformation1,True,False\n"
                "theUuid2,1,theInstruction2,theInformation2,True,False\n"
                "theUuid3,2,theInstruction3,theInformation3,True,False",
                "```",
            ]
        ),
        call().set_user_prompt(user_prompts["constraints"]),
        call().chat(None),
    ]
    assert chatter.mock_calls == calls
    calls = [call(tested.identification, "transcript2instructions:theSection", aws_credentials)]
    assert memory_log.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call(settings, cache, tested.identification),
            call().__bool__(),
            call().class_name(),
            call().is_available(),
        ]
        if idx != 2:
            calls.append(call().class_name())
            calls.append(call().class_name().__hash__())

        calls.append(call.class_name())
        calls.append(call.instruction_description())
        calls.append(call.class_name())
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()
    # -- -- error on second call
    instruction_constraints.side_effect = [["theConstraint1", "theConstraint2"]]
    chatter.return_value.chat.side_effect = [
        JsonExtract(
            has_error=False,
            error="",
            content=[
                [
                    "uuid,index,instruction,information,is_new,is_updated",
                    "theUuid1,0,theInstruction1,theInformation1,true,false",
                    "theUuid2,1,theInstruction2,theInformation2,true,false",
                    "theUuid3,2,theInstruction3,theInformation3,true,false",
                ]
            ],
        ),
        JsonExtract(has_error=True, error="Some Error", content=[]),
    ]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.detect_instructions_flat(discussion, [], mocks, "theSection")
    expected = []
    assert result == expected
    assert instruction_constraints.mock_calls == instruction_constraints_calls
    calls = [
        call(settings, "MemoryLogInstance", ModelSpec.COMPLEX),
        call().set_system_prompt(system_prompt),
        call().set_user_prompt(user_prompts["noKnownInstructions"]),
        call().chat(None),
        call().set_model_prompt(
            [
                "```csv",
                "uuid,index,instruction,information,is_new,is_updated\n"
                "theUuid1,0,theInstruction1,theInformation1,True,False\n"
                "theUuid2,1,theInstruction2,theInformation2,True,False\n"
                "theUuid3,2,theInstruction3,theInformation3,True,False",
                "```",
            ]
        ),
        call().set_user_prompt(user_prompts["constraints"]),
        call().chat(None),
    ]
    assert chatter.mock_calls == calls
    calls = [call(tested.identification, "transcript2instructions:theSection", aws_credentials)]
    assert memory_log.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call.class_name(),
            call.instruction_description(),
            call.class_name(),
        ]
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()
    # -- -- error on first call
    instruction_constraints.side_effect = [["theConstraint1", "theConstraint2"]]
    chatter.return_value.chat.side_effect = [
        JsonExtract(has_error=True, error="Some Error", content=[]),
    ]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.detect_instructions_flat(discussion, [], mocks, "theSection")
    expected = []
    assert result == expected
    assert instruction_constraints.mock_calls == []
    calls = [
        call(settings, "MemoryLogInstance", ModelSpec.COMPLEX),
        call().set_system_prompt(system_prompt),
        call().set_user_prompt(user_prompts["noKnownInstructions"]),
        call().chat(None),
    ]
    assert chatter.mock_calls == calls
    calls = [call(tested.identification, "transcript2instructions:theSection", aws_credentials)]
    assert memory_log.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call.class_name(),
            call.instruction_description(),
            call.class_name(),
        ]
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()

    # -- no known instruction + no constraint
    instruction_constraints.side_effect = [[]]
    chatter.return_value.chat.side_effect = [
        JsonExtract(
            has_error=False,
            error="",
            content=[
                [
                    "uuid,index,instruction,information,is_new,is_updated",
                    "theUuid1,0,theInstruction1,theInformation1,true,false",
                    "theUuid2,1,theInstruction2,theInformation2,true,false",
                    "theUuid3,2,theInstruction3,theInformation3,true,false",
                ]
            ],
        ),
    ]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.detect_instructions_flat(discussion, [], mocks, "theSection")
    expected = [
        Instruction(
            uuid="theUuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="theUuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="theUuid3",
            index=2,
            instruction="theInstruction3",
            information="theInformation3",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
    ]
    assert result == expected
    assert instruction_constraints.mock_calls == instruction_constraints_calls
    calls = [
        call(settings, "MemoryLogInstance", ModelSpec.COMPLEX),
        call().set_system_prompt(system_prompt),
        call().set_user_prompt(user_prompts["noKnownInstructions"]),
        call().chat(None),
    ]
    assert chatter.mock_calls == calls
    calls = [call(tested.identification, "transcript2instructions:theSection", aws_credentials)]
    assert memory_log.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call.class_name(),
            call.instruction_description(),
            call.class_name(),
        ]
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()

    # -- with known instructions
    # -- -- all instructions repeated
    instruction_constraints.side_effect = [["theConstraint1", "theConstraint2"]]
    chatter.return_value.chat.side_effect = [
        JsonExtract(
            has_error=False,
            error="",
            content=[
                [
                    "uuid,index,instruction,information,is_new,is_updated",
                    "theUuid1,0,theInstruction1,theInformation1,true,false",
                    "theUuid2,1,theInstruction2,theInformation2,true,false",
                    "theUuid3,2,theInstruction3,theInformation3,true,false",
                ]
            ],
        ),
        JsonExtract(
            has_error=False,
            error="",
            content=[
                [
                    "uuid,index,instruction,information,is_new,is_updated",
                    "theUuid1,0,theInstruction1,theInformation1,false,false",
                    "theUuid2,1,theInstruction2,theInformation2,false,false",
                    "theUuid3,2,theInstruction3,changedInstruction3,false,true",
                ]
            ],
        ),
    ]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.detect_instructions_flat(discussion, known_instructions, mocks, "theSection")
    expected = [
        Instruction(
            uuid="theUuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="theUuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=False,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="theUuid3",
            index=2,
            instruction="theInstruction3",
            information="changedInstruction3",
            is_new=False,
            is_updated=True,
            previous_information="",
        ),
    ]
    assert result == expected
    assert instruction_constraints.mock_calls == instruction_constraints_calls
    calls = [
        call(settings, "MemoryLogInstance", ModelSpec.COMPLEX),
        call().set_system_prompt(system_prompt),
        call().set_user_prompt(user_prompts["withKnownInstructions"]),
        call().chat(None),
        call().set_model_prompt(
            [
                "```csv",
                "uuid,index,instruction,information,is_new,is_updated\n"
                "theUuid1,0,theInstruction1,theInformation1,True,False\n"
                "theUuid2,1,theInstruction2,theInformation2,True,False\n"
                "theUuid3,2,theInstruction3,theInformation3,True,False",
                "```",
            ]
        ),
        call().set_user_prompt(user_prompts["constraints"]),
        call().chat(None),
    ]
    assert chatter.mock_calls == calls
    calls = [call(tested.identification, "transcript2instructions:theSection", aws_credentials)]
    assert memory_log.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call.class_name(),
            call.instruction_description(),
            call.class_name(),
        ]
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()
    # -- -- forgotten instructions (no constraints)
    instruction_constraints.side_effect = [[]]
    chatter.return_value.chat.side_effect = [
        JsonExtract(
            has_error=False,
            error="",
            content=[
                [
                    "uuid,index,instruction,information,is_new,is_updated",
                    # "theUuid1,0,theInstruction1,theInformation1,true,false", <-- forgotten instruction
                    "theUuid2,1,theInstruction2,theInformation2,false,false",  # <-- not new, nor updated
                    "theUuid3,2,theInstruction3,theInformation3a,false,true",
                    "theUuid4,3,theInstruction4,theInformation4,true,false",
                ]
            ],
        ),
    ]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.detect_instructions_flat(discussion, known_instructions, mocks, "theSection")
    expected = [
        Instruction(
            uuid="theUuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=False,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="theUuid3",
            index=2,
            instruction="theInstruction3",
            information="theInformation3a",
            is_new=False,
            is_updated=True,
            previous_information="",
        ),
        Instruction(
            uuid="theUuid4",
            index=3,
            instruction="theInstruction4",
            information="theInformation4",
            is_new=True,
            is_updated=False,
            previous_information="",
        ),
        Instruction(
            uuid="theUuid1",
            index=0,
            instruction="theInstruction1",
            information="the information 1",
            is_new=False,
            is_updated=False,
            previous_information="thePreviousInformation1",
        ),
    ]
    assert result == expected
    calls = [
        call(
            [
                Instruction(
                    uuid="theUuid3",
                    index=2,
                    instruction="theInstruction3",
                    information="theInformation3a",
                    is_new=False,
                    is_updated=True,
                    previous_information="",
                ),
                Instruction(
                    uuid="theUuid4",
                    index=3,
                    instruction="theInstruction4",
                    information="theInformation4",
                    is_new=True,
                    is_updated=False,
                    previous_information="",
                ),
            ],
        ),
    ]
    assert instruction_constraints.mock_calls == calls
    calls = [
        call(settings, "MemoryLogInstance", ModelSpec.COMPLEX),
        call().set_system_prompt(system_prompt),
        call().set_user_prompt(user_prompts["withKnownInstructions"]),
        call().chat(None),
    ]
    assert chatter.mock_calls == calls
    calls = [call(tested.identification, "transcript2instructions:theSection", aws_credentials)]
    assert memory_log.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call.class_name(),
            call.instruction_description(),
            call.class_name(),
        ]
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()


@patch("hyperscribe.libraries.audio_interpreter.datetime", wraps=datetime)
@patch("hyperscribe.libraries.audio_interpreter.ProgressDisplay")
@patch("hyperscribe.libraries.audio_interpreter.MemoryLog")
@patch.object(Helper, "chatter")
@patch.object(AudioInterpreter, "command_schema")
@patch.object(AudioInterpreter, "command_structures")
def test_create_sdk_command_parameters(
    command_structures,
    command_schema,
    chatter,
    memory_log,
    progress,
    mock_datetime,
):
    def reset_mocks():
        command_structures.reset_mock()
        command_schema.reset_mock()
        chatter.reset_mock()
        memory_log.reset_mock()
        progress.reset_mock()
        mock_datetime.reset_mock()

    instruction = Instruction(
        uuid="theUuid",
        index=3,
        instruction="Second",
        information="theInformation",
        is_new=False,
        is_updated=True,
        previous_information="thePreviousInformation",
    )
    system_prompt = [
        "The conversation is in the context of a clinical encounter between patient (thePatientDemographic) and "
        "licensed healthcare provider.",
        "During the encounter, the user has identified instructions with key information to record in its software.",
        "The user will submit an instruction and the linked information grounded in the transcript, as well "
        "as the structure of the associated command.",
        "Your task is to help the user by writing correctly detailed data for the structured command.",
        "Unless explicitly instructed otherwise by the user for a specific command, "
        "you must restrict your response to information explicitly present in the transcript "
        "or prior instructions.",
        "",
        "Your response has to be a JSON Markdown block encapsulating the filled structure.",
        "",
        "Please, note that now is 2025-02-04T07:48:21+00:00.",
    ]
    user_prompts = {
        "commandWithSchema": [
            "Based on the text:",
            "```text",
            "theInformation",
            "```",
            "",
            "Your task is to replace the values of the JSON object with the relevant information:",
            "```json",
            '[\n "theStructure"\n]',
            "```",
            "",
            "The explanations and constraints about the fields are defined in this JSON Schema:",
            "```json",
            '"theSchema"',
            "```",
            "",
            "Be sure your response validates the JSON Schema.",
            "",
            "Before finalizing, verify completeness by checking that patient concerns are accurately captured "
            "and any provider recommendations, follow-up plans, and instructions are complete, specific "
            "and are accurate given the conversation.",
            "",
        ],
        "commandNoSchema": [
            "Based on the text:",
            "```text",
            "theInformation",
            "```",
            "",
            "Your task is to replace the values of the JSON object with the relevant information:",
            "```json",
            '[\n "theStructure"\n]',
            "```",
            "",
            "The explanations and constraints about the fields are defined in this JSON Schema:",
            "```json",
            "{\n "
            '"$schema": "http://json-schema.org/draft-07/schema#",\n '
            '"type": "array",\n '
            '"items": {\n  "type": "object",\n  "additionalProperties": true\n }\n}',
            "```",
            "",
            "Be sure your response validates the JSON Schema.",
            "",
            "Before finalizing, verify completeness by checking that patient concerns are accurately captured "
            "and any provider recommendations, follow-up plans, and instructions are complete, specific "
            "and are accurate given the conversation.",
            "",
        ],
    }
    schemas = [
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {"type": "object", "additionalProperties": True},
        },
    ]
    reset_mocks()

    tested, settings, aws_credentials, cache = helper_instance([], True)
    # with response
    # -- with schema
    command_structures.side_effect = ["theStructure"]
    command_schema.side_effect = [["theSchema"]]
    mock_datetime.now.side_effect = [datetime(2025, 2, 4, 7, 48, 21, tzinfo=timezone.utc)]
    chatter.return_value.single_conversation.side_effect = [[{"key": "response1"}, {"key": "response2"}]]
    result = tested.create_sdk_command_parameters(instruction)
    expected = InstructionWithParameters(
        uuid="theUuid",
        index=3,
        instruction="Second",
        information="theInformation",
        is_new=False,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "response1"},
    )
    assert result == expected

    calls = [call("Second")]
    assert command_structures.mock_calls == calls
    assert command_schema.mock_calls == calls
    calls = [
        call(settings, memory_log.instance.return_value, ModelSpec.SIMPLER),
        call().single_conversation(system_prompt, user_prompts["commandWithSchema"], ["theSchema"], instruction),
    ]
    assert chatter.mock_calls == calls
    calls = [call.instance(tested.identification, "Second_theUuid_instruction2parameters", aws_credentials)]
    assert memory_log.mock_calls == calls
    calls = [
        call.send_to_user(
            tested.identification,
            settings,
            [ProgressMessage(message="parameters identified for Second", section="events:4")],
        )
    ]
    assert progress.mock_calls == calls
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    reset_mocks()
    # -- with NO schema
    command_structures.side_effect = ["theStructure"]
    command_schema.side_effect = [[]]
    mock_datetime.now.side_effect = [datetime(2025, 2, 4, 7, 48, 21, tzinfo=timezone.utc)]
    chatter.return_value.single_conversation.side_effect = [[{"key": "response1"}, {"key": "response2"}]]
    result = tested.create_sdk_command_parameters(instruction)
    expected = InstructionWithParameters(
        uuid="theUuid",
        index=3,
        instruction="Second",
        information="theInformation",
        is_new=False,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "response1"},
    )
    assert result == expected

    calls = [call("Second")]
    assert command_structures.mock_calls == calls
    assert command_schema.mock_calls == calls
    calls = [
        call(settings, memory_log.instance.return_value, ModelSpec.SIMPLER),
        call().single_conversation(system_prompt, user_prompts["commandNoSchema"], schemas, instruction),
    ]
    assert chatter.mock_calls == calls
    calls = [call.instance(tested.identification, "Second_theUuid_instruction2parameters", aws_credentials)]
    assert memory_log.mock_calls == calls
    calls = [
        call.send_to_user(
            tested.identification,
            settings,
            [ProgressMessage(message="parameters identified for Second", section="events:4")],
        )
    ]
    assert progress.mock_calls == calls
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    reset_mocks()

    # without response
    command_structures.side_effect = ["theStructure"]
    command_schema.side_effect = [["theSchema"]]

    mock_datetime.now.side_effect = [datetime(2025, 2, 4, 7, 48, 21, tzinfo=timezone.utc)]
    chatter.return_value.single_conversation.side_effect = [[]]
    result = tested.create_sdk_command_parameters(instruction)
    assert result is None

    calls = [call("Second")]
    assert command_structures.mock_calls == calls
    assert command_schema.mock_calls == calls
    calls = [
        call(settings, memory_log.instance.return_value, ModelSpec.SIMPLER),
        call().single_conversation(system_prompt, user_prompts["commandWithSchema"], ["theSchema"], instruction),
    ]
    assert chatter.mock_calls == calls
    calls = [call.instance(tested.identification, "Second_theUuid_instruction2parameters", aws_credentials)]
    assert memory_log.mock_calls == calls
    calls = []
    assert progress.mock_calls == calls
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.libraries.audio_interpreter.ProgressDisplay")
@patch("hyperscribe.libraries.audio_interpreter.MemoryLog")
@patch.object(Helper, "chatter")
def test_create_sdk_command_from(chatter, memory_log, progress):
    mocks = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    commands = [
        MockClass(summary="theSummary1", is_updated=True),
        MockClass(summary=""),  # <--- no summary
        MockClass(summary="theSummary3", is_updated=False),
        MockClass(summary="theSummary4", is_updated=False),
    ]

    def reset_mocks():
        chatter.reset_mock()
        memory_log.reset_mock()
        progress.reset_mock()
        for item in mocks:
            item.reset_mock()
        mocks[0].return_value.class_name.side_effect = ["First", "First"]
        mocks[1].return_value.class_name.side_effect = ["Second", "Second"]
        mocks[2].return_value.class_name.side_effect = ["Third", "Third"]
        mocks[3].return_value.class_name.side_effect = ["Fourth", "Fourth"]
        mocks[4].return_value.class_name.side_effect = ["Fifth", "Fifth"]
        mocks[0].return_value.command_from_json_with_summary.side_effect = [commands[0]]
        mocks[1].return_value.command_from_json_with_summary.side_effect = [commands[1]]
        mocks[2].return_value.command_from_json_with_summary.side_effect = [commands[2]]
        mocks[3].return_value.command_from_json_with_summary.side_effect = [commands[3]]
        mocks[4].return_value.command_from_json_with_summary.side_effect = [None]

    reset_mocks()

    tests = [
        (
            "First",
            0,
            commands[0],
            "First_theUuid_parameters2command",
            [
                ProgressMessage(message="command generated for First", section="events:4"),
                ProgressMessage(message="theSummary1", section="events:2"),
            ],
        ),
        (
            "Second",
            1,
            commands[1],
            "Second_theUuid_parameters2command",
            [ProgressMessage(message="command generated for Second", section="events:4")],
        ),
        ("Third", 5, None, None, None),
        (
            "Fourth",
            3,
            commands[3],
            "Fourth_theUuid_parameters2command",
            [
                ProgressMessage(message="command generated for Fourth", section="events:4"),
                ProgressMessage(message="theSummary4", section="events:1"),
            ],
        ),
        ("Fifth", 4, None, "Fifth_theUuid_parameters2command", None),
    ]
    for name, rank, expected, exp_log_label, exp_log_ui in tests:
        chatter.side_effect = ["LlmBaseInstance"]
        instruction = InstructionWithParameters(
            uuid="theUuid",
            index=7,
            instruction=name,
            information="theInformation",
            is_new=False,
            is_updated=True,
            previous_information="thePreviousInformation",
            parameters={"theKey": "theValue"},
        )
        tested, settings, aws_credentials, cache = helper_instance(mocks, True)
        result = tested.create_sdk_command_from(instruction)
        assert result == expected

        calls = [call(settings, memory_log.instance.return_value, ModelSpec.SIMPLER)] if exp_log_label else []
        assert chatter.mock_calls == calls
        calls = [call.instance(tested.identification, exp_log_label, aws_credentials)] if exp_log_label else []
        assert memory_log.mock_calls == calls
        calls = []
        if exp_log_ui:
            calls = [call.send_to_user(tested.identification, settings, exp_log_ui)]
        assert progress.mock_calls == calls
        for idx, mock in enumerate(mocks):
            calls = [
                call(settings, cache, tested.identification),
                call().__bool__(),
                call().class_name(),
                call().is_available(),
            ]
            if idx != 2:
                calls.extend([call().class_name()])
            if idx == rank and idx != 2:
                calls.extend([call().command_from_json_with_summary(instruction, "LlmBaseInstance")])
            assert mock.mock_calls == calls, f"---> {idx}"
        reset_mocks()


@patch.object(MemoryLog, "instance")
@patch.object(Helper, "chatter")
def test_update_questionnaire(chatter, memory_log):
    command_mocks = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
    questionnaire_mocks = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        chatter.reset_mock()
        memory_log.reset_mock()
        for item in command_mocks:
            item.reset_mock()
            item.return_value.__class__ = BaseQuestionnaire
        for item in questionnaire_mocks:
            item.reset_mock()

        command_mocks[0].return_value.class_name.side_effect = ["First", "First"]
        command_mocks[1].return_value.class_name.side_effect = ["Second", "Second"]
        command_mocks[2].return_value.class_name.side_effect = ["Third", "Third"]
        command_mocks[3].return_value.class_name.side_effect = ["Fourth", "Fourth"]
        command_mocks[0].return_value.update_from_transcript.side_effect = [questionnaire_mocks[0]]
        command_mocks[1].return_value.update_from_transcript.side_effect = [questionnaire_mocks[1]]
        command_mocks[2].return_value.update_from_transcript.side_effect = [questionnaire_mocks[2]]
        command_mocks[3].return_value.update_from_transcript.side_effect = [None]
        command_mocks[0].return_value.command_from_questionnaire.side_effect = ["theCommand1"]
        command_mocks[1].return_value.command_from_questionnaire.side_effect = ["theCommand2"]
        command_mocks[2].return_value.command_from_questionnaire.side_effect = ["theCommand3"]
        command_mocks[3].return_value.command_from_questionnaire.side_effect = ["theCommand4"]
        questionnaire_mocks[0].to_json.side_effect = [{"key": "questionnaire1"}]
        questionnaire_mocks[1].to_json.side_effect = [{"key": "questionnaire2"}]
        questionnaire_mocks[2].to_json.side_effect = [{"key": "questionnaire3"}]
        questionnaire_mocks[3].to_json.side_effect = [{"key": "questionnaire4"}]

    reset_mocks()

    discussion = [
        Line(speaker="personA", text="the text 1", start=0.0, end=1.3),
        Line(speaker="personB", text="the text 2", start=1.3, end=2.5),
        Line(speaker="personA", text="the text 3", start=2.5, end=3.6),
    ]

    tests = [
        ("First", 0, '{"key": "questionnaire1"}', "theCommand1", "First_theUuid_questionnaire_update"),
        ("Second", 1, '{"key": "questionnaire2"}', "theCommand2", "Second_theUuid_questionnaire_update"),
        # ("Fourth", 3, '{"key": "questionnaire4"}', "theCommand4", "Fourth_theUuid_questionnaire_update"),
        ("Fourth", 3, None, None, "Fourth_theUuid_questionnaire_update"),
        # ("Third", 4, None, None, None),
    ]
    for name, rank, exp_information, exp_command, exp_log_label in tests:
        chatter.side_effect = ["LlmBaseInstance"]
        memory_log.side_effect = ["MemoryLogInstance"]
        instruction = Instruction(
            uuid="theUuid",
            index=0,
            instruction=name,
            information="theInformation",
            is_new=False,
            is_updated=True,
            previous_information="thePreviousInformation",
        )
        tested, settings, aws_credentials, cache = helper_instance(command_mocks, True)
        result = tested.update_questionnaire(discussion, instruction)
        if exp_information is not None:
            expected = InstructionWithCommand(
                uuid="theUuid",
                index=0,
                instruction=name,
                information=exp_information,
                is_new=False,
                is_updated=True,
                previous_information="thePreviousInformation",
                parameters={},
                command=exp_command,
            )
            assert result == expected
        else:
            assert result is None

        calls = [call(settings, "MemoryLogInstance", ModelSpec.COMPLEX)] if exp_log_label else []
        assert chatter.mock_calls == calls
        calls = [call(tested.identification, exp_log_label, aws_credentials)] if exp_log_label else []
        assert memory_log.mock_calls == calls
        for idx, mock in enumerate(command_mocks):
            calls = [
                call(settings, cache, tested.identification),
                call().__bool__(),
                call().class_name(),
                call().is_available(),
            ]
            if idx != 2:
                calls.extend([call().class_name()])
            if idx == rank and idx != 2:
                if idx != 2:
                    calls.extend([call().update_from_transcript(discussion, instruction, "LlmBaseInstance")])
                    if rank != 3:
                        calls.extend([call().command_from_questionnaire("theUuid", questionnaire_mocks[rank])])
            assert mock.mock_calls == calls, f"---> {idx}"
        reset_mocks()


def test_json_schema_instructions():
    tested = AudioInterpreter
    result = tested.json_schema_instructions(["Command1", "Command2"])
    expected = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "items": {
            "additionalProperties": False,
            "properties": {
                "index": {
                    "type": "integer",
                    "description": "the 0-based appearance order of the instruction in this discussion",
                },
                "information": {
                    "description": "all relevant information extracted from the discussion explaining and/or "
                    "defining the instruction",
                    "type": "string",
                },
                "instruction": {"enum": ["Command1", "Command2"], "type": "string"},
                "isNew": {"description": "the instruction is new to the discussion", "type": "boolean"},
                "isUpdated": {
                    "description": "the instruction is an update of an instruction previously identified in "
                    "the discussion",
                    "type": "boolean",
                },
                "uuid": {
                    "description": "a unique identifier in this discussion",
                    "type": "string",
                },
            },
            "required": ["uuid", "index", "instruction", "information", "isNew", "isUpdated"],
            "type": "object",
        },
        "type": "array",
    }
    assert result == expected


def test_json_schema_instructions_validation():
    tested = AudioInterpreter
    schema = tested.json_schema_instructions(["Command1", "Command2"])

    tests = [
        # Valid case
        (
            [
                {
                    "uuid": "uuid-123",
                    "index": 0,
                    "instruction": "Command1",
                    "information": "Some relevant info",
                    "isNew": True,
                    "isUpdated": False,
                }
            ],
            "",
        ),
        # Valid case with Command2
        (
            [
                {
                    "uuid": "uuid-456",
                    "index": 1,
                    "instruction": "Command2",
                    "information": "Different info",
                    "isNew": False,
                    "isUpdated": True,
                }
            ],
            "",
        ),
        # Additional properties
        (
            [
                {
                    "uuid": "uuid-123",
                    "index": 0,
                    "instruction": "Command1",
                    "information": "Info",
                    "isNew": True,
                    "isUpdated": False,
                    "extra": "field",
                }
            ],
            "Additional properties are not allowed ('extra' was unexpected), in path [0]",
        ),
        # Missing uuid
        (
            [
                {
                    "index": 0,
                    "instruction": "Command1",
                    "information": "Info",
                    "isNew": True,
                    "isUpdated": False,
                }
            ],
            "'uuid' is a required property, in path [0]",
        ),
        # Missing index
        (
            [
                {
                    "uuid": "uuid-123",
                    "instruction": "Command1",
                    "information": "Info",
                    "isNew": True,
                    "isUpdated": False,
                }
            ],
            "'index' is a required property, in path [0]",
        ),
        # Missing instruction
        (
            [
                {
                    "uuid": "uuid-123",
                    "index": 0,
                    "information": "Info",
                    "isNew": True,
                    "isUpdated": False,
                }
            ],
            "'instruction' is a required property, in path [0]",
        ),
        # Missing information
        (
            [
                {
                    "uuid": "uuid-123",
                    "index": 0,
                    "instruction": "Command1",
                    "isNew": True,
                    "isUpdated": False,
                }
            ],
            "'information' is a required property, in path [0]",
        ),
        # Missing isNew
        (
            [
                {
                    "uuid": "uuid-123",
                    "index": 0,
                    "instruction": "Command1",
                    "information": "Info",
                    "isUpdated": False,
                }
            ],
            "'isNew' is a required property, in path [0]",
        ),
        # Missing isUpdated
        (
            [
                {
                    "uuid": "uuid-123",
                    "index": 0,
                    "instruction": "Command1",
                    "information": "Info",
                    "isNew": True,
                }
            ],
            "'isUpdated' is a required property, in path [0]",
        ),
        # Invalid instruction enum value
        (
            [
                {
                    "uuid": "uuid-123",
                    "index": 0,
                    "instruction": "InvalidCommand",
                    "information": "Info",
                    "isNew": True,
                    "isUpdated": False,
                }
            ],
            "'InvalidCommand' is not one of ['Command1', 'Command2'], in path [0, 'instruction']",
        ),
        # Wrong type for index (string instead of integer)
        (
            [
                {
                    "uuid": "uuid-123",
                    "index": "0",
                    "instruction": "Command1",
                    "information": "Info",
                    "isNew": True,
                    "isUpdated": False,
                }
            ],
            "'0' is not of type 'integer', in path [0, 'index']",
        ),
        # Wrong type for isNew (string instead of boolean)
        (
            [
                {
                    "uuid": "uuid-123",
                    "index": 0,
                    "instruction": "Command1",
                    "information": "Info",
                    "isNew": "true",
                    "isUpdated": False,
                }
            ],
            "'true' is not of type 'boolean', in path [0, 'isNew']",
        ),
    ]

    for idx, (test_data, expected) in enumerate(tests):
        result = LlmBase.json_validator(test_data, schema)
        assert result == expected, f"---> {idx}"


def test_json_schema_sections():
    tested = AudioInterpreter
    result = tested.json_schema_sections(["section1", "section2", "section3"])
    expected = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "minItems": 1,
        "items": {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "enum": ["section1", "section2", "section3"],
                },
                "transcript": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "speaker": {"type": "string", "minLength": 1},
                            "text": {"type": "string", "minLength": 1},
                        },
                        "required": ["speaker", "text"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["section", "transcript"],
            "additionalProperties": False,
        },
    }
    assert result == expected


def test_json_schema_sections_validation():
    tested = AudioInterpreter
    schema = tested.json_schema_sections(["section1", "section2", "section3"])

    tests = [
        # Valid case
        (
            [
                {
                    "section": "section1",
                    "transcript": [
                        {"speaker": "Doctor", "text": "Hello"},
                        {"speaker": "Patient", "text": "Hi"},
                    ],
                }
            ],
            "",
        ),
        # Valid case with different section
        (
            [
                {
                    "section": "section2",
                    "transcript": [{"speaker": "Doctor", "text": "How are you?"}],
                }
            ],
            "",
        ),
        # Valid case with empty transcript array
        ([{"section": "section3", "transcript": []}], ""),
        # Empty array
        ([], "[] should be non-empty"),
        # Additional properties at root level
        (
            [
                {
                    "section": "section1",
                    "transcript": [],
                    "extra": "field",
                }
            ],
            "Additional properties are not allowed ('extra' was unexpected), in path [0]",
        ),
        # Missing section
        ([{"transcript": []}], "'section' is a required property, in path [0]"),
        # Missing transcript
        ([{"section": "section1"}], "'transcript' is a required property, in path [0]"),
        # Invalid section enum value
        (
            [{"section": "invalidSection", "transcript": []}],
            "'invalidSection' is not one of ['section1', 'section2', 'section3'], in path [0, 'section']",
        ),
        # Wrong type for transcript (not array)
        (
            [{"section": "section1", "transcript": "not an array"}],
            "'not an array' is not of type 'array', in path [0, 'transcript']",
        ),
        # Additional properties in transcript item
        (
            [
                {
                    "section": "section1",
                    "transcript": [
                        {
                            "speaker": "Doctor",
                            "text": "Hello",
                            "extra": "field",
                        }
                    ],
                }
            ],
            "Additional properties are not allowed ('extra' was unexpected), in path [0, 'transcript', 0]",
        ),
        # Missing speaker in transcript item
        (
            [
                {
                    "section": "section1",
                    "transcript": [{"text": "Hello"}],
                }
            ],
            "'speaker' is a required property, in path [0, 'transcript', 0]",
        ),
        # Missing text in transcript item
        (
            [
                {
                    "section": "section1",
                    "transcript": [{"speaker": "Doctor"}],
                }
            ],
            "'text' is a required property, in path [0, 'transcript', 0]",
        ),
        # Empty speaker (minLength violation)
        (
            [
                {
                    "section": "section1",
                    "transcript": [{"speaker": "", "text": "Hello"}],
                }
            ],
            "'' should be non-empty, in path [0, 'transcript', 0, 'speaker']",
        ),
        # Empty text (minLength violation)
        (
            [
                {
                    "section": "section1",
                    "transcript": [{"speaker": "Doctor", "text": ""}],
                }
            ],
            "'' should be non-empty, in path [0, 'transcript', 0, 'text']",
        ),
        # Wrong type for speaker (not string)
        (
            [
                {
                    "section": "section1",
                    "transcript": [{"speaker": 123, "text": "Hello"}],
                }
            ],
            "123 is not of type 'string', in path [0, 'transcript', 0, 'speaker']",
        ),
    ]

    for idx, (test_data, expected) in enumerate(tests):
        result = LlmBase.json_validator(test_data, schema)
        assert result == expected, f"---> {idx}"
