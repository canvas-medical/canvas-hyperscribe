from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, call, MagicMock

from evaluations.case_builders.realworld_case_orchestrator import RealworldCaseOrchestrator
from tests.helper import MockClass


@patch("evaluations.case_builders.realworld_case_orchestrator.Path")
@patch("evaluations.case_builders.realworld_case_orchestrator.ArgumentParser")
def test__parameters(argument_parser, path):
    def reset_mocks():
        argument_parser.reset_mock()
        path.reset_mock()

    expected = Namespace(path_temp_files="thePathTempFiles")
    tested = RealworldCaseOrchestrator

    tests = [
        (True, True, []),
        (True, False, [call().error("The path_temp_files is not a directory: thePathTempFiles")]),
        (False, True, [call().error("The path_temp_files directory does not exist: thePathTempFiles")]),
    ]
    for exists, is_dir, expected_calls in tests:
        argument_parser.return_value.parse_args.side_effect = [expected]
        path.return_value.exists.side_effect = [exists]
        path.return_value.is_dir.side_effect = [is_dir]
        result = tested._parameters()
        assert result == expected

        calls = [
            call(description="Build the topical cases from the tuning files stored in AWS S3"),
            call().add_argument(
                "--customer",
                type=str,
                required=True,
                help="The customer as defined in AWS S3",
            ),
            call().add_argument(
                "--path_temp_files",
                type=str,
                required=True,
                help="Folder to store temporary files",
            ),
            call().add_argument(
                "--cycle_duration",
                type=int,
                required=True,
                help="Duration of each cycle, i.e. the duration of the audio chunks",
            ),
            call().add_argument(
                "--cycle_overlap",
                type=int,
                default=100,
                help="Amount of words provided to the LLM as context from the previous cycle",
            ),
            call().add_argument(
                "--max_workers",
                type=int,
                default=3,
                help="Max cases built simultaneously",
            ),
            call().parse_args(),
        ]
        calls.extend(expected_calls)
        assert argument_parser.mock_calls == calls
        calls = [
            call("thePathTempFiles"),
            call().exists(),
            call().is_dir(),
        ]
        assert path.mock_calls == calls
        reset_mocks()


@patch("evaluations.case_builders.realworld_case_orchestrator.HelperEvaluation")
@patch("evaluations.case_builders.realworld_case_orchestrator.Postgres")
@patch("evaluations.case_builders.realworld_case_orchestrator.AwsS3")
def test_notes(aws_s3, postgres, helper):
    def reset_mocks():
        aws_s3.reset_mock()
        postgres.reset_mock()
        helper.reset_mock()

    tested = RealworldCaseOrchestrator

    aws_s3.return_value.list_s3_objects.side_effect = [
        [
            MockClass(key="hyperscribe-theCustomer/patient_abc123/note_efg456/limited_chart.json"),
            MockClass(key="hyperscribe-theCustomer/patient_abc123/note_efg456/audio_001.webm"),
            MockClass(key="hyperscribe-theCustomer/patient_abc123/note_efg456/audio_002.webm"),
            MockClass(key="hyperscribe-theCustomer/patient_xyz321/note_uvw654/limited_chart.json"),
            MockClass(key="hyperscribe-theCustomer/patient_xyz321/note_uvw654/audio_001.webm"),
            MockClass(key="hyperscribe-theCustomer/patient_xyz321/note_uvw654/audio_002.webm"),
            MockClass(key="hyperscribe-theCustomer/patient_xyz321/note_uvw678/limited_chart.json"),
            MockClass(key="hyperscribe-theCustomer/patient_xyz321/note_uvw678/audio_001.webm"),
            MockClass(key="hyperscribe-theCustomer/patient_xyz321/note_uvw789/limited_chart.json"),
            MockClass(key="hyperscribe-theCustomer/patient_xyz321/note_uvw789/audio_001.webm"),
            MockClass(key="hyperscribe-theCustomer/patient_xyz321/note_uvw890/limited_chart.json"),
            MockClass(key="hyperscribe-theCustomer/patient_xyz321/note_uvw890/audio_001.webm"),
        ]
    ]
    postgres.return_value._select.side_effect = [
        [
            {"patient_note_hash": "patient_xyz321/note_uvw654"},
            {"patient_note_hash": "patient_xyz321/note_uvw678"},
            {"patient_note_hash": "shouldNotOccur"},
        ]
    ]
    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    helper.aws_s3_credentials.side_effect = ["theAwsS3Credentials"]

    result = tested.notes("theCustomer")
    expected = [
        ("abc123", "efg456"),
        ("xyz321", "uvw789"),
        ("xyz321", "uvw890"),
    ]

    assert result == expected

    calls = [
        call("theAwsS3Credentials"),
        call().list_s3_objects("hyperscribe-theCustomer/patient_"),
    ]
    assert aws_s3.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call()._select(
            "\n                             select rwc.patient_note_hash, max(rwc.created) as created"
            "\n                             from real_world_case rwc"
            "\n                             where rwc.customer_identifier = %(customer)s"
            "\n                             group by rwc.patient_note_hash"
            "\n                             order by 2 desc",
            {"customer": "theCustomer"},
        ),
    ]
    assert postgres.mock_calls == calls
    calls = [
        call.postgres_credentials(),
        call.aws_s3_credentials(),
    ]
    assert helper.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.realworld_case_orchestrator.Path")
