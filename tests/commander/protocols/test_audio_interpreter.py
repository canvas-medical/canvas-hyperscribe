from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, call

from commander.protocols.audio_interpreter import AudioInterpreter
from commander.protocols.commands.base import Base
from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.instruction import Instruction
from commander.protocols.structures.json_extract import JsonExtract
from commander.protocols.structures.line import Line
from commander.protocols.structures.settings import Settings


def helper_instance(mocks, updates: bool) -> AudioInterpreter:
    def reset_mocks():
        implemented_commands.reset_mocks()

    with patch.object(AudioInterpreter, 'implemented_commands') as implemented_commands:
        settings = Settings(
            openai_key="openaiKey",
            science_host="scienceHost",
            ontologies_host="ontologiesHost",
            pre_shared_key="preSharedKey",
            allow_update=updates,
        )
        if mocks:
            mocks[0].return_value.is_available.side_effect = [True]
            mocks[1].return_value.is_available.side_effect = [True]
            mocks[2].return_value.is_available.side_effect = [False]
            mocks[3].return_value.is_available.side_effect = [True]

        implemented_commands.side_effect = [mocks]

        instance = AudioInterpreter(settings, "patientUuid", "noteUuid", "providerUuid")
        calls = [call()]
        assert implemented_commands.mock_calls == calls
        reset_mocks()

        return instance


