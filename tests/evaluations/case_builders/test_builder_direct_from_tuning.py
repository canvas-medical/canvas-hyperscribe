import json
from argparse import ArgumentParser, Namespace
from datetime import datetime
from datetime import timezone
from pathlib import Path, PosixPath
from unittest.mock import patch, call, MagicMock

import pytest
from requests import Response

from evaluations.case_builders.builder_direct_from_tuning import BuilderDirectFromTuning
from evaluations.structures.case_exchange import CaseExchange
from evaluations.structures.case_exchange_summary import CaseExchangeSummary
from evaluations.structures.enums.case_status import CaseStatus
from evaluations.structures.records.case import Case as RecordCase
from evaluations.structures.records.generated_note import GeneratedNote as RecordGeneratedNote
from evaluations.structures.records.real_world_case import RealWorldCase as RecordRealWorldCase
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.aws_s3_object import AwsS3Object
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import MockFile


def helper_instance() -> BuilderDirectFromTuning:
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
    return BuilderDirectFromTuning(settings, s3_credentials, identification, Path("/some/path"), 45, True)


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
        call(description='Build the case files directly from the tuning files stored in AWS S3'),
        call().add_argument('--patient', type=str, required=True, help='The patient UUID to consider'),
        call().add_argument('--note', type=str, required=True, help='The note UUID to consider'),
        call().add_argument('--path_temp_files', type=str, help='Folder to store temporary files, if provided, most existing files will be reused'),
        call().add_argument("--cycle_duration", type=int, required=True, help="Duration of each cycle, i.e. the duration of the audio chunks"),
        call().add_argument("--force_refresh", action="store_true", help="Force refresh the temporary files"),
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
    # -- provided path exists
    parameters.side_effect = [Namespace(
        patient="thePatientUuid",
        note="theNoteUuid",
        cycle_duration=37,
        force_refresh=False,
        path_temp_files=Path("/some/path"),
    )]
    path.side_effect = [mock_path_provided, mock_path_temp_dir]
    mock_path_provided.exists.side_effect = [True]
    helper.aws_s3_credentials.side_effect = ["awsS3Credentials"]
    helper.settings.side_effect = ["settings"]
    helper.get_canvas_instance.side_effect = ["canvasInstance"]

    tested.run()

    calls = [call(
        'settings',
        'awsS3Credentials',
        IdentificationParameters(
            patient_uuid='thePatientUuid',
            note_uuid='theNoteUuid',
            provider_uuid='_ProviderUuid',
            canvas_instance='canvasInstance',
        ),
        mock_path_provided,
        37,
        False,
    )]
    assert init.mock_calls == calls
    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call()]
    assert run.mock_calls == calls
    calls = [
        call.aws_s3_credentials(),
        call.settings(),
        call.get_canvas_instance(),
    ]
    assert helper.mock_calls == calls
    calls = [
        call(),
        call().__enter__(),
        call().__exit__(None, None, None),
    ]
    assert temp_dir.mock_calls == calls
    calls = [call(PosixPath('/some/path'))]
    assert path.mock_calls == calls
    calls = [call.exists()]
    assert mock_path_provided.mock_calls == calls
    assert mock_path_temp_dir.mock_calls == []
    reset_mocks()
    # -- provided path does not exist
    parameters.side_effect = [Namespace(
        patient="thePatientUuid",
        note="theNoteUuid",
        cycle_duration=37,
        force_refresh=False,
        path_temp_files=Path("/some/path"),
    )]
    path.side_effect = [mock_path_provided, mock_path_temp_dir]
    mock_path_provided.exists.side_effect = [False]
    helper.aws_s3_credentials.side_effect = ["awsS3Credentials"]
    helper.settings.side_effect = ["settings"]
    helper.get_canvas_instance.side_effect = ["canvasInstance"]

    tested.run()

    calls = [call(
        'settings',
        'awsS3Credentials',
        IdentificationParameters(
            patient_uuid='thePatientUuid',
            note_uuid='theNoteUuid',
            provider_uuid='_ProviderUuid',
            canvas_instance='canvasInstance',
        ),
        mock_path_temp_dir,
        37,
        False,
    )]
    assert init.mock_calls == calls
    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call()]
    assert run.mock_calls == calls
    calls = [
        call.aws_s3_credentials(),
        call.settings(),
        call.get_canvas_instance(),
    ]
    assert helper.mock_calls == calls
    calls = [
        call(),
        call().__enter__(),
        call().__exit__(None, None, None),
    ]
    assert temp_dir.mock_calls == calls
    calls = [
        call(PosixPath('/some/path')),
        call(temp_dir.return_value.__enter__.return_value),
    ]
    assert path.mock_calls == calls
    calls = [call.exists()]
    assert mock_path_provided.mock_calls == calls
    assert mock_path_temp_dir.mock_calls == []
    reset_mocks()
    # path not provided
    parameters.side_effect = [Namespace(
        patient="thePatientUuid",
        note="theNoteUuid",
        cycle_duration=37,
        force_refresh=False,
        path_temp_files="",
    )]
    path.side_effect = [mock_path_temp_dir]
    mock_path_provided.exists.side_effect = []
    helper.aws_s3_credentials.side_effect = ["awsS3Credentials"]
    helper.settings.side_effect = ["settings"]
    helper.get_canvas_instance.side_effect = ["canvasInstance"]

    tested.run()

    calls = [call(
        'settings',
        'awsS3Credentials',
        IdentificationParameters(
            patient_uuid='thePatientUuid',
            note_uuid='theNoteUuid',
            provider_uuid='_ProviderUuid',
            canvas_instance='canvasInstance',
        ),
        mock_path_temp_dir,
        37,
        False,
    )]
    assert init.mock_calls == calls
    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call()]
    assert run.mock_calls == calls
    calls = [
        call.aws_s3_credentials(),
        call.settings(),
        call.get_canvas_instance(),
    ]
    assert helper.mock_calls == calls
    calls = [
        call(),
        call().__enter__(),
        call().__exit__(None, None, None),
    ]
    assert temp_dir.mock_calls == calls
    calls = [
        call(temp_dir.return_value.__enter__.return_value),
    ]
    assert path.mock_calls == calls
    assert mock_path_provided.mock_calls == []
    assert mock_path_temp_dir.mock_calls == []
    reset_mocks()


