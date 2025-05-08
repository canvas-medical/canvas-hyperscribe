from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, call

import pytest
from canvas_sdk.v1.data import Patient, Command

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from hyperscribe.handlers.commander import Commander
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.structures.identification_parameters import IdentificationParameters


def test_validate_files():
    tested = BuilderBase
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

    tested = BuilderBase

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


def test__parameters():
    tested = BuilderBase
    with pytest.raises(NotImplementedError):
        _ = tested._parameters()


def test__run():
    tested = BuilderBase
    with pytest.raises(NotImplementedError):
        _ = tested._run(
            Namespace(),
            AuditorFile("theCase"),
            IdentificationParameters(
                patient_uuid="patientUuid",
                note_uuid="noteUuid",
                provider_uuid="providerUuid",
                canvas_instance="canvasInstance",
            ))


@patch("evaluations.case_builders.builder_base.datetime", wraps=datetime)
@patch("evaluations.case_builders.builder_base.MemoryLog")
@patch("evaluations.case_builders.builder_base.LlmDecisionsReviewer")
@patch("evaluations.case_builders.builder_base.HelperEvaluation")
@patch("evaluations.case_builders.builder_base.AwsS3")
@patch("evaluations.case_builders.builder_base.AuditorFile")
@patch.object(BuilderBase, "_parameters")
@patch.object(BuilderBase, "_run")
def test_run(
        run,
        parameters,
        auditor_file,
        aws_s3,
        helper,
        llm_decisions_reviewer,
        memory_log,
        mock_datetime,
        capsys,
):
    def reset_mocks():
        run.reset_mock()
        parameters.reset_mock()
        auditor_file.reset_mock()
        aws_s3.reset_mock()
        helper.reset_mock()
        llm_decisions_reviewer.reset_mock()
        memory_log.reset_mock()
        mock_datetime.reset_mock()

    identifications = {
        "target": IdentificationParameters(
            patient_uuid='patientUuid',
            note_uuid='noteUuid',
            provider_uuid='providerUuid',
            canvas_instance="canvasInstance",
        ),
        "generic": IdentificationParameters(
            patient_uuid='_PatientUuid',
            note_uuid='_NoteUuid',
            provider_uuid='_ProviderUuid',
            canvas_instance="canvasInstance",
        ),
    }

    tested = BuilderBase()

    # auditor is not ready
    run.side_effect = []
    parameters.side_effect = [Namespace(case="theCase")]
    auditor_file.return_value.is_ready.side_effect = [False]
    aws_s3.return_value.is_ready.side_effect = []
    helper.side_effect = []
    memory_log.end_session.side_effect = []
    mock_datetime.now.side_effect = []

    result = tested.run()
    assert result is None

    exp_out = [
        "Case 'theCase': some files exist already",
        "",
    ]
    assert capsys.readouterr().out == "\n".join(exp_out)

    assert run.mock_calls == []
    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [
        call("theCase"),
        call().is_ready(),
    ]
    assert auditor_file.mock_calls == calls
    assert aws_s3.mock_calls == []
    assert helper.mock_calls == []
    assert llm_decisions_reviewer.mock_calls == []
    assert memory_log.mock_calls == []
    assert mock_datetime.mock_calls == []
    reset_mocks()

    # auditor is ready
    # -- patient is provided
    for aws_is_ready in [True, False]:
        arguments = Namespace(case="theCase", patient="patientUuid")

        run.side_effect = [None]
        parameters.side_effect = [arguments]
        auditor_file.return_value.is_ready.side_effect = [True]
        aws_s3.return_value.is_ready.side_effect = [aws_is_ready]
        helper.aws_s3_credentials.side_effect = ["awsS3CredentialsInstance1"]
        helper.get_note_uuid.side_effect = ["noteUuid"]
        helper.get_provider_uuid.side_effect = ["providerUuid"]
        helper.get_canvas_instance.side_effect = ["canvasInstance"]
        helper.settings.side_effect = ["settingsInstance"]
        memory_log.end_session.side_effect = ["flushedMemoryLog"]
        mock_datetime.now.side_effect = [datetime(2025, 3, 10, 7, 48, 21, tzinfo=timezone.utc)]

        result = tested.run()
        assert result is None

        exp_out = []
        if aws_is_ready:
            exp_out.append('Logs saved in: canvasInstance/finals/2025-03-10/theCase.log')
        exp_out.append('')
        assert capsys.readouterr().out == "\n".join(exp_out)
        calls = [call(arguments, auditor_file.return_value, identifications["target"])]
        assert run.mock_calls == calls
        calls = [call()]
        assert parameters.mock_calls == calls
        calls = [
            call.get_note_uuid('patientUuid'),
            call.get_provider_uuid('patientUuid'),
            call.get_canvas_instance(),
            call.aws_s3_credentials(),
            call.settings(),
        ]
        assert helper.mock_calls == calls
        calls = [
            call("theCase"),
            call().is_ready(),
        ]
        assert auditor_file.mock_calls == calls
        calls = [
            call("awsS3CredentialsInstance1"),
            call().__bool__(),
            call().is_ready(),
        ]
        if aws_is_ready:
            calls.append(call().upload_text_to_s3(
                'canvasInstance/finals/2025-03-10/theCase.log',
                "flushedMemoryLog"),
            )
        assert aws_s3.mock_calls == calls
        calls = [
            call.review(
                identifications["target"],
                'settingsInstance',
                'awsS3CredentialsInstance1',
                memory_log.return_value,
                {},
            ),
        ]
        assert llm_decisions_reviewer.mock_calls == calls
        calls = [call(identifications["target"], "case_builder")]
        if aws_is_ready:
            calls.append(call.end_session('noteUuid'))
        assert memory_log.mock_calls == calls
        calls = []
        if aws_is_ready:
            calls.append(call.now())
        assert mock_datetime.mock_calls == calls
        reset_mocks()

    # -- patient is NOT provided
    for aws_is_ready in [True, False]:
        arguments = Namespace(case="theCase")

        run.side_effect = [None]
        parameters.side_effect = [arguments]
        auditor_file.return_value.is_ready.side_effect = [True]
        aws_s3.return_value.is_ready.side_effect = [aws_is_ready]
        helper.aws_s3_credentials.side_effect = ["awsS3CredentialsInstance1"]
        helper.get_note_uuid.side_effect = ["noteUuid"]
        helper.get_provider_uuid.side_effect = ["providerUuid"]
        helper.get_canvas_instance.side_effect = ["canvasInstance"]
        helper.settings.side_effect = ["settingsInstance"]
        memory_log.end_session.side_effect = ["flushedMemoryLog"]
        mock_datetime.now.side_effect = [datetime(2025, 3, 10, 7, 48, 21, tzinfo=timezone.utc)]

        result = tested.run()
        assert result is None

        exp_out = []
        if aws_is_ready:
            exp_out.append('Logs saved in: canvasInstance/finals/2025-03-10/theCase.log')
        exp_out.append('')
        assert capsys.readouterr().out == "\n".join(exp_out)

        calls = [call(arguments, auditor_file.return_value, identifications["generic"])]
        assert run.mock_calls == calls
        calls = [call()]
        assert parameters.mock_calls == calls
        calls = [
            call.get_canvas_instance(),
            call.aws_s3_credentials(),
            call.settings(),
        ]
        assert helper.mock_calls == calls
        calls = [
            call("theCase"),
            call().is_ready(),
        ]
        assert auditor_file.mock_calls == calls
        calls = [
            call("awsS3CredentialsInstance1"),
            call().__bool__(),
            call().is_ready(),
        ]
        if aws_is_ready:
            calls.append(call().upload_text_to_s3(
                'canvasInstance/finals/2025-03-10/theCase.log',
                "flushedMemoryLog"),
            )
        assert aws_s3.mock_calls == calls
        calls = [
            call.review(
                identifications["generic"],
                'settingsInstance',
                'awsS3CredentialsInstance1',
                memory_log.return_value,
                {},
            ),
        ]
        assert llm_decisions_reviewer.mock_calls == calls
        calls = [call(identifications["generic"], "case_builder")]
        if aws_is_ready:
            calls.append(call.end_session('_NoteUuid'))
        assert memory_log.mock_calls == calls
        calls = []
        if aws_is_ready:
            calls.append(call.now())
        assert mock_datetime.mock_calls == calls
        reset_mocks()


@patch.object(Commander, 'existing_commands_to_coded_items')
@patch.object(Command, "objects")
def test__limited_cache_from(command_db, existing_commands_to_coded_items):
    def reset_mocks():
        command_db.reset_mock()
        existing_commands_to_coded_items.reset_mock()

    tested = BuilderBase
    command_db.filter.return_value.order_by.side_effect = ["QuerySetCommands"]
    existing_commands_to_coded_items.side_effect = [{}]
    result = tested._limited_cache_from(IdentificationParameters(
        patient_uuid="thePatient",
        note_uuid="theNoteUuid",
        provider_uuid="theProviderUuid",
        canvas_instance="theCanvasInstance",
    ))
    assert isinstance(result, LimitedCache)
    assert result.patient_uuid == "thePatient"
    assert result._staged_commands == {}

    calls = [
        call.filter(patient__id='thePatient', note__id='theNoteUuid', state='staged'),
        call.filter().order_by('dbid'),
    ]
    assert command_db.mock_calls == calls
    calls = [call("QuerySetCommands")]
    assert existing_commands_to_coded_items.mock_calls == calls
    reset_mocks()
