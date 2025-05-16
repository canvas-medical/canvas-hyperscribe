from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, call

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance(mocks, with_audit) -> tuple[AudioInterpreter, Settings, AwsS3Credentials, LimitedCache]:
    def reset_mocks():
        command_list.reset_mocks()

    with patch.object(ImplementedCommands, 'command_list') as command_list:
        settings = Settings(
            llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
            llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
            science_host="scienceHost",
            ontologies_host="ontologiesHost",
            pre_shared_key="preSharedKey",
            structured_rfv=False,
            audit_llm=with_audit,
            api_signing_key="theApiSigningKey",
            send_progress=False,
        )
        aws_s3 = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")
        if mocks:
            mocks[0].return_value.is_available.side_effect = [True]
            mocks[1].return_value.is_available.side_effect = [True]
            mocks[2].return_value.is_available.side_effect = [False]
            mocks[3].return_value.is_available.side_effect = [True]

        command_list.side_effect = [mocks]

        cache = LimitedCache("patientUuid", {})
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


@patch.object(ImplementedCommands, 'command_list')
def test___init__(command_list):
    mocks = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        command_list.reset_mocks()
        for item in mocks:
            item.reset_mock()

    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
        audit_llm=False,
        api_signing_key="theApiSigningKey",
        send_progress=False,
    )
    aws_s3 = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket")

    mocks[0].return_value.is_available.side_effect = [True]
    mocks[1].return_value.is_available.side_effect = [True]
    mocks[2].return_value.is_available.side_effect = [False]
    mocks[3].return_value.is_available.side_effect = [True]
    command_list.side_effect = [mocks]

    cache = LimitedCache("patientUuid", {})
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

    calls = [call()]
    assert command_list.mock_calls == calls
    for mock in mocks:
        calls = [
            call(settings, cache, identification),
            call().__bool__(),
            call().is_available(),
        ]
        assert mock.mock_calls == calls
    reset_mocks()


def test_instruction_definitions():
    mocks = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

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
        mocks[0].return_value.instruction_description.side_effect = ["Description1"]
        mocks[1].return_value.instruction_description.side_effect = ["Description2"]
        mocks[2].return_value.instruction_description.side_effect = ["Description3"]
        mocks[3].return_value.instruction_description.side_effect = ["Description4"]

        tested, settings, aws_credentials, cache = helper_instance(mocks, True)
        result = tested.instruction_definitions()
        expected = [
            {'information': 'Description2', 'instruction': 'Second'},
            {'information': 'Description4', 'instruction': 'Fourth'},
        ]

        absent_idx = [2]
        if expected_present:
            expected.insert(0, {'information': 'Description1', 'instruction': class_name})
        else:
            absent_idx.append(0)

        assert result == expected
        for idx, mock in enumerate(mocks):
            calls = [
                call(settings, cache, tested.identification),
                call().__bool__(),
                call().is_available(),
            ]
            if idx != 2:
                calls.append(call().class_name())
            if idx not in absent_idx:
                calls.extend([
                    call().class_name(),
                    call().instruction_description(),
                ])
            assert mock.mock_calls == calls, f"---> {idx}"
        reset_mocks()


def test_instruction_constraints():
    mocks = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        for item in mocks:
            item.reset_mock()

    instructions = Instruction.load_from_json([
        {"instruction": "Command1"},
        {"instruction": "Command2"},
        {"instruction": "Command3"},
        {"instruction": "Command4"},
    ])

    tests = [
        ([0, 1, 2, 3], ["Constraints1", "Constraints4"]),
        ([0], ["Constraints1"]),
        ([2, 3], ["Constraints4"]),
    ]
    for list_idx, expected in tests:
        mocks[0].return_value.class_name.side_effect = ["Command1"]
        mocks[1].return_value.class_name.side_effect = ["Command2"]
        mocks[2].return_value.class_name.side_effect = ["Command3"]
        mocks[3].return_value.class_name.side_effect = ["Command4"]
        mocks[0].return_value.instruction_constraints.side_effect = ["Constraints1"]
        mocks[1].return_value.instruction_constraints.side_effect = [""]
        mocks[2].return_value.instruction_constraints.side_effect = ["Constraints3"]
        mocks[3].return_value.instruction_constraints.side_effect = ["Constraints4"]

        tested, settings, aws_credentials, cache = helper_instance(mocks, True)
        result = tested.instruction_constraints([instructions[i] for i in list_idx])
        assert result == expected
        for idx, mock in enumerate(mocks):
            calls = [
                call(settings, cache, tested.identification),
                call().__bool__(),
                call().is_available(),
            ]
            if idx != 2:
                calls.append(call().class_name())
                if idx in list_idx:
                    calls.append(call().instruction_constraints())
            assert mock.mock_calls == calls, f"---> {idx}"
        reset_mocks()