def test___init__():
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
    path = Path("/some/path")
    tested = BuilderDirectFromTuning(
        settings,
        s3_credentials,
        identification,
        path,
        45,
        True,
    )
    assert tested.s3_credentials == s3_credentials
    assert tested.identification == identification
    assert tested.settings == settings
    assert tested.output_dir == path
    assert tested.cycle_duration == 45
    assert tested.force_refresh is True


@patch("evaluations.case_builders.builder_direct_from_tuning.HelperEvaluation")
@patch("evaluations.case_builders.builder_direct_from_tuning.ImplementedCommands")
@patch("evaluations.case_builders.builder_direct_from_tuning.AuditorPostgres")
@patch("evaluations.case_builders.builder_direct_from_tuning.Commander")
@patch("evaluations.case_builders.builder_direct_from_tuning.CachedSdk")
@patch("evaluations.case_builders.builder_direct_from_tuning.AudioInterpreter")
@patch("evaluations.case_builders.builder_direct_from_tuning.GeneratedNoteStore")
@patch("evaluations.case_builders.builder_direct_from_tuning.RealWorldCaseStore")
@patch("evaluations.case_builders.builder_direct_from_tuning.CaseStore")
def test_generate_case(
        case_store,
        real_world_case_store,
        generated_note_store,
        audio_interpreter,
        cached_sdk,
        commander,
        auditor_postgres,
        implemented_commands,
        helper,
):
    mock_chatter = MagicMock()
    limited_cache = MagicMock()
    mock_settings = MagicMock()

    def reset_mocks():
        case_store.reset_mock()
        real_world_case_store.reset_mock()
        generated_note_store.reset_mock()
        audio_interpreter.reset_mock()
        cached_sdk.reset_mock()
        commander.reset_mock()
        auditor_postgres.reset_mock()
        implemented_commands.reset_mock()
        helper.reset_mock()
        mock_chatter.reset_mock()
        limited_cache.reset_mock()
        mock_settings.reset_mock()

    tested = helper_instance()
    lines = [
        Line(speaker="theSpeaker1", text="theText1"),
        Line(speaker="theSpeaker2", text="theText2"),
        Line(speaker="theSpeaker3", text="theText3"),
        Line(speaker="theSpeaker4", text="theText4"),
        Line(speaker="theSpeaker5", text="theText5"),
        Line(speaker="theSpeaker6", text="theText6"),
    ]
    case_store.return_value.upsert.side_effect = [
        RecordCase(
            name="theName",
            transcript=lines,
            limited_chart={"limited": "chart"},
            profile="theProfile",
            validation_status=CaseStatus.REVIEW,
            batch_identifier="theBatchIdentifier",
            tags={"tag1": "tag1", "tag2": "tag2"},
            id=147,
        )
    ]
    generated_note_store.return_value.insert.side_effect = [RecordGeneratedNote(case_id=147, id=333)]
    audio_interpreter.side_effect = [mock_chatter]
    commander.transcript2commands.side_effect = [
        (["previous1"], ["effects1"]),
        (["previous2"], ["effects2"]),
        (["previous3"], ["effects3"]),
        (["previous4"], ["effects4"]),
    ]
    auditor_postgres.return_value.summarized_generated_commands_as_instructions.side_effect = ["summarizedInstructions"]
    implemented_commands.schema_key2instruction.side_effect = [{'implemented': 'json'}]
    mock_chatter.identification = tested.identification
    limited_cache.to_json.side_effect = [{"obfuscated": "json"}]
    limited_cache.staged_commands_as_instructions.side_effect = [["previous0"]]
    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
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

    calls = [
        call('thePostgresCredentials'),
        call().upsert(RecordCase(
            name='theTitle',
            transcript=lines,
            limited_chart={'obfuscated': 'json'},
            profile='theSummary',
            validation_status=CaseStatus.GENERATION,
            batch_identifier='',
            tags={},
            id=0,
        ))
    ]
    assert case_store.mock_calls == calls
    calls = [
        call('thePostgresCredentials'),
        call().upsert(RecordRealWorldCase(
            case_id=147,
            customer_identifier='canvasInstance',
            patient_note_hash='patient_patientUuid/note_noteUuid',
            topical_exchange_identifier='theTitle',
            start_time=0.0,
            end_time=0.0,
            duration=0.0,
            audio_llm_vendor='theVendorAudio',
            audio_llm_name='theModelAudio',
            id=0,
        )),
    ]
    assert real_world_case_store.mock_calls == calls
    calls = [
        call('thePostgresCredentials'),
        call().insert(RecordGeneratedNote(
            case_id=147,
            cycle_duration=45,
            cycle_count=0,
            cycle_transcript_overlap=100,
            text_llm_vendor='theVendorText',
            text_llm_name='theModelText',
            note_json=[],
            hyperscribe_version='',
            staged_questionnaires={},
            transcript2instructions={},
            instruction2parameters={},
            parameters2command={},
            failed=True,
            errors={},
            id=0,
        )),
    ]
    assert generated_note_store.mock_calls == calls
    calls = [call(tested.settings, tested.s3_credentials, limited_cache, tested.identification)]
    assert audio_interpreter.mock_calls == calls
    calls = [
        call.get_discussion("noteUuid"),
        call.get_discussion().set_cycle(1),
        call.get_discussion().set_cycle(2),
        call.get_discussion().set_cycle(3),
        call.get_discussion().set_cycle(4),
    ]
    assert cached_sdk.mock_calls == calls
    calls = [
        call.transcript2commands(
            auditor_postgres.return_value,
            [Line(speaker='theSpeaker1', text='theText1')],
            mock_chatter,
            ["previous0"],
        ),
        call.transcript2commands(
            auditor_postgres.return_value,
            [Line(speaker='theSpeaker2', text='theText2'), Line(speaker='theSpeaker3', text='theText3')],
            mock_chatter,
            ["previous1"],
        ),
        call.transcript2commands(
            auditor_postgres.return_value,
            [Line(speaker='theSpeaker4', text='theText4'), Line(speaker='theSpeaker5', text='theText5')],
            mock_chatter,
            ["previous2"],
        ),
        call.transcript2commands(
            auditor_postgres.return_value,
            [Line(speaker='theSpeaker6', text='theText6')],
            mock_chatter,
            ["previous3"],
        ),
    ]
    assert commander.mock_calls == calls
    calls = [
        call('theTitle', 0, 333),
        call().set_cycle(1),
        call().set_cycle(2),
        call().set_cycle(3),
        call().set_cycle(4),
        call().finalize([]),
        call().summarized_generated_commands_as_instructions(),
    ]
    assert auditor_postgres.mock_calls == calls
    calls = [call.schema_key2instruction()]
    assert implemented_commands.mock_calls == calls
    calls = [call.postgres_credentials()]
    assert helper.mock_calls == calls
    assert mock_chatter.mock_calls == []
    calls = [
        call.to_json(True),
        call.staged_commands_as_instructions({'implemented': 'json'}),
    ]
    assert limited_cache.mock_calls == calls
    calls = [
        call.llm_audio_model(),
        call.llm_text_model(),
    ]
    assert mock_settings.mock_calls == calls
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
            audio_buffers[idx].content = f"audio content {idx}".encode('utf-8')
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
            JsonExtract(
                error='error',
                has_error=False,
                content=[{"speaker": "theSpeaker1", "text": "theText1"}],
            ),
            JsonExtract(
                error='error',
                has_error=False,
                content=[{"speaker": "theSpeaker2", "text": "theText2"}],
            ),
            JsonExtract(
                error='error',
                has_error=False,
                content=[{"speaker": "theSpeaker3", "text": "theText3"}],
            ),
        ]
        result = tested.create_transcripts(mock_audio_files, mock_interpreter)
        expected = mock_json_files
        assert result == expected

        calls = [
            call.combine_and_speaker_detection([b'audio content 0'], []),
            call.combine_and_speaker_detection([b'audio content 1'], [Line(speaker='theSpeaker1', text='theText1')]),
            call.combine_and_speaker_detection([b'audio content 2'], [Line(speaker='theSpeaker2', text='theText2')]),
        ]
        assert mock_interpreter.mock_calls == calls
        calls = [call.open('w')]
        for index, mock_file in enumerate(mock_json_files):
            assert mock_file.mock_calls == calls
            exp_content = [{"speaker": f"theSpeaker{index + 1}", "text": f"theText{index + 1}"}]
            assert json.loads(json_buffers[index].content) == exp_content

        for index, mock_file in enumerate(mock_audio_files):
            calls = [
                call.parent.__truediv__(f"transcript_{index:03d}.json"),
                call.open('rb'),
            ]
            assert mock_file.mock_calls == calls
            exp_content = f"audio content {index}".encode('utf-8')
            assert audio_buffers[index].content == exp_content
        reset_mocks()

    # not forced refresh and some json does exist
    tested.force_refresh = False
    mock_json_files[0].exists.side_effect = [False]
    mock_json_files[1].exists.side_effect = [True]
    mock_json_files[2].exists.side_effect = [True]

    mock_interpreter.combine_and_speaker_detection.side_effect = [
        JsonExtract(
            error='error',
            has_error=False,
            content=[{"speaker": "theSpeaker1", "text": "theText1"}],
        ),
        JsonExtract(
            error='error',
            has_error=False,
            content=[{"speaker": "theSpeaker2", "text": "theText2"}],
        ),
        JsonExtract(
            error='error',
            has_error=False,
            content=[{"speaker": "theSpeaker3", "text": "theText3"}],
        ),
    ]
    result = tested.create_transcripts(mock_audio_files, mock_interpreter)
    expected = mock_json_files
    assert result == expected

    calls = [
        call.combine_and_speaker_detection([b'audio content 0'], []),
    ]
    assert mock_interpreter.mock_calls == calls
    calls = [
        call.exists(),
        call.open('w'),
    ]
    assert mock_json_files[0].mock_calls == calls
    exp_content = [{"speaker": "theSpeaker1", "text": "theText1"}]
    assert json.loads(json_buffers[0].content) == exp_content

    calls = [call.exists()]
    assert mock_json_files[1].mock_calls == calls
    assert mock_json_files[2].mock_calls == calls
    assert json_buffers[1].content == ""
    assert json_buffers[2].content == ""

    calls = [
        call.parent.__truediv__("transcript_000.json"),
        call.open('rb'),
    ]
    assert mock_audio_files[0].mock_calls == calls
    calls = [call.parent.__truediv__("transcript_001.json")]
    assert mock_audio_files[1].mock_calls == calls
    calls = [call.parent.__truediv__("transcript_002.json")]
    assert mock_audio_files[2].mock_calls == calls

    for index, mock_file in enumerate(mock_audio_files):
        exp_content = f"audio content {index}".encode('utf-8')
        assert audio_buffers[index].content == exp_content

    reset_mocks()


