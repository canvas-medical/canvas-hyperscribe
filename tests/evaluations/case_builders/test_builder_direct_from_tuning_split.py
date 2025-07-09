import json
from pathlib import Path
from unittest.mock import patch, call, MagicMock

from evaluations.case_builders.builder_direct_from_tuning import BuilderDirectFromTuning
from evaluations.case_builders.builder_direct_from_tuning_split import BuilderDirectFromTuningSplit
from evaluations.structures.case_exchange import CaseExchange
from evaluations.structures.case_exchange_summary import CaseExchangeSummary
from evaluations.structures.topical_exchange import TopicalExchange
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import MockFile
from tests.helper import is_constant


def helper_instance() -> BuilderDirectFromTuningSplit:
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        science_host='theScienceHost',
        ontologies_host='theOntologiesHost',
        pre_shared_key='thePreSharedKey',
        structured_rfv=True,
        audit_llm=False,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
    )
    s3_credentials = AwsS3Credentials(
        aws_key='theKey',
        aws_secret='theSecret',
        region='theRegion',
        bucket='theBucket',
    )
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return BuilderDirectFromTuningSplit(settings, s3_credentials, identification, Path("/some/path"), 45, True)


def test_class():
    tested = BuilderDirectFromTuningSplit
    assert issubclass(tested, BuilderDirectFromTuning)
    constants = {
        "MAX_WORDS_PER_COMPACTED_TRANSCRIPT": 1000,
    }
    assert is_constant(tested, constants)


def test__parameters():
    argument_parser = MagicMock()

    def reset_mocks():
        argument_parser.reset_mock()

    tested = BuilderDirectFromTuningSplit
    tested._parameters(argument_parser)
    calls = [call.add_argument('--direct-split', action='store_true')]
    assert argument_parser.mock_calls == calls
    reset_mocks()


def test_compact_transcripts():
    files = [
        # original files
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
        # compacted files
        MagicMock(), MagicMock(), MagicMock(),
    ]
    buffers = [
        MockFile(), MockFile(), MockFile(), MockFile(), MockFile(), MockFile(), MockFile(),
        MockFile(mode="w"), MockFile(mode="w"), MockFile(mode="w"),
    ]

    def reset_mocks():
        for idx, item in enumerate(files):
            item.reset_mock()
            item.open.return_value = buffers[idx]
            if idx == 0:
                item.parent.__truediv__.side_effect = files[7:]

            if idx < 7:
                buffers[idx].content = json.dumps([
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5"},
                    {"speaker": "speaker2", "text": "word6 word7 word8"},
                    {"speaker": "speaker3", "text": "word9 word10"},
                ])
            else:
                buffers[idx].content = ""

    reset_mocks()

    tested = BuilderDirectFromTuningSplit
    # 30 words per compact file
    with patch.object(BuilderDirectFromTuningSplit, "MAX_WORDS_PER_COMPACTED_TRANSCRIPT", 30):
        result = tested.compact_transcripts(files[:7])
        expected = files[7:10]
        assert result == expected

        for index, item in enumerate(files):
            if index == 0:
                calls = [
                    call.parent.__truediv__('transcript_compacted_000.json'),
                    call.open('r'),
                    call.parent.__truediv__('transcript_compacted_001.json'),
                    call.parent.__truediv__('transcript_compacted_002.json'),
                ]
            elif index < 7:
                calls = [call.open('r')]
            elif index in [7, 8]:
                calls = [
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                ]
            elif index in [9]:
                calls = [
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                ]
            else:
                calls = []
            assert item.mock_calls == calls

            if index < 7:
                exp_content = json.dumps([
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5"},
                    {"speaker": "speaker2", "text": "word6 word7 word8"},
                    {"speaker": "speaker3", "text": "word9 word10"},
                ])
            elif index in [7]:
                exp_content = json.dumps([
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 1},
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 1},
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 1},
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 2},
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 2},
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 2},
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 3},
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 3},
                ], indent=2)
            elif index in [8]:
                exp_content = json.dumps([
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 3},
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 4},
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 4},
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 4},
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 5},
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 5},
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 5},
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 6},
                ], indent=2)
            elif index in [9]:
                exp_content = json.dumps([
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 6},
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 6},
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 7},
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 7},
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 7},
                ], indent=2)
            else:
                exp_content = ""
            assert buffers[index].content == exp_content
        reset_mocks()

    # 50 words per compact file
    with patch.object(BuilderDirectFromTuningSplit, "MAX_WORDS_PER_COMPACTED_TRANSCRIPT", 50):
        result = tested.compact_transcripts(files[:7])
        expected = files[7:9]
        assert result == expected

        for index, item in enumerate(files):
            if index == 0:
                calls = [
                    call.parent.__truediv__('transcript_compacted_000.json'),
                    call.open('r'),
                    call.parent.__truediv__('transcript_compacted_001.json'),
                ]
            elif index < 7:
                calls = [call.open('r')]
            elif index in [7]:
                calls = [
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                ]
            elif index in [8]:
                calls = [
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                    call.open('w'),
                ]
            else:
                calls = []
            assert item.mock_calls == calls

            if index < 7:
                exp_content = json.dumps([
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5"},
                    {"speaker": "speaker2", "text": "word6 word7 word8"},
                    {"speaker": "speaker3", "text": "word9 word10"},
                ])
            elif index in [7]:
                exp_content = json.dumps([
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 1},
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 1},
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 1},
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 2},
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 2},
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 2},
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 3},
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 3},
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 3},
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 4},
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 4},
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 4},
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 5},
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 5},
                ], indent=2)
            elif index in [8]:
                exp_content = json.dumps([
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 5},
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 6},
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 6},
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 6},
                    {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 7},
                    {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 7},
                    {"speaker": "speaker3", "text": "word9 word10", "chunk": 7},
                ], indent=2)
            else:
                exp_content = ""
            assert buffers[index].content == exp_content
        reset_mocks()


