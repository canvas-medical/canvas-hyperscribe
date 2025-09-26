import json
from argparse import ArgumentParser, Namespace
from datetime import datetime
from datetime import timezone
from pathlib import Path, PosixPath
from unittest.mock import patch, call, MagicMock

import pytest
from requests import Response

from evaluations.case_builders.builder_direct_from_tuning import BuilderDirectFromTuning
from evaluations.structures.anonymization import Anonymization
from evaluations.structures.anonymization_error import AnonymizationError
from evaluations.structures.anonymization_result import AnonymizationResult
from evaluations.structures.anonymization_substitution import AnonymizationSubstitution
from evaluations.structures.case_exchange import CaseExchange
from evaluations.structures.case_exchange_summary import CaseExchangeSummary
from evaluations.structures.records.real_world_case import RealWorldCase as RecordRealWorldCase
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.aws_s3_object import AwsS3Object
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import MockFile, is_constant, MockClass


def helper_instance() -> BuilderDirectFromTuning:
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        structured_rfv=True,
        audit_llm=False,
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
    return BuilderDirectFromTuning(
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
    tested = BuilderDirectFromTuning
    constants = {"MAX_WORDS_PER_COMPACTED_TRANSCRIPT": 1000, "MAX_ANONYMIZATION_ATTEMPTS": 3}
    assert is_constant(tested, constants)


def test__parameters():
    tested = BuilderDirectFromTuning
    with pytest.raises(NotImplementedError):
        _ = tested._parameters(ArgumentParser())


def test__run():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested._run()


@patch("evaluations.case_builders.builder_direct_from_tuning.ArgumentParser")
@patch.object(BuilderDirectFromTuning, "_parameters")
def test_parameters(parameters, argument_parser):
    def reset_mocks():
        parameters.reset_mock()
        argument_parser.reset_mock()

    tested = BuilderDirectFromTuning
    argument_parser.return_value.parse_args.side_effect = ["parse_args called"]
    result = tested.parameters()
    expected = "parse_args called"
    assert result == expected

    calls = [call(argument_parser.return_value)]
    assert parameters.mock_calls == calls
    calls = [
        call(description="Build the case files directly from the tuning files stored in AWS S3"),
        call().add_argument("--patient", type=str, required=True, help="The patient UUID to consider"),
        call().add_argument("--note", type=str, required=True, help="The note UUID to consider"),
        call().add_argument(
            "--path_temp_files",
            type=str,
            help="Folder to store temporary files, if provided, most existing files will be reused",
        ),
        call().add_argument(
            "--cycle_duration",
            type=int,
            required=True,
            help="Duration of each cycle, i.e. the duration of the audio chunks",
        ),
        call().add_argument("--force_refresh", action="store_true", help="Force refresh the temporary files"),
        call().add_argument("--force_rerun", action="store_true", help="Force rerun the cases generation"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_direct_from_tuning.Path")
@patch("evaluations.case_builders.builder_direct_from_tuning.TemporaryDirectory")
@patch("evaluations.case_builders.builder_direct_from_tuning.HelperEvaluation")
@patch.object(BuilderDirectFromTuning, "_run")
@patch.object(BuilderDirectFromTuning, "parameters")
@patch.object(BuilderDirectFromTuning, "__init__", return_value=None)
def test_run(init, parameters, run, helper, temp_dir, path):
    mock_path_temp_dir = MagicMock()
    mock_path_provided = MagicMock()

    def reset_mocks():
        init.reset_mock()
        parameters.reset_mock()
        run.reset_mock()
        helper.reset_mock()
        temp_dir.reset_mock()
        path.reset_mock()
        mock_path_provided.reset_mock()
        mock_path_temp_dir.reset_mock()

    tested = BuilderDirectFromTuning

    # path provided
    # -- the provided path exists
    parameters.side_effect = [
        Namespace(
            patient="thePatientUuid",
            note="theNoteUuid",
            cycle_duration=37,
            force_refresh=False,
            force_rerun=True,
            path_temp_files=Path("/some/path"),
        ),
    ]
    path.side_effect = [mock_path_provided, mock_path_temp_dir]
    mock_path_provided.exists.side_effect = [True]
    helper.aws_s3_credentials.side_effect = ["awsS3CredentialsLogs"]
    helper.aws_s3_credentials_tuning.side_effect = ["awsS3CredentialsTuning"]
    helper.settings.side_effect = ["settings"]
    helper.get_canvas_instance.side_effect = ["canvasInstance"]

    tested.run()

    calls = [
        call(
            "settings",
            "awsS3CredentialsLogs",
            "awsS3CredentialsTuning",
            IdentificationParameters(
                patient_uuid="thePatientUuid",
                note_uuid="theNoteUuid",
                provider_uuid="_ProviderUuid",
                canvas_instance="canvasInstance",
            ),
            mock_path_provided,
            37,
            False,
            True,
        ),
    ]
    assert init.mock_calls == calls
    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call()]
    assert run.mock_calls == calls
    calls = [
        call.aws_s3_credentials(),
        call.aws_s3_credentials_tuning(),
        call.settings(),
        call.get_canvas_instance(),
    ]
    assert helper.mock_calls == calls
    calls = [call(), call().__enter__(), call().__exit__(None, None, None)]
    assert temp_dir.mock_calls == calls
    calls = [call(PosixPath("/some/path"))]
    assert path.mock_calls == calls
    calls = [call.exists()]
    assert mock_path_provided.mock_calls == calls
    assert mock_path_temp_dir.mock_calls == []
    reset_mocks()
    # -- provided path does not exist
    parameters.side_effect = [
        Namespace(
            patient="thePatientUuid",
            note="theNoteUuid",
            cycle_duration=37,
            force_refresh=False,
            force_rerun=True,
            path_temp_files=Path("/some/path"),
        ),
    ]
    path.side_effect = [mock_path_provided, mock_path_temp_dir]
    mock_path_provided.exists.side_effect = [False]
    helper.aws_s3_credentials.side_effect = ["awsS3CredentialsLogs"]
    helper.aws_s3_credentials_tuning.side_effect = ["awsS3CredentialsTuning"]
    helper.settings.side_effect = ["settings"]
    helper.get_canvas_instance.side_effect = ["canvasInstance"]

    tested.run()

    calls = [
        call(
            "settings",
            "awsS3CredentialsLogs",
            "awsS3CredentialsTuning",
            IdentificationParameters(
                patient_uuid="thePatientUuid",
                note_uuid="theNoteUuid",
                provider_uuid="_ProviderUuid",
                canvas_instance="canvasInstance",
            ),
            mock_path_temp_dir,
            37,
            False,
            True,
        ),
    ]
    assert init.mock_calls == calls
    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call()]
    assert run.mock_calls == calls
    calls = [
        call.aws_s3_credentials(),
        call.aws_s3_credentials_tuning(),
        call.settings(),
        call.get_canvas_instance(),
    ]
    assert helper.mock_calls == calls
    calls = [call(), call().__enter__(), call().__exit__(None, None, None)]
    assert temp_dir.mock_calls == calls
    calls = [call(PosixPath("/some/path")), call(temp_dir.return_value.__enter__.return_value)]
    assert path.mock_calls == calls
    calls = [call.exists()]
    assert mock_path_provided.mock_calls == calls
    assert mock_path_temp_dir.mock_calls == []
    reset_mocks()
    # path not provided
    parameters.side_effect = [
        Namespace(
            patient="thePatientUuid",
            note="theNoteUuid",
            cycle_duration=37,
            force_refresh=False,
            force_rerun=True,
            path_temp_files="",
        ),
    ]
    path.side_effect = [mock_path_temp_dir]
    mock_path_provided.exists.side_effect = []
    helper.aws_s3_credentials.side_effect = ["awsS3CredentialsLogs"]
    helper.aws_s3_credentials_tuning.side_effect = ["awsS3CredentialsTuning"]
    helper.settings.side_effect = ["settings"]
    helper.get_canvas_instance.side_effect = ["canvasInstance"]

    tested.run()

    calls = [
        call(
            "settings",
            "awsS3CredentialsLogs",
            "awsS3CredentialsTuning",
            IdentificationParameters(
                patient_uuid="thePatientUuid",
                note_uuid="theNoteUuid",
                provider_uuid="_ProviderUuid",
                canvas_instance="canvasInstance",
            ),
            mock_path_temp_dir,
            37,
            False,
            True,
        ),
    ]
    assert init.mock_calls == calls
    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call()]
    assert run.mock_calls == calls
    calls = [
        call.aws_s3_credentials(),
        call.aws_s3_credentials_tuning(),
        call.settings(),
        call.get_canvas_instance(),
    ]
    assert helper.mock_calls == calls
    calls = [call(), call().__enter__(), call().__exit__(None, None, None)]
    assert temp_dir.mock_calls == calls
    calls = [call(temp_dir.return_value.__enter__.return_value)]
    assert path.mock_calls == calls
    assert mock_path_provided.mock_calls == []
    assert mock_path_temp_dir.mock_calls == []
    reset_mocks()


def test___init__():
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        structured_rfv=True,
        audit_llm=False,
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
        aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket"
    )
    s3_tuning_credentials = AwsS3Credentials(
        aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucket"
    )
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    path = Path("/some/path")
    tested = BuilderDirectFromTuning(
        settings,
        s3_logs_credentials,
        s3_tuning_credentials,
        identification,
        path,
        45,
        True,
        False,
    )
    assert tested.s3_logs_credentials == s3_logs_credentials
    assert tested.s3_tuning_credentials == s3_tuning_credentials
    assert tested.identification == identification
    assert tested.settings == settings
    assert tested.output_dir == path
    assert tested.cycle_duration == 45
    assert tested.force_refresh is True
    assert tested.force_rerun is False


