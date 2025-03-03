from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, call

from hyperscribe.protocols.audio_interpreter import AudioInterpreter
from hyperscribe.protocols.helper import Helper
from hyperscribe.protocols.implemented_commands import ImplementedCommands
from hyperscribe.protocols.limited_cache import LimitedCache
from hyperscribe.protocols.structures.instruction import Instruction
from hyperscribe.protocols.structures.json_extract import JsonExtract
from hyperscribe.protocols.structures.line import Line
from hyperscribe.protocols.structures.settings import Settings
from hyperscribe.protocols.structures.vendor_key import VendorKey


def helper_instance(mocks) -> tuple[AudioInterpreter, Settings, LimitedCache]:
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
        )
        if mocks:
            mocks[0].return_value.is_available.side_effect = [True]
            mocks[1].return_value.is_available.side_effect = [True]
            mocks[2].return_value.is_available.side_effect = [False]
            mocks[3].return_value.is_available.side_effect = [True]

        command_list.side_effect = [mocks]

        cache = LimitedCache("patientUuid", {})
        instance = AudioInterpreter(settings, cache, "patientUuid", "noteUuid", "providerUuid")
        calls = [call()]
        assert command_list.mock_calls == calls
        reset_mocks()

        return instance, settings, cache


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
        for mock in mocks:
            mock.reset_mock()

    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
    )
    mocks[0].return_value.is_available.side_effect = [True]
    mocks[1].return_value.is_available.side_effect = [True]
    mocks[2].return_value.is_available.side_effect = [False]
    mocks[3].return_value.is_available.side_effect = [True]
    command_list.side_effect = [mocks]

    cache = LimitedCache("patientUuid", {})

    instance = AudioInterpreter(settings, cache, "patientUuid", "noteUuid", "providerUuid")
    assert instance.settings == settings
    assert instance.patient_id == "patientUuid"
    assert instance.note_uuid == "noteUuid"

    calls = [call()]
    assert command_list.mock_calls == calls
    for mock in mocks:
        calls = [
            call(settings, cache, 'patientUuid', 'noteUuid', 'providerUuid'),
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
        for mock in mocks:
            mock.reset_mock()

    mocks[0].return_value.class_name.side_effect = ["First"]
    mocks[1].return_value.class_name.side_effect = ["Second"]
    mocks[2].return_value.class_name.side_effect = ["Third"]
    mocks[3].return_value.class_name.side_effect = ["Fourth"]
    mocks[0].return_value.instruction_description.side_effect = ["Description1"]
    mocks[1].return_value.instruction_description.side_effect = ["Description2"]
    mocks[2].return_value.instruction_description.side_effect = ["Description3"]
    mocks[3].return_value.instruction_description.side_effect = ["Description4"]

    tested, settings, cache = helper_instance(mocks)
    result = tested.instruction_definitions()
    expected = [
        {'information': 'Description1', 'instruction': 'First'},
        {'information': 'Description2', 'instruction': 'Second'},
        {'information': 'Description4', 'instruction': 'Fourth'},
    ]
    assert result == expected
    for idx, mock in enumerate(mocks):
        calls = [
            call(settings, cache, 'patientUuid', 'noteUuid', 'providerUuid'),
            call().__bool__(),
            call().is_available(),
        ]
        if idx != 2:
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
        for mock in mocks:
            mock.reset_mock()

    mocks[0].return_value.instruction_constraints.side_effect = ["Constraints1"]
    mocks[1].return_value.instruction_constraints.side_effect = [""]
    mocks[2].return_value.instruction_constraints.side_effect = ["Constraints3"]
    mocks[3].return_value.instruction_constraints.side_effect = ["Constraints4"]

    tested, settings, cache = helper_instance(mocks)
    result = tested.instruction_constraints()
    expected = ["Constraints1", "Constraints4"]
    assert result == expected
    for idx, mock in enumerate(mocks):
        calls = [
            call(settings, cache, 'patientUuid', 'noteUuid', 'providerUuid'),
            call().__bool__(),
            call().is_available(),
        ]
        if idx != 2:
            calls.extend([
                call().instruction_constraints(),
            ])
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
        for mock in mocks:
            mock.reset_mock()

    mocks[0].return_value.class_name.side_effect = ["First"]
    mocks[1].return_value.class_name.side_effect = ["Second"]
    mocks[2].return_value.class_name.side_effect = ["Third"]
    mocks[3].return_value.class_name.side_effect = ["Fourth"]
    mocks[0].return_value.command_parameters.side_effect = ["Parameters1"]
    mocks[1].return_value.command_parameters.side_effect = ["Parameters2"]
    mocks[2].return_value.command_parameters.side_effect = ["Parameters3"]
    mocks[3].return_value.command_parameters.side_effect = ["Parameters4"]

    tested, settings, cache = helper_instance(mocks)
    result = tested.command_structures()
    expected = {
        'First': 'Parameters1',
        'Fourth': 'Parameters4',
        'Second': 'Parameters2',
    }
    assert result == expected
    for idx, mock in enumerate(mocks):
        calls = [
            call(settings, cache, 'patientUuid', 'noteUuid', 'providerUuid'),
            call().__bool__(),
            call().is_available(),
        ]
        if idx != 2:
            calls.extend([
                call().class_name(),
                call().command_parameters(),
            ])
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()


@patch.object(Helper, "audio2texter")
def test_combine_and_speaker_detection(audio2texter):
    def reset_mocks():
        audio2texter.reset_mock()

    system_prompt = [
        "The conversation is in the medical context, and related to a visit of a patient with a healthcare provider.",
        "",
        "Your task is to transcribe what was said, regardless of whether the audio recordings were of dialogue during the visit or monologue after the visit.",
        "",
    ]
    user_prompt = [
        "The recording takes place in a medical setting, specifically related to a patient's visit with a clinician.",
        "",
        "These audio files contain recordings of a single visit.",
        "There is no overlap between the segments, so they should be regarded as a continuous flow and analyzed at once.",
        "",
        "Your task is to:",
        "1. label each voice if multiple voices are present.",
        "2. transcribe each speaker's words with maximum accuracy",
        "",
        "Present your findings in a JSON format within a Markdown code block:",
        "```json",
        '[\n {\n  "voice": "voice_X/voice_Y/.../voice_N",\n  "text": "the verbatim transcription of what the speaker said"\n }\n]',
        "```",
        "",
        "Then, review the discussion from the top and distinguish the role of the voices (patient, clinician, nurse, parents...) in the conversation, if there is only voice, assume this is the clinician",
        "",
        "Present your findings in a JSON format within a Markdown code block:",
        "```json",
        '[\n {\n  "speaker": "Patient/Clinician/Nurse/...",\n  "voice": "voice_A/voice_B/.../voice_N"\n }\n]',
        "```",
        "",
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

    tested, settings, cache = helper_instance([])
    # no error
    # -- all JSON
    audio2texter.return_value.chat.side_effect = [JsonExtract(error="theError", has_error=False, content=[discussion, speakers])]
    result = tested.combine_and_speaker_detection(audio_chunks)
    expected = JsonExtract(error="", has_error=False, content=conversation)
    assert result == expected
    calls = [
        call(settings),
        call().set_system_prompt(system_prompt),
        call().set_user_prompt(user_prompt),
        call().add_audio(b'chunk1', 'mp3'),
        call().add_audio(b'chunk2', 'mp3'),
        call().chat([], True),
    ]
    assert audio2texter.mock_calls == calls
    reset_mocks()
    # -- only one JSON
    audio2texter.return_value.chat.side_effect = [JsonExtract(error="theError", has_error=False, content=[discussion])]
    result = tested.combine_and_speaker_detection(audio_chunks)
    expected = JsonExtract(error="partial response", has_error=True, content=[discussion])
    assert result == expected
    calls = [
        call(settings),
        call().set_system_prompt(system_prompt),
        call().set_user_prompt(user_prompt),
        call().add_audio(b'chunk1', 'mp3'),
        call().add_audio(b'chunk2', 'mp3'),
        call().chat([], True),
    ]
    assert audio2texter.mock_calls == calls
    reset_mocks()

    # with error
    audio2texter.return_value.chat.side_effect = [JsonExtract(error="theError", has_error=True, content=[discussion, speakers])]
    result = tested.combine_and_speaker_detection(audio_chunks)
    expected = JsonExtract(error="theError", has_error=True, content=[discussion, speakers])
    assert result == expected
    calls = [
        call(settings),
        call().set_system_prompt(system_prompt),
        call().set_user_prompt(user_prompt),
        call().add_audio(b'chunk1', 'mp3'),
        call().add_audio(b'chunk2', 'mp3'),
        call().chat([], True),
    ]
    assert audio2texter.mock_calls == calls
    reset_mocks()


@patch.object(Helper, "chatter")
@patch.object(AudioInterpreter, 'instruction_constraints')
@patch.object(AudioInterpreter, 'json_schema')
@patch.object(AudioInterpreter, 'instruction_definitions')
def test_detect_instructions(
        instruction_definitions,
        json_schema,
        instruction_constraints,
        chatter,
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
        for mock in mocks:
            mock.reset_mock()
        mocks[0].return_value.class_name.side_effect = ["First"]
        mocks[1].return_value.class_name.side_effect = ["Second"]
        mocks[2].return_value.class_name.side_effect = ["Third"]
        mocks[3].return_value.class_name.side_effect = ["Fourth"]
        mocks[0].return_value.instruction_description.side_effect = ["Description1"]
        mocks[1].return_value.instruction_description.side_effect = ["Description2"]
        mocks[2].return_value.instruction_description.side_effect = ["Description3"]
        mocks[3].return_value.instruction_description.side_effect = ["Description4"]

    system_prompts = [
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
        'Your response must be a JSON Markdown block with a list of objects: ',
        '{'
        '"uuid": "a unique identifier in this discussion", '
        '"instruction": "the instruction", '
        '"information": "the information associated with the instruction, grounded in the transcript with no embellishment or omission", '
        '"isNew": "the instruction is new for the discussion, as boolean", '
        '"isUpdated": "the instruction is an update of one already identified in the discussion, as boolean"'
        '}',
        '', 'The JSON will be validated with the schema:',
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
            "From among all previous segments of the transcript, the following instructions were identified",
            '```json',
            '[\n {'
            '\n  "uuid": "uuid1",'
            '\n  "instruction": "the instruction 1",'
            '\n  "information": "the information 1",'
            '\n  "isNew": false,'
            '\n  "isUpdated": false'
            '\n },\n {'
            '\n  "uuid": "uuid2",'
            '\n  "instruction": "the instruction 2",'
            '\n  "information": "the information 2",'
            '\n  "isNew": false,'
            '\n  "isUpdated": false'
            '\n }\n]',
            '```',
            'Include them in your response, with any necessary additional information.',
        ],
        "constraints": [
            'Here is your last response:',
            '```json',
            '[\n "response1"\n]',
            '```',
            '',
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
        Instruction(uuid="uuid1", instruction="the instruction 1", information="the information 1", is_new=True, is_updated=False),
        Instruction(uuid="uuid2", instruction="the instruction 2", information="the information 2", is_new=False, is_updated=True),
    ]
    reset_mocks()

    # allow updates
    tested, settings, cache = helper_instance(mocks)
    # -- no known instruction
    instruction_definitions.side_effect = ["theInstructionDefinition"]
    json_schema.side_effect = ["theJsonSchema"]
    instruction_constraints.side_effect = [["theConstraint1", "theConstraint2"]]
    chatter.return_value.single_conversation.side_effect = [["response1"], ["response2"]]
    result = tested.detect_instructions(discussion, [])
    expected = ["response2"]
    assert result == expected
    calls = [call()]
    assert instruction_definitions.mock_calls == calls
    calls = [call(['First', 'Second', 'Fourth'])]
    assert json_schema.mock_calls == calls
    calls = [call()]
    assert instruction_constraints.mock_calls == calls
    calls = [
        call(settings),
        call().single_conversation(system_prompts, user_prompts["noKnownInstructions"]),
        call(settings),
        call().single_conversation(system_prompts, user_prompts["constraints"]),
    ]
    assert chatter.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call(settings, cache, 'patientUuid', 'noteUuid', 'providerUuid'),
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
    chatter.return_value.single_conversation.side_effect = [["response1"], ["response2"]]
    result = tested.detect_instructions(discussion, [])
    expected = ["response1"]
    assert result == expected
    calls = [call()]
    assert instruction_definitions.mock_calls == calls
    calls = [call(['First', 'Second', 'Fourth'])]
    assert json_schema.mock_calls == calls
    calls = [call()]
    assert instruction_constraints.mock_calls == calls
    calls = [
        call(settings),
        call().single_conversation(system_prompts, user_prompts["noKnownInstructions"]),
    ]
    assert chatter.mock_calls == calls
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
    chatter.return_value.single_conversation.side_effect = [["response1"], ["response2"]]
    result = tested.detect_instructions(discussion, known_instructions)
    expected = ["response2"]
    assert result == expected
    calls = [call()]
    assert instruction_definitions.mock_calls == calls
    calls = [call(['First', 'Second', 'Fourth'])]
    assert json_schema.mock_calls == calls
    calls = [call()]
    assert instruction_constraints.mock_calls == calls
    calls = [
        call(settings),
        call().single_conversation(system_prompts, user_prompts["withKnownInstructions"]),
        call(settings),
        call().single_conversation(system_prompts, user_prompts["constraints"]),
    ]
    assert chatter.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = []
        if idx != 2:
            calls.extend([call().class_name()])
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()


@patch("hyperscribe.protocols.audio_interpreter.datetime", wraps=datetime)
@patch.object(Helper, "chatter")
def test_create_sdk_command_parameters(chatter, mock_datetime):
    mocks = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        chatter.reset_mock()
        mock_datetime.reset_mock()
        for mock in mocks:
            mock.reset_mock()
        mocks[0].return_value.class_name.side_effect = ["First"]
        mocks[1].return_value.class_name.side_effect = ["Second"]
        mocks[2].return_value.class_name.side_effect = ["Third"]
        mocks[3].return_value.class_name.side_effect = ["Fourth"]
        mocks[0].return_value.command_parameters.side_effect = [{"Command": "Parameters1"}]
        mocks[1].return_value.command_parameters.side_effect = [{"Command": "Parameters2"}]
        mocks[2].return_value.command_parameters.side_effect = [{"Command": "Parameters3"}]
        mocks[3].return_value.command_parameters.side_effect = [{"Command": "Parameters4"}]

    instruction = Instruction(uuid="theUuid", instruction="Second", information="theInformation", is_new=False, is_updated=True)
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
    reset_mocks()

    tested, settings, cache = helper_instance(mocks)
    # with response
    mock_datetime.now.side_effect = [datetime(2025, 2, 4, 7, 48, 21, tzinfo=timezone.utc)]
    chatter.return_value.single_conversation.side_effect = [["response1", "response2"]]
    result = tested.create_sdk_command_parameters(instruction)
    expected = instruction, "response1"
    assert result == expected
    calls = [
        call(settings),
        call().single_conversation(system_prompt, user_prompt),
    ]
    assert chatter.mock_calls == calls
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call(settings, cache, 'patientUuid', 'noteUuid', 'providerUuid'),
            call().__bool__(),
            call().is_available(),
        ]
        if idx != 2:
            calls.extend([
                call().class_name(),
                call().command_parameters(),
            ])
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()
    # without response
    mock_datetime.now.side_effect = [datetime(2025, 2, 4, 7, 48, 21, tzinfo=timezone.utc)]
    chatter.return_value.single_conversation.side_effect = [[]]
    result = tested.create_sdk_command_parameters(instruction)
    expected = instruction, None
    assert result == expected
    calls = [
        call(settings),
        call().single_conversation(system_prompt, user_prompt),
    ]
    assert chatter.mock_calls == calls
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = []
        if idx != 2:
            calls.extend([
                call().class_name(),
                call().command_parameters(),
            ])
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()


def test_create_sdk_command_from():
    mocks = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        for mock in mocks:
            mock.reset_mock()
        mocks[0].return_value.class_name.side_effect = ["First"]
        mocks[1].return_value.class_name.side_effect = ["Second"]
        mocks[2].return_value.class_name.side_effect = ["Third"]
        mocks[3].return_value.class_name.side_effect = ["Fourth"]
        mocks[0].return_value.command_from_json.side_effect = ["theCommand1"]
        mocks[1].return_value.command_from_json.side_effect = ["theCommand2"]
        mocks[2].return_value.command_from_json.side_effect = ["theCommand3"]
        mocks[3].return_value.command_from_json.side_effect = ["theCommand4"]

    reset_mocks()

    tests = [
        ("First", 0, "theCommand1"),
        ("Second", 1, "theCommand2"),
        ("Fourth", 3, "theCommand4"),
        ("Third", 4, None),
    ]
    for instruction, number, expected in tests:
        instruction = Instruction(uuid="theUuid", instruction=instruction, information="theInformation", is_new=False, is_updated=True)
        parameters = {"theKey": "theValue"}
        tested, settings, cache = helper_instance(mocks)
        result = tested.create_sdk_command_from(instruction, parameters)
        assert result == expected
        for idx, mock in enumerate(mocks):
            calls = [
                call(settings, cache, 'patientUuid', 'noteUuid', 'providerUuid'),
                call().__bool__(),
                call().is_available(),
            ]
            if idx < number + 1 and idx != 2:
                calls.extend([call().class_name()])
            if idx == number and idx != 2:
                calls.extend([call().command_from_json({'theKey': 'theValue'})])
            assert mock.mock_calls == calls, f"---> {idx}"
        reset_mocks()


def test_json_schema():
    tested = AudioInterpreter

    result = tested.json_schema(["Command1", "Command2"])
    expected = {
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'items': {
            'additionalProperties': False,
            'properties': {
                'information': {
                    'description': 'all relevant information extracted from the discussion explaining and/or defining the instruction',
                    'type': 'string',
                },
                'instruction': {
                    'enum': ['Command1', 'Command2'],
                    'type': 'string',
                },
                'isNew': {
                    'description': 'the instruction is new to the discussion',
                    'type': 'boolean',
                },
                'isUpdated': {
                    'description': 'the instruction is an update of an instruction previously identified in the discussion',
                    'type': 'boolean',
                },
                'uuid': {
                    'description': 'a unique identifier in this discussion',
                    'type': 'string',
                },
            },
            'required': ['uuid', 'instruction', 'information', 'isNew', 'isUpdated'],
            'type': 'object',
        },
        'type': 'array',
    }

    assert result == expected