def test_schema_topical_exchanges():
    tested = BuilderDirectFromTuningSplit
    result = tested.schema_topical_exchanges()
    expected = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "speaker": {"type": "string"},
                "text": {"type": "string", "minLength": 1},
                "chunk": {"type": "integer"},
                "topic": {"type": "integer"},
            },
            "required": ["speaker", "text", "chunk", "topic"],
            "additionalProperties": False,
        },
    }
    assert result == expected


def test_schema_summary():
    tested = BuilderDirectFromTuningSplit
    result = tested.schema_summary()
    expected = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "minItems": 1,
        "items": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9 ]+$",
                    "description": "a concise title composed with 25 to 40 characters",
                },
                "summary": {
                    "type": "string",
                    "description": "a summary of the exchange",
                },
            },
            "required": ["title", "summary"],
            "additionalProperties": False,
        },
    }
    assert result == expected


@patch("evaluations.case_builders.builder_direct_from_tuning_split.LimitedCache")
@patch("evaluations.case_builders.builder_direct_from_tuning_split.ImplementedCommands")
@patch("evaluations.case_builders.builder_direct_from_tuning_split.AudioInterpreter")
@patch.object(BuilderDirectFromTuningSplit, "generate_case")
@patch.object(BuilderDirectFromTuningSplit, "topical_exchange_summary")
@patch.object(BuilderDirectFromTuningSplit, "detect_topical_exchanges")
@patch.object(BuilderDirectFromTuningSplit, "anonymize_transcripts")
@patch.object(BuilderDirectFromTuningSplit, "compact_transcripts")
@patch.object(BuilderDirectFromTuningSplit, "create_transcripts")
@patch.object(BuilderDirectFromTuningSplit, "split_audio")
@patch.object(BuilderDirectFromTuningSplit, "collated_webm_to_mp3")
def test__run(
        collated_webm_to_mp3,
        split_audio,
        create_transcripts,
        compact_transcripts,
        anonymize_transcripts,
        detect_topical_exchanges,
        topical_exchange_summary,
        generate_case,
        audio_interpreter,
        implemented_commands,
        limited_cache,
        capsys,
):
    full_mp3_file = MagicMock()
    json_file = MagicMock()
    json_buffer = MockFile('{"limited":"cache"}')

    def reset_mocks():
        collated_webm_to_mp3.reset_mock()
        split_audio.reset_mock()
        create_transcripts.reset_mock()
        compact_transcripts.reset_mock()
        anonymize_transcripts.reset_mock()
        detect_topical_exchanges.reset_mock()
        topical_exchange_summary.reset_mock()
        generate_case.reset_mock()
        audio_interpreter.reset_mock()
        implemented_commands.reset_mock()
        limited_cache.reset_mock()

        full_mp3_file.reset_mock()
        json_file.reset_mock()

    tested = helper_instance()

    topical_exchanges = [
        TopicalExchange(speaker="theSpeaker1", text="theText1", chunk=1, topic=1),
        TopicalExchange(speaker="theSpeaker2", text="theText2", chunk=1, topic=1),
        TopicalExchange(speaker="theSpeaker1", text="theText3", chunk=1, topic=2),
        TopicalExchange(speaker="theSpeaker2", text="theText4", chunk=2, topic=2),
        TopicalExchange(speaker="theSpeaker2", text="theText5", chunk=2, topic=3),
        TopicalExchange(speaker="theSpeaker1", text="theText6", chunk=2, topic=3),
        TopicalExchange(speaker="theSpeaker1", text="theText7", chunk=4, topic=3),
        TopicalExchange(speaker="theSpeaker1", text="theText7", chunk=5, topic=4),
    ]
    case_exchanges = [
        CaseExchange(speaker="theSpeaker1", text="theText1", chunk=1),
        CaseExchange(speaker="theSpeaker2", text="theText2", chunk=1),
        CaseExchange(speaker="theSpeaker1", text="theText3", chunk=1),
        CaseExchange(speaker="theSpeaker2", text="theText4", chunk=2),
        CaseExchange(speaker="theSpeaker2", text="theText5", chunk=2),
        CaseExchange(speaker="theSpeaker1", text="theText6", chunk=2),
        CaseExchange(speaker="theSpeaker1", text="theText7", chunk=4),
        CaseExchange(speaker="theSpeaker1", text="theText7", chunk=5),
    ]
    exchange_summaries = [
        CaseExchangeSummary(title="title1", summary="summary1"),
        CaseExchangeSummary(title="title2", summary="summary2"),
        CaseExchangeSummary(title="title3", summary="summary3"),
        CaseExchangeSummary(title="title4", summary="summary4"),
    ]

    split_audio.side_effect = ["theSplitAudioFiles"]
    create_transcripts.side_effect = ["theCreatedTranscripts"]
    compact_transcripts.side_effect = ["theCompactedTranscripts"]
    anonymize_transcripts.side_effect = ["theAnonymizedTranscripts"]
    detect_topical_exchanges.side_effect = [topical_exchanges]
    topical_exchange_summary.side_effect = exchange_summaries
    generate_case.side_effect = [
        "theGeneratedInstructions1",
        "theGeneratedInstructions2",
        "theGeneratedInstructions3",
        "theGeneratedInstructions4",
    ]
    audio_interpreter.side_effect = ["theAudioInterpreter"]
    implemented_commands.schema_key2instruction.side_effect = ["schemaKey2Instruction"]

    collated_webm_to_mp3.side_effect = [full_mp3_file]
    json_file.open.side_effect = [json_buffer]
    full_mp3_file.parent.__truediv__.side_effect = [json_file]

    tested._run()

    exp_out = ("collect webm, collate to mp3...\n"
               "split mp3 into chunks...\n"
               "create transcripts...\n"
               "de-identification transcripts...\n"
               "detect topical exchanges...\n"
               "build case for topic title1:\n"
               "build case for topic title2:\n"
               "build case for topic title3:\n"
               "build case for topic title4:\n")
    assert capsys.readouterr().out == exp_out

    calls = [call()]
    assert collated_webm_to_mp3.mock_calls == calls
    calls = [call(full_mp3_file)]
    assert split_audio.mock_calls == calls
    calls = [call('theSplitAudioFiles', 'theAudioInterpreter')]
    assert create_transcripts.mock_calls == calls
    calls = [call('theCreatedTranscripts')]
    assert compact_transcripts.mock_calls == calls
    calls = [call('theCompactedTranscripts')]
    assert anonymize_transcripts.mock_calls == calls
    calls = [call('theAnonymizedTranscripts')]
    assert detect_topical_exchanges.mock_calls == calls
    calls = [
        call([topical_exchanges[i] for i in [0, 1]], full_mp3_file.parent),
        call([topical_exchanges[i] for i in [2, 3]], full_mp3_file.parent),
        call([topical_exchanges[i] for i in [4, 5, 6]], full_mp3_file.parent),
        call([topical_exchanges[i] for i in [7]], full_mp3_file.parent),
    ]
    assert topical_exchange_summary.mock_calls == calls
    calls = [
        call(limited_cache.load_from_json.return_value, exchange_summaries[0], [case_exchanges[i] for i in [0, 1]]),
        call(limited_cache.load_from_json.return_value, exchange_summaries[1], [case_exchanges[i] for i in [2, 3]]),
        call(limited_cache.load_from_json.return_value, exchange_summaries[2], [case_exchanges[i] for i in [4, 5, 6]]),
        call(limited_cache.load_from_json.return_value, exchange_summaries[3], [case_exchanges[i] for i in [7]]),
    ]
    assert generate_case.mock_calls == calls
    calls = [call(
        tested.settings,
        tested.s3_credentials,
        limited_cache.load_from_json.return_value,
        tested.identification,
    )]
    assert audio_interpreter.mock_calls == calls
    calls = [call.schema_key2instruction()]
    assert implemented_commands.mock_calls == calls
    calls = [
        call.load_from_json({'limited': 'cache'}),
        call.load_from_json().add_instructions_as_staged_commands('theGeneratedInstructions1', 'schemaKey2Instruction'),
        call.load_from_json().add_instructions_as_staged_commands('theGeneratedInstructions2', 'schemaKey2Instruction'),
        call.load_from_json().add_instructions_as_staged_commands('theGeneratedInstructions3', 'schemaKey2Instruction'),
        call.load_from_json().add_instructions_as_staged_commands('theGeneratedInstructions4', 'schemaKey2Instruction')
    ]
    assert limited_cache.mock_calls == calls
    calls = [call.parent.__truediv__('limited_chart.json')]
    assert full_mp3_file.mock_calls == calls
    calls = [call.open('r')]
    assert json_file.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_direct_from_tuning_split.uuid4")