@patch("evaluations.case_builders.builder_direct_from_tuning.GeneratedNote")
@patch("evaluations.case_builders.builder_direct_from_tuning.HelperEvaluation")
@patch("evaluations.case_builders.builder_direct_from_tuning.ImplementedCommands")
@patch("evaluations.case_builders.builder_direct_from_tuning.AuditorPostgres")
@patch("evaluations.case_builders.builder_direct_from_tuning.Commander")
@patch("evaluations.case_builders.builder_direct_from_tuning.CachedSdk")
@patch("evaluations.case_builders.builder_direct_from_tuning.AudioInterpreter")
@patch("evaluations.case_builders.builder_direct_from_tuning.RealWorldCaseStore")
def test_generate_case(
    real_world_case_store,
    audio_interpreter,
    cached_sdk,
    commander,
    auditor_postgres,
    implemented_commands,
    helper,
    generated_note,
):
    mock_chatter = MagicMock()
    limited_cache = MagicMock()
    mock_settings = MagicMock()

    def reset_mocks():
        real_world_case_store.reset_mock()
        audio_interpreter.reset_mock()
        cached_sdk.reset_mock()
        commander.reset_mock()
        auditor_postgres.reset_mock()
        implemented_commands.reset_mock()
        helper.reset_mock()
        generated_note.reset_mock()
        mock_chatter.reset_mock()
        limited_cache.reset_mock()
        mock_settings.reset_mock()

    error = RuntimeError("There was an error")
    full_t2c_side_effects = [
        (["previous1"], ["effects1"]),
        (["previous2"], ["effects2"]),
        (["previous3"], ["effects3"]),
        (["previous4"], ["effects4"]),
    ]
    tests = [
        (full_t2c_side_effects, False, True, (0, 0), True),
        ([(["previous1"], ["effects1"]), error], True, True, (0, 0), True),
        (full_t2c_side_effects, False, True, (12, 52), True),
        (full_t2c_side_effects, False, False, (12, 52), False),
    ]
    for t2c_side_effects, has_error, force_rerun, last_run_side_effect, exp_calls in tests:
        tested = helper_instance()
        tested.force_rerun = force_rerun
        audio_interpreter.side_effect = [mock_chatter]
        commander.transcript2commands.side_effect = t2c_side_effects
        auditor_postgres.return_value.summarized_generated_commands_as_instructions.side_effect = [
            "summarizedInstructions",
        ]
        auditor_postgres.return_value.case_id.side_effect = [147]
        auditor_postgres.return_value.cycle_key = "theCycleKey"
        implemented_commands.schema_key2instruction.side_effect = [{"implemented": "json"}]
        mock_chatter.identification = tested.identification
        limited_cache.to_json.side_effect = [{"obfuscated": "json"}]
        limited_cache.staged_commands_as_instructions.side_effect = [["previous0"]]
        helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
        helper.trace_error.side_effect = [{"error": "test"}]
        generated_note.return_value.last_run_for.side_effect = [last_run_side_effect]
        mock_settings.llm_audio.vendor = "theVendorAudio"
        mock_settings.llm_audio_model.side_effect = ["theModelAudio"]
        mock_settings.llm_text.vendor = "theVendorText"
        mock_settings.llm_text_model.side_effect = ["theModelText"]

        case_summary = CaseExchangeSummary(title="theTitle", summary="theSummary")
        case_exchanges = [
            CaseExchange(speaker="theSpeaker1", text="theText1", chunk=1),
            CaseExchange(speaker="theSpeaker2", text="theText2", chunk=2),
            CaseExchange(speaker="theSpeaker3", text="theText3", chunk=2),
            CaseExchange(speaker="theSpeaker4", text="theText4", chunk=3),
            CaseExchange(speaker="theSpeaker5", text="theText5", chunk=3),
            CaseExchange(speaker="theSpeaker6", text="theText6", chunk=4),
        ]
        tested.settings = mock_settings
        result = tested.generate_case(limited_cache, case_summary, case_exchanges)
        expected = "summarizedInstructions"
        assert result == expected

        if exp_calls:
            calls = [
                call("thePostgresCredentials"),
                call().upsert(
                    RecordRealWorldCase(
                        case_id=147,
                        customer_identifier="canvasInstance",
                        patient_note_hash="patient_patientUuid/note_noteUuid",
                        topical_exchange_identifier="theTitle",
                        publishable=False,
                        start_time=0.0,
                        end_time=0.0,
                        duration=0.0,
                        audio_llm_vendor="theVendorAudio",
                        audio_llm_name="theModelAudio",
                        id=0,
                    ),
                ),
            ]
            assert real_world_case_store.mock_calls == calls
            calls = [call(tested.settings, tested.s3_logs_credentials, limited_cache, tested.identification)]
            assert audio_interpreter.mock_calls == calls
            calls = [
                call.get_discussion("noteUuid"),
                call.get_discussion().set_cycle(1),
                call.get_discussion().set_cycle(2),
            ]
            if not has_error:
                calls.extend([call.get_discussion().set_cycle(3), call.get_discussion().set_cycle(4)])
            assert cached_sdk.mock_calls == calls
            calls = [
                call.transcript2commands(
                    auditor_postgres.return_value,
                    [Line(speaker="theSpeaker1", text="theText1")],
                    mock_chatter,
                    ["previous0"],
                ),
                call.transcript2commands(
                    auditor_postgres.return_value,
                    [Line(speaker="theSpeaker2", text="theText2"), Line(speaker="theSpeaker3", text="theText3")],
                    mock_chatter,
                    ["previous1"],
                ),
            ]
            if not has_error:
                calls.extend(
                    [
                        call.transcript2commands(
                            auditor_postgres.return_value,
                            [
                                Line(speaker="theSpeaker4", text="theText4"),
                                Line(speaker="theSpeaker5", text="theText5"),
                            ],
                            mock_chatter,
                            ["previous2"],
                        ),
                        call.transcript2commands(
                            auditor_postgres.return_value,
                            [Line(speaker="theSpeaker6", text="theText6")],
                            mock_chatter,
                            ["previous3"],
                        ),
                    ],
                )
            assert commander.mock_calls == calls
            calls = [
                call("theTitle", 0, mock_settings, tested.s3_logs_credentials, "thePostgresCredentials"),
                call().case_prepare(),
                call().case_update_limited_cache({"obfuscated": "json"}),
                call().case_id(),
                call().set_cycle(1),
                call().upsert_json(
                    "audio2transcript",
                    {"theCycleKey": [{"speaker": "theSpeaker1", "text": "theText1"}]},
                ),
                call().set_cycle(2),
                call().upsert_json(
                    "audio2transcript",
                    {
                        "theCycleKey": [
                            {"speaker": "theSpeaker2", "text": "theText2"},
                            {"speaker": "theSpeaker3", "text": "theText3"},
                        ],
                    },
                ),
            ]
            if not has_error:
                calls.extend(
                    [
                        call().set_cycle(3),
                        call().upsert_json(
                            "audio2transcript",
                            {
                                "theCycleKey": [
                                    {"speaker": "theSpeaker4", "text": "theText4"},
                                    {"speaker": "theSpeaker5", "text": "theText5"},
                                ],
                            },
                        ),
                        call().set_cycle(4),
                        call().upsert_json(
                            "audio2transcript",
                            {"theCycleKey": [{"speaker": "theSpeaker6", "text": "theText6"}]},
                        ),
                        call().case_finalize({}),
                    ],
                )
            else:
                calls.extend([call().case_finalize({"error": "test"})])
            calls.extend([call().summarized_generated_commands_as_instructions()])
            assert auditor_postgres.mock_calls == calls
            calls = [call.schema_key2instruction()]
            assert implemented_commands.mock_calls == calls
            calls = [call.staged_commands_as_instructions({"implemented": "json"}), call.to_json(True)]
            assert limited_cache.mock_calls == calls
            calls = [call.llm_audio_model()]
            assert mock_settings.mock_calls == calls
        else:
            assert real_world_case_store.mock_calls == []
            assert audio_interpreter.mock_calls == []
            assert cached_sdk.mock_calls == []
            assert commander.mock_calls == []
            calls = [
                call("theTitle", 0, mock_settings, tested.s3_logs_credentials, "thePostgresCredentials"),
                call().summarized_generated_commands_as_instructions(),
            ]
            assert auditor_postgres.mock_calls == calls
            assert implemented_commands.mock_calls == []
            assert limited_cache.mock_calls == []
            assert mock_settings.mock_calls == []

        calls = [call.postgres_credentials()]
        if has_error:
            calls.extend([call.trace_error(error)])
        assert helper.mock_calls == calls
        calls = [call("thePostgresCredentials"), call().last_run_for("theTitle")]
        assert generated_note.mock_calls == calls
        assert mock_chatter.mock_calls == []
        reset_mocks()


def test_create_transcripts():
    mock_interpreter = MagicMock()
    mock_json_files = [MagicMock(), MagicMock(), MagicMock()]
    mock_audio_files = [MagicMock(), MagicMock(), MagicMock()]
    json_buffers = [MockFile(), MockFile(), MockFile()]
    audio_buffers = [MockFile(), MockFile(), MockFile()]

    def reset_mocks():
        mock_interpreter.reset_mock()
        for idx, item in enumerate(mock_audio_files):
            item.reset_mock()
            item.open.side_effect = [audio_buffers[idx]]
            audio_buffers[idx].content = f"audio content {idx}".encode("utf-8")
            item.parent.__truediv__.side_effect = [mock_json_files[idx]]

        for idx, item in enumerate(mock_json_files):
            item.reset_mock()
            item.open.side_effect = [json_buffers[idx]]
            json_buffers[idx].content = ""

    reset_mocks()

    tested = helper_instance()

    # forced refresh or json does not exist
    for test in [True, False]:
        tested.force_refresh = True
        for mock_file in mock_json_files:
            mock_file.exists.side_effect = [not test]

        mock_interpreter.combine_and_speaker_detection.side_effect = [
            JsonExtract(error="error", has_error=False, content=[{"speaker": "theSpeaker1", "text": "theText1"}]),
            JsonExtract(error="error", has_error=False, content=[{"speaker": "theSpeaker2", "text": "theText2"}]),
            JsonExtract(error="error", has_error=False, content=[{"speaker": "theSpeaker3", "text": "theText3"}]),
        ]
        mock_interpreter.settings = tested.settings
        result = tested.create_transcripts(mock_audio_files, mock_interpreter)
        expected = mock_json_files
        assert result == expected

        calls = [
            call.combine_and_speaker_detection([b"audio content 0"], []),
            call.combine_and_speaker_detection([b"audio content 1"], [Line(speaker="theSpeaker1", text="theText1")]),
            call.combine_and_speaker_detection([b"audio content 2"], [Line(speaker="theSpeaker2", text="theText2")]),
        ]
        assert mock_interpreter.mock_calls == calls
        calls = [call.open("w")]
        for index, mock_file in enumerate(mock_json_files):
            assert mock_file.mock_calls == calls
            exp_content = [{"speaker": f"theSpeaker{index + 1}", "text": f"theText{index + 1}"}]
            assert json.loads(json_buffers[index].content) == exp_content

        for index, mock_file in enumerate(mock_audio_files, start=1):
            calls = [call.parent.__truediv__(f"transcript_{index:03d}.json"), call.open("rb")]
            assert mock_file.mock_calls == calls
            exp_content = f"audio content {index - 1}".encode("utf-8")
            assert audio_buffers[index - 1].content == exp_content
        reset_mocks()

    # not forced refresh and some json does exist
    tested.force_refresh = False
    mock_json_files[0].exists.side_effect = [False]
    mock_json_files[1].exists.side_effect = [True]
    mock_json_files[2].exists.side_effect = [True]

    mock_interpreter.combine_and_speaker_detection.side_effect = [
        JsonExtract(error="error", has_error=False, content=[{"speaker": "theSpeaker1", "text": "theText1"}]),
        JsonExtract(error="error", has_error=False, content=[{"speaker": "theSpeaker2", "text": "theText2"}]),
        JsonExtract(error="error", has_error=False, content=[{"speaker": "theSpeaker3", "text": "theText3"}]),
    ]
    result = tested.create_transcripts(mock_audio_files, mock_interpreter)
    expected = mock_json_files
    assert result == expected

    calls = [call.combine_and_speaker_detection([b"audio content 0"], [])]
    assert mock_interpreter.mock_calls == calls
    calls = [call.exists(), call.open("w")]
    assert mock_json_files[0].mock_calls == calls
    exp_content = [{"speaker": "theSpeaker1", "text": "theText1"}]
    assert json.loads(json_buffers[0].content) == exp_content

    calls = [call.exists()]
    assert mock_json_files[1].mock_calls == calls
    assert mock_json_files[2].mock_calls == calls
    assert json_buffers[1].content == ""
    assert json_buffers[2].content == ""

    calls = [call.parent.__truediv__("transcript_001.json"), call.open("rb")]
    assert mock_audio_files[0].mock_calls == calls
    calls = [call.parent.__truediv__("transcript_002.json")]
    assert mock_audio_files[1].mock_calls == calls
    calls = [call.parent.__truediv__("transcript_003.json")]
    assert mock_audio_files[2].mock_calls == calls

    for index, mock_file in enumerate(mock_audio_files):
        exp_content = f"audio content {index}".encode("utf-8")
        assert audio_buffers[index].content == exp_content

    reset_mocks()