def test_command_structures():
    mocks = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

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
        mocks[0].return_value.command_parameters.side_effect = ["Parameters1"]
        mocks[1].return_value.command_parameters.side_effect = ["Parameters2"]
        mocks[2].return_value.command_parameters.side_effect = ["Parameters3"]
        mocks[3].return_value.command_parameters.side_effect = ["Parameters4"]

        tested, settings, aws_credentials, cache = helper_instance(mocks, True)
        result = tested.command_structures()
        expected = {
            'Fourth': 'Parameters4',
            'Second': 'Parameters2',
        }
        absent_idx = [2]
        if expected_present:
            expected[class_name] = 'Parameters1'
        else:
            absent_idx.append(0)

        assert result == expected
        for idx, mock in enumerate(mocks):
            calls = [
                call(settings, cache, tested.identification),
                call().__bool__(),
                call().is_available(),
            ]
            if idx != 2:
                calls.append(call().class_name())
            if idx not in absent_idx:
                calls.extend([
                    call().class_name(),
                    call().command_parameters(),
                ])
            assert mock.mock_calls == calls, f"---> {idx}"
        reset_mocks()


@patch.object(MemoryLog, "instance")
@patch.object(Helper, "audio2texter")
def test_combine_and_speaker_detection(audio2texter, memory_log):
    def reset_mocks():
        audio2texter.reset_mock()
        memory_log.reset_mock()

    system_prompt = [
        "The conversation is in the medical context, and related to a visit of a patient with a healthcare provider.",
        "",
        "Your task is to transcribe what was said, regardless of whether the audio recordings were of dialogue during the visit or monologue after the visit.",
        "",
    ]
    user_prompt = {
        "noTailedTranscript": [
            "The recording takes place in a medical setting, specifically related to a patient's visit with a clinician.",
            "",
            "These audio files contain recordings of a single visit.",
            "There is no overlap between the segments, so they should be regarded as a continuous flow and analyzed at once.",
            "",
            "Your task is to:",
            "1. label each voice if multiple voices are present.",
            "2. transcribe each speaker's words with maximum accuracy.",
            "",
            "Present your findings in a JSON format within a Markdown code block:",
            "```json",
            '[\n {\n  "voice": "voice_1/voice_2/.../voice_N",\n  "text": "the verbatim transcription of what the speaker said"\n }\n]',
            "```",
            "",
            "Then, review the discussion from the top and distinguish the role of the voices (patient, clinician, nurse, parents...) in the conversation, if there is only voice, assume this is the clinician",
            "",
            "Present your findings in a JSON format within a Markdown code block:",
            "```json",
            '[\n {\n  "speaker": "Patient/Clinician/Nurse/...",\n  "voice": "voice_1/voice_2/.../voice_N"\n }\n]',
            "```",
            "",
        ],
        "withTailedTranscript": [
            "The recording takes place in a medical setting, specifically related to a patient's visit with a clinician.",
            "",
            "These audio files contain recordings of a single visit.",
            "There is no overlap between the segments, so they should be regarded as a continuous flow and analyzed at once.",
            "\nThe previous segment finished with: 'the last words.'.\n",
            "Your task is to:",
            "1. label each voice if multiple voices are present.",
            "2. transcribe each speaker's words with maximum accuracy.",
            "",
            "Present your findings in a JSON format within a Markdown code block:",
            "```json",
            '[\n {\n  "voice": "voice_1/voice_2/.../voice_N",\n  "text": "the verbatim transcription of what the speaker said"\n }\n]',
            "```",
            "",
            "Then, review the discussion from the top and distinguish the role of the voices (patient, clinician, nurse, parents...) in the conversation, if there is only voice, assume this is the clinician",
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
            '$schema': 'http://json-schema.org/draft-07/schema#',
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'voice': {'type': 'string', 'pattern': '^voice_[1-9]\\d*$'},
                    'text': {'type': 'string', 'minLength': 1},
                },
                'required': ['voice', 'text'],
                'additionalProperties': False,
            },
            'minItems': 1,
        },
        {
            '$schema': 'http://json-schema.org/draft-07/schema#',
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'speaker': {'type': 'string', 'minLength': 1},
                    'voice': {'type': 'string', 'pattern': '^voice_[1-9]\\d*$'},
                },
                'required': ['speaker', 'voice'],
                'additionalProperties': False,
            },
            'minItems': 1,
            'uniqueItems': True,
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
    audio_chunks = [b"chunk1", b"chunk2"]

    tested, settings, aws_credentials, cache = helper_instance([], True)
    # no error
    # -- all JSON
    audio2texter.return_value.chat.side_effect = [JsonExtract(error="theError", has_error=False, content=[discussion, speakers])]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.combine_and_speaker_detection(audio_chunks, "")
    expected = JsonExtract(error="", has_error=False, content=conversation)
    assert result == expected
    calls = [
        call(settings, "MemoryLogInstance"),
        call().set_system_prompt(system_prompt),
        call().set_user_prompt(user_prompt["noTailedTranscript"]),
        call().add_audio(b'chunk1', 'mp3'),
        call().add_audio(b'chunk2', 'mp3'),
        call().chat(schemas),
    ]
    assert audio2texter.mock_calls == calls
    calls = [call(tested.identification, "audio2transcript", aws_credentials)]
    assert memory_log.mock_calls == calls
    reset_mocks()
    # -- only one JSON
    audio2texter.return_value.chat.side_effect = [JsonExtract(error="theError", has_error=False, content=[discussion])]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.combine_and_speaker_detection(audio_chunks, "")
    expected = JsonExtract(error="partial response", has_error=True, content=[discussion])
    assert result == expected
    calls = [
        call(settings, "MemoryLogInstance"),
        call().set_system_prompt(system_prompt),
        call().set_user_prompt(user_prompt["noTailedTranscript"]),
        call().add_audio(b'chunk1', 'mp3'),
        call().add_audio(b'chunk2', 'mp3'),
        call().chat(schemas),
    ]
    assert audio2texter.mock_calls == calls
    calls = [call(tested.identification, "audio2transcript", aws_credentials)]
    assert memory_log.mock_calls == calls
    reset_mocks()
    # -- with some previous transcript
    audio2texter.return_value.chat.side_effect = [JsonExtract(error="theError", has_error=False, content=[discussion, speakers])]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.combine_and_speaker_detection(audio_chunks, "the last words.")
    expected = JsonExtract(error="", has_error=False, content=conversation)
    assert result == expected
    calls = [
        call(settings, "MemoryLogInstance"),
        call().set_system_prompt(system_prompt),
        call().set_user_prompt(user_prompt["withTailedTranscript"]),
        call().add_audio(b'chunk1', 'mp3'),
        call().add_audio(b'chunk2', 'mp3'),
        call().chat(schemas),
    ]
    assert audio2texter.mock_calls == calls
    calls = [call(tested.identification, "audio2transcript", aws_credentials)]
    assert memory_log.mock_calls == calls
    reset_mocks()

    # with error
    audio2texter.return_value.chat.side_effect = [JsonExtract(error="theError", has_error=True, content=[discussion, speakers])]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.combine_and_speaker_detection(audio_chunks, "")
    expected = JsonExtract(error="theError", has_error=True, content=[discussion, speakers])
    assert result == expected
    calls = [
        call(settings, "MemoryLogInstance"),
        call().set_system_prompt(system_prompt),
        call().set_user_prompt(user_prompt["noTailedTranscript"]),
        call().add_audio(b'chunk1', 'mp3'),
        call().add_audio(b'chunk2', 'mp3'),
        call().chat(schemas),
    ]
    assert audio2texter.mock_calls == calls
    calls = [call(tested.identification, "audio2transcript", aws_credentials)]
    assert memory_log.mock_calls == calls
    reset_mocks()