@patch("evaluations.case_builders.builder_direct_from_tuning_split.Helper")
@patch("evaluations.case_builders.builder_direct_from_tuning_split.MemoryLog")
@patch.object(BuilderDirectFromTuningSplit, "schema_summary")
def test_topical_exchange_summary(schema_summary, memory_log, helper, uuid4):
    temporary_folder = MagicMock()
    summary_file = MagicMock()
    buffer = MockFile()

    def reset_mocks(mode):
        schema_summary.reset_mock()
        memory_log.reset_mock()
        helper.reset_mock()
        uuid4.reset_mock()

        temporary_folder.reset_mock()
        summary_file.reset_mock()
        summary_file.open.side_effect = [buffer]
        buffer.mode = mode
        buffer.content = json.dumps([{"title": "the_title_abcd123", "summary": "theSummary0"}])

    reset_mocks("w")

    topical_exchanges = [
        TopicalExchange(speaker="theSpeaker2", text="theText5", chunk=2, topic=3),
        TopicalExchange(speaker="theSpeaker1", text="theText6", chunk=2, topic=3),
        TopicalExchange(speaker="theSpeaker1", text="theText7", chunk=4, topic=3),
    ]
    system_prompt = [
        'The conversation is in the medical context, and related to a visit of a patient with a healthcare provider.',
        '',
        'Your task is to give a meaningful title to a provided sub set of the discussion, previously identified as a coherent topical exchange.',
        '',
        'The title should be as concise as possible, composed of about 25 to 40 characters.',
        '',
        'Format your response following the JSON Schema:',
        '```json',
        '{\n "schema": "summary1"\n}',
        '```',
        '',
    ]
    user_prompt = [
        'Coherent topical exchange:',
        '```json',
        '['
        '\n {\n  "speaker": "theSpeaker2",\n  "text": "theText5",\n  "chunk": 2,\n  "topic": 3\n },'
        '\n {\n  "speaker": "theSpeaker1",\n  "text": "theText6",\n  "chunk": 2,\n  "topic": 3\n },'
        '\n {\n  "speaker": "theSpeaker1",\n  "text": "theText7",\n  "chunk": 4,\n  "topic": 3\n }'
        '\n]',
        '```',
        '',
        '',
        'Follow rigorously the instructions and provide the requested information using the mentioned JSON Schema within a Markdown code block:',
        '```json',
        'YOUR JSON OUTPUT HERE',
        '```'
    ]

    tested = helper_instance()

    # forced refresh or json does not exist
    tested.force_refresh = True
    for test in [True, False]:
        # -- with error or empty response
        summary_file.exists.side_effect = [not test]
        temporary_folder.__truediv__.side_effect = [summary_file]
        memory_log.instance.side_effect = ["theMemoryLog"]
        schema_summary.side_effect = [{"schema": "summary1"}, {"schema": "summary2"}]
        uuid4.side_effect = ["12345abcd54321"]
        helper.chatter.return_value.chat.side_effect = [
            JsonExtract(error="", has_error=False, content=[[]]),
        ]
        result = tested.topical_exchange_summary(topical_exchanges, temporary_folder)
        expected = CaseExchangeSummary(title="12345abcd54321", summary="")
        assert result == expected
        exp_content = [{"title": "12345abcd54321", "summary": ""}]
        assert json.loads(buffer.content) == exp_content

        calls = [call(), call()]
        assert schema_summary.mock_calls == calls
        calls = [call.instance(tested.identification, 'topical_exchange_naming', tested.s3_credentials)]
        assert memory_log.mock_calls == calls
        calls = [
            call.chatter(tested.settings, "theMemoryLog"),
            call.chatter().set_system_prompt(system_prompt),
            call.chatter().set_user_prompt(user_prompt),
            call.chatter().chat([{'schema': 'summary2'}]),
        ]
        assert helper.mock_calls == calls
        calls = [call()]
        assert uuid4.mock_calls == calls
        calls = [call.__truediv__('topic_summary_003.json')]
        assert temporary_folder.mock_calls == calls
        calls = [
            call.exists(),
            call.open('w'),
        ]
        assert summary_file.mock_calls == calls

        reset_mocks("w")

        # -- no error and no empty response
        summary_file.exists.side_effect = [not test]
        temporary_folder.__truediv__.side_effect = [summary_file]
        memory_log.instance.side_effect = ["theMemoryLog"]
        schema_summary.side_effect = [{"schema": "summary1"}, {"schema": "summary2"}]
        uuid4.side_effect = ["12345abcd54321"]
        helper.chatter.return_value.chat.side_effect = [
            JsonExtract(
                error="",
                has_error=False,
                content=[[
                    {"title": "The Title 1", "summary": "Some Summary 1"},
                    {"title": "The Title 2", "summary": "Some Summary 2"},
                ]],
            ),
        ]
        result = tested.topical_exchange_summary(topical_exchanges, temporary_folder)
        expected = CaseExchangeSummary(
            title="the_title_1_12345abcd5",
            summary="Some Summary 1",
        )
        assert result == expected
        exp_content = [{"title": "the_title_1_12345abcd5", "summary": "Some Summary 1"}]
        assert json.loads(buffer.content) == exp_content

        calls = [call(), call()]
        assert schema_summary.mock_calls == calls
        calls = [call.instance(tested.identification, 'topical_exchange_naming', tested.s3_credentials)]
        assert memory_log.mock_calls == calls
        calls = [
            call.chatter(tested.settings, "theMemoryLog"),
            call.chatter().set_system_prompt(system_prompt),
            call.chatter().set_user_prompt(user_prompt),
            call.chatter().chat([{'schema': 'summary2'}]),
        ]
        assert helper.mock_calls == calls
        calls = [call()]
        assert uuid4.mock_calls == calls
        calls = [call.__truediv__('topic_summary_003.json')]
        assert temporary_folder.mock_calls == calls
        calls = [
            call.exists(),
            call.open('w'),
        ]
        assert summary_file.mock_calls == calls

        reset_mocks("w")

    # no forced refresh and json does exist
    reset_mocks("r")
    tested.force_refresh = False
    summary_file.exists.side_effect = [True]

    temporary_folder.__truediv__.side_effect = [summary_file]
    memory_log.instance.side_effect = []
    helper.chatter.return_value.chat.side_effect = []
    schema_summary.side_effect = []
    uuid4.side_effect = []

    result = tested.topical_exchange_summary(topical_exchanges, temporary_folder)
    expected = CaseExchangeSummary(
        title="the_title_abcd123",
        summary="theSummary0",
    )
    assert result == expected
    exp_content = [{"title": "the_title_abcd123", "summary": "theSummary0"}]
    assert json.loads(buffer.content) == exp_content

    assert schema_summary.mock_calls == []
    assert memory_log.mock_calls == []
    assert helper.mock_calls == []
    assert uuid4.mock_calls == []
    calls = [call.__truediv__('topic_summary_003.json')]
    assert temporary_folder.mock_calls == calls
    calls = [
        call.exists(),
        call.open('r'),
    ]
    assert summary_file.mock_calls == calls

    reset_mocks("r")


