import json
from pathlib import Path
from unittest.mock import patch, call, MagicMock

from evaluations.case_builders.builder_direct_from_tuning import BuilderDirectFromTuning
from evaluations.case_builders.builder_direct_from_tuning_full import BuilderDirectFromTuningFull
from evaluations.structures.case_exchange import CaseExchange
from evaluations.structures.case_exchange_summary import CaseExchangeSummary
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import MockFile, MockClass


def helper_instance() -> BuilderDirectFromTuningFull:
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        structured_rfv=True,
        audit_llm=False,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    s3_logs_credentials = AwsS3Credentials(
        aws_key="theKeyLogs",
        aws_secret="theSecretLogs",
        region="theRegionLogs",
        bucket="theBucketLogs",
    )
    s3_tuning_credentials = AwsS3Credentials(
        aws_key="theKeyTuning",
        aws_secret="theSecretTuning",
        region="theRegionTuning",
        bucket="theBucketTuning",
    )
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return BuilderDirectFromTuningFull(
        settings,
        s3_logs_credentials,
        s3_tuning_credentials,
        identification,
        Path("/some/path"),
        45,
        True,
        True,
    )


def test_class():
    tested = BuilderDirectFromTuningFull
    assert issubclass(tested, BuilderDirectFromTuning)


def test__parameters():
    argument_parser = MagicMock()

    def reset_mocks():
        argument_parser.reset_mock()

    tested = BuilderDirectFromTuningFull
    tested._parameters(argument_parser)
    calls = [call.add_argument("--direct-full", action="store_true")]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_direct_from_tuning_full.LimitedCache")