@patch("evaluations.case_builders.builder_direct_from_tuning.ffmpeg")
@patch("evaluations.case_builders.builder_direct_from_tuning.AwsS3")
@patch.object(BuilderDirectFromTuning, "create_silent_mp3")
def test_collated_webm_to_mp3(create_silent_mp3, client_s3, ffmpeg):
    output_dir = MagicMock()
    mock_files = [
        # the first file is the full webm built
        MagicMock(),
        # the second file is the full mp3 built
        MagicMock(),
        # these files are the chunk webm coming from the S3
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        # these files are the locally saved webm
        MagicMock(),
        MagicMock(),
    ]
    buffers = [MockFile(), MockFile(), MockFile(), MockFile(), MockFile(), MockFile(), MockFile(), MockFile()]

    def reset_mocks():
        create_silent_mp3.reset_mock()
        client_s3.reset_mock()
        ffmpeg.reset_mock()
        output_dir.reset_mock()
        for idx, item in enumerate(mock_files):
            item.reset_mock()
            item.open.side_effect = [buffers[idx]]
            item.stem = f"webm_{idx:03}.webm"
            item.as_posix.side_effect = [f"posix{idx:03}"]
            buffers[idx].content = b""
            if idx == 5:
                buffers[idx].content = ""
            if idx > 5:
                buffers[idx].content = f"locally saved audio content {idx}".encode("utf-8")

    reset_mocks()

    date_0 = datetime(2025, 6, 27, 10, 36, 21, 123456, tzinfo=timezone.utc)
    responses = [Response(), Response(), Response(), Response()]
    responses[0].status_code = 200
    responses[1].status_code = 200
    responses[2].status_code = 500
    responses[3].status_code = 200
    responses[0]._content = b"audio content 0"
    responses[1]._content = b"audio content 1"
    responses[2]._content = b"audio content 2"
    responses[3]._content = json.dumps([{"limited": "cache"}])

    tested = helper_instance()
    tested.output_dir = output_dir

    # forced refresh or files does not exist
    for file_exists in [True, False]:
        for file_size in [0, 452]:
            tested.force_refresh = True
            mock_files[0].stat.side_effect = [MockClass(st_size=file_size)]
            mock_files[0].exists.side_effect = [not file_exists]
            mock_files[0].parent.glob.side_effect = [[mock_files[6], mock_files[7]]]
            mock_files[1].exists.side_effect = [not file_exists]

            output_dir.__truediv__.side_effect = mock_files
            client_s3.return_value.list_s3_objects.side_effect = [
                [
                    AwsS3Object(key="/patient_uuid/note_uuid/webm_001.webm", size=1, last_modified=date_0),
                    AwsS3Object(key="/patient_uuid/note_uuid/webm_002.webm", size=1, last_modified=date_0),
                    AwsS3Object(
                        key="/patient_uuid/note_uuid/webm_003.webm",
                        size=1,
                        last_modified=date_0,
                    ),  # <-- response 500
                    AwsS3Object(key="/patient_uuid/note_uuid/limited_chart.json", size=1, last_modified=date_0),
                ],
            ]
            client_s3.return_value.access_s3_object.side_effect = responses

            result = tested.collated_webm_to_mp3()
            expected = mock_files[1]
            assert result is expected

            calls = []
            if file_size == 0:
                calls = [call(mock_files[1])]
            assert create_silent_mp3.mock_calls == calls
            calls = [
                call(
                    AwsS3Credentials(
                        aws_key="theKeyTuning",
                        aws_secret="theSecretTuning",
                        region="theRegionTuning",
                        bucket="theBucketTuning",
                    )
                ),
                call().list_s3_objects("hyperscribe-canvasInstance/patient_patientUuid/note_noteUuid"),
                call().access_s3_object("/patient_uuid/note_uuid/webm_001.webm"),
                call().access_s3_object("/patient_uuid/note_uuid/webm_002.webm"),
                call().access_s3_object("/patient_uuid/note_uuid/webm_003.webm"),
                call().access_s3_object("/patient_uuid/note_uuid/limited_chart.json"),
            ]
            assert client_s3.mock_calls == calls
            calls = []
            if file_size > 0:
                calls = [
                    call.input("posix000"),
                    call.input().output("posix001", acodec="libmp3lame", ar=44100, ab="192k", vn=None),
                    call.input().output().overwrite_output(),
                    call.input().output().overwrite_output().run(overwrite_output=True, quiet=True),
                ]
            assert ffmpeg.mock_calls == calls
            calls = [
                call.__truediv__("hyperscribe-canvasInstance/patient_patientUuid/note_noteUuid/note_noteUuid.webm"),
                call.__truediv__("hyperscribe-canvasInstance/patient_patientUuid/note_noteUuid/note_noteUuid.mp3"),
                call.__truediv__("/patient_uuid/note_uuid/webm_001.webm"),
                call.__truediv__("/patient_uuid/note_uuid/webm_002.webm"),
                call.__truediv__("/patient_uuid/note_uuid/webm_003.webm"),
                call.__truediv__("/patient_uuid/note_uuid/limited_chart.json"),
            ]
            assert output_dir.mock_calls == calls
            calls = [
                call.unlink(missing_ok=True),
                call.open("wb"),
                call.parent.glob("*.webm"),
                call.stat(),
            ]
            if file_size > 0:
                calls.append(call.as_posix())
            assert mock_files[0].mock_calls == calls
            assert buffers[0].content == (b"locally saved audio content 6locally saved audio content 7")
            calls = []
            if file_size > 0:
                calls.append(call.as_posix())
            assert mock_files[1].mock_calls == calls
            assert buffers[1].content == b""

            calls = [call.parent.mkdir(parents=True, exist_ok=True), call.open("wb")]
            assert mock_files[2].mock_calls == calls
            assert mock_files[3].mock_calls == calls
            assert mock_files[4].mock_calls == []
            assert mock_files[5].mock_calls == calls
            assert buffers[2].content == b"audio content 0"
            assert buffers[3].content == b"audio content 1"
            assert buffers[4].content == b""
            assert buffers[5].content == '[{"limited": "cache"}]'

            calls = [call.open("rb")]
            assert mock_files[6].mock_calls == calls
            assert mock_files[7].mock_calls == calls
            assert buffers[6].content == b"locally saved audio content 6"
            assert buffers[7].content == b"locally saved audio content 7"

            reset_mocks()

    # not forced refresh and files exist
    tested.force_refresh = False
    mock_files[0].stat.side_effect = []
    mock_files[0].exists.side_effect = [True]
    mock_files[0].parent.glob.side_effect = []
    mock_files[1].exists.side_effect = [True]

    output_dir.__truediv__.side_effect = mock_files
    client_s3.return_value.list_s3_objects.side_effect = []
    client_s3.return_value.access_s3_object.side_effect = []

    result = tested.collated_webm_to_mp3()
    expected = mock_files[1]
    assert result is expected

    calls = []
    assert create_silent_mp3.mock_calls == calls
    calls = [
        call(
            AwsS3Credentials(
                aws_key="theKeyTuning",
                aws_secret="theSecretTuning",
                region="theRegionTuning",
                bucket="theBucketTuning",
            )
        )
    ]
    assert client_s3.mock_calls == calls
    assert ffmpeg.mock_calls == []
    calls = [
        call.__truediv__("hyperscribe-canvasInstance/patient_patientUuid/note_noteUuid/note_noteUuid.webm"),
        call.__truediv__("hyperscribe-canvasInstance/patient_patientUuid/note_noteUuid/note_noteUuid.mp3"),
    ]
    assert output_dir.mock_calls == calls
    calls = [call.exists()]
    assert mock_files[0].mock_calls == calls
    assert buffers[0].content == b""

    calls = [call.exists()]
    assert mock_files[1].mock_calls == calls
    assert buffers[1].content == b""

    assert mock_files[2].mock_calls == []
    assert mock_files[3].mock_calls == []
    assert mock_files[4].mock_calls == []
    assert mock_files[5].mock_calls == []
    assert buffers[2].content == b""
    assert buffers[3].content == b""
    assert buffers[4].content == b""
    assert buffers[5].content == ""

    assert mock_files[6].mock_calls == []
    assert mock_files[7].mock_calls == []
    assert buffers[6].content == b"locally saved audio content 6"
    assert buffers[7].content == b"locally saved audio content 7"

    reset_mocks()