@patch("evaluations.case_builders.builder_direct_from_tuning_split.Helper")
@patch("evaluations.case_builders.builder_direct_from_tuning_split.MemoryLog")
@patch.object(BuilderDirectFromTuningSplit, "schema_topical_exchanges")
def test_detect_topical_exchanges(schema_topical_exchanges, memory_log, helper):
    files = [
        # transcripts
        MagicMock(), MagicMock(), MagicMock(),
        # topical exchanges
        MagicMock(), MagicMock(), MagicMock(),
    ]
    buffers = [
        MockFile(), MockFile(), MockFile(),
        MockFile(mode="w"), MockFile(mode="w"), MockFile(mode="w"),
    ]

    def reset_mocks():
        schema_topical_exchanges.reset_mock()
        memory_log.reset_mock()
        helper.reset_mock()
        for idx, item in enumerate(files):
            item.reset_mock()
            item.open.return_value = buffers[idx]
            if idx < 3:
                item.parent.__truediv__.side_effect = [files[idx + 3]]
            buffers[idx].content = json.dumps([{"speaker": f"theSpeaker{idx}", "text": f"theText{idx}", "chunk": idx, "topic": idx}])

    reset_mocks()

    system_prompt = [
        'The conversation is in the medical context, and related to a visit of a patient with a healthcare provider.',
        '',
        'The conversation is divided into sequential fragment of several seconds each.',
        '',
        'Your task is to segment the conversation into coherent sets of topical medical exchanges.',
        'This means:',
        '* Each set should correspond to a distinct medical topic.',
        '* Non-medical content (e.g., small talk, greetings) should be included in the current medical topic '
        'set but should not initiate a new topic on its own.',
        '',
        'For each new fragment, you will be given:',
        '* The transcript of the current fragment.',
        '* The last previously identified topic exchange.',
        '',
        '',
        'Your job is to:',
        '* Determine whether the current fragment introduces a new medical topic.',
        "* If it does, increment the 'topic' field by one (1) for the exchanges starting from this new topic.",
        '* Topic shifts may occur anywhere within the fragment, not necessarily at the beginning.',
        '',
        'Be precise and consistent. Only mark a new topic when the medical focus clearly changes.',
        '',
        'Format your response following the JSON Schema:',
        '```json',
        '{\n "schema": "topical"\n}',
        '```',
        '',
    ]
    user_prompts = [
        [
            'The fragment of the discussion is:',
            '```json',
            '[{"speaker": "theSpeaker0", "text": "theText0", "chunk": 0, "topic": 0}]',
            '```',
            '',
            'Follow rigorously the instructions and provide the requested information using the mentioned JSON Schema within a Markdown code block:',
            '```json',
            'YOUR JSON OUTPUT HERE',
            '```',
        ],
        [
            'Here is the current set of exchanges for the topic #02:',
            '```json',
            '[\n {\n  "speaker": "theSpeaker2",\n  "text": "theText3",\n  "chunk": 1,\n  "topic": 2\n }\n]',
            '```',
            '',
            'This is just for the context, so do not repeat it in your answer.',
        ],
        [
            'The fragment of the discussion is:',
            '```json',
            '[{"speaker": "theSpeaker1", "text": "theText1", "chunk": 1, "topic": 1}]',
            '```',
            '',
            'Follow rigorously the instructions and provide the requested information using the mentioned JSON Schema within a Markdown code block:',
            '```json',
            'YOUR JSON OUTPUT HERE',
            '```',
        ],
        [
            'Here is the current set of exchanges for the topic #02:',
            '```json',
            '[\n '
            '{\n  "speaker": "theSpeaker2",\n  "text": "theText3",\n  "chunk": 1,\n  "topic": 2\n },\n '
            '{\n  "speaker": "theSpeaker1",\n  "text": "theText1",\n  "chunk": 2,\n  "topic": 2\n },\n '
            '{\n  "speaker": "theSpeaker1",\n  "text": "theText2",\n  "chunk": 2,\n  "topic": 2\n },\n '
            '{\n  "speaker": "theSpeaker2",\n  "text": "theText3",\n  "chunk": 2,\n  "topic": 2\n }\n]',
            '```',
            '',
            'This is just for the context, so do not repeat it in your answer.',
        ],
        [
            'The fragment of the discussion is:',
            '```json',
            '[{"speaker": "theSpeaker2", "text": "theText2", "chunk": 2, "topic": 2}]',
            '```', '',
            'Follow rigorously the instructions and provide the requested information using the mentioned JSON Schema within a Markdown code block:',
            '```json',
            'YOUR JSON OUTPUT HERE',
            '```',
        ],

    ]

    tested = helper_instance()

    # forced refresh or json does not exist
    tested.force_refresh = True
    for test in [True, False]:
        for item in files[3:]:
            item.exists.side_effect = [test]

        memory_log.instance.side_effect = ["theMemoryLog"]
        schema_topical_exchanges.side_effect = [{"schema": "topical"}]
        helper.chatter.return_value.chat.side_effect = [
            JsonExtract(error="", has_error=False, content=[[
                {"speaker": "theSpeaker1", "text": "theText1", "chunk": 1, "topic": 1},
                {"speaker": "theSpeaker1", "text": "theText2", "chunk": 1, "topic": 1},
                {"speaker": "theSpeaker2", "text": "theText3", "chunk": 1, "topic": 2},
            ]]),
            JsonExtract(error="", has_error=False, content=[[
                {"speaker": "theSpeaker1", "text": "theText1", "chunk": 2, "topic": 2},
                {"speaker": "theSpeaker1", "text": "theText2", "chunk": 2, "topic": 2},
                {"speaker": "theSpeaker2", "text": "theText3", "chunk": 2, "topic": 2},
            ]]),
            JsonExtract(error="", has_error=False, content=[[
                {"speaker": "theSpeaker1", "text": "theText1", "chunk": 3, "topic": 2},
                {"speaker": "theSpeaker1", "text": "theText2", "chunk": 3, "topic": 3},
                {"speaker": "theSpeaker2", "text": "theText3", "chunk": 3, "topic": 4},
            ]]),
        ]

        result = tested.detect_topical_exchanges(files[:3])
        expected = [
            TopicalExchange(speaker='theSpeaker1', text='theText1', chunk=1, topic=1),
            TopicalExchange(speaker='theSpeaker1', text='theText2', chunk=1, topic=1),
            TopicalExchange(speaker='theSpeaker2', text='theText3', chunk=1, topic=2),
            TopicalExchange(speaker='theSpeaker1', text='theText1', chunk=2, topic=2),
            TopicalExchange(speaker='theSpeaker1', text='theText2', chunk=2, topic=2),
            TopicalExchange(speaker='theSpeaker2', text='theText3', chunk=2, topic=2),
            TopicalExchange(speaker='theSpeaker1', text='theText1', chunk=3, topic=2),
            TopicalExchange(speaker='theSpeaker1', text='theText2', chunk=3, topic=3),
            TopicalExchange(speaker='theSpeaker2', text='theText3', chunk=3, topic=4),
        ]
        assert result == expected

        calls = [call()]
        assert schema_topical_exchanges.mock_calls == calls
        calls = [call.instance(tested.identification, 'detect_topical_exchanges', tested.s3_credentials)]
        assert memory_log.mock_calls == calls
        calls = [
            call.chatter(tested.settings, 'theMemoryLog'),
            call.chatter().set_system_prompt(system_prompt),
            call.chatter().set_user_prompt(user_prompts[0]),
            call.chatter().chat([{'schema': 'topical'}]),
            #
            call.chatter(tested.settings, 'theMemoryLog'),
            call.chatter().set_system_prompt(system_prompt),
            call.chatter().set_user_prompt(user_prompts[1]),
            call.chatter().set_user_prompt(user_prompts[2]),
            call.chatter().chat([{'schema': 'topical'}]),
            #
            call.chatter(tested.settings, 'theMemoryLog'),
            call.chatter().set_system_prompt(system_prompt),
            call.chatter().set_user_prompt(user_prompts[3]),
            call.chatter().set_user_prompt(user_prompts[4]),
            call.chatter().chat([{'schema': 'topical'}]),
        ]
        assert helper.mock_calls == calls

        for index, file in enumerate(files):
            if index < 3:
                calls = [
                    call.parent.__truediv__(f'topic_detection_{index + 1:03d}.json'),
                    call.open('r'),
                ]
            else:
                calls = [
                    call.exists(),
                    call.open('w'),
                ]
            assert files[index].mock_calls == calls

            if index < 3:
                exp_content = json.dumps([{"speaker": f"theSpeaker{index}", "text": f"theText{index}", "chunk": index, "topic": index}])
            elif index == 3:
                exp_content = json.dumps(
                    [
                        {"speaker": "theSpeaker1", "text": "theText1", "chunk": 1, "topic": 1},
                        {"speaker": "theSpeaker1", "text": "theText2", "chunk": 1, "topic": 1},
                        {"speaker": "theSpeaker2", "text": "theText3", "chunk": 1, "topic": 2},
                    ],
                    indent=2,
                )
            elif index == 4:
                exp_content = json.dumps(
                    [
                        {"speaker": "theSpeaker1", "text": "theText1", "chunk": 2, "topic": 2},
                        {"speaker": "theSpeaker1", "text": "theText2", "chunk": 2, "topic": 2},
                        {"speaker": "theSpeaker2", "text": "theText3", "chunk": 2, "topic": 2},
                    ],
                    indent=2,
                )
            else:
                exp_content = json.dumps(
                    [
                        {"speaker": "theSpeaker1", "text": "theText1", "chunk": 3, "topic": 2},
                        {"speaker": "theSpeaker1", "text": "theText2", "chunk": 3, "topic": 3},
                        {"speaker": "theSpeaker2", "text": "theText3", "chunk": 3, "topic": 4},
                    ],
                    indent=2,
                )
            assert buffers[index].content == exp_content
        reset_mocks()

    # no forced refresh and json does exist
    reset_mocks()
    tested.force_refresh = False
    for item in files[3:]:
        item.exists.side_effect = [True]
    for item in buffers:
        item.mode = "r"

    memory_log.instance.side_effect = ["theMemoryLog"]
    schema_topical_exchanges.side_effect = [{"schema": "topical"}]
    helper.chatter.return_value.chat.side_effect = []

    result = tested.detect_topical_exchanges(files[:3])
    expected = [
        TopicalExchange(speaker='theSpeaker3', text='theText3', chunk=3, topic=3),
        TopicalExchange(speaker='theSpeaker4', text='theText4', chunk=4, topic=4),
        TopicalExchange(speaker='theSpeaker5', text='theText5', chunk=5, topic=5),
    ]
    assert result == expected

    calls = [call()]
    assert schema_topical_exchanges.mock_calls == calls
    calls = [call.instance(tested.identification, 'detect_topical_exchanges', tested.s3_credentials)]
    assert memory_log.mock_calls == calls
    assert helper.mock_calls == []

    for index, file in enumerate(files):
        if index < 3:
            calls = [
                call.parent.__truediv__(f'topic_detection_{index + 1:03d}.json'),
            ]
        else:
            calls = [
                call.exists(),
                call.open('r'),
            ]
        assert files[index].mock_calls == calls

        if index < 3:
            exp_content = json.dumps([{"speaker": f"theSpeaker{index}", "text": f"theText{index}", "chunk": index, "topic": index}])
        elif index == 3:
            exp_content = json.dumps(
                [{"speaker": "theSpeaker3", "text": "theText3", "chunk": 3, "topic": 3}],
            )
        elif index == 4:
            exp_content = json.dumps(
                [{"speaker": "theSpeaker4", "text": "theText4", "chunk": 4, "topic": 4}],
            )
        else:
            exp_content = json.dumps(
                [{"speaker": "theSpeaker5", "text": "theText5", "chunk": 5, "topic": 5}],
            )
        assert buffers[index].content == exp_content
    reset_mocks()
