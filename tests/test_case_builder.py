import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, call, MagicMock

import pytest
from _pytest.capture import CaptureResult
from canvas_sdk.v1.data import Patient, Note

from case_builder import CaseBuilder
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.handlers.structures.line import Line


def test_validate_files():
    tested = CaseBuilder
    tests = [
        (__file__, Path(__file__), ""),
        ("nope", None, "'nope' is not a valid file"),
    ]
    for file, exp_path, exp_error in tests:
        if exp_path is None:
            with pytest.raises(Exception) as e:
                _ = tested.validate_files(file)
            assert str(e.value) == exp_error
        else:
            result = tested.validate_files(file)
            assert result == exp_path


@patch.object(Patient, "objects")
def test_validate_patient(patient_db):
    def reset_mocks():
        patient_db.reset_mock()

    tested = CaseBuilder

    # patient not found
    patient_db.filter.side_effect = [[]]
    with pytest.raises(Exception) as e:
        _ = tested.validate_patient("patientUuid")
    expected = "'patientUuid' is not a valid patient uuid"
    assert str(e.value) == expected

    calls = [call.filter(id="patientUuid")]
    assert patient_db.mock_calls == calls
    reset_mocks()

    # patient is found
    patient_db.filter.side_effect = [[Patient(id="patientUuid")]]
    result = tested.validate_patient("patientUuid")
    expected = "patientUuid"
    assert result == expected

    calls = [call.filter(id="patientUuid")]
    assert patient_db.mock_calls == calls
    reset_mocks()


