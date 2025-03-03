from pathlib import Path
from unittest.mock import patch, call, MagicMock

import pytest
from _pytest.capture import CaptureResult
from canvas_sdk.v1.data import Patient, Note

from case_builder import CaseBuilder
from hyperscribe.protocols.audio_interpreter import AudioInterpreter
from hyperscribe.protocols.commander import Commander
from hyperscribe.protocols.limited_cache import LimitedCache
from integrations.auditor_file import AuditorFile
from integrations.helper_settings import HelperSettings


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
        call(description='Build all the files of the integration tests against a patient and the provided mp3 files'),
        call().add_argument('--patient', type=CaseBuilder.validate_patient, required=True, help='Patient UUID'),
        call().add_argument('--label', type=str, required=True, help='Integration label'),
        call().add_argument('--mp3', nargs='+', type=CaseBuilder.validate_files, required=True, help='List of MP3 files'),
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
            call().add_argument('--label', type=str),
            call().parse_args(),
        ]
        assert argument_parser.mock_calls == calls
        reset_mocks()


@patch.object(Note, "objects")
@patch.object(Commander, "audio2commands")
@patch.object(LimitedCache, "__new__")
@patch.object(HelperSettings, "settings")
@patch.object(AudioInterpreter, "__new__")
@patch.object(AuditorFile, "__new__")
@patch.object(CaseBuilder, "parameters")
@patch.object(CaseBuilder, "reset")
def test_run(reset, parameters, auditor_file, audio_interpreter, settings, limited_cache, audio2commands, note_db, capsys):
    mock_arguments = MagicMock()
    mock_files = [MagicMock(), MagicMock()]
    mock_note = MagicMock()

    def reset_mocks():
        mock_arguments.reset_mock()
        reset.reset_mock()
        parameters.reset_mock()
        auditor_file.reset_mock()
        audio_interpreter.reset_mock()
        settings.reset_mock()
        limited_cache.reset_mock()
        audio2commands.reset_mock()
        note_db.reset_mock()
        mock_arguments.reset_mock()
        for mock_file in mock_files:
            mock_file.reset_mock()
        mock_note.reset_mock()

    tested = CaseBuilder()

    # deletion
    reset.side_effect = [mock_arguments]
    mock_arguments.delete = True
    mock_arguments.label = "theLabel"

    result = tested.run()
    assert result is None

    exp_out = CaptureResult("Integration Label 'theLabel' deleted\n", "")
    assert capsys.readouterr() == exp_out
    calls = [call()]
    assert reset.mock_calls == calls
    calls = [call.__bool__()]
    assert mock_arguments.mock_calls == calls
    assert parameters.mock_calls == []
    calls = [call(AuditorFile, "theLabel")]
    assert auditor_file.mock_calls == calls
    assert audio_interpreter.mock_calls == []
    assert settings.mock_calls == []
    assert limited_cache.mock_calls == []
    assert audio2commands.mock_calls == []
    assert note_db.mock_calls == []
    assert mock_note.mock_calls == []
    for mock_file in mock_files:
        assert mock_file.mock_calls == []
    reset_mocks()

    # creation
    reset.side_effect = [None]
    parameters.side_effect = [mock_arguments]
    mock_arguments.patient = "patientUuid"
    mock_arguments.label = "theLabel"
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
    limited_cache.side_effect = ["limitedCacheInstance"]

    result = tested.run()
    assert result is None

    exp_out = CaptureResult(
        out='Patient UUID: patientUuid\n'
            'Integration Label: theLabel\n'
            'MP3 Files:\n'
            '- audio file 0\n'
            '- audio file 1\n',
        err='',
    )
    assert capsys.readouterr() == exp_out
    calls = [call()]
    assert reset.mock_calls == calls
    assert parameters.mock_calls == calls
    calls = [call(AuditorFile, "theLabel")]
    assert auditor_file.mock_calls == calls
    calls = [call(AudioInterpreter, "settingsInstance", "limitedCacheInstance", "patientUuid", "noteUuid", "providerUuid")]
    assert audio_interpreter.mock_calls == calls
    calls = [call()]
    assert settings.mock_calls == calls
    calls = [call(LimitedCache, "patientUuid", {})]
    assert limited_cache.mock_calls == calls
    calls = [call(
        "auditorFileInstance",
        [b'audio content 0', b'audio content 1'],
        "audioInterpreterInstance",
        [],
    )]
    assert audio2commands.mock_calls == calls
    calls = [
        call.filter(patient__id='patientUuid'),
        call.filter().order_by('-dbid'),
        call.filter().order_by().first()
    ]
    assert note_db.mock_calls == calls
    assert mock_note.mock_calls == []
    reset_mocks()