@patch("evaluations.case_builders.builder_direct_from_tuning.ffmpeg")
def test_create_silent_mp3(ffmpeg):
    silent_file = MagicMock()

    def reset_mocks():
        ffmpeg.reset_mock()
        silent_file.reset_mock()

    tested = helper_instance()

    silent_file.as_posix.side_effect = ["silentFileAsPosix"]
    tested.create_silent_mp3(silent_file)

    calls = [
        call.input("anullsrc=r=44100:cl=stereo", f="lavfi", t=3),
        call.input().output("silentFileAsPosix", acodec="libmp3lame", ar=44100, ab="192k"),
        call.input().output().overwrite_output(),
        call.input().output().overwrite_output().run(overwrite_output=True, quiet=True),
    ]
    assert ffmpeg.mock_calls == calls
    calls = [call.as_posix()]
    assert silent_file.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_direct_from_tuning.ffmpeg")
def test_split_audio(ffmpeg):
    audio_file = MagicMock()
    chunk_files = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        ffmpeg.reset_mock()
        audio_file.reset_mock()
        for idx, item in enumerate(chunk_files):
            item.reset_mock()
            item.as_posix.side_effect = [f"chunk{idx:02d}AsPosix"]

    reset_mocks()

    tested = helper_instance()

    # forced refresh or files does not exist
    # -- duration 200s
    for test in [True, False]:
        tested.cycle_duration = 200
        tested.force_refresh = True
        for chunk_file in chunk_files:
            chunk_file.exists.side_effect = [not test]

        audio_file.as_posix.side_effect = ["audioFileAsPosix"]
        audio_file.stem = "theAudioFile"
        audio_file.parent.__truediv__.side_effect = chunk_files
        ffmpeg.probe.side_effect = [{"format": {"duration": 621}}]

        result = tested.split_audio(audio_file)
        expected = chunk_files[:4]
        assert result == expected

        calls = [
            call.probe("audioFileAsPosix"),
            call.input("audioFileAsPosix", ss=0.0, t=200.0),
            call.input().output("chunk00AsPosix", acodec="copy"),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
            call.input("audioFileAsPosix", ss=200.0, t=200.0),
            call.input().output("chunk01AsPosix", acodec="copy"),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
            call.input("audioFileAsPosix", ss=400.0, t=200.0),
            call.input().output("chunk02AsPosix", acodec="copy"),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
            call.input("audioFileAsPosix", ss=600.0, t=21.0),
            call.input().output("chunk03AsPosix", acodec="copy"),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
        ]
        assert ffmpeg.mock_calls == calls
        calls = [
            call.as_posix(),
            call.parent.__truediv__("theAudioFile_200_001.mp3"),
            call.parent.__truediv__("theAudioFile_200_002.mp3"),
            call.parent.__truediv__("theAudioFile_200_003.mp3"),
            call.parent.__truediv__("theAudioFile_200_004.mp3"),
        ]
        assert audio_file.mock_calls == calls
        for index, chunk_file in enumerate(chunk_files):
            if index < 4:
                calls = [call.as_posix()]
            else:
                calls = []
            assert chunk_file.mock_calls == calls
        reset_mocks()

    # -- duration 300s
    for test in [True, False]:
        tested.cycle_duration = 300
        tested.force_refresh = True
        for chunk_file in chunk_files:
            chunk_file.exists.side_effect = [not test]

        audio_file.as_posix.side_effect = ["audioFileAsPosix"]
        audio_file.stem = "theAudioFile"
        audio_file.parent.__truediv__.side_effect = chunk_files
        ffmpeg.probe.side_effect = [{"format": {"duration": 621}}]

        result = tested.split_audio(audio_file)
        expected = chunk_files[:3]
        assert result == expected

        calls = [
            call.probe("audioFileAsPosix"),
            call.input("audioFileAsPosix", ss=0.0, t=300.0),
            call.input().output("chunk00AsPosix", acodec="copy"),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
            call.input("audioFileAsPosix", ss=300.0, t=300.0),
            call.input().output("chunk01AsPosix", acodec="copy"),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
            call.input("audioFileAsPosix", ss=600.0, t=21.0),
            call.input().output("chunk02AsPosix", acodec="copy"),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
        ]
        assert ffmpeg.mock_calls == calls
        calls = [
            call.as_posix(),
            call.parent.__truediv__("theAudioFile_300_001.mp3"),
            call.parent.__truediv__("theAudioFile_300_002.mp3"),
            call.parent.__truediv__("theAudioFile_300_003.mp3"),
        ]
        assert audio_file.mock_calls == calls
        for index, chunk_file in enumerate(chunk_files):
            if index < 3:
                calls = [call.as_posix()]
            else:
                calls = []
            assert chunk_file.mock_calls == calls
        reset_mocks()

    # no forced refresh and files exist
    tested.cycle_duration = 150
    tested.force_refresh = False
    for chunk_file in chunk_files:
        chunk_file.exists.side_effect = [True]

    audio_file.as_posix.side_effect = ["audioFileAsPosix"]
    audio_file.stem = "theAudioFile"
    audio_file.parent.__truediv__.side_effect = chunk_files
    ffmpeg.probe.side_effect = [{"format": {"duration": 621}}]

    result = tested.split_audio(audio_file)
    expected = chunk_files[:5]
    assert result == expected

    calls = [call.probe("audioFileAsPosix")]
    assert ffmpeg.mock_calls == calls
    calls = [
        call.as_posix(),
        call.parent.__truediv__("theAudioFile_150_001.mp3"),
        call.parent.__truediv__("theAudioFile_150_002.mp3"),
        call.parent.__truediv__("theAudioFile_150_003.mp3"),
        call.parent.__truediv__("theAudioFile_150_004.mp3"),
        call.parent.__truediv__("theAudioFile_150_005.mp3"),
    ]
    assert audio_file.mock_calls == calls
    for index, chunk_file in enumerate(chunk_files):
        if index < 5:
            calls = [call.exists()]
        else:
            calls = []
        assert chunk_file.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_direct_from_tuning.MemoryLog")