@patch("evaluations.case_builders.realworld_case_orchestrator.subprocess.Popen")
@patch("evaluations.case_builders.realworld_case_orchestrator.environ")
def test_run_for(environ, popen, path, capsys):
    mock_process = MagicMock()
    mock_stdout = MagicMock()

    def reset_mocks():
        environ.reset_mock()
        popen.reset_mock()
        path.reset_mock()
        mock_process.reset_mock()

    environ.copy.side_effect = [{"variable": "value"}]
    mock_stdout.__bool__.side_effect = [False, True, True, True, True, True, True, True]
    mock_stdout.readline.side_effect = ["", "output line 1\n", "output line 2\n", "", "", "", ""]
    mock_process.stdout = mock_stdout
    mock_process.poll.side_effect = [None, None, None, None, 31]
    mock_process.returncode = 37
    popen.side_effect = [mock_process]
    path.return_value.parent.parent.parent = "thePath"

    parameters = Namespace(
        path_temp_files="thePathTempFiles",
        customer="theCustomer",
        cycle_duration=91,
        cycle_overlap=65,
        max_workers=7,
    )
    tested = RealworldCaseOrchestrator
    result = tested.run_for(117, "thePatientUuid", "theNoteUuid", parameters)
    expected = (117, "thePatientUuid", "theNoteUuid", 37)
    assert result == expected

    calls = [call.copy()]
    assert environ.mock_calls == calls
    calls = [
        call(
            [
                "uv",
                "run",
                "python",
                "case_builder.py",
                "--direct-split",
                "--patient",
                "thePatientUuid",
                "--note",
                "theNoteUuid",
                "--cycle_duration",
                "91",
                "--path_temp_files",
                "thePathTempFiles",
                "--force_rerun",
            ],
            env={
                "variable": "value",
                "CUSTOMER_IDENTIFIER": "theCustomer",
                "CycleTranscriptOverlap": "65",
                "PYTHONUNBUFFERED": "1",
            },
            stdout=-1,
            stderr=-2,
            text=True,
            bufsize=1,
            cwd="thePath",
        )
    ]
    assert popen.mock_calls == calls

    captured = capsys.readouterr()
    expected_output = (
        "[117] processing patient thePatientUuid, note theNoteUuid\n"
        "[117] output line 1\n"
        "[117] output line 2\n"
        "[117] completed with return code: 37\n"
    )
    assert captured.out == expected_output
    directory = Path(__file__).parent.as_posix().replace("/tests", "")
    calls = [call(f"{directory}/realworld_case_orchestrator.py")]
    assert path.mock_calls == calls
    calls = [
        call.stdout.__bool__(),
        call.stdout.__bool__(),
        call.stdout.readline(),
        call.poll(),
        call.stdout.__bool__(),
        call.stdout.readline(),
        call.stdout.__bool__(),
        call.stdout.readline(),
        call.stdout.__bool__(),
        call.stdout.readline(),
        call.poll(),
        call.stdout.__bool__(),
        call.stdout.readline(),
        call.poll(),
        call.stdout.__bool__(),
        call.stdout.readline(),
        call.poll(),
        call.stdout.__bool__(),
        call.stdout.readline(),
        call.poll(),
        call.wait(),
    ]
    assert mock_process.mock_calls == calls
    calls = [
        call.__bool__(),
        call.__bool__(),
        call.readline(),
        call.__bool__(),
        call.readline(),
        call.__bool__(),
        call.readline(),
        call.__bool__(),
        call.readline(),
        call.__bool__(),
        call.readline(),
        call.__bool__(),
        call.readline(),
        call.__bool__(),
        call.readline(),
    ]
    assert mock_stdout.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.realworld_case_orchestrator.ThreadPoolExecutor")