@patch.object(MemoryLog, "instance")
@patch.object(Helper, "chatter")
@patch.object(AudioInterpreter, 'instruction_constraints')
@patch.object(AudioInterpreter, 'json_schema')
@patch.object(AudioInterpreter, 'instruction_definitions')
def test_detect_instructions(
        instruction_definitions,
        json_schema,
        instruction_constraints,
        chatter,
        memory_log,
):
    mocks = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        instruction_definitions.reset_mock()
        json_schema.reset_mock()
        instruction_constraints.reset_mock()
        chatter.reset_mock()
        memory_log.reset_mock()
        for item in mocks:
            item.reset_mock()
        mocks[0].return_value.class_name.side_effect = ["First"]
        mocks[1].return_value.class_name.side_effect = ["Second"]
        mocks[2].return_value.class_name.side_effect = ["Third"]
        mocks[3].return_value.class_name.side_effect = ["Fourth"]
        mocks[0].return_value.instruction_description.side_effect = ["Description1"]
        mocks[1].return_value.instruction_description.side_effect = ["Description2"]
        mocks[2].return_value.instruction_description.side_effect = ["Description3"]
        mocks[3].return_value.instruction_description.side_effect = ["Description4"]

    system_prompt = [
        "The conversation is in the context of a clinical encounter between patient and licensed healthcare provider.",
        "The user will submit the transcript of the visit of a patient with the healthcare provider.",
        "The user needs to extract and store the relevant information in their software using structured commands as described below.",
        "Your task is to help the user by identifying the relevant instructions and their linked information, regardless of their location in the transcript.",
        "If any portion of the transcript is small talk, chit chat, or side bar with no discernible connection to health concerns, then it should be ignored."
        "",
        "The instructions are limited to the following:",
        '```json',
        '"theInstructionDefinition"',
        '```',
        '',
        'Your response must be a JSON Markdown block validated with the schema:',
        '```json',
        '"theJsonSchema"',
        '```',
        '',
    ]
    user_prompts = {
        "noKnownInstructions": [
            "Below is the most recent segment of the transcript of the visit of a patient with a healthcare provider.",
            "What are the instructions I need to add to my software to document the visit correctly?",
            '```json',
            '['
            '\n {\n  "speaker": "personA",\n  "text": "the text 1"\n },'
            '\n {\n  "speaker": "personB",\n  "text": "the text 2"\n },'
            '\n {\n  "speaker": "personA",\n  "text": "the text 3"\n }'
            '\n]',
            '```',
            '',
        ],
        "withKnownInstructions": [
            "Below is the most recent segment of the transcript of the visit of a patient with a healthcare provider.",
            "What are the instructions I need to add to my software to document the visit correctly?",
            '```json',
            '['
            '\n {\n  "speaker": "personA",\n  "text": "the text 1"\n },'
            '\n {\n  "speaker": "personB",\n  "text": "the text 2"\n },'
            '\n {\n  "speaker": "personA",\n  "text": "the text 3"\n }'
            '\n]',
            '```',
            '',
            "From among all previous segments of the transcript, the following instructions were identified:",
            '```json',
            '[\n {'
            '\n  "uuid": "uuid1",'
            '\n  "index": 0,'
            '\n  "instruction": "the instruction 1",'
            '\n  "information": "the information 1",'
            '\n  "isNew": false,'
            '\n  "isUpdated": false'
            '\n },\n {'
            '\n  "uuid": "uuid2",'
            '\n  "index": 1,'
            '\n  "instruction": "the instruction 2",'
            '\n  "information": "the information 2",'
            '\n  "isNew": false,'
            '\n  "isUpdated": false'
            '\n }\n]',
            '```',
            'It is important to include them in your response, with any necessary additional information mentioned in the transcript.',
        ],
        "constraints": [
            'Review your response and be sure to follow these constraints:',
            ' * theConstraint1',
            ' * theConstraint2',
            '',
            'Return the original JSON if valid, or provide a corrected version to follow the constraints if needed.',
            '',
        ],
    }

    discussion = [
        Line(speaker="personA", text="the text 1"),
        Line(speaker="personB", text="the text 2"),
        Line(speaker="personA", text="the text 3"),
    ]
    known_instructions = [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="the instruction 1",
            information="the information 1",
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid2",
            index=1,
            instruction="the instruction 2",
            information="the information 2",
            is_new=False,
            is_updated=True,
        ),
    ]
    reset_mocks()

    tested, settings, aws_credentials, cache = helper_instance(mocks, False)
    # -- no known instruction
    instruction_definitions.side_effect = ["theInstructionDefinition"]
    json_schema.side_effect = ["theJsonSchema"]
    instruction_constraints.side_effect = [["theConstraint1", "theConstraint2"]]
    chatter.return_value.single_conversation.side_effect = [[{"information": "response1"}], [{"information": "response2"}]]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.detect_instructions(discussion, [])
    expected = [{"information": "response2"}]
    assert result == expected
    calls = [call()]
    assert instruction_definitions.mock_calls == calls
    calls = [call(['First', 'Second', 'Fourth'])]
    assert json_schema.mock_calls == calls
    calls = [call([Instruction(uuid='', index=0, instruction='', information='response1', is_new=True, is_updated=False)])]
    assert instruction_constraints.mock_calls == calls
    calls = [
        call(settings, "MemoryLogInstance"),
        call().single_conversation(system_prompt, user_prompts["noKnownInstructions"], ['theJsonSchema'], None),
        call().set_model_prompt(['```json', '[{"information": "response1"}]', '```']),
        call().single_conversation(system_prompt, user_prompts["constraints"], ['theJsonSchema'], None),
    ]
    assert chatter.mock_calls == calls
    calls = [call(tested.identification, "transcript2instructions", aws_credentials)]
    assert memory_log.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call(settings, cache, tested.identification),
            call().__bool__(),
            call().is_available(),
        ]
        if idx != 2:
            calls.extend([call().class_name()])
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()

    # -- no known instruction + no constraint
    instruction_definitions.side_effect = ["theInstructionDefinition"]
    json_schema.side_effect = ["theJsonSchema"]
    instruction_constraints.side_effect = [[]]
    chatter.return_value.single_conversation.side_effect = [[{"information": "response1"}], [{"information": "response2"}]]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.detect_instructions(discussion, [])
    expected = [{"information": "response1"}]
    assert result == expected
    calls = [call()]
    assert instruction_definitions.mock_calls == calls
    calls = [call(['First', 'Second', 'Fourth'])]
    assert json_schema.mock_calls == calls
    calls = [call([Instruction(uuid='', index=0, instruction='', information='response1', is_new=True, is_updated=False)])]
    assert instruction_constraints.mock_calls == calls
    calls = [
        call(settings, "MemoryLogInstance"),
        call().single_conversation(system_prompt, user_prompts["noKnownInstructions"], ['theJsonSchema'], None),
    ]
    assert chatter.mock_calls == calls
    calls = [call(tested.identification, "transcript2instructions", aws_credentials)]
    assert memory_log.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = []
        if idx != 2:
            calls.extend([call().class_name()])
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()

    # -- with known instructions
    instruction_definitions.side_effect = ["theInstructionDefinition"]
    json_schema.side_effect = ["theJsonSchema"]
    instruction_constraints.side_effect = [["theConstraint1", "theConstraint2"]]
    chatter.return_value.single_conversation.side_effect = [[{"information": "response1"}], [{"information": "response2"}]]
    memory_log.side_effect = ["MemoryLogInstance"]
    result = tested.detect_instructions(discussion, known_instructions)
    expected = [{"information": "response2"}]
    assert result == expected
    calls = [call()]
    assert instruction_definitions.mock_calls == calls
    calls = [call(['First', 'Second', 'Fourth'])]
    assert json_schema.mock_calls == calls
    calls = [call([Instruction(uuid='', index=0, instruction='', information='response1', is_new=True, is_updated=False)])]
    assert instruction_constraints.mock_calls == calls
    calls = [
        call(settings, "MemoryLogInstance"),
        call().single_conversation(system_prompt, user_prompts["withKnownInstructions"], ['theJsonSchema'], None),
        call().set_model_prompt(['```json', '[{"information": "response1"}]', '```']),
        call().single_conversation(system_prompt, user_prompts["constraints"], ['theJsonSchema'], None),
    ]
    assert chatter.mock_calls == calls
    calls = [call(tested.identification, "transcript2instructions", aws_credentials)]
    assert memory_log.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = []
        if idx != 2:
            calls.extend([call().class_name()])
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()