@patch.object(BuilderDirectFromTuning, "anonymize_transcripts_chat")
def test_anonymize_transcripts(anonymize_transcripts_chat, memory_log):
    substitutions_file = MagicMock()
    files = [
        # original transcripts
        MagicMock(),
        MagicMock(),
        MagicMock(),
        # anonymized transcripts
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    buffers = [
        MockFile(),
        MockFile(),
        MockFile(),
        MockFile(mode="w"),
        MockFile(mode="w"),
        MockFile(mode="w"),
    ]

    def reset_mocks():
        anonymize_transcripts_chat.reset_mock()
        memory_log.reset_mock()
        substitutions_file.reset_mock()
        substitutions_file.exists.return_value = False
        for idx, item in enumerate(files):
            item.reset_mock()
            item.open.return_value = buffers[idx]
            buffers[idx].content = ""
            if idx < 3:
                side_effects = [files[idx + 3]]
                if idx == 0:
                    side_effects.insert(0, substitutions_file)
                item.parent.__truediv__.side_effect = side_effects
                buffers[idx].content = json.dumps(
                    [{"speaker": f"theSpeaker{idx}", "text": f"theText{idx}", "chunk": idx}],
                )

    reset_mocks()

    tested = helper_instance()

    # no transcript files
    result = tested.anonymize_transcripts([])
    expected = AnonymizationResult(files=[], substitutions=[])
    assert result == expected
    assert anonymize_transcripts_chat.mock_calls == []
    assert memory_log.mock_calls == []
    assert substitutions_file.mock_calls == []
    for index, file in enumerate(files):
        assert files[index].mock_calls == []
        exp_content = ""
        if index < 3:
            exp_content = f'[{{"speaker": "theSpeaker{index}", "text": "theText{index}", "chunk": {index}}}]'
        assert buffers[index].content == exp_content
    reset_mocks()

    # forced refresh or json does not exist
    tested.force_refresh = True
    tests = [
        (True, True),
        (True, False),
        (False, False),
    ]
    for json_file_exists, substitutions_file_exists in tests:
        substitutions_file.exists.side_effect = [substitutions_file_exists]
        if substitutions_file_exists:
            substitutions_file.read_text.side_effect = [
                '[{"originalEntity": "theOriginal", "anonymizedWith": "theAnonymized"}]',
            ]

        for item in files[3:]:
            item.exists.side_effect = [json_file_exists]

        memory_log.instance.side_effect = ["theMemoryLog"]
        anonymize_transcripts_chat.side_effect = [
            Anonymization(
                source=[],
                result=[
                    CaseExchange(speaker="theSpeaker1", text="theText1", chunk=1),
                    CaseExchange(speaker="theSpeaker1", text="theText2", chunk=1),
                    CaseExchange(speaker="theSpeaker2", text="theText3", chunk=1),
                ],
                substitutions=[
                    AnonymizationSubstitution(original_entity="theOriginal1", anonymized_with="theAnonymized1"),
                ],
            ),
            Anonymization(
                source=[],
                result=[
                    CaseExchange(speaker="theSpeaker1", text="theText1", chunk=2),
                    CaseExchange(speaker="theSpeaker1", text="theText2", chunk=2),
                    CaseExchange(speaker="theSpeaker2", text="theText3", chunk=2),
                ],
                substitutions=[
                    AnonymizationSubstitution(original_entity="theOriginal1", anonymized_with="theAnonymized1"),
                    AnonymizationSubstitution(original_entity="theOriginal2", anonymized_with="theAnonymized2"),
                    AnonymizationSubstitution(original_entity="theOriginal3", anonymized_with="theAnonymized3"),
                ],
            ),
            Anonymization(
                source=[],
                result=[
                    CaseExchange(speaker="theSpeaker1", text="theText1", chunk=3),
                    CaseExchange(speaker="theSpeaker1", text="theText2", chunk=3),
                    CaseExchange(speaker="theSpeaker2", text="theText3", chunk=3),
                ],
                substitutions=[
                    AnonymizationSubstitution(original_entity="theOriginal1", anonymized_with="theAnonymized1"),
                    AnonymizationSubstitution(original_entity="theOriginal2", anonymized_with="theAnonymized2"),
                    AnonymizationSubstitution(original_entity="theOriginal3", anonymized_with="theAnonymized3"),
                    AnonymizationSubstitution(original_entity="theOriginal4", anonymized_with="theAnonymized4"),
                ],
            ),
        ]

        result = tested.anonymize_transcripts(files[:3])
        substitutions = [
            AnonymizationSubstitution(original_entity="theOriginal", anonymized_with="theAnonymized"),
            AnonymizationSubstitution(original_entity="theOriginal1", anonymized_with="theAnonymized1"),
            AnonymizationSubstitution(original_entity="theOriginal2", anonymized_with="theAnonymized2"),
            AnonymizationSubstitution(original_entity="theOriginal3", anonymized_with="theAnonymized3"),
            AnonymizationSubstitution(original_entity="theOriginal4", anonymized_with="theAnonymized4"),
        ]
        start_idx = 1
        if substitutions_file_exists:
            start_idx = 0
        expected = AnonymizationResult(files=files[3:], substitutions=substitutions[start_idx:])
        assert result == expected

        calls = [
            call("theMemoryLog", files[0], substitutions[start_idx:1]),
            call("theMemoryLog", files[1], substitutions[start_idx:2]),
            call("theMemoryLog", files[2], substitutions[start_idx:-1]),
        ]
        assert anonymize_transcripts_chat.mock_calls == calls
        calls = [call.instance(tested.identification, "anonymize_transcript", tested.s3_logs_credentials)]
        assert memory_log.mock_calls == calls
        calls = [call.exists()]
        content = ""
        if substitutions_file_exists:
            calls.append(call.read_text())
            content = '{"originalEntity": "theOriginal", "anonymizedWith": "theAnonymized"}, '
        calls.extend(
            [
                call.write_text(f'[{content}{{"originalEntity": "theOriginal1", "anonymizedWith": "theAnonymized1"}}]'),
                call.write_text(
                    f"[{content}"
                    '{"originalEntity": "theOriginal1", "anonymizedWith": "theAnonymized1"}, '
                    '{"originalEntity": "theOriginal2", "anonymizedWith": "theAnonymized2"}, '
                    '{"originalEntity": "theOriginal3", "anonymizedWith": "theAnonymized3"}]'
                ),
                call.write_text(
                    f"[{content}"
                    '{"originalEntity": "theOriginal1", "anonymizedWith": "theAnonymized1"}, '
                    '{"originalEntity": "theOriginal2", "anonymizedWith": "theAnonymized2"}, '
                    '{"originalEntity": "theOriginal3", "anonymizedWith": "theAnonymized3"}, '
                    '{"originalEntity": "theOriginal4", "anonymizedWith": "theAnonymized4"}]'
                ),
            ]
        )
        assert substitutions_file.mock_calls == calls

        for index, file in enumerate(files):
            if index == 0:
                calls = [
                    call.parent.__truediv__("anonymized_substitutions.json"),
                    call.parent.__truediv__(f"transcript_anonymized_{index:03d}.json"),
                ]
            elif index < 3:
                calls = [call.parent.__truediv__(f"transcript_anonymized_{index:03d}.json")]
            else:
                calls = [call.exists(), call.open("w")]
            assert files[index].mock_calls == calls

            if index < 3:
                exp_content = json.dumps([{"speaker": f"theSpeaker{index}", "text": f"theText{index}", "chunk": index}])
            elif index == 3:
                exp_content = json.dumps(
                    [
                        {"speaker": "theSpeaker1", "text": "theText1", "chunk": 1},
                        {"speaker": "theSpeaker1", "text": "theText2", "chunk": 1},
                        {"speaker": "theSpeaker2", "text": "theText3", "chunk": 1},
                    ],
                    indent=2,
                )
            elif index == 4:
                exp_content = json.dumps(
                    [
                        {"speaker": "theSpeaker1", "text": "theText1", "chunk": 2},
                        {"speaker": "theSpeaker1", "text": "theText2", "chunk": 2},
                        {"speaker": "theSpeaker2", "text": "theText3", "chunk": 2},
                    ],
                    indent=2,
                )
            else:
                exp_content = json.dumps(
                    [
                        {"speaker": "theSpeaker1", "text": "theText1", "chunk": 3},
                        {"speaker": "theSpeaker1", "text": "theText2", "chunk": 3},
                        {"speaker": "theSpeaker2", "text": "theText3", "chunk": 3},
                    ],
                    indent=2,
                )
            assert buffers[index].content == exp_content
        reset_mocks()

    # no forced refresh and json does exist, substitutions JSON exists
    reset_mocks()
    tested.force_refresh = False
    for item in files[3:]:
        item.exists.side_effect = [True]
    for item in buffers:
        item.mode = "r"
    substitutions_file.exists.side_effect = [True]
    substitutions_file.read_text.side_effect = [
        '[{"originalEntity": "theOriginal", "anonymizedWith": "theAnonymized"}]',
    ]
    memory_log.instance.side_effect = ["theMemoryLog"]

    result = tested.anonymize_transcripts(files[:3])
    expected = AnonymizationResult(
        files=files[3:],
        substitutions=[AnonymizationSubstitution(original_entity="theOriginal", anonymized_with="theAnonymized")],
    )
    assert result == expected

    calls = []
    assert anonymize_transcripts_chat.mock_calls == calls
    calls = [call.instance(tested.identification, "anonymize_transcript", tested.s3_logs_credentials)]
    assert memory_log.mock_calls == calls
    calls = [call.exists(), call.read_text()]
    assert substitutions_file.mock_calls == calls

    for index, file in enumerate(files):
        if index == 0:
            calls = [
                call.parent.__truediv__("anonymized_substitutions.json"),
                call.parent.__truediv__(f"transcript_anonymized_{index:03d}.json"),
            ]
        elif index < 3:
            calls = [call.parent.__truediv__(f"transcript_anonymized_{index:03d}.json")]
        else:
            calls = [call.exists()]
        assert files[index].mock_calls == calls

        if index < 3:
            exp_content = json.dumps([{"speaker": f"theSpeaker{index}", "text": f"theText{index}", "chunk": index}])
        else:
            exp_content = ""
        assert buffers[index].content == exp_content
    reset_mocks()


@patch("evaluations.case_builders.builder_direct_from_tuning.Helper")
@patch("evaluations.case_builders.builder_direct_from_tuning.MemoryLog")
@patch.object(BuilderDirectFromTuning, "schema_code_items")
def test_anonymize_limited_cache(schema_code_items, memory_log, helper):
    def reset_mocks():
        schema_code_items.reset_mock()
        memory_log.reset_mock()
        helper.reset_mock()

    system_prompt = [
        "You are part of an anonymization process.",
        "Your task is to carefully achieve the substitutions as directed.",
        "",
    ]
    user_prompt = [
        "The list of all substitutions is:",
        "```json",
        "[\n "
        '{\n  "originalEntity": "theOriginal1",\n  "anonymizedWith": "theAnonymized1"\n },\n '
        '{\n  "originalEntity": "theOriginal2",\n  "anonymizedWith": "theAnonymized2"\n }\n]',
        "```",
        "",
        "The original data is:",
        "```json",
        "[\n "
        '{\n  "uuid": "uuid1",\n  "label": "name1",\n  "code": "code1"\n },\n '
        '{\n  "uuid": "uuid2",\n  "label": "name2",\n  "code": "code2"\n }\n]',
        "```",
        "",
        "Transform the original data following the requested substitutions in a JSON Markdown block.",
        "",
    ]

    tested = helper_instance()
    # no substitutions
    schema_code_items.side_effect = []
    memory_log.instance.side_effect = []
    helper.chatter.return_value.chat.side_effect = []
    cache = LimitedCache.load_from_json(
        {
            "existingStaffMembers": [
                {"uuid": "uuid1", "code": "code1", "label": "name1"},
                {"uuid": "uuid2", "code": "code2", "label": "name2"},
            ]
        }
    )
    result = tested.anonymize_limited_cache([], cache)
    assert result is cache

    assert schema_code_items.mock_calls == []
    assert memory_log.mock_calls == []
    assert helper.mock_calls == []
    reset_mocks()

    # no staff members
    schema_code_items.side_effect = []
    memory_log.instance.side_effect = []
    helper.chatter.return_value.chat.side_effect = []
    cache = LimitedCache.load_from_json({"existingStaffMembers": []})
    result = tested.anonymize_limited_cache(
        [
            AnonymizationSubstitution(original_entity="theOriginal1", anonymized_with="theAnonymized1"),
            AnonymizationSubstitution(original_entity="theOriginal2", anonymized_with="theAnonymized2"),
        ],
        cache,
    )
    assert result is cache

    assert schema_code_items.mock_calls == []
    assert memory_log.mock_calls == []
    assert helper.mock_calls == []
    reset_mocks()

    # all good
    schema_code_items.side_effect = ["theCodeItemsSchema"]
    memory_log.instance.side_effect = ["theMemoryLogInstance"]
    helper.chatter.return_value.chat.side_effect = [
        JsonExtract(
            has_error=False,
            error="",
            content=[
                [
                    {"uuid": "uuidX", "code": "codeX", "label": "nameX"},
                    {"uuid": "uuidY", "code": "codeY", "label": "nameY"},
                    {"uuid": "uuidZ", "code": "codeZ", "label": "nameZ"},
                ]
            ],
        )
    ]
    cache = LimitedCache.load_from_json(
        {
            "existingStaffMembers": [
                {"uuid": "uuid1", "code": "code1", "label": "name1"},
                {"uuid": "uuid2", "code": "code2", "label": "name2"},
            ]
        }
    )
    result = tested.anonymize_limited_cache(
        [
            AnonymizationSubstitution(original_entity="theOriginal1", anonymized_with="theAnonymized1"),
            AnonymizationSubstitution(original_entity="theOriginal2", anonymized_with="theAnonymized2"),
        ],
        cache,
    )
    expected = [
        CodedItem(uuid="uuidX", code="codeX", label="nameX"),
        CodedItem(uuid="uuidY", code="codeY", label="nameY"),
        CodedItem(uuid="uuidZ", code="codeZ", label="nameZ"),
    ]
    assert result is cache
    assert result._staff_members == expected

    calls = [call()]
    assert schema_code_items.mock_calls == calls
    calls = [call.instance(tested.identification, "anonymize_limited_cache", tested.s3_logs_credentials)]
    assert memory_log.mock_calls == calls
    calls = [
        call.chatter(tested.settings, "theMemoryLogInstance"),
        call.chatter().set_system_prompt(system_prompt),
        call.chatter().set_user_prompt(user_prompt),
        call.chatter().chat(["theCodeItemsSchema"]),
    ]
    assert helper.mock_calls == calls
    reset_mocks()

    # no response
    schema_code_items.side_effect = ["theCodeItemsSchema"]
    memory_log.instance.side_effect = ["theMemoryLogInstance"]
    helper.chatter.return_value.chat.side_effect = [
        JsonExtract(
            has_error=True,
            error="theError",
            content=[
                [
                    {"uuid": "uuidX", "code": "codeX", "label": "nameX"},
                    {"uuid": "uuidY", "code": "codeY", "label": "nameY"},
                    {"uuid": "uuidZ", "code": "codeZ", "label": "nameZ"},
                ]
            ],
        )
    ]
    cache = LimitedCache.load_from_json(
        {
            "existingStaffMembers": [
                {"uuid": "uuid1", "code": "code1", "label": "name1"},
                {"uuid": "uuid2", "code": "code2", "label": "name2"},
            ]
        }
    )
    result = tested.anonymize_limited_cache(
        [
            AnonymizationSubstitution(original_entity="theOriginal1", anonymized_with="theAnonymized1"),
            AnonymizationSubstitution(original_entity="theOriginal2", anonymized_with="theAnonymized2"),
        ],
        cache,
    )
    assert result is cache

    calls = [call()]
    assert schema_code_items.mock_calls == calls
    calls = [call.instance(tested.identification, "anonymize_limited_cache", tested.s3_logs_credentials)]
    assert memory_log.mock_calls == calls
    calls = [
        call.chatter(tested.settings, "theMemoryLogInstance"),
        call.chatter().set_system_prompt(system_prompt),
        call.chatter().set_user_prompt(user_prompt),
        call.chatter().chat(["theCodeItemsSchema"]),
    ]
    assert helper.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_direct_from_tuning.Helper")
@patch.object(BuilderDirectFromTuning, "anonymize_transcripts_check")
@patch.object(BuilderDirectFromTuning, "schema_changes")
@patch.object(BuilderDirectFromTuning, "schema_anonymization")
def test_anonymize_transcripts_chat(schema_anonymization, schema_changes, anonymize_transcripts_check, helper):
    memory_log = MagicMock()
    transcript = MagicMock()
    buffer = MockFile()

    def reset_mocks():
        schema_anonymization.reset_mock()
        schema_changes.reset_mock()
        anonymize_transcripts_check.reset_mock()
        helper.reset_mock()
        memory_log.reset_mock()
        transcript.reset_mock()
        transcript.open.return_value = buffer
        buffer.content = json.dumps(
            [
                {"speaker": "theSpeaker1", "text": "theText1", "chunk": 3},
                {"speaker": "theSpeaker1", "text": "theText2", "chunk": 3},
                {"speaker": "theSpeaker2", "text": "theText3", "chunk": 4},
            ],
        )
        transcript.as_posix.side_effect = ["theTranscriptPosix"]

    reset_mocks()

    exchange_123 = [
        CaseExchange(speaker="theSpeaker1", text="theText1", chunk=3),
        CaseExchange(speaker="theSpeaker1", text="theText2", chunk=3),
        CaseExchange(speaker="theSpeaker2", text="theText3", chunk=4),
    ]
    exchange_xyz = [
        CaseExchange(speaker="theSpeaker1", text="theTextX", chunk=3),
        CaseExchange(speaker="theSpeaker1", text="theTextY", chunk=3),
        CaseExchange(speaker="theSpeaker2", text="theTextZ", chunk=4),
    ]
    exchange_abc = [
        CaseExchange(speaker="theSpeaker1", text="theTextA", chunk=3),
        CaseExchange(speaker="theSpeaker1", text="theTextB", chunk=3),
        CaseExchange(speaker="theSpeaker2", text="theTextC", chunk=4),
    ]
    exchange_efg = [
        CaseExchange(speaker="theSpeaker1", text="theTextE", chunk=3),
        CaseExchange(speaker="theSpeaker1", text="theTextF", chunk=3),
        CaseExchange(speaker="theSpeaker2", text="theTextG", chunk=4),
    ]
    substitutions = [
        AnonymizationSubstitution(original_entity="theOriginal1", anonymized_with="theAnonymized1"),
        AnonymizationSubstitution(original_entity="theOriginal2", anonymized_with="theAnonymized2"),
        AnonymizationSubstitution(original_entity="theOriginal3", anonymized_with="theAnonymized3"),
        AnonymizationSubstitution(original_entity="theOriginal4", anonymized_with="theAnonymized4"),
    ]

    system_prompt = [
        "You are a medical transcript anonymization specialist with expertise in healthcare privacy compliance.",
        "Your task is to remove all personally identifiable information (PII) from medical transcripts while "
        "preserving complete clinical context and medical accuracy through realistic replacements.",
        "",
        "**Anonymization Approach**",
        "Use realistic, plausible substitutions rather than placeholders:",
        "- Replace names with culturally appropriate alternatives of similar length/structure",
        "- Substitute locations with comparable geographic areas (similar urban/rural, climate, healthcare "
        "infrastructure)",
        "- Change dates, several days, and times while maintaining temporal relationships and seasonal context "
        "when medically relevant",
        "- Replace specific institutions with similar types (community hospital → regional medical center)",
        "- Replace any identification numbers, including but not limited to, zip code, phone, fax, social security, "
        "medical record, license plate, account, serial numbers, IP address, code",
        "- Generalize any other unique identifying numbers, characteristics, or codes that could be used to identify "
        "the individual or their household",
        "",
        "",
        "**Medical Preservation Requirements**",
        "- Maintain ALL clinical terminology, symptoms, diagnoses, differential diagnoses",
        "- Preserve exact medication names, dosages, frequencies, routes of administration",
        "- Keep all vital signs, laboratory values, imaging results, and measurements unchanged",
        "- Retain medical history details, surgical history, family medical history",
        "- Preserve healthcare provider specialties and their clinical roles",
        "- Maintain treatment timelines and follow-up schedules precisely",
        "- Keep allergies, adverse reactions, and contraindications intact",
        "",
        "Format the anonymized transcript following the JSON Schema:",
        "```json",
        '{\n "schema": "anonymization"\n}',
        "```",
        "",
        "**Global Consistency**: Use identical replacements for the exact same entity throughout the entire "
        "transcript.",
        "But, two different entities cannot use the same anonymization replacement.",
        "",
        "",
        "In a second JSON Markdown block, format the report of the changes following the JSON Schema:",
        "```json",
        '{\n "schema": "changes"\n}',
        "```",
        "",
    ]
    user_prompts = {
        "firstRound": [
            "Please anonymize the following medical transcript while preserving all clinical information:",
            "```json",
            '[{"speaker": "theSpeaker1", "text": "theText1", "chunk": 3}, '
            '{"speaker": "theSpeaker1", "text": "theText2", "chunk": 3}, '
            '{"speaker": "theSpeaker2", "text": "theText3", "chunk": 4}]',
            "```",
            "",
            "Follow rigorously the instructions and provide both JSON Markdown code blocks using the mentioned "
            "JSON Schemas.",
        ],
        "usedAnonymizations": [
            "Continue to used these anonymized entities:",
            "```json",
            "[\n "
            '{\n  "originalEntity": "theOriginal1",\n  "anonymizedWith": "theAnonymized1"\n },\n '
            '{\n  "originalEntity": "theOriginal3",\n  "anonymizedWith": "theAnonymized3"\n }\n]',
            "```",
            "",
            "Also, include this list with any new substitution in your response to ensure you will used "
            "the sames substitutions for uniquely the exact same entities (which means for the dates, "
            "provide the full dates, not just the day of week)",
        ],
        "firstError": [
            "Here is the list of the errors you made in regards to the anonymization:",
            "```json",
            '[\n "error1",\n "error2"\n]',
            "```",
            "",
            "While still following rigorously the initial instructions, correct your response and provide both "
            "JSON Markdown code blocks using the mentioned JSON Schemas.",
        ],
        "secondError": [
            "Here is the list of the errors you made in regards to the anonymization:",
            "```json",
            '[\n "error3"\n]',
            "```",
            "",
            "While still following rigorously the initial instructions, correct your response and provide both "
            "JSON Markdown code blocks using the mentioned JSON Schemas.",
        ],
    }
    model_prompts = {
        "firstResponse": [
            "```json",
            "[\n "
            '{\n  "speaker": "theSpeaker1",\n  "text": "theTextX",\n  "chunk": 3\n },\n '
            '{\n  "speaker": "theSpeaker1",\n  "text": "theTextY",\n  "chunk": 3\n },\n '
            '{\n  "speaker": "theSpeaker2",\n  "text": "theTextZ",\n  "chunk": 4\n }\n]',
            "```",
            "```json",
            "[\n "
            '{\n  "originalEntity": "theOriginal1",\n  "anonymizedWith": "theAnonymized1"\n },\n '
            '{\n  "originalEntity": "theOriginal2",\n  "anonymizedWith": "theAnonymized2"\n }\n]',
            "```",
        ],
        "secondResponse": [
            "```json",
            "[\n "
            '{\n  "speaker": "theSpeaker1",\n  "text": "theTextA",\n  "chunk": 3\n },\n '
            '{\n  "speaker": "theSpeaker1",\n  "text": "theTextB",\n  "chunk": 3\n },\n '
            '{\n  "speaker": "theSpeaker2",\n  "text": "theTextC",\n  "chunk": 4\n }\n]',
            "```",
            "```json",
            "[\n "
            '{\n  "originalEntity": "theOriginal1",\n  "anonymizedWith": "theAnonymized1"\n },\n '
            '{\n  "originalEntity": "theOriginal3",\n  "anonymizedWith": "theAnonymized3"\n }\n]',
            "```",
        ],
    }
    tested = helper_instance()

    # no error
    schema_anonymization.side_effect = [{"schema": "anonymization"}]
    schema_changes.side_effect = [{"schema": "changes"}]
    anonymize_transcripts_check.side_effect = [AnonymizationError(has_errors=False, errors=[])]
    helper.chatter.return_value.chat.side_effect = [
        JsonExtract(
            error="",
            has_error=False,
            content=[
                [
                    {"speaker": "theSpeaker1", "text": "theTextX", "chunk": 3},
                    {"speaker": "theSpeaker1", "text": "theTextY", "chunk": 3},
                    {"speaker": "theSpeaker2", "text": "theTextZ", "chunk": 4},
                ],
                [
                    {"originalEntity": "theOriginal1", "anonymizedWith": "theAnonymized1"},
                    {"originalEntity": "theOriginal2", "anonymizedWith": "theAnonymized2"},
                ],
            ],
        ),
    ]

    result = tested.anonymize_transcripts_chat(memory_log, transcript, [substitutions[i] for i in [0, 2]])
    expected = Anonymization(source=exchange_123, result=exchange_xyz, substitutions=[substitutions[i] for i in [0, 1]])
    assert result == expected

    calls = [call()]
    assert schema_anonymization.mock_calls == calls
    calls = [call()]
    assert schema_changes.mock_calls == calls
    calls = [call(memory_log, expected)]
    assert anonymize_transcripts_check.mock_calls == calls
    calls = [
        call.chatter(tested.settings, memory_log),
        call.chatter().set_system_prompt(system_prompt),
        call.chatter().set_user_prompt(user_prompts["firstRound"]),
        call.chatter().set_user_prompt(user_prompts["usedAnonymizations"]),
        call.chatter().chat([{"schema": "anonymization"}, {"schema": "changes"}]),
    ]
    assert helper.mock_calls == calls
    assert memory_log.mock_calls == []
    calls = [call.open("r")]
    assert transcript.mock_calls == calls
    reset_mocks()

    # two errors
    # -- max error 3
    with patch.object(BuilderDirectFromTuning, "MAX_ANONYMIZATION_ATTEMPTS", 3):
        schema_anonymization.side_effect = [{"schema": "anonymization"}]
        schema_changes.side_effect = [{"schema": "changes"}]
        anonymize_transcripts_check.side_effect = [
            AnonymizationError(has_errors=True, errors=["error1", "error2"]),
            AnonymizationError(has_errors=True, errors=["error3"]),
            AnonymizationError(has_errors=False, errors=[]),
        ]
        helper.chatter.return_value.chat.side_effect = [
            JsonExtract(
                error="",
                has_error=False,
                content=[
                    [
                        {"speaker": "theSpeaker1", "text": "theTextX", "chunk": 3},
                        {"speaker": "theSpeaker1", "text": "theTextY", "chunk": 3},
                        {"speaker": "theSpeaker2", "text": "theTextZ", "chunk": 4},
                    ],
                    [
                        {"originalEntity": "theOriginal1", "anonymizedWith": "theAnonymized1"},
                        {"originalEntity": "theOriginal2", "anonymizedWith": "theAnonymized2"},
                    ],
                ],
            ),
            JsonExtract(
                error="",
                has_error=False,
                content=[
                    [
                        {"speaker": "theSpeaker1", "text": "theTextA", "chunk": 3},
                        {"speaker": "theSpeaker1", "text": "theTextB", "chunk": 3},
                        {"speaker": "theSpeaker2", "text": "theTextC", "chunk": 4},
                    ],
                    [
                        {"originalEntity": "theOriginal1", "anonymizedWith": "theAnonymized1"},
                        {"originalEntity": "theOriginal3", "anonymizedWith": "theAnonymized3"},
                    ],
                ],
            ),
            JsonExtract(
                error="",
                has_error=False,
                content=[
                    [
                        {"speaker": "theSpeaker1", "text": "theTextE", "chunk": 3},
                        {"speaker": "theSpeaker1", "text": "theTextF", "chunk": 3},
                        {"speaker": "theSpeaker2", "text": "theTextG", "chunk": 4},
                    ],
                    [
                        {"originalEntity": "theOriginal1", "anonymizedWith": "theAnonymized1"},
                        {"originalEntity": "theOriginal4", "anonymizedWith": "theAnonymized4"},
                    ],
                ],
            ),
        ]

        result = tested.anonymize_transcripts_chat(memory_log, transcript, [])
        expected = Anonymization(
            source=exchange_123,
            result=exchange_efg,
            substitutions=[substitutions[i] for i in [0, 3]],
        )
        assert result == expected

        calls = [call()]
        assert schema_anonymization.mock_calls == calls
        calls = [call()]
        assert schema_changes.mock_calls == calls
        calls = [
            call(
                memory_log,
                Anonymization(
                    source=exchange_123,
                    result=exchange_xyz,
                    substitutions=[substitutions[i] for i in [0, 1]],
                ),
            ),
            call(
                memory_log,
                Anonymization(
                    source=exchange_123,
                    result=exchange_abc,
                    substitutions=[substitutions[i] for i in [0, 2]],
                ),
            ),
            call(memory_log, expected),
        ]
        assert anonymize_transcripts_check.mock_calls == calls
        calls = [
            call.chatter(tested.settings, memory_log),
            call.chatter().set_system_prompt(system_prompt),
            call.chatter().set_user_prompt(user_prompts["firstRound"]),
            call.chatter().chat([{"schema": "anonymization"}, {"schema": "changes"}]),
            call.chatter().set_model_prompt(model_prompts["firstResponse"]),
            call.chatter().set_user_prompt(user_prompts["firstError"]),
            call.chatter().chat([{"schema": "anonymization"}, {"schema": "changes"}]),
            call.chatter().set_model_prompt(model_prompts["secondResponse"]),
            call.chatter().set_user_prompt(user_prompts["secondError"]),
            call.chatter().chat([{"schema": "anonymization"}, {"schema": "changes"}]),
        ]
        assert helper.mock_calls == calls
        assert memory_log.mock_calls == []
        calls = [call.open("r")]
        assert transcript.mock_calls == calls
        reset_mocks()
    # -- max error 2
    with pytest.raises(Exception) as e:
        with patch.object(BuilderDirectFromTuning, "MAX_ANONYMIZATION_ATTEMPTS", 2):
            schema_anonymization.side_effect = [{"schema": "anonymization"}]
            schema_changes.side_effect = [{"schema": "changes"}]
            anonymize_transcripts_check.side_effect = [
                AnonymizationError(has_errors=True, errors=["error1", "error2"]),
                AnonymizationError(has_errors=True, errors=["error3"]),
                AnonymizationError(has_errors=False, errors=[]),
            ]
            helper.chatter.return_value.chat.side_effect = [
                JsonExtract(
                    error="",
                    has_error=False,
                    content=[
                        [
                            {"speaker": "theSpeaker1", "text": "theTextX", "chunk": 3},
                            {"speaker": "theSpeaker1", "text": "theTextY", "chunk": 3},
                            {"speaker": "theSpeaker2", "text": "theTextZ", "chunk": 4},
                        ],
                        [
                            {"originalEntity": "theOriginal1", "anonymizedWith": "theAnonymized1"},
                            {"originalEntity": "theOriginal2", "anonymizedWith": "theAnonymized2"},
                        ],
                    ],
                ),
                JsonExtract(
                    error="",
                    has_error=False,
                    content=[
                        [
                            {"speaker": "theSpeaker1", "text": "theTextA", "chunk": 3},
                            {"speaker": "theSpeaker1", "text": "theTextB", "chunk": 3},
                            {"speaker": "theSpeaker2", "text": "theTextC", "chunk": 4},
                        ],
                        [
                            {"originalEntity": "theOriginal1", "anonymizedWith": "theAnonymized1"},
                            {"originalEntity": "theOriginal3", "anonymizedWith": "theAnonymized3"},
                        ],
                    ],
                ),
                JsonExtract(
                    error="",
                    has_error=False,
                    content=[
                        [
                            {"speaker": "theSpeaker1", "text": "theTextE", "chunk": 3},
                            {"speaker": "theSpeaker1", "text": "theTextF", "chunk": 3},
                            {"speaker": "theSpeaker2", "text": "theTextG", "chunk": 4},
                        ],
                        [
                            {"originalEntity": "theOriginal1", "anonymizedWith": "theAnonymized1"},
                            {"originalEntity": "theOriginal4", "anonymizedWith": "theAnonymized4"},
                        ],
                    ],
                ),
            ]

            result = tested.anonymize_transcripts_chat(memory_log, transcript, [])
            expected = Anonymization(
                source=exchange_123,
                result=exchange_efg,
                substitutions=[substitutions[i] for i in [0, 3]],
            )
            assert result == expected

            calls = [call()]
            assert schema_anonymization.mock_calls == calls
            calls = [call()]
            assert schema_changes.mock_calls == calls
            calls = [
                call(
                    memory_log,
                    Anonymization(
                        source=exchange_123,
                        result=exchange_xyz,
                        substitutions=[substitutions[i] for i in [0, 1]],
                    ),
                ),
                call(
                    memory_log,
                    Anonymization(
                        source=exchange_123,
                        result=exchange_abc,
                        substitutions=[substitutions[i] for i in [0, 2]],
                    ),
                ),
                call(memory_log, expected),
            ]
            assert anonymize_transcripts_check.mock_calls == calls
            calls = [
                call.chatter(tested.settings, memory_log),
                call.chatter().set_system_prompt(system_prompt),
                call.chatter().set_user_prompt(user_prompts["firstRound"]),
                call.chatter().chat([{"schema": "anonymization"}, {"schema": "changes"}]),
                call.chatter().set_model_prompt(model_prompts["firstResponse"]),
                call.chatter().set_user_prompt(user_prompts["firstError"]),
                call.chatter().chat([{"schema": "anonymization"}, {"schema": "changes"}]),
                call.chatter().set_model_prompt(model_prompts["secondResponse"]),
                call.chatter().set_user_prompt(user_prompts["secondError"]),
                call.chatter().chat([{"schema": "anonymization"}, {"schema": "changes"}]),
            ]
            assert helper.mock_calls == calls
            assert memory_log.mock_calls == []
            calls = [call.open("r")]
            assert transcript.mock_calls == calls
            reset_mocks()
    exp_error = "Could not anonymize transcript: theTranscriptPosix"
    assert str(e.value) == exp_error


@patch("evaluations.case_builders.builder_direct_from_tuning.Helper")
@patch.object(BuilderDirectFromTuning, "schema_errors")
def test_anonymize_transcripts_check(schema_errors, helper):
    memory_log = MagicMock()

    def reset_mocks():
        schema_errors.reset_mock()
        helper.reset_mock()
        memory_log.reset_mock()

    system_prompt = [
        "You are a validator of medical transcript anonymization with expertise in healthcare privacy compliance.",
        "",
        "The user will submit two transcripts: the original and the anonymized version.",
        "",
        "Your task is to identify any violations of anonymization rules based on the following principles:",
        "",
        "Any identifying information relating to an individual or to relatives, employers, "
        "or household members must be "
        "**replaced with realistic, synthetic alternatives** that do **not allow anyone to identify "
        "the actual individuals**. "
        "These replacements must be:",
        "",
        "- Plausible and coherent in context,",
        "- Non-traceable to the real identities,",
        "- Not obviously artificial (e.g. 'XXX' or 'Redacted' are invalid replacements).",
        "",
        "Substitution of identifiers with realistic but non-identifying values is considered fully compliant. "
        "You must **not report an error** if the original identifier was correctly substituted in a way that "
        "protects the individual's identity.",
        "",
        "Only report an error when:",
        "- The original identifier remains in the anonymized transcript,",
        "- The replacement is unrealistic or placeholder-like,",
        "- The replacement is still obviously identifying the real people,",
        "- The rules listed below are otherwise **blatantly** violated.",
        "",
        "The following identifiers **must** be anonymized through valid substitution:",
        "",
        "(A) Names;  ",
        "(B) All geographic subdivisions smaller than a State, including street address, city, county, "
        "precinct, zip code, and their equivalent geocodes;  ",
        "(C) All elements of dates (except year) for dates directly related to an individual, including "
        "birth date, admission date, discharge date, date of death;  ",
        "(D) Telephone numbers;  ",
        "(E) Fax numbers;  ",
        "(F) Electronic mail addresses;  ",
        "(G) Social security numbers;  ",
        "(H) Medical record numbers;  ",
        "(I) Health plan beneficiary numbers;  ",
        "(J) Account numbers;  ",
        "(K) Certificate/license numbers;  ",
        "(L) Vehicle identifiers and serial numbers, including license plate numbers;  ",
        "(M) Device identifiers and serial numbers;  ",
        "(N) Web Universal Resource Locators (URLs);  ",
        "(O) Internet Protocol (IP) address numbers;  ",
        "(P) Any other unique identifying number, characteristic, or code.",
        "",
        "Format your output strictly using this JSON Schema:",
        "```json",
        '"theSchemaErrors"',
        "```",
        "",
        "Report only errors with the full context; do not comment if there is no error.",
    ]
    user_prompt = [
        "The original transcript is:",
        "```json",
        '[{"speaker": "theSpeaker1", "text": "theText1", "chunk": 3},'
        ' {"speaker": "theSpeaker1", "text": "theText2", "chunk": 3},'
        ' {"speaker": "theSpeaker2", "text": "theText3", "chunk": 4}]',
        "```",
        "",
        "The anonymized transcript is:",
        "```json",
        '[{"speaker": "theSpeaker1", "text": "theTextX", "chunk": 3},'
        ' {"speaker": "theSpeaker1", "text": "theTextY", "chunk": 3},'
        ' {"speaker": "theSpeaker2", "text": "theTextZ", "chunk": 4}]',
        "```",
        "",
        "Follow rigorously the instructions and report any broken rules using the mentioned JSON Schema.",
        "If there is no error, just send back an empty list in the JSON Markdown block.",
    ]

    tested = helper_instance()

    tests = [
        (JsonExtract(has_error=False, error="", content=[[]]), AnonymizationError(has_errors=False, errors=[])),
        (
            JsonExtract(
                has_error=False,
                error="",
                content=[
                    [
                        {"explanation": "error1", "error": True},
                        {"explanation": "error2", "error": False},
                        {"explanation": "error3", "error": True},
                        {"explanation": "error4", "error": True},
                    ]
                ],
            ),
            AnonymizationError(has_errors=True, errors=["error1", "error3", "error4"]),
        ),
    ]
    for side_effect, expected in tests:
        schema_errors.side_effect = ["theSchemaErrors"]
        helper.chatter.return_value.chat.side_effect = [side_effect]

        anonymization = Anonymization(
            source=[
                CaseExchange(speaker="theSpeaker1", text="theText1", chunk=3),
                CaseExchange(speaker="theSpeaker1", text="theText2", chunk=3),
                CaseExchange(speaker="theSpeaker2", text="theText3", chunk=4),
            ],
            result=[
                CaseExchange(speaker="theSpeaker1", text="theTextX", chunk=3),
                CaseExchange(speaker="theSpeaker1", text="theTextY", chunk=3),
                CaseExchange(speaker="theSpeaker2", text="theTextZ", chunk=4),
            ],
            substitutions=[AnonymizationSubstitution(original_entity="theOriginal1", anonymized_with="theAnonymized1")],
        )

        result = tested.anonymize_transcripts_check(memory_log, anonymization)
        assert result == expected

        calls = [call()]
        assert schema_errors.mock_calls == calls
        calls = [
            call.chatter(tested.settings, memory_log),
            call.chatter().set_system_prompt(system_prompt),
            call.chatter().set_user_prompt(user_prompt),
            call.chatter().chat(["theSchemaErrors"]),
        ]
        assert helper.mock_calls == calls
        assert memory_log.mock_calls == []
        reset_mocks()


def test_schema_anonymization():
    tested = BuilderDirectFromTuning
    result = tested.schema_anonymization()
    expected = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "array",
        "items": {
            "type": "object",
            "required": ["speaker", "text", "chunk"],
            "properties": {
                "speaker": {"type": "string", "minLength": 1},
                "text": {"type": "string"},
                "chunk": {"type": "integer"},
            },
            "additionalProperties": False,
        },
    }
    assert result == expected