@patch("case_builder.ArgumentParser")
def test_parameters(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    tested = CaseBuilder

    argument_parser.return_value.parse_args.side_effect = ["parse_args called"]
    result = tested.parameters()
    expected = "parse_args called"
    assert result == expected

    calls = [
        call(description="Build the files of the evaluation tests against a patient based on the provided files"),
        call().add_argument("--patient", type=CaseBuilder.validate_patient, required=True, help="Patient UUID"),
        call().add_argument("--case", type=str, required=True, help="Evaluation case"),
        call().add_argument("--group", type=str, help="Group of the case", default="common"),
        call().add_argument("--type", type=str, choices=["situational", "general"], help="Type of the case: situational, general", default="general"),
        call().add_mutually_exclusive_group(required=True),
        call().add_mutually_exclusive_group().add_argument("--mp3", nargs="+", type=CaseBuilder.validate_files, help="List of MP3 files"),
        call().add_mutually_exclusive_group().add_argument("--transcript", type=CaseBuilder.validate_files, help="JSON file with transcript"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("case_builder.ArgumentParser")
def test_reset(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    tested = CaseBuilder

    with patch('case_builder.argv', []):
        argument_parser.return_value.parse_args.side_effect = ["parse_args called"]
        result = tested.reset()
        assert result is None
        assert argument_parser.mock_calls == []
        reset_mocks()
    with patch('case_builder.argv', ['--delete']):
        argument_parser.return_value.parse_args.side_effect = ["parse_args called"]
        result = tested.reset()
        expected = "parse_args called"
        assert result == expected
        calls = [
            call(),
            call().add_argument('--delete', action='store_true'),
            call().add_argument('--case', type=str),
            call().parse_args(),
        ]
        assert argument_parser.mock_calls == calls
        reset_mocks()


@patch("case_builder.datetime", wraps=datetime)
@patch("case_builder.StoreCases")
@patch("case_builder.MemoryLog")
@patch("case_builder.LimitedCache")
@patch("case_builder.AwsS3")
@patch("case_builder.AudioInterpreter")
@patch("case_builder.AuditorFile")
@patch("case_builder.Commander")
@patch.object(Note, "objects")
@patch.object(HelperEvaluation, "aws_s3_credentials")
@patch.object(HelperEvaluation, "settings")
@patch.object(CaseBuilder, "parameters")
@patch.object(CaseBuilder, "reset")
def test_run(
        reset,
        parameters,
        settings,
        aws_s3_credentials,
        note_db,
        commander,
        auditor_file,
        audio_interpreter,
        aws_s3,
        limited_cache,
        memory_log,
        store_cases,
        mock_datetime,
        monkeypatch,
        capsys,
):
    mock_arguments = MagicMock()
    mock_files = [MagicMock(), MagicMock()]
    mock_note = MagicMock()

    def reset_mocks():
        mock_arguments.reset_mock()
        reset.reset_mock()
        parameters.reset_mock()
        settings.reset_mock()
        aws_s3_credentials.reset_mock()
        commander.reset_mock()
        note_db.reset_mock()
        auditor_file.reset_mock()
        audio_interpreter.reset_mock()
        aws_s3.reset_mock()
        limited_cache.reset_mock()
        memory_log.reset_mock()
        store_cases.reset_mock()
        mock_datetime.reset_mock()
        mock_arguments.reset_mock()
        for mock_file in mock_files:
            mock_file.reset_mock()
        mock_note.reset_mock()

    monkeypatch.setenv("CANVAS_SDK_DB_HOST", "theSDKDbHost")

    tested = CaseBuilder()

    # deletion
    reset.side_effect = [mock_arguments]
    mock_arguments.delete = True
    mock_arguments.case = "theCase"

    result = tested.run()
    assert result is None

    exp_out = CaptureResult("Evaluation Case 'theCase' deleted (files and record)\n", "")
    assert capsys.readouterr() == exp_out
    calls = [call()]
    assert reset.mock_calls == calls
    calls = [call.__bool__()]
    assert mock_arguments.mock_calls == calls
    assert parameters.mock_calls == []
    calls = [call("theCase")]
    assert auditor_file.mock_calls == calls
    assert audio_interpreter.mock_calls == []
    assert aws_s3.mock_calls == []
    assert settings.mock_calls == []
    assert aws_s3_credentials.mock_calls == []
    assert limited_cache.mock_calls == []
    assert commander.mock_calls == []
    assert note_db.mock_calls == []
    assert memory_log.mock_calls == []
    calls = [call.delete('theCase')]
    assert store_cases.mock_calls == calls
    assert mock_datetime.mock_calls == []
    assert mock_note.mock_calls == []
    for mock_file in mock_files:
        assert mock_file.mock_calls == []
    reset_mocks()

    # creation
    # -- with audio files
    for is_ready in [True, False]:
        reset.side_effect = [None]
        parameters.side_effect = [mock_arguments]
        mock_arguments.patient = "patientUuid"
        mock_arguments.case = "theCase"
        mock_arguments.group = "theGroup"
        mock_arguments.type = "theType"
        mock_arguments.transcript = None
        mock_arguments.mp3 = mock_files
        for idx, mock_file in enumerate(mock_files):
            mock_file.__str__.side_effect = [f"audio file {idx}"]
            mock_file.open.return_value.__enter__.return_value.read.side_effect = [f"audio content {idx}".encode('utf-8')]

        auditor_file.side_effect = ["auditorFileInstance"]
        audio_interpreter.side_effect = ["audioInterpreterInstance"]
        note_db.filter.return_value.order_by.return_value.first.side_effect = [mock_note]
        mock_note.provider.id = "providerUuid"
        mock_note.id = "noteUuid"
        settings.side_effect = ["settingsInstance"]
        aws_s3_credentials.side_effect = ["awsS3CredentialsInstance1", "awsS3CredentialsInstance2"]
        limited_cache.side_effect = ["limitedCacheInstance"]
        aws_s3.return_value.is_ready.side_effect = [is_ready]
        memory_log.end_session.side_effect = ["flushedMemoryLog"]
        mock_datetime.now.side_effect = [datetime(2025, 3, 10, 7, 48, 21, tzinfo=timezone.utc)]

        result = tested.run()
        assert result is None

        exp_out = [
            'Patient UUID: patientUuid',
            'Evaluation Case: theCase',
            'MP3 Files:',
            '- audio file 0',
            '- audio file 1',
        ]
        if is_ready:
            exp_out.append('Logs saved in: 2025-03-10/case-builder-theCase.log')
        exp_out.append('')
        assert capsys.readouterr().out == "\n".join(exp_out)
        calls = [call()]
        assert reset.mock_calls == calls
        assert parameters.mock_calls == calls
        calls = [call("theCase")]
        assert auditor_file.mock_calls == calls
        calls = [call(
            "settingsInstance",
            "awsS3CredentialsInstance1",
            "limitedCacheInstance",
            "patientUuid",
            "noteUuid",
            "providerUuid",
        )]
        assert audio_interpreter.mock_calls == calls
        calls = [
            call("awsS3CredentialsInstance2"),
            call().__bool__(),
            call().is_ready(),
        ]
        if is_ready:
            calls.append(call().upload_text_to_s3(
                '2025-03-10/case-builder-theCase.log',
                "flushedMemoryLog"),
            )
        assert aws_s3.mock_calls == calls
        calls = [call()]
        assert settings.mock_calls == calls
        calls = [call(), call()]
        assert aws_s3_credentials.mock_calls == calls
        calls = [call("patientUuid", {})]
        assert limited_cache.mock_calls == calls
        calls = [call.audio2commands(
            "auditorFileInstance",
            [b'audio content 0', b'audio content 1'],
            "audioInterpreterInstance",
            [],
        )]
        assert commander.mock_calls == calls
        calls = [
            call.filter(patient__id='patientUuid'),
            call.filter().order_by('-dbid'),
            call.filter().order_by().first()
        ]
        assert note_db.mock_calls == calls
        calls = [call.begin_session('noteUuid')]
        if is_ready:
            calls.append(call.end_session('noteUuid'))
        assert memory_log.mock_calls == calls
        calls = [call.upsert(EvaluationCase(
            environment="theSDKDbHost",
            patient_uuid="patientUuid",
            case_type="theType",
            case_group="theGroup",
            case_name="theCase",
            description="theCase",
        ))]
        assert store_cases.mock_calls == calls
        calls = []
        if is_ready:
            calls.append(call.now())
        assert mock_datetime.mock_calls == calls
        assert mock_note.mock_calls == []
        reset_mocks()

    lines = [
        Line(speaker="speakerA", text="text1"),
        Line(speaker="speakerB", text="text2"),
        Line(speaker="speakerA", text="text3"),
    ]

    # -- with JSON file
    for is_ready in [True, False]:
        reset.side_effect = [None]
        parameters.side_effect = [mock_arguments]
        mock_arguments.patient = "patientUuid"
        mock_arguments.case = "theCase"
        mock_arguments.transcript = mock_files[0]
        mock_files[0].__str__.side_effect = ["the json file"]
        mock_files[0].open.return_value.__enter__.return_value.read.side_effect = [
            json.dumps([l.to_json() for l in lines])
        ]
        mock_arguments.mp3 = None

        auditor_file.side_effect = ["auditorFileInstance"]
        audio_interpreter.side_effect = ["audioInterpreterInstance"]
        note_db.filter.return_value.order_by.return_value.first.side_effect = [mock_note]
        mock_note.provider.id = "providerUuid"
        mock_note.id = "noteUuid"
        settings.side_effect = ["settingsInstance"]
        aws_s3_credentials.side_effect = ["awsS3CredentialsInstance1", "awsS3CredentialsInstance2"]
        limited_cache.side_effect = ["limitedCacheInstance"]
        aws_s3.return_value.is_ready.side_effect = [is_ready]
        memory_log.end_session.side_effect = ["flushedMemoryLog"]
        mock_datetime.now.side_effect = [datetime(2025, 3, 10, 7, 48, 21, tzinfo=timezone.utc)]

        result = tested.run()
        assert result is None

        exp_out = [
            'Patient UUID: patientUuid',
            'Evaluation Case: theCase',
            'JSON file: the json file',
        ]
        if is_ready:
            exp_out.append('Logs saved in: 2025-03-10/case-builder-theCase.log')
        exp_out.append('')
        assert capsys.readouterr().out == "\n".join(exp_out)
        calls = [call()]
        assert reset.mock_calls == calls
        assert parameters.mock_calls == calls
        calls = [call("theCase")]
        assert auditor_file.mock_calls == calls
        calls = [call(
            "settingsInstance",
            "awsS3CredentialsInstance1",
            "limitedCacheInstance",
            "patientUuid",
            "noteUuid",
            "providerUuid",
        )]
        assert audio_interpreter.mock_calls == calls
        calls = [
            call("awsS3CredentialsInstance2"),
            call().__bool__(),
            call().is_ready(),
        ]
        if is_ready:
            calls.append(call().upload_text_to_s3(
                '2025-03-10/case-builder-theCase.log',
                "flushedMemoryLog"),
            )
        assert aws_s3.mock_calls == calls
        calls = [call()]
        assert settings.mock_calls == calls
        calls = [call(), call()]
        assert aws_s3_credentials.mock_calls == calls
        calls = [call("patientUuid", {})]
        assert limited_cache.mock_calls == calls
        calls = [call.transcript2commands(
            "auditorFileInstance",
            lines,
            "audioInterpreterInstance",
            [],
        )]
        assert commander.mock_calls == calls
        calls = [
            call.filter(patient__id='patientUuid'),
            call.filter().order_by('-dbid'),
            call.filter().order_by().first()
        ]
        assert note_db.mock_calls == calls
        calls = [call.begin_session('noteUuid')]
        if is_ready:
            calls.append(call.end_session('noteUuid'))
        assert memory_log.mock_calls == calls
        calls = []
        if is_ready:
            calls.append(call.now())
        assert mock_datetime.mock_calls == calls
        assert mock_note.mock_calls == []
        reset_mocks()