@patch("hyperscribe.libraries.audio_interpreter.datetime", wraps=datetime)
@patch("hyperscribe.libraries.audio_interpreter.Progress")
@patch("hyperscribe.libraries.audio_interpreter.MemoryLog")
@patch.object(Helper, "chatter")
def test_create_sdk_command_parameters(chatter, memory_log, progress, mock_datetime):
    mocks = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        chatter.reset_mock()
        memory_log.reset_mock()
        progress.reset_mock()
        mock_datetime.reset_mock()
        for item in mocks:
            item.reset_mock()
        mocks[0].return_value.class_name.side_effect = ["First", "First"]
        mocks[1].return_value.class_name.side_effect = ["Second", "Second"]
        mocks[2].return_value.class_name.side_effect = ["Third", "Third"]
        mocks[3].return_value.class_name.side_effect = ["Fourth", "Fourth"]
        mocks[0].return_value.command_parameters.side_effect = [{"Command": "Parameters1"}]
        mocks[1].return_value.command_parameters.side_effect = [{"Command": "Parameters2"}]
        mocks[2].return_value.command_parameters.side_effect = [{"Command": "Parameters3"}]
        mocks[3].return_value.command_parameters.side_effect = [{"Command": "Parameters4"}]

    instruction = Instruction(
        uuid="theUuid",
        index=0,
        instruction="Second",
        information="theInformation",
        is_new=False,
        is_updated=True,
    )
    system_prompt = [
        "The conversation is in the context of a clinical encounter between patient and licensed healthcare provider.",
        "During the encounter, the user has identified instructions with key information to record in its software.",
        "The user will submit an instruction and the linked information grounded in the transcript, as well as the structure of the associated command.",
        "Your task is to help the user by writing correctly detailed data for the structured command.",
        "Unless explicitly instructed otherwise for a specific command, you must not make up or refer to any details of any kind that are not explicitly present in the transcript or prior instructions.",
        "",
        "Your response has to be a JSON Markdown block encapsulating the filled structure.",
        "",
        f"Please, note that now is 2025-02-04T07:48:21+00:00."
    ]
    user_prompt = [
        'Based on the text:',
        '```text',
        'theInformation',
        '```',
        '',
        'Your task is to replace the values of the JSON object with the relevant information:',
        '```json',
        '[\n {\n  "Command": "Parameters2"\n }\n]',
        '```',
        '',
    ]
    schemas = [
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {"type": "object", "additionalProperties": True},
        },
    ]
    reset_mocks()

    tested, settings, aws_credentials, cache = helper_instance(mocks, True)
    # with response
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
        parameters={"key": "response1"},
    )
    assert result == expected
    calls = [
        call(settings, memory_log.instance.return_value),
        call().single_conversation(system_prompt, user_prompt, schemas, instruction),
    ]
    assert chatter.mock_calls == calls
    calls = [call.instance(tested.identification, "Second_theUuid_instruction2parameters", aws_credentials)]
    assert memory_log.mock_calls == calls
    calls = [
        call.send_to_user(tested.identification, settings, "parameters identified for Second"),
    ]
    assert progress.mock_calls == calls
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call(settings, cache, tested.identification),
            call().__bool__(),
            call().is_available(),
        ]
        if idx != 2:
            calls.extend([
                call().class_name(),
                call().class_name(),
                call().command_parameters(),
            ])
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()
    # without response
    mock_datetime.now.side_effect = [datetime(2025, 2, 4, 7, 48, 21, tzinfo=timezone.utc)]
    chatter.return_value.single_conversation.side_effect = [[]]
    result = tested.create_sdk_command_parameters(instruction)
    assert result is None
    calls = [
        call(settings, memory_log.instance.return_value),
        call().single_conversation(system_prompt, user_prompt, schemas, instruction),
    ]
    assert chatter.mock_calls == calls
    calls = [call.instance(tested.identification, "Second_theUuid_instruction2parameters", aws_credentials)]
    assert memory_log.mock_calls == calls
    calls = []
    assert progress.mock_calls == calls
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = []
        if idx != 2:
            calls.extend([
                call().class_name(),
                call().class_name(),
                call().command_parameters(),
            ])
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()