def test_schema_changes():
    tested = BuilderDirectFromTuning
    result = tested.schema_changes()
    expected = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "array",
        "items": {
            "type": "object",
            "required": ["originalEntity", "anonymizedWith"],
            "properties": {
                "originalEntity": {"type": "string", "description": "value of the original entity before replacement"},
                "anonymizedWith": {
                    "type": "string",
                    "description": "value of the replacement ; "
                    "two different entities cannot use the same anonymization",
                },
            },
            "additionalProperties": False,
        },
    }
    assert result == expected


def test_schema_code_items():
    tested = BuilderDirectFromTuning
    result = tested.schema_code_items()
    expected = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "array",
        "items": {
            "type": "object",
            "required": ["uuid", "label", "code"],
            "properties": {
                "uuid": {"type": "string"},
                "label": {"type": "string"},
                "code": {"type": "string"},
            },
            "additionalProperties": False,
        },
    }
    assert result == expected


def test_schema_errors():
    tested = BuilderDirectFromTuning
    result = tested.schema_errors()
    expected = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "array",
        "items": {
            "type": "object",
            "required": ["explanation", "error"],
            "properties": {
                "explanation": {
                    "type": "string",
                    "description": "full explanation of the deidentification error, "
                    "including the related text source and the broken rules",
                },
                "error": {
                    "type": "boolean",
                    "description": "set to True if this is an error, False otherwise",
                },
            },
            "additionalProperties": False,
        },
    }
    assert result == expected