@patch("evaluations.case_builders.builder_direct_from_tuning_full.AudioInterpreter")
@patch.object(BuilderDirectFromTuningFull, "generate_case")
@patch.object(BuilderDirectFromTuningFull, "exchange_summary")
@patch.object(BuilderDirectFromTuningFull, "anonymize_limited_cache")
@patch.object(BuilderDirectFromTuningFull, "anonymize_transcripts")
@patch.object(BuilderDirectFromTuningFull, "compact_transcripts")
@patch.object(BuilderDirectFromTuningFull, "create_transcripts")
@patch.object(BuilderDirectFromTuningFull, "split_audio")
@patch.object(BuilderDirectFromTuningFull, "collated_webm_to_mp3")
def test__run(
    collated_webm_to_mp3,
    split_audio,
    create_transcripts,
    compact_transcripts,
    anonymize_transcripts,
    anonymize_limited_cache,
    exchange_summary,
    generate_case,
    audio_interpreter,
    limited_cache,
    capsys,
):
    full_mp3_file = MagicMock()
    json_file = MagicMock()
    json_buffer = MockFile('{"limited":"cache"}')
    anonymized_cache = MagicMock()
    anonymized_files = [MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        collated_webm_to_mp3.reset_mock()
        split_audio.reset_mock()
        create_transcripts.reset_mock()
        compact_transcripts.reset_mock()
        anonymize_transcripts.reset_mock()
        anonymize_limited_cache.reset_mock()
        exchange_summary.reset_mock()
        generate_case.reset_mock()
        audio_interpreter.reset_mock()
        limited_cache.reset_mock()

        full_mp3_file.reset_mock()
        json_file.reset_mock()
        anonymized_cache.reset_mock()
        times = [
            0.0,
            1.7,
            3.5,
            4.8,
            6.1,
            8.3,
            9.9,
            11.7,
            15.5,
            17.8,
        ]
        for idx in range(len(anonymized_files)):
            anonymized_files[idx].reset_mock()
            anonymized_files[idx].read_text.side_effect = [
                json.dumps(
                    [
                        {
                            "speaker": f"theSpeaker{idx}x",
                            "text": f"theText{idx}x",
                            "chunk": idx,
                            "start": times[3 * idx],
                            "end": times[3 * idx + 1],
                        },
                        {
                            "speaker": f"theSpeaker{idx}y",
                            "text": f"theText{idx}y",
                            "chunk": idx,
                            "start": times[3 * idx + 1],
                            "end": times[3 * idx + 2],
                        },
                        {
                            "speaker": f"theSpeaker{idx}z",
                            "text": f"theText{idx}z",
                            "chunk": idx + 1,
                            "start": times[3 * idx + 2],
                            "end": times[3 * idx + 3],
                        },
                    ],
                ),
            ]

    reset_mocks()

    tested = helper_instance()

    case_exchanges = [
        CaseExchange(speaker="theSpeaker0x", text="theText0x", chunk=0, start=0.0, end=1.7),
        CaseExchange(speaker="theSpeaker0y", text="theText0y", chunk=0, start=1.7, end=3.5),
        CaseExchange(speaker="theSpeaker0z", text="theText0z", chunk=1, start=3.5, end=4.8),
        CaseExchange(speaker="theSpeaker1x", text="theText1x", chunk=1, start=4.8, end=6.1),
        CaseExchange(speaker="theSpeaker1y", text="theText1y", chunk=1, start=6.1, end=8.3),
        CaseExchange(speaker="theSpeaker1z", text="theText1z", chunk=2, start=8.3, end=9.9),
        CaseExchange(speaker="theSpeaker2x", text="theText2x", chunk=2, start=9.9, end=11.7),
        CaseExchange(speaker="theSpeaker2y", text="theText2y", chunk=2, start=11.7, end=15.5),
        CaseExchange(speaker="theSpeaker2z", text="theText2z", chunk=3, start=15.5, end=17.8),
    ]
    summary = CaseExchangeSummary(title="theTitle", summary="theSummary")

    collated_webm_to_mp3.side_effect = [full_mp3_file]
    split_audio.side_effect = ["theSplitAudioFiles"]
    create_transcripts.side_effect = ["theCreatedTranscripts"]
    compact_transcripts.side_effect = ["theCompactedTranscripts"]
    anonymize_transcripts.side_effect = [
        MockClass(files=anonymized_files, substitutions=["substitution1", "substitution2"])
    ]
    anonymize_limited_cache.side_effect = [anonymized_cache]
    exchange_summary.side_effect = [summary]
    audio_interpreter.side_effect = ["theAudioInterpreter"]
    limited_cache.load_from_json.side_effect = ["theLimitedCache"]
    json_file.open.side_effect = [json_buffer]
    full_mp3_file.parent.__truediv__.side_effect = [json_file]

    tested._run()

    exp_out = (
        "collect webm, collate to mp3...\n"
        "split mp3 into chunks...\n"
        "create transcripts...\n"
        "de-identification transcripts...\n"
        "de-identification limited cache...\n"
        "case name and summary...\n"
        "build case theTitle:\n"
    )
    assert capsys.readouterr().out == exp_out

    calls = [call()]
    assert collated_webm_to_mp3.mock_calls == calls
    calls = [call(full_mp3_file)]
    assert split_audio.mock_calls == calls
    calls = [call("theSplitAudioFiles", "theAudioInterpreter")]
    assert create_transcripts.mock_calls == calls
    calls = [call("theCreatedTranscripts")]
    assert compact_transcripts.mock_calls == calls
    calls = [call("theCompactedTranscripts")]
    assert anonymize_transcripts.mock_calls == calls
    calls = [call(["substitution1", "substitution2"], "theLimitedCache")]
    assert anonymize_limited_cache.mock_calls == calls
    calls = [call(anonymized_files)]
    assert exchange_summary.mock_calls == calls
    calls = [call(anonymized_cache, summary, case_exchanges)]
    assert generate_case.mock_calls == calls
    calls = [call(tested.settings, tested.s3_logs_credentials, "theLimitedCache", tested.identification)]
    assert audio_interpreter.mock_calls == calls
    calls = [call.load_from_json({"limited": "cache"})]
    assert limited_cache.mock_calls == calls
    calls = [call.parent.__truediv__("limited_chart.json")]
    assert full_mp3_file.mock_calls == calls
    calls = [call.open("r")]
    assert json_file.mock_calls == calls
    calls = []
    assert anonymized_cache.mock_calls == calls
    calls = [call.read_text()]
    for idx in range(len(anonymized_files)):
        assert anonymized_files[idx].mock_calls == calls

    reset_mocks()


@patch("evaluations.case_builders.builder_direct_from_tuning_full.uuid4")
@patch("evaluations.case_builders.builder_direct_from_tuning_full.Helper")
@patch("evaluations.case_builders.builder_direct_from_tuning_full.MemoryLog")
@patch.object(BuilderDirectFromTuningFull, "schema_summary")
def test_exchange_summary(schema_summary, memory_log, helper, uuid4):
    summary_file = MagicMock()
    buffer_read = MockFile("r")
    buffer_writes = [MockFile("w"), MockFile("w"), MockFile("w")]
    transcript_files = [MagicMock(), MagicMock(), MagicMock()]
    buffer_transcripts = [MockFile("r"), MockFile("r"), MockFile("r")]

    def reset_mocks():
        schema_summary.reset_mock()
        memory_log.reset_mock()
        helper.reset_mock()
        uuid4.reset_mock()

        summary_file.reset_mock()
        # summary_file.open.side_effect = [buffer_read] + buffer_writes
        buffer_read.content = json.dumps(
            [
                {"title": "the_title_abcd1231", "summary": "Some Summary 1"},
                {"title": "the_title_abcd1232", "summary": "Some Summary 2"},
            ],
        )
        for idx in range(len(transcript_files)):
            transcript_files[idx].reset_mock()
            transcript_files[idx].open.side_effect = [buffer_transcripts[idx]]
            buffer_transcripts[idx].content = json.dumps(
                [
                    {"speaker": f"theSpeakerX{idx}", "text": f"theTextX{idx}"},
                    {"speaker": f"theSpeakerY{idx}", "text": f"theTextY{idx}"},
                ],
            )
            buffer_writes[idx].content = ""

    reset_mocks()

    system_prompt = [
        "The conversation is in the medical context, and related to a visit of a patient with a healthcare provider.",
        "",
        "Your task is to give meaningful title and summary to the *whole* discussion.",
        "",
        "But because the conversation is too long, it has been divided into sequential fragment of several "
        "seconds each, "
        "so the user will provide you the title and summary defined so far when giving you a new fragment.",
        "",
        "The title should be as concise as possible, composed of about 25 to 40 characters.",
        "",
        "Format your response following the JSON Schema:",
        "```json",
        '{\n "schema": "summary"\n}',
        "```",
        "",
    ]
    user_prompts = {
        "initial_0": [
            "The fragment of the discussion is:",
            "```json",
            '[{"speaker": "theSpeakerX0", "text": "theTextX0"}, {"speaker": "theSpeakerY0", "text": "theTextY0"}]',
            "```",
            "",
            "Follow rigorously the instructions and provide the requested information using "
            "the mentioned JSON Schema within a Markdown code block:",
            "```json",
            "YOUR JSON OUTPUT HERE",
            "```",
        ],
        "initial_1": [
            "The fragment of the discussion is:",
            "```json",
            '[{"speaker": "theSpeakerX1", "text": "theTextX1"}, {"speaker": "theSpeakerY1", "text": "theTextY1"}]',
            "```",
            "",
            "Follow rigorously the instructions and provide the requested information using "
            "the mentioned JSON Schema within a Markdown code block:",
            "```json",
            "YOUR JSON OUTPUT HERE",
            "```",
        ],
        "initial_2": [
            "The fragment of the discussion is:",
            "```json",
            '[{"speaker": "theSpeakerX2", "text": "theTextX2"}, {"speaker": "theSpeakerY2", "text": "theTextY2"}]',
            "```",
            "",
            "Follow rigorously the instructions and provide the requested information using "
            "the mentioned JSON Schema within a Markdown code block:",
            "```json",
            "YOUR JSON OUTPUT HERE",
            "```",
        ],
        "previous_1": ["Here how to describe the discussion so far:", "Some Summary 1", ""],
        "previous_2": ["Here how to describe the discussion so far:", "Some Summary 2", ""],
    }

    tested = helper_instance()

    # forced refresh or json does not exist
    tested.force_refresh = True
    for test in [False, True]:
        summary_file.exists.side_effect = [not test]
        transcript_files[0].parent.__truediv__.side_effect = [summary_file]

        summary_file.open.side_effect = buffer_writes

        schema_summary.side_effect = [{"schema": "summary"}]
        memory_log.instance.side_effect = ["theMemoryLog"]
        uuid4.side_effect = ["12345abcd54321"]
        helper.chatter.return_value.chat.side_effect = [
            JsonExtract(error="", has_error=False, content=[[{"title": "The Title 1", "summary": "Some Summary 1"}]]),
            JsonExtract(
                error="",
                has_error=False,
                content=[
                    [
                        {"title": "The Title 1", "summary": "Some Summary 1"},
                        {"title": "The Title 2", "summary": "Some Summary 2"},
                    ],
                ],
            ),
            JsonExtract(
                error="",
                has_error=False,
                content=[
                    [
                        {"title": "The Title 2", "summary": "Some Summary 2"},
                        {"title": "The Title 3", "summary": "Some Summary 3"},
                    ],
                ],
            ),
        ]

        result = tested.exchange_summary(transcript_files)
        expected = CaseExchangeSummary(title="the_title_3_12345abcd5", summary="Some Summary 3")
        assert result == expected
        exp_content = [
            {"summary": "Some Summary 1", "title": "the_title_abcd1231"},
            {"summary": "Some Summary 2", "title": "the_title_abcd1232"},
        ]
        assert json.loads(buffer_read.content) == exp_content

        calls = [call()]
        assert schema_summary.mock_calls == calls
        calls = [call.instance(tested.identification, "detect_summary", tested.s3_logs_credentials)]
        assert memory_log.mock_calls == calls
        calls = [
            call.chatter(tested.settings, "theMemoryLog"),
            call.chatter().set_system_prompt(system_prompt),
            call.chatter().set_user_prompt(user_prompts["initial_0"]),
            call.chatter().chat([{"schema": "summary"}]),
            #
            call.chatter(tested.settings, "theMemoryLog"),
            call.chatter().set_system_prompt(system_prompt),
            call.chatter().set_user_prompt(user_prompts["previous_1"]),
            call.chatter().set_user_prompt(user_prompts["initial_1"]),
            call.chatter().chat([{"schema": "summary"}]),
            #
            call.chatter(tested.settings, "theMemoryLog"),
            call.chatter().set_system_prompt(system_prompt),
            call.chatter().set_user_prompt(user_prompts["previous_2"]),
            call.chatter().set_user_prompt(user_prompts["initial_2"]),
            call.chatter().chat([{"schema": "summary"}]),
        ]
        assert helper.mock_calls == calls
        calls = [call()]
        assert uuid4.mock_calls == calls
        calls = [call.parent.__truediv__("summary_detection.json"), call.open("r")]
        assert transcript_files[0].mock_calls == calls
        calls = [call.open("r")]
        assert transcript_files[1].mock_calls == calls
        assert transcript_files[2].mock_calls == calls
        calls = [call.exists(), call.open("w"), call.open("w"), call.open("w")]
        assert summary_file.mock_calls == calls

        reset_mocks()

    # no forced refresh and json does exist
    reset_mocks()
    tested.force_refresh = False
    summary_file.exists.side_effect = [True]
    transcript_files[0].parent.__truediv__.side_effect = [summary_file]

    summary_file.open.side_effect = [buffer_read, buffer_writes[0]]

    schema_summary.side_effect = [{"schema": "summary"}]
    memory_log.instance.side_effect = ["theMemoryLog"]
    uuid4.side_effect = ["12345abcd54321"]
    helper.chatter.return_value.chat.side_effect = [
        JsonExtract(
            error="",
            has_error=False,
            content=[
                [
                    {"title": "The Title 3", "summary": "Some Summary 3"},
                    {"title": "The Title 4", "summary": "Some Summary 4"},
                ],
            ],
        ),
    ]

    result = tested.exchange_summary(transcript_files)
    expected = CaseExchangeSummary(title="the_title_4_12345abcd5", summary="Some Summary 4")
    assert result == expected
    exp_content = [
        {"summary": "Some Summary 1", "title": "the_title_abcd1231"},
        {"summary": "Some Summary 2", "title": "the_title_abcd1232"},
    ]
    assert json.loads(buffer_read.content) == exp_content

    calls = [call()]
    assert schema_summary.mock_calls == calls
    calls = [call.instance(tested.identification, "detect_summary", tested.s3_logs_credentials)]
    assert memory_log.mock_calls == calls
    calls = [
        call.chatter(tested.settings, "theMemoryLog"),
        call.chatter().set_system_prompt(system_prompt),
        call.chatter().set_user_prompt(user_prompts["previous_2"]),
        call.chatter().set_user_prompt(user_prompts["initial_2"]),
        call.chatter().chat([{"schema": "summary"}]),
    ]
    assert helper.mock_calls == calls
    calls = [call()]
    assert uuid4.mock_calls == calls
    calls = [call.parent.__truediv__("summary_detection.json")]
    assert transcript_files[0].mock_calls == calls
    assert transcript_files[1].mock_calls == []
    calls = [call.open("r")]
    assert transcript_files[2].mock_calls == calls
    calls = [call.exists(), call.open("r"), call.open("w")]
    assert summary_file.mock_calls == calls

    reset_mocks()