@patch("hyperscribe.libraries.audio_interpreter.Progress")
@patch("hyperscribe.libraries.audio_interpreter.MemoryLog")
@patch.object(Helper, "chatter")
def test_create_sdk_command_from(chatter, memory_log, progress):
    mocks = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        chatter.reset_mock()
        memory_log.reset_mock()
        progress.reset_mock()
        for item in mocks:
            item.reset_mock()
        mocks[0].return_value.class_name.side_effect = ["First"]
        mocks[1].return_value.class_name.side_effect = ["Second"]
        mocks[2].return_value.class_name.side_effect = ["Third"]
        mocks[3].return_value.class_name.side_effect = ["Fourth"]
        mocks[0].return_value.command_from_json.side_effect = ["theCommand1"]
        mocks[1].return_value.command_from_json.side_effect = ["theCommand2"]
        mocks[2].return_value.command_from_json.side_effect = ["theCommand3"]
        mocks[3].return_value.command_from_json.side_effect = [None]

    reset_mocks()

    tests = [
        ("First", 0, "theCommand1", "First_theUuid_parameters2command", "command generated for First"),
        ("Second", 1, "theCommand2", "Second_theUuid_parameters2command", "command generated for Second"),
        ("Fourth", 3, None, "Fourth_theUuid_parameters2command", None),
        ("Third", 4, None, None, None),
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
            parameters={"theKey": "theValue"},
        )
        tested, settings, aws_credentials, cache = helper_instance(mocks, True)
        result = tested.create_sdk_command_from(instruction)
        assert result == expected

        calls = [call(settings, memory_log.instance.return_value)] if exp_log_label else []
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
                call().is_available(),
            ]
            if idx < rank + 1 and idx != 2:
                calls.extend([call().class_name()])
            if idx == rank and idx != 2:
                calls.extend([call().command_from_json(instruction, "LlmBaseInstance")])
            assert mock.mock_calls == calls, f"---> {idx}"
        reset_mocks()