def test_schema_summary():
    tested = BuilderDirectFromTuning
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
                "summary": {"type": "string", "description": "a summary of the exchange"},
            },
            "required": ["title", "summary"],
            "additionalProperties": False,
        },
    }
    assert result == expected


def test_compact_transcripts():
    files = [
        # original files
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        # compacted files
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    buffers = [
        MockFile(),
        MockFile(),
        MockFile(),
        MockFile(),
        MockFile(),
        MockFile(),
        MockFile(),
        MockFile(mode="w"),
        MockFile(mode="w"),
        MockFile(mode="w"),
    ]

    def reset_mocks():
        for idx, item in enumerate(files):
            item.reset_mock()
            item.open.return_value = buffers[idx]
            if idx == 0:
                item.parent.__truediv__.side_effect = files[7:]

            if idx < 7:
                buffers[idx].content = json.dumps(
                    [
                        {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5"},
                        {"speaker": "speaker2", "text": "word6 word7 word8"},
                        {"speaker": "speaker3", "text": "word9 word10"},
                    ],
                )
            else:
                buffers[idx].content = ""

    reset_mocks()

    tested = BuilderDirectFromTuning
    # 30 words per compact file
    with patch.object(BuilderDirectFromTuning, "MAX_WORDS_PER_COMPACTED_TRANSCRIPT", 30):
        result = tested.compact_transcripts(files[:7])
        expected = files[7:10]
        assert result == expected

        for index, item in enumerate(files):
            if index == 0:
                calls = [
                    call.parent.__truediv__("transcript_compacted_000.json"),
                    call.open("r"),
                    call.parent.__truediv__("transcript_compacted_001.json"),
                    call.parent.__truediv__("transcript_compacted_002.json"),
                ]
            elif index < 7:
                calls = [call.open("r")]
            elif index in [7]:
                calls = [
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                ]
            elif index in [8]:
                calls = [
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                ]
            elif index in [9]:
                calls = [call.open("w"), call.open("w"), call.open("w"), call.open("w"), call.open("w")]
            else:
                calls = []
            assert item.mock_calls == calls, f"---> {index}"

            if index < 7:
                exp_content = json.dumps(
                    [
                        {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5"},
                        {"speaker": "speaker2", "text": "word6 word7 word8"},
                        {"speaker": "speaker3", "text": "word9 word10"},
                    ],
                )
            elif index in [7]:
                exp_content = json.dumps(
                    [
                        {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 1},
                        {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 1},
                        {"speaker": "speaker3", "text": "word9 word10", "chunk": 1},
                        {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 2},
                        {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 2},
                        {"speaker": "speaker3", "text": "word9 word10", "chunk": 2},
                        {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 3},
                        {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 3},
                    ],
                    indent=2,
                )
            elif index in [8]:
                exp_content = json.dumps(
                    [
                        {"speaker": "speaker3", "text": "word9 word10", "chunk": 3},
                        {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 4},
                        {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 4},
                        {"speaker": "speaker3", "text": "word9 word10", "chunk": 4},
                        {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 5},
                        {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 5},
                        {"speaker": "speaker3", "text": "word9 word10", "chunk": 5},
                        {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 6},
                    ],
                    indent=2,
                )
            elif index in [9]:
                exp_content = json.dumps(
                    [
                        {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 6},
                        {"speaker": "speaker3", "text": "word9 word10", "chunk": 6},
                        {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 7},
                        {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 7},
                        {"speaker": "speaker3", "text": "word9 word10", "chunk": 7},
                    ],
                    indent=2,
                )
            else:
                exp_content = ""
            assert buffers[index].content == exp_content
        reset_mocks()

    # 50 words per compact file
    with patch.object(BuilderDirectFromTuning, "MAX_WORDS_PER_COMPACTED_TRANSCRIPT", 50):
        result = tested.compact_transcripts(files[:7])
        expected = files[7:9]
        assert result == expected

        for index, item in enumerate(files):
            if index == 0:
                calls = [
                    call.parent.__truediv__("transcript_compacted_000.json"),
                    call.open("r"),
                    call.parent.__truediv__("transcript_compacted_001.json"),
                ]
            elif index < 7:
                calls = [call.open("r")]
            elif index in [7]:
                calls = [
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                ]
            elif index in [8]:
                calls = [
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                    call.open("w"),
                ]
            else:
                calls = []
            assert item.mock_calls == calls, f"---> {index}"

            if index < 7:
                exp_content = json.dumps(
                    [
                        {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5"},
                        {"speaker": "speaker2", "text": "word6 word7 word8"},
                        {"speaker": "speaker3", "text": "word9 word10"},
                    ],
                )
            elif index in [7]:
                exp_content = json.dumps(
                    [
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
                    ],
                    indent=2,
                )
            elif index in [8]:
                exp_content = json.dumps(
                    [
                        {"speaker": "speaker3", "text": "word9 word10", "chunk": 5},
                        {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 6},
                        {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 6},
                        {"speaker": "speaker3", "text": "word9 word10", "chunk": 6},
                        {"speaker": "speaker1", "text": "word1 word2 word3 word4 word5", "chunk": 7},
                        {"speaker": "speaker2", "text": "word6 word7 word8", "chunk": 7},
                        {"speaker": "speaker3", "text": "word9 word10", "chunk": 7},
                    ],
                    indent=2,
                )
            else:
                exp_content = ""
            assert buffers[index].content == exp_content
        reset_mocks()
