import json
from pathlib import Path
from unittest.mock import patch, call, MagicMock

from evaluations.datastores.filesystem.case import Case
from evaluations.structures.evaluation_case import EvaluationCase


def test__db_path():
    tested = Case
    with patch('evaluations.datastores.filesystem.case.Path') as mock_path:
        mock_path.side_effect = [Path('/a/b/c/d/e/theFile.py')]
        result = tested._db_path()
        assert result == Path('/a/b/c/datastores/cases')


@patch.object(Case, "_db_path")
def test_upsert(db_path):
    mock_files = [
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        db_path.reset_mock()
        for item in mock_files:
            item.reset_mock()

    tested = Case

    db_path.return_value.__truediv__.side_effect = mock_files

    tested.upsert(EvaluationCase(
        environment="theEnvironment",
        patient_uuid="thePatientUuid",
        limited_cache={"key": "theLimitedCache"},
        case_type="theType",
        case_group="theGroup",
        case_name="theCaseName",
        cycles=7,
        description="theDescription",
    ))
    calls = [
        call(),
        call().__truediv__('theCaseName.json'),
        call(),
        call().__truediv__('limited_caches/theCaseName.json'),
    ]
    assert db_path.mock_calls == calls
    calls = [
        call.open(mode='w'),
        call.open().__enter__(),
        call.open().__enter__().write(
            '{\n'
            '  "environment": "theEnvironment",\n'
            '  "patientUuid": "thePatientUuid",\n'
            '  "caseType": "theType",\n'
            '  "caseGroup": "theGroup",\n'
            '  "caseName": "theCaseName",\n'
            '  "cycles": 7,\n'
            '  "description": "theDescription"\n'
            '}'
        ),
        call.open().__exit__(None, None, None),
    ]
    assert mock_files[0].mock_calls == calls
    calls = [
        call.open(mode='w'),
        call.open().__enter__(),
        call.open().__enter__().write(
            '{\n'
            '  "key": "theLimitedCache"\n'
            '}'
        ),
        call.open().__exit__(None, None, None),
    ]
    assert mock_files[1].mock_calls == calls
    reset_mocks()


@patch.object(Case, "_db_path")
def test_delete(db_path):
    mock_files = [
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        db_path.reset_mock()
        for item in mock_files:
            item.reset_mock()

    tested = Case
    tests = [True, False]
    for exists in tests:
        db_path.return_value.__truediv__.side_effect = mock_files
        for file in mock_files:
            file.exists.side_effect = [exists]

        tested.delete("theCaseName")
        calls = [
            call(),
            call().__truediv__('theCaseName.json'),
            call(),
            call().__truediv__('limited_caches/theCaseName.json'),
        ]
        assert db_path.mock_calls == calls
        calls = [
            call.exists(),
        ]
        if exists:
            calls.append(call.unlink())
        for file in mock_files:
            assert file.mock_calls == calls
        reset_mocks()


@patch.object(Case, "_db_path")
def test_get(db_path):
    mock_files = [
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        db_path.reset_mock()
        for item in mock_files:
            item.reset_mock()

    tested = Case

    data = json.dumps({
        "environment": "theEnvironment",
        "patientUuid": "thePatientUuid",
        "caseType": "theCaseType",
        "caseGroup": "theCaseGroup",
        "caseName": "theCaseName",
        "cycles": 7,
        "description": "theDescription",
    })
    cache = json.dumps({"key": "theLimitedCache"})

    tests = [
        ("theCaseName", False, False, [], [], EvaluationCase()),
        ("theCaseName", False, True, [], [cache], EvaluationCase()),
        ("theCaseName", True, True, [data], [cache], EvaluationCase(
            environment="theEnvironment",
            patient_uuid="thePatientUuid",
            case_type="theCaseType",
            case_group="theCaseGroup",
            case_name="theCaseName",
            cycles=7,
            description="theDescription",
            limited_cache={"key": "theLimitedCache"},
        )),
        ("theCaseName", True, False, [data], [], EvaluationCase(
            environment="theEnvironment",
            patient_uuid="thePatientUuid",
            case_type="theCaseType",
            case_group="theCaseGroup",
            case_name="theCaseName",
            cycles=7,
            description="theDescription",
            limited_cache={},
        )),
    ]
    for case_name, case_exists, cache_exists, side_effect_case, side_effect_cache, expected in tests:
        db_path.return_value.__truediv__.side_effect = mock_files
        mock_files[0].exists.side_effect = [case_exists]
        mock_files[1].exists.side_effect = [cache_exists]
        mock_files[0].read_text.side_effect = side_effect_case
        mock_files[1].read_text.side_effect = side_effect_cache

        result = tested.get(case_name)
        assert result == expected

        calls = [
            call(),
            call().__truediv__('theCaseName.json'),
            call(),
            call().__truediv__('limited_caches/theCaseName.json'),
        ]
        assert db_path.mock_calls == calls
        calls = [call.exists()]
        if case_exists:
            calls.append(call.read_text())
        assert mock_files[0].mock_calls == calls
        calls = [call.exists()]
        if cache_exists:
            calls.append(call.read_text())
        assert mock_files[1].mock_calls == calls
        reset_mocks()


@patch.object(Case, "_db_path")
def test_all(db_path):
    mock_files = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        db_path.reset_mock()
        for item in mock_files:
            item.reset_mock()

    tested = Case

    data = [json.dumps({
        "environment": f"theEnvironment{i:02d}",
        "patientUuid": f"thePatientUuid{i:02d}",
        "caseType": f"theCaseType{i:02d}",
        "caseGroup": f"theCaseGroup{i:02d}",
        "caseName": f"theCaseName{i:02d}",
        "cycles": 2 * i + 1,
        "description": f"theDescription{i:02d}",
    }) for i in range(3)]
    expected = [
        EvaluationCase(
            environment=f"theEnvironment{i:02d}",
            patient_uuid=f"thePatientUuid{i:02d}",
            case_type=f"theCaseType{i:02d}",
            case_group=f"theCaseGroup{i:02d}",
            case_name=f"theCaseName{i:02d}",
            cycles=2 * i + 1,
            description=f"theDescription{i:02d}",
            limited_cache={},
        )
        for i in range(3)
    ]
    # no files
    db_path.return_value.glob.side_effect = [[]]

    result = tested.all()
    assert result == []
    calls = [
        call(),
        call().glob('*.json'),
    ]
    assert db_path.mock_calls == calls
    reset_mocks()
    # with files
    db_path.return_value.glob.side_effect = [mock_files]
    for idx, file in enumerate(mock_files):
        file.read_text.side_effect = [data[idx]]

    result = tested.all()
    assert result == expected
    calls = [
        call(),
        call().glob('*.json'),
    ]
    assert db_path.mock_calls == calls
    calls = [call.read_text()]
    for file in mock_files:
        assert file.mock_calls == calls
    reset_mocks()