@patch.object(AudioInterpreter, 'implemented_commands')
def test___init__(implemented_commands):
    mocks = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        implemented_commands.reset_mocks()
        for mock in mocks:
            mock.reset_mock()

    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    mocks[0].return_value.is_available.side_effect = [True]
    mocks[1].return_value.is_available.side_effect = [True]
    mocks[2].return_value.is_available.side_effect = [False]
    mocks[3].return_value.is_available.side_effect = [True]
    implemented_commands.side_effect = [mocks]

    instance = AudioInterpreter(settings, "patientUuid", "noteUuid", "providerUuid")
    assert instance.settings == settings
    assert instance.patient_id == "patientUuid"
    assert instance.note_uuid == "noteUuid"

    calls = [call()]
    assert implemented_commands.mock_calls == calls
    for mock in mocks:
        calls = [
            call(settings, 'patientUuid', 'noteUuid', 'providerUuid'),
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

    tested = helper_instance(mocks, True)
    result = tested.instruction_definitions()
    expected = [
        {'information': 'Description1', 'instruction': 'First'},
        {'information': 'Description2', 'instruction': 'Second'},
        {'information': 'Description4', 'instruction': 'Fourth'},
    ]
    assert result == expected
    for idx, mock in enumerate(mocks):
        calls = [
            call(tested.settings, 'patientUuid', 'noteUuid', 'providerUuid'),
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

    tested = helper_instance(mocks, True)
    result = tested.instruction_constraints()
    expected = ["Constraints1", "Constraints4"]
    assert result == expected
    for idx, mock in enumerate(mocks):
        calls = [
            call(tested.settings, 'patientUuid', 'noteUuid', 'providerUuid'),
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

    tested = helper_instance(mocks, True)
    result = tested.command_structures()
    expected = {
        'First': 'Parameters1',
        'Fourth': 'Parameters4',
        'Second': 'Parameters2',
    }
    assert result == expected
    for idx, mock in enumerate(mocks):
        calls = [
            call(tested.settings, 'patientUuid', 'noteUuid', 'providerUuid'),
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


def test_combine_and_speaker_detection():
    with patch("commander.protocols.audio_interpreter.OpenaiChat") as chat:
        def reset_mocks():
            chat.reset_mock()

        discussion = [
            {"voice": "voice3", "text": "the text A"},
            {"voice": "voice2", "text": "the text B"},
            {"voice": "voice1", "text": "the text C"},
            {"voice": "voice2", "text": "the text D"},
            {"voice": "voice2", "text": "the text E"},
            {"voice": "voice1", "text": "the text F"},
            {"voice": "voice2", "text": "the text G"},
            {"voice": "voice3", "text": "the text H"},
        ]
        speakers = [
            {"voice": "voice1", "speaker": "doctor"},
            {"voice": "voice2", "speaker": "patient"},
            {"voice": "voice3", "speaker": "nurse"},
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

        test = helper_instance([], True)
        # no error
        # -- all JSON
        chat.return_value.chat.side_effect = [JsonExtract(error="theError", has_error=False, content=[discussion, speakers])]
        result = test.combine_and_speaker_detection(audio_chunks)
        expected = JsonExtract(error="", has_error=False, content=conversation)
        assert result == expected
        calls = [
            call('openaiKey', 'gpt-4o-audio-preview'),
            call().add_audio(b'chunk1', 'mp3'),
            call().add_audio(b'chunk2', 'mp3'),
            call().chat(True),
        ]
        assert chat.mock_calls == calls, f"---> {chat.mock_calls}"
        reset_mocks()
        # -- only one JSON
        chat.return_value.chat.side_effect = [JsonExtract(error="theError", has_error=False, content=[discussion])]
        result = test.combine_and_speaker_detection(audio_chunks)
        expected = JsonExtract(error="partial response", has_error=True, content=[discussion])
        assert result == expected
        calls = [
            call('openaiKey', 'gpt-4o-audio-preview'),
            call().add_audio(b'chunk1', 'mp3'),
            call().add_audio(b'chunk2', 'mp3'),
            call().chat(True),
        ]
        assert chat.mock_calls == calls, f"---> {chat.mock_calls}"
        reset_mocks()

        # with error
        chat.return_value.chat.side_effect = [JsonExtract(error="theError", has_error=True, content=[discussion, speakers])]
        result = test.combine_and_speaker_detection(audio_chunks)
        expected = JsonExtract(error="theError", has_error=True, content=[discussion, speakers])
        assert result == expected
        calls = [
            call('openaiKey', 'gpt-4o-audio-preview'),
            call().add_audio(b'chunk1', 'mp3'),
            call().add_audio(b'chunk2', 'mp3'),
            call().chat(True),
        ]
        assert chat.mock_calls == calls, f"---> {chat.mock_calls}"
        reset_mocks()


@patch.object(OpenaiChat, "single_conversation")
@patch.object(AudioInterpreter, 'instruction_constraints')
@patch.object(AudioInterpreter, 'json_schema')
@patch.object(AudioInterpreter, 'instruction_definitions')
def test_detect_instructions(
        instruction_definitions,
        json_schema,
        instruction_constraints,
        single_conversation,
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
        single_conversation.reset_mock()
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

    system_prompts = {
        "updatesOk": [
            'The conversation is in the medical context.',
            'The user will submit the transcript of the visit of a patient with a healthcare provider.',
            'The user needs to extract and store the relevant information in their software using several commands as described below.',
            'Your task is to help the user by identifying the instructions and the linked information, regardless of their location in the transcript.',
            '', 'The instructions are limited to:',
            '```json',
            '"theInstructionDefinition"',
            '```',
            '',
            'Your response has to be a JSON Markdown block with a list of objects: ',
            '{'
            '"uuid": "a unique identifier in this discussion", '
            '"instruction": "the instruction", '
            '"information": "any information related to the instruction", '
            '"isNew": "the instruction is new for the discussion, as boolean", '
            '"isUpdated": "the instruction is an update of one already identified in the discussion, as boolean"'
            '}',
            '', 'The JSON will be validated with the schema:',
            '```json',
            '"theJsonSchema"',
            '```',
            '',
        ],
        "updatesNo": [
            'The conversation is in the medical context.',
            'The user will submit the transcript of the visit of a patient with a healthcare provider.',
            'The user needs to extract and store the relevant information in their software using several commands as described below.',
            'Your task is to help the user by identifying the instructions and the linked information, regardless of their location in the transcript.',
            '', 'The instructions are limited to:',
            '```json',
            '"theInstructionDefinition"',
            '```',
            '',
            'Your response has to be a JSON Markdown block with a list of objects: ',
            '{'
            '"uuid": "a unique identifier in this discussion", '
            '"instruction": "the instruction", '
            '"information": "any information related to the instruction"'
            '}',
            '', 'The JSON will be validated with the schema:',
            '```json',
            '"theJsonSchema"',
            '```',
            '',
        ],
    }
    user_prompts = {
        "noKnownInstructions": [
            'Below is a part of the transcript of the visit of a patient with a healthcare provider.',
            'What are the instructions I need to add to my software to correctly record the visit?',
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
            'Below is a part of the transcript of the visit of a patient with a healthcare provider.',
            'What are the instructions I need to add to my software to correctly record the visit?',
            '```json',
            '['
            '\n {\n  "speaker": "personA",\n  "text": "the text 1"\n },'
            '\n {\n  "speaker": "personB",\n  "text": "the text 2"\n },'
            '\n {\n  "speaker": "personA",\n  "text": "the text 3"\n }'
            '\n]',
            '```',
            '',
            'From previous parts of the transcript, the following instructions were identified',
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
        "withKnownInstructionsNoUpdate": [
            'Below is a part of the transcript of the visit of a patient with a healthcare provider.',
            'What are the instructions I need to add to my software to correctly record the visit?',
            '```json',
            '['
            '\n {\n  "speaker": "personA",\n  "text": "the text 1"\n },'
            '\n {\n  "speaker": "personB",\n  "text": "the text 2"\n },'
            '\n {\n  "speaker": "personA",\n  "text": "the text 3"\n }'
            '\n]',
            '```',
            '',
            'From previous parts of the transcript, the following instructions were identified',
            '```json',
            '[\n {'
            '\n  "uuid": "uuid1",'
            '\n  "instruction": "the instruction 1",'
            '\n  "information": "the information 1"'
            '\n },\n {'
            '\n  "uuid": "uuid2",'
            '\n  "instruction": "the instruction 2",'
            '\n  "information": "the information 2"'
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
    tested = helper_instance(mocks, True)
    # -- no known instruction
    instruction_definitions.side_effect = ["theInstructionDefinition"]
    json_schema.side_effect = ["theJsonSchema"]
    instruction_constraints.side_effect = [["theConstraint1", "theConstraint2"]]
    single_conversation.side_effect = [["response1"], ["response2"]]
    result = tested.detect_instructions(discussion, [])
    expected = ["response2"]
    assert result == expected
    calls = [call()]
    assert instruction_definitions.mock_calls == calls
    calls = [call(['First', 'Second', 'Fourth'], True)]
    assert json_schema.mock_calls == calls
    calls = [call()]
    assert instruction_constraints.mock_calls == calls
    calls = [
        call('openaiKey', system_prompts["updatesOk"], user_prompts["noKnownInstructions"]),
        call('openaiKey', system_prompts["updatesOk"], user_prompts["constraints"]),
    ]
    assert single_conversation.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call(tested.settings, 'patientUuid', 'noteUuid', 'providerUuid'),
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
    single_conversation.side_effect = [["response1"], ["response2"]]
    result = tested.detect_instructions(discussion, [])
    expected = ["response1"]
    assert result == expected
    calls = [call()]
    assert instruction_definitions.mock_calls == calls
    calls = [call(['First', 'Second', 'Fourth'], True)]
    assert json_schema.mock_calls == calls
    calls = [call()]
    assert instruction_constraints.mock_calls == calls
    calls = [
        call('openaiKey', system_prompts["updatesOk"], user_prompts["noKnownInstructions"]),
    ]
    assert single_conversation.mock_calls == calls
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
    single_conversation.side_effect = [["response1"], ["response2"]]
    result = tested.detect_instructions(discussion, known_instructions)
    expected = ["response2"]
    assert result == expected
    calls = [call()]
    assert instruction_definitions.mock_calls == calls
    calls = [call(['First', 'Second', 'Fourth'], True)]
    assert json_schema.mock_calls == calls
    calls = [call()]
    assert instruction_constraints.mock_calls == calls
    calls = [
        call('openaiKey', system_prompts["updatesOk"], user_prompts["withKnownInstructions"]),
        call('openaiKey', system_prompts["updatesOk"], user_prompts["constraints"]),
    ]
    assert single_conversation.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = []
        if idx != 2:
            calls.extend([call().class_name()])
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()

    # no updates
    tested = helper_instance(mocks, False)
    # -- no known instruction
    instruction_definitions.side_effect = ["theInstructionDefinition"]
    json_schema.side_effect = ["theJsonSchema"]
    instruction_constraints.side_effect = [["theConstraint1", "theConstraint2"]]
    single_conversation.side_effect = [["response1"], ["response2"]]
    result = tested.detect_instructions(discussion, [])
    expected = ["response2"]
    assert result == expected
    calls = [call()]
    assert instruction_definitions.mock_calls == calls
    calls = [call(['First', 'Second', 'Fourth'], False)]
    assert json_schema.mock_calls == calls
    calls = [call()]
    assert instruction_constraints.mock_calls == calls
    calls = [
        call('openaiKey', system_prompts["updatesNo"], user_prompts["noKnownInstructions"]),
        call('openaiKey', system_prompts["updatesNo"], user_prompts["constraints"]),
    ]
    assert single_conversation.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call(tested.settings, 'patientUuid', 'noteUuid', 'providerUuid'),
            call().__bool__(),
            call().is_available(),
        ]
        if idx != 2:
            calls.extend([call().class_name()])
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()
    # -- with known instructions
    instruction_definitions.side_effect = ["theInstructionDefinition"]
    json_schema.side_effect = ["theJsonSchema"]
    instruction_constraints.side_effect = [["theConstraint1", "theConstraint2"]]
    single_conversation.side_effect = [["response1"], ["response2"]]
    result = tested.detect_instructions(discussion, known_instructions)
    expected = ["response2"]
    assert result == expected
    calls = [call()]
    assert instruction_definitions.mock_calls == calls
    calls = [call(['First', 'Second', 'Fourth'], False)]
    assert json_schema.mock_calls == calls
    calls = [call()]
    assert instruction_constraints.mock_calls == calls
    calls = [
        call('openaiKey', system_prompts["updatesNo"], user_prompts["withKnownInstructionsNoUpdate"]),
        call('openaiKey', system_prompts["updatesNo"], user_prompts["constraints"]),
    ]
    assert single_conversation.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = []
        if idx != 2:
            calls.extend([call().class_name()])
        assert mock.mock_calls == calls, f"---> {idx}"
    reset_mocks()


@patch("commander.protocols.audio_interpreter.datetime", wraps=datetime)
@patch.object(OpenaiChat, "single_conversation")
def test_create_sdk_command_parameters(single_conversation, mock_datetime):
    mocks = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        single_conversation.reset_mock()
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
        "The conversation is in the medical context.",
        "During a visit of a patient with a healthcare provider, the user has identified instructions to record in its software.",
        "The user will submit an instruction, i.e. an action and the related information, as well as the structure of the associated command.",
        "Your task is to help the user by identifying the actual data of the structured command.",
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

    tested = helper_instance(mocks, True)
    # with response
    mock_datetime.now.side_effect = [datetime(2025, 2, 4, 7, 48, 21, tzinfo=timezone.utc)]
    single_conversation.side_effect = [["response1", "response2"]]
    result = tested.create_sdk_command_parameters(instruction)
    expected = instruction, "response1"
    assert result == expected
    calls = [call('openaiKey', system_prompt, user_prompt)]
    assert single_conversation.mock_calls == calls
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    for idx, mock in enumerate(mocks):
        calls = [
            call(tested.settings, 'patientUuid', 'noteUuid', 'providerUuid'),
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
    single_conversation.side_effect = [[]]
    result = tested.create_sdk_command_parameters(instruction)
    expected = instruction, None
    assert result == expected
    calls = [call('openaiKey', system_prompt, user_prompt)]
    assert single_conversation.mock_calls == calls
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
        tested = helper_instance(mocks, True)
        result = tested.create_sdk_command_from(instruction, parameters)
        assert result == expected
        for idx, mock in enumerate(mocks):
            calls = [
                call(tested.settings, 'patientUuid', 'noteUuid', 'providerUuid'),
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

    # no update
    result = tested.json_schema(["Command1", "Command2"], False)
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
                'uuid': {
                    'description': 'a unique identifier in this discussion',
                    'type': 'string',
                },
            },
            'required': ['uuid', 'instruction', 'information'],
            'type': 'object',
        },
        'type': 'array',
    }

    assert result == expected

    # with update
    result = tested.json_schema(["Command1", "Command2"], True)
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


def test_implemented_commands():
    tested = AudioInterpreter
    result = tested.implemented_commands()
    for command in result:
        assert issubclass(command, Base)
    commands = [c.class_name() for c in result]
    expected = [
        'Allergy',
        'Assess',
        'CloseGoal',
        'Diagnose',
        'FamilyHistory',
        'Goal',
        'HistoryOfPresentIllness',
        'Immunize',
        'Instruct',
        'LabOrder',
        'MedicalHistory',
        'Medication',
        'PhysicalExam',
        'Plan',
        'Prescription',
        'Questionnaire',
        'ReasonForVisit',
        'Refill',
        'RemoveAllergy',
        'StopMedication',
        'SurgeryHistory',
        'Task',
        'UpdateDiagnose',
        'UpdateGoal',
        'Vitals',
    ]
    assert commands == expected


def test_schema_key2instruction():
    tested = AudioInterpreter
    result = tested.schema_key2instruction()
    expected = {
        'allergy': 'Allergy',
        'assess': 'Assess',
        'closeGoal': 'CloseGoal',
        'diagnose': 'Diagnose',
        'exam': 'PhysicalExam',
        'familyHistory': 'FamilyHistory',
        'goal': 'Goal',
        'hpi': 'HistoryOfPresentIllness',
        'immunize': 'Immunize',
        'instruct': 'Instruct',
        'labOrder': 'LabOrder',
        'medicalHistory': 'MedicalHistory',
        'medicationStatement': 'Medication',
        'plan': 'Plan',
        'prescribe': 'Prescription',
        'questionnaire': 'Questionnaire',
        'reasonForVisit': 'ReasonForVisit',
        'refill': 'Refill',
        'removeAllergy': 'RemoveAllergy',
        'stopMedication': 'StopMedication',
        'surgicalHistory': 'SurgeryHistory',
        'task': 'Task',
        'updateDiagnosis': 'UpdateDiagnose',
        'updateGoal': 'UpdateGoal',
        'vitals': 'Vitals',
    }
    assert result == expected