@patch("evaluations.case_builders.builder_direct_from_tuning.ffmpeg")
@patch("evaluations.case_builders.builder_direct_from_tuning.AwsS3")
def test_collated_webm_to_mp3(client_s3, ffmpeg):
    output_dir = MagicMock()
    mock_files = [
        # the first file is the full webm built
        MagicMock(),
        # the second file is the full mp3 built
        MagicMock(),
        # these files are the chunk webm coming from the S3
        MagicMock(), MagicMock(), MagicMock(), MagicMock(),
        # these files are the locally saved webm
        MagicMock(), MagicMock(),
    ]
    buffers = [
        MockFile(),
        MockFile(),
        MockFile(), MockFile(), MockFile(), MockFile(),
        MockFile(), MockFile(),
    ]

    def reset_mocks():
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
                buffers[idx].content = f"locally saved audio content {idx}".encode('utf-8')

    reset_mocks()

    date_0 = datetime(2025, 6, 27, 10, 36, 21, 123456, tzinfo=timezone.utc)
    responses = [Response(), Response(), Response(), Response(), ]
    responses[0].status_code = 200
    responses[1].status_code = 200
    responses[2].status_code = 500
    responses[3].status_code = 200
    responses[0]._content = b'audio content 0'
    responses[1]._content = b'audio content 1'
    responses[2]._content = b'audio content 2'
    responses[3]._content = json.dumps([{"limited": "cache"}])

    tested = helper_instance()
    tested.output_dir = output_dir

    # forced refresh or files does not exist
    for test in [True, False]:
        tested.force_refresh = True
        mock_files[0].exists.side_effect = [not test]
        mock_files[0].parent.glob.side_effect = [
            [mock_files[6], mock_files[7]],
        ]
        mock_files[1].exists.side_effect = [not test]

        output_dir.__truediv__.side_effect = mock_files
        client_s3.return_value.list_s3_objects.side_effect = [[
            AwsS3Object(key="/patient_uuid/note_uuid/webm_001.webm", size=1, last_modified=date_0),
            AwsS3Object(key="/patient_uuid/note_uuid/webm_002.webm", size=1, last_modified=date_0),
            AwsS3Object(key="/patient_uuid/note_uuid/webm_003.webm", size=1, last_modified=date_0),  # <-- response 500
            AwsS3Object(key="/patient_uuid/note_uuid/limited_chart.json", size=1, last_modified=date_0),
        ]]
        client_s3.return_value.access_s3_object.side_effect = responses

        result = tested.collated_webm_to_mp3()
        expected = mock_files[1]
        assert result is expected

        calls = [
            call(AwsS3Credentials(aws_key='theKey', aws_secret='theSecret', region='theRegion', bucket='theBucket')),
            call().list_s3_objects('hyperscribe-canvasInstance/patient_patientUuid/note_noteUuid'),
            call().access_s3_object('/patient_uuid/note_uuid/webm_001.webm'),
            call().access_s3_object('/patient_uuid/note_uuid/webm_002.webm'),
            call().access_s3_object('/patient_uuid/note_uuid/webm_003.webm'),
            call().access_s3_object('/patient_uuid/note_uuid/limited_chart.json'),
        ]
        assert client_s3.mock_calls == calls
        calls = [
            call.input('posix000'),
            call.input().output('posix001', acodec='libmp3lame', ar=44100, ab='192k', vn=None),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(overwrite_output=True, quiet=True),
        ]
        assert ffmpeg.mock_calls == calls
        calls = [
            call.__truediv__('hyperscribe-canvasInstance/patient_patientUuid/note_noteUuid/note_noteUuid.webm'),
            call.__truediv__('hyperscribe-canvasInstance/patient_patientUuid/note_noteUuid/note_noteUuid.mp3'),
            call.__truediv__('/patient_uuid/note_uuid/webm_001.webm'),
            call.__truediv__('/patient_uuid/note_uuid/webm_002.webm'),
            call.__truediv__('/patient_uuid/note_uuid/webm_003.webm'),
            call.__truediv__('/patient_uuid/note_uuid/limited_chart.json'),
        ]
        assert output_dir.mock_calls == calls
        calls = [
            call.unlink(missing_ok=True),
            call.open('wb'),
            call.parent.glob('*.webm'),
            call.as_posix(),
        ]
        assert mock_files[0].mock_calls == calls
        assert buffers[0].content == (b'locally saved audio content 6'
                                      b'locally saved audio content 7')
        calls = [call.as_posix()]
        assert mock_files[1].mock_calls == calls
        assert buffers[1].content == b''

        calls = [
            call.parent.mkdir(parents=True, exist_ok=True),
            call.open('wb'),
        ]
        assert mock_files[2].mock_calls == calls
        assert mock_files[3].mock_calls == calls
        assert mock_files[4].mock_calls == []
        assert mock_files[5].mock_calls == calls
        assert buffers[2].content == b'audio content 0'
        assert buffers[3].content == b'audio content 1'
        assert buffers[4].content == b''
        assert buffers[5].content == '[{"limited": "cache"}]'

        calls = [call.open('rb')]
        assert mock_files[6].mock_calls == calls
        assert mock_files[7].mock_calls == calls
        assert buffers[6].content == b'locally saved audio content 6'
        assert buffers[7].content == b'locally saved audio content 7'

        reset_mocks()

    # not forced refresh and files exist
    tested.force_refresh = False
    mock_files[0].exists.side_effect = [True]
    mock_files[0].parent.glob.side_effect = []
    mock_files[1].exists.side_effect = [True]

    output_dir.__truediv__.side_effect = mock_files
    client_s3.return_value.list_s3_objects.side_effect = []
    client_s3.return_value.access_s3_object.side_effect = []

    result = tested.collated_webm_to_mp3()
    expected = mock_files[1]
    assert result is expected

    calls = [
        call(AwsS3Credentials(aws_key='theKey', aws_secret='theSecret', region='theRegion', bucket='theBucket')),
    ]
    assert client_s3.mock_calls == calls
    assert ffmpeg.mock_calls == []
    calls = [
        call.__truediv__('hyperscribe-canvasInstance/patient_patientUuid/note_noteUuid/note_noteUuid.webm'),
        call.__truediv__('hyperscribe-canvasInstance/patient_patientUuid/note_noteUuid/note_noteUuid.mp3'),
    ]
    assert output_dir.mock_calls == calls
    calls = [call.exists()]
    assert mock_files[0].mock_calls == calls
    assert buffers[0].content == b''

    calls = [call.exists()]
    assert mock_files[1].mock_calls == calls
    assert buffers[1].content == b''

    assert mock_files[2].mock_calls == []
    assert mock_files[3].mock_calls == []
    assert mock_files[4].mock_calls == []
    assert mock_files[5].mock_calls == []
    assert buffers[2].content == b''
    assert buffers[3].content == b''
    assert buffers[4].content == b''
    assert buffers[5].content == ''

    assert mock_files[6].mock_calls == []
    assert mock_files[7].mock_calls == []
    assert buffers[6].content == b'locally saved audio content 6'
    assert buffers[7].content == b'locally saved audio content 7'

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
            call.probe('audioFileAsPosix'),
            call.input('audioFileAsPosix', ss=0.0, t=200.0),
            call.input().output('chunk00AsPosix', acodec='copy'),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
            call.input('audioFileAsPosix', ss=200.0, t=200.0),
            call.input().output('chunk01AsPosix', acodec='copy'),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
            call.input('audioFileAsPosix', ss=400.0, t=200.0),
            call.input().output('chunk02AsPosix', acodec='copy'),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
            call.input('audioFileAsPosix', ss=600.0, t=21.0),
            call.input().output('chunk03AsPosix', acodec='copy'),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
        ]
        assert ffmpeg.mock_calls == calls
        calls = [
            call.as_posix(),
            call.parent.__truediv__('theAudioFile_200_001.mp3'),
            call.parent.__truediv__('theAudioFile_200_002.mp3'),
            call.parent.__truediv__('theAudioFile_200_003.mp3'),
            call.parent.__truediv__('theAudioFile_200_004.mp3'),
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
            call.probe('audioFileAsPosix'),
            call.input('audioFileAsPosix', ss=0.0, t=300.0),
            call.input().output('chunk00AsPosix', acodec='copy'),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
            call.input('audioFileAsPosix', ss=300.0, t=300.0),
            call.input().output('chunk01AsPosix', acodec='copy'),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
            call.input('audioFileAsPosix', ss=600.0, t=21.0),
            call.input().output('chunk02AsPosix', acodec='copy'),
            call.input().output().overwrite_output(),
            call.input().output().overwrite_output().run(quiet=True),
        ]
        assert ffmpeg.mock_calls == calls
        calls = [
            call.as_posix(),
            call.parent.__truediv__('theAudioFile_300_001.mp3'),
            call.parent.__truediv__('theAudioFile_300_002.mp3'),
            call.parent.__truediv__('theAudioFile_300_003.mp3'),
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

    calls = [call.probe('audioFileAsPosix')]
    assert ffmpeg.mock_calls == calls
    calls = [
        call.as_posix(),
        call.parent.__truediv__('theAudioFile_150_001.mp3'),
        call.parent.__truediv__('theAudioFile_150_002.mp3'),
        call.parent.__truediv__('theAudioFile_150_003.mp3'),
        call.parent.__truediv__('theAudioFile_150_004.mp3'),
        call.parent.__truediv__('theAudioFile_150_005.mp3'),
    ]
    assert audio_file.mock_calls == calls
    for index, chunk_file in enumerate(chunk_files):
        if index < 5:
            calls = [call.exists()]
        else:
            calls = []
        assert chunk_file.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_direct_from_tuning.Helper")
@patch("evaluations.case_builders.builder_direct_from_tuning.MemoryLog")
@patch.object(BuilderDirectFromTuning, "schema_changes")
@patch.object(BuilderDirectFromTuning, "schema_anonymization")
def test_anonymize_transcripts(schema_anonymization, schema_changes, memory_log, helper):
    files = [
        # original transcripts
        MagicMock(), MagicMock(), MagicMock(),
        # anonymized transcripts
        MagicMock(), MagicMock(), MagicMock(),
    ]
    buffers = [
        MockFile(), MockFile(), MockFile(),
        MockFile(mode="w"), MockFile(mode="w"), MockFile(mode="w"),
    ]

    def reset_mocks():
        schema_anonymization.reset_mock()
        schema_changes.reset_mock()
        memory_log.reset_mock()
        helper.reset_mock()
        for idx, item in enumerate(files):
            item.reset_mock()
            item.open.return_value = buffers[idx]
            buffers[idx].content = ""
            if idx < 3:
                item.parent.__truediv__.side_effect = [files[idx + 3]]
                buffers[idx].content = json.dumps([{
                    "speaker": f"theSpeaker{idx}",
                    "text": f"theText{idx}",
                    "chunk": idx,
                    "topic": idx,
                }])

    reset_mocks()

    system_prompt = [
        "You are a medical transcript anonymization specialist with expertise in healthcare privacy compliance."
        "",
        "Your task is to remove all personally identifiable information (PII) from medical transcripts while preserving "
        "complete clinical context and medical accuracy through realistic replacements.",
        "",
        "**Anonymization Approach**",
        "Use realistic, plausible substitutions rather than placeholders:",
        "- Replace names with culturally appropriate alternatives of similar length/structure",
        "- Substitute locations with comparable geographic areas (similar urban/rural, climate, healthcare infrastructure)",
        "- Change dates while maintaining temporal relationships and seasonal context when medically relevant",
        "- Replace specific institutions with similar types (community hospital → regional medical center)",
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
        '```',
        "",
        "**Global Consistency**: Use identical replacements for the exact same entity throughout the entire transcript.",
        "But, two different entities cannot use the same anonymization replacement.",
        "",
        "",
        "In a second JSON Markdown block, format the report of the changes following the JSON Schema:",
        "```json",
        '{\n "schema": "changes"\n}',
        "```",
        "",
    ]
    user_prompts = [
        [
            "Please anonymize the following medical transcript while preserving all clinical information:",
            "```json",
            '[{"speaker": "theSpeaker0", "text": "theText0", "chunk": 0, "topic": 0}]',
            "```",
            "",
            "Follow rigorously the instructions and provide both JSON Markdown code block using the mentioned JSON Schemas.",
        ],
        [
            "Please anonymize the following medical transcript while preserving all clinical information:",
            "```json",
            '[{"speaker": "theSpeaker1", "text": "theText1", "chunk": 1, "topic": 1}]',
            "```",
            "",
            "Follow rigorously the instructions and provide both JSON Markdown code block using the mentioned JSON Schemas.",
        ],
        [
            "The anonymized entities so far are:",
            "```json",
            '[\n {\n  "originalEntity": "theOriginal1",\n  "anonymizedWith": "theAnonymized1"\n }\n]',
            "```",
            "",
            "Include this list in your response to be sure you are not using the same anonymization value for different entities.",
        ],
        [
            "Please anonymize the following medical transcript while preserving all clinical information:",
            "```json",
            '[{"speaker": "theSpeaker2", "text": "theText2", "chunk": 2, "topic": 2}]',
            "```",
            "",
            "Follow rigorously the instructions and provide both JSON Markdown code block using the mentioned JSON Schemas.",
        ],
        [
            "The anonymized entities so far are:",
            "```json",
            '['
            '\n {\n  "originalEntity": "theOriginal1",\n  "anonymizedWith": "theAnonymized1"\n },'
            '\n {\n  "originalEntity": "theOriginal2",\n  "anonymizedWith": "theAnonymized2"\n },'
            '\n {\n  "originalEntity": "theOriginal3",\n  "anonymizedWith": "theAnonymized3"\n }'
            '\n]',
            "```",
            "",
            "Include this list in your response to be sure you are not using the same anonymization value for different entities.",
        ],
    ]

    tested = helper_instance()

    # forced refresh or json does not exist
    tested.force_refresh = True
    for test in [True, False]:
        for item in files[3:]:
            item.exists.side_effect = [test]

        memory_log.instance.side_effect = ["theMemoryLog"]
        schema_anonymization.side_effect = [{"schema": "anonymization"}]
        schema_changes.side_effect = [{"schema": "changes"}]
        helper.chatter.return_value.chat.side_effect = [
            JsonExtract(error="", has_error=False, content=[
                [
                    {"speaker": "theSpeaker1", "text": "theText1", "chunk": 1, "topic": 1},
                    {"speaker": "theSpeaker1", "text": "theText2", "chunk": 1, "topic": 1},
                    {"speaker": "theSpeaker2", "text": "theText3", "chunk": 1, "topic": 2},
                ],
                [
                    {"originalEntity": "theOriginal1", "anonymizedWith": "theAnonymized1"},
                ]
            ]),
            JsonExtract(error="", has_error=False, content=[
                [
                    {"speaker": "theSpeaker1", "text": "theText1", "chunk": 2, "topic": 2},
                    {"speaker": "theSpeaker1", "text": "theText2", "chunk": 2, "topic": 2},
                    {"speaker": "theSpeaker2", "text": "theText3", "chunk": 2, "topic": 2},
                ],
                [
                    {"originalEntity": "theOriginal1", "anonymizedWith": "theAnonymized1"},
                    {"originalEntity": "theOriginal2", "anonymizedWith": "theAnonymized2"},
                    {"originalEntity": "theOriginal3", "anonymizedWith": "theAnonymized3"},
                ]
            ]),
            JsonExtract(error="", has_error=False, content=[
                [
                    {"speaker": "theSpeaker1", "text": "theText1", "chunk": 3, "topic": 2},
                    {"speaker": "theSpeaker1", "text": "theText2", "chunk": 3, "topic": 3},
                    {"speaker": "theSpeaker2", "text": "theText3", "chunk": 3, "topic": 4},
                ],
                [
                    {"originalEntity": "theOriginal1", "anonymizedWith": "theAnonymized1"},
                    {"originalEntity": "theOriginal2", "anonymizedWith": "theAnonymized2"},
                    {"originalEntity": "theOriginal3", "anonymizedWith": "theAnonymized3"},
                    {"originalEntity": "theOriginal4", "anonymizedWith": "theAnonymized4"},
                ]
            ]),
        ]

        result = tested.anonymize_transcripts(files[:3])
        expected = files[3:]
        assert result == expected

        calls = [call()]
        assert schema_anonymization.mock_calls == calls
        assert schema_changes.mock_calls == calls
        calls = [call.instance(tested.identification, 'anonymize_transcript', tested.s3_credentials)]
        assert memory_log.mock_calls == calls
        calls = [
            call.chatter(tested.settings, 'theMemoryLog'),
            call.chatter().set_system_prompt(system_prompt),
            call.chatter().set_user_prompt(user_prompts[0]),
            call.chatter().chat([{'schema': 'anonymization'}, {'schema': 'changes'}]),
            #
            call.chatter(tested.settings, 'theMemoryLog'),
            call.chatter().set_system_prompt(system_prompt),
            call.chatter().set_user_prompt(user_prompts[1]),
            call.chatter().set_user_prompt(user_prompts[2]),
            call.chatter().chat([{'schema': 'anonymization'}, {'schema': 'changes'}]),
            #
            call.chatter(tested.settings, 'theMemoryLog'),
            call.chatter().set_system_prompt(system_prompt),
            call.chatter().set_user_prompt(user_prompts[3]),
            call.chatter().set_user_prompt(user_prompts[4]),
            call.chatter().chat([{'schema': 'anonymization'}, {'schema': 'changes'}]),
        ]
        assert helper.mock_calls == calls

        for index, file in enumerate(files):
            if index < 3:
                calls = [
                    call.parent.__truediv__(f'transcript_anonymized_{index:03d}.json'),
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
    schema_anonymization.side_effect = [{"schema": "anonymization"}]
    schema_changes.side_effect = [{"schema": "changes"}]
    helper.chatter.return_value.chat.side_effect = []

    result = tested.anonymize_transcripts(files[:3])
    expected = files[3:]
    assert result == expected

    calls = [call()]
    assert schema_anonymization.mock_calls == calls
    assert schema_changes.mock_calls == calls
    calls = [call.instance(tested.identification, 'anonymize_transcript', tested.s3_credentials)]
    assert memory_log.mock_calls == calls
    assert helper.mock_calls == []

    for index, file in enumerate(files):
        if index < 3:
            calls = [
                call.parent.__truediv__(f'transcript_anonymized_{index:03d}.json'),
            ]
        else:
            calls = [
                call.exists(),
            ]
        assert files[index].mock_calls == calls

        if index < 3:
            exp_content = json.dumps([{"speaker": f"theSpeaker{index}", "text": f"theText{index}", "chunk": index, "topic": index}])
        else:
            exp_content = ""
        assert buffers[index].content == exp_content
    reset_mocks()


def test_schema_anonymization():
    tested = BuilderDirectFromTuning
    result = tested.schema_anonymization()
    expected = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "array",
        "items": {
            "type": "object",
            "required": ["speaker", "text"],
            "properties": {
                "speaker": {"type": "string", "minLength": 1},
                "text": {"type": "string"},
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
                "originalEntity": {
                    "type": "string",
                    "description": "value of the original entity before replacement",
                },
                "anonymizedWith": {
                    "type": "string",
                    "description": "value of the replacement ; two different entities cannot use the same anonymization",
                },
            },
            "additionalProperties": False,
        },
    }
    assert result == expected