@patch("evaluations.case_builders.realworld_case_orchestrator.RealworldCaseOrchestrator.notes")
@patch("evaluations.case_builders.realworld_case_orchestrator.RealworldCaseOrchestrator._summary")
@patch("evaluations.case_builders.realworld_case_orchestrator.RealworldCaseOrchestrator._parameters")
def test_run(parameters, summary, notes, thread_pool_executor, capsys):
    mock_executor = MagicMock()
    mock_future_1 = MagicMock()
    mock_future_2 = MagicMock()

    def reset_mocks():
        parameters.reset_mock()
        notes.reset_mock()
        thread_pool_executor.reset_mock()
        summary.reset_mock()
        mock_executor.reset_mock()
        mock_future_1.reset_mock()
        mock_future_2.reset_mock()

    namespace = Namespace(max_workers=5, customer="theCustomer")
    mock_future_1.result.side_effect = [(1, "patient1", "note1", 0)]
    mock_future_2.result.side_effect = [(2, "patient2", "note2", 1)]
    mock_executor.submit.side_effect = [mock_future_1, mock_future_2]
    parameters.side_effect = [namespace]
    notes.side_effect = [[("patient1", "note1"), ("patient2", "note2")]]
    thread_pool_executor.return_value.__enter__.side_effect = [mock_executor]

    tested = RealworldCaseOrchestrator
    result = tested.run()
    expected = None
    assert result == expected

    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call("theCustomer")]
    assert notes.mock_calls == calls

    captured = capsys.readouterr()
    expected_output = "notes  : 2\nworkers: 5\n"
    assert captured == (expected_output, "")
    calls = [call(max_workers=5), call().__enter__(), call().__exit__(None, None, None)]
    assert thread_pool_executor.mock_calls == calls
    calls = [call([(1, "patient1", "note1", 0), (2, "patient2", "note2", 1)])]
    assert summary.mock_calls == calls
    calls = [
        call.submit(tested.run_for, 1, "patient1", "note1", namespace),
        call.submit(tested.run_for, 2, "patient2", "note2", namespace),
    ]
    assert mock_executor.mock_calls == calls
    calls = [call()]
    assert mock_future_1.result.mock_calls == calls
    calls = [call()]
    assert mock_future_2.result.mock_calls == calls
    reset_mocks()


def test__summary(capsys):
    tested = RealworldCaseOrchestrator

    # test with mixed success and failure results
    executions = [
        (1, "patient1", "note1", 0),
        (2, "patient2", "note2", 1),
        (3, "patient3", "note3", 2),
        (4, "patient4", "note4", 0),
        (5, "patient5", "note5", 0),
    ]
    result = tested._summary(executions)
    expected = None
    assert result == expected

    captured = capsys.readouterr()
    expected_output = (
        "\n\n"
        "================================================================================\n"
        "summary\n"
        "================================================================================\n"
        "✅ [001] Patient: patient1, Note: note1 (exit code: 0)\n"
        "❌ [002] Patient: patient2, Note: note2 (exit code: 1)\n"
        "❌ [003] Patient: patient3, Note: note3 (exit code: 2)\n"
        "✅ [004] Patient: patient4, Note: note4 (exit code: 0)\n"
        "✅ [005] Patient: patient5, Note: note5 (exit code: 0)\n"
        "--------------------------------------------------------------------------------\n"
        "Total: 5 | Success: 3 | Failed: 2\n"
        "================================================================================\n"
    )
    assert captured.out == expected_output

    # test with empty executions list
    executions = []
    result = tested._summary(executions)
    expected = None
    assert result == expected

    captured = capsys.readouterr()
    expected_output = (
        "\n\n"
        "================================================================================\n"
        "summary\n"
        "================================================================================\n"
        "--------------------------------------------------------------------------------\n"
        "Total: 0 | Success: 0 | Failed: 0\n"
        "================================================================================\n"
    )
    assert captured.out == expected_output