@patch.object(MemoryLog, "instance")
@patch.object(Helper, "chatter")
def test_update_questionnaire(chatter, memory_log):
    command_mocks = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    questionnaire_mocks = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        chatter.reset_mock()
        memory_log.reset_mock()
        for item in command_mocks:
            item.reset_mock()
            item.return_value.__class__ = BaseQuestionnaire
        for item in questionnaire_mocks:
            item.reset_mock()

        command_mocks[0].return_value.class_name.side_effect = ["First"]
        command_mocks[1].return_value.class_name.side_effect = ["Second"]
        command_mocks[2].return_value.class_name.side_effect = ["Third"]
        command_mocks[3].return_value.class_name.side_effect = ["Fourth"]
        command_mocks[0].return_value.update_from_transcript.side_effect = [questionnaire_mocks[0]]
        command_mocks[1].return_value.update_from_transcript.side_effect = [questionnaire_mocks[1]]
        command_mocks[2].return_value.update_from_transcript.side_effect = [questionnaire_mocks[2]]
        command_mocks[3].return_value.update_from_transcript.side_effect = [questionnaire_mocks[3]]
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
        Line(speaker="personA", text="the text 1"),
        Line(speaker="personB", text="the text 2"),
        Line(speaker="personA", text="the text 3"),
    ]

    tests = [
        ("First", 0, '{"key": "questionnaire1"}', "theCommand1", "First_theUuid_questionnaire_update"),
        ("Second", 1, '{"key": "questionnaire2"}', "theCommand2", "Second_theUuid_questionnaire_update"),
        ("Fourth", 3, '{"key": "questionnaire4"}', "theCommand4", "Fourth_theUuid_questionnaire_update"),
        ("Third", 4, None, None, None),
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
                parameters={},
                command=exp_command,
            )
            assert result == expected
        else:
            assert result is None

        calls = [call(settings, "MemoryLogInstance")] if exp_log_label else []
        assert chatter.mock_calls == calls
        calls = [call(tested.identification, exp_log_label, aws_credentials)] if exp_log_label else []
        assert memory_log.mock_calls == calls
        for idx, mock in enumerate(command_mocks):
            calls = [
                call(settings, cache, tested.identification),
                call().__bool__(),
                call().is_available(),
            ]
            if idx < rank + 1 and idx != 2:
                calls.extend([call().class_name()])
            if idx == rank and idx != 2:
                calls.extend([
                    call().update_from_transcript(discussion, instruction, "LlmBaseInstance"),
                    call().command_from_questionnaire('theUuid', questionnaire_mocks[rank]),
                ])
            assert mock.mock_calls == calls, f"---> {idx}"
        reset_mocks()


def test_json_schema():
    tested = AudioInterpreter
    result = tested.json_schema(["Command1", "Command2"])
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
                    "description": "all relevant information extracted from the discussion explaining and/or defining the instruction",
                    "type": "string",
                },
                "instruction": {
                    "enum": ["Command1", "Command2"],
                    "type": "string",
                },
                "isNew": {
                    "description": "the instruction is new to the discussion",
                    "type": "boolean",
                },
                "isUpdated": {
                    "description": "the instruction is an update of an instruction previously identified in the discussion",
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
