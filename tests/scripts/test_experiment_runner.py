import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, call, MagicMock

from evaluations.auditors.auditor_postgres import AuditorPostgres
from evaluations.structures.case_runner_job import CaseRunnerJob
from evaluations.structures.experiment_job import ExperimentJob
from evaluations.structures.note_grader_job import NoteGraderJob
from evaluations.structures.records.case_id import CaseId as CaseIdRecord
from evaluations.structures.records.experiment import Experiment as ExperimentRecord
from evaluations.structures.records.experiment_result import ExperimentResult as ExperimentResultRecord
from evaluations.structures.records.model import Model as ModelRecord
from scripts.experiment_runner import ExperimentRunner
from tests.helper import MockFile


@patch("scripts.experiment_runner.ArgumentParser")
def test__parameters(argument_parser):
    tested = ExperimentRunner
    argument_parser.return_value.parse_args.side_effect = ["parsed"]
    result = tested._parameters()
    assert result == "parsed"

    calls = [
        call(description="Run the provided experiment"),
        call().add_argument(
            "--experiment_id",
            type=int,
            required=True,
            help="The experiment id from the database",
        ),
        call().add_argument(
            "--max_workers",
            type=int,
            default=3,
            help="Max cases run simultaneously",
        ),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls


@patch.object(AuditorPostgres, "get_plugin_commit")
def test_hyperscribe_version(get_plugin_commit):
    def reset_mocks():
        get_plugin_commit.reset_mock()

    tested = ExperimentRunner

    get_plugin_commit.side_effect = ["theVersion"]

    result = tested.hyperscribe_version()
    expected = "theVersion"
    assert result == expected

    calls = [call()]
    assert get_plugin_commit.mock_calls == calls
    reset_mocks()


@patch("scripts.experiment_runner.Path")
def test_hyperscribe_tags(path):
    def reset_mocks():
        path.reset_mock()

    tested = ExperimentRunner

    json_string = json.dumps({"tags": {"tag1": "value1", "tag2": "value2"}})
    mock_read = MockFile(mode="r", content=json_string)
    path.return_value.parent.parent.__truediv__.return_value.__truediv__.return_value.open.side_effect = [mock_read]

    result = tested.hyperscribe_tags()
    expected = {"tag1": "value1", "tag2": "value2"}
    assert result == expected

    directory = Path(__file__).parent.parent.as_posix().replace("/tests", "")
    calls = [
        call(f"{directory}/scripts/experiment_runner.py"),
        call().parent.parent.__truediv__("hyperscribe"),
        call().parent.parent.__truediv__().__truediv__("CANVAS_MANIFEST.json"),
        call().parent.parent.__truediv__().__truediv__().open("r"),
    ]
    assert path.mock_calls == calls
    reset_mocks()


@patch("scripts.experiment_runner.Path")
@patch("scripts.experiment_runner.Popen")
@patch("scripts.experiment_runner.environ")
@patch.object(ExperimentRunner, "_build_command_note_grader")
@patch.object(ExperimentRunner, "run_case_runner_jobs")
def test_run(run_case_runner_jobs, build_command_note_grader, environ, popen, path, capsys):
    jobs = [
        MagicMock(job_index=3),
        MagicMock(job_index=7),
        MagicMock(job_index=8),
    ]
    processes = [
        MagicMock(stdout=["line1", "line2"]),
        MagicMock(stdout=["line3", "line4"]),
        MagicMock(stdout=["\n\r\n"]),
    ]

    def reset_mocks():
        run_case_runner_jobs.reset_mock()
        build_command_note_grader.reset_mock()
        environ.reset_mock()
        popen.reset_mock()
        path.reset_mock()
        map(lambda m: m.reset_mock(), jobs)
        map(lambda m: m.reset_mock(), processes)

    tested = ExperimentRunner

    run_case_runner_jobs.side_effect = [jobs]
    build_command_note_grader.side_effect = ["cmd1", "cmd2", "cmd3"]
    environ.copy.side_effect = ["env1", "env2", "env3"]
    popen.side_effect = processes
    path.return_value.parent.parent = "thePath"

    tested.run()
    exp_out = "\n".join(
        [
            "[003] line1",
            "[003] line2",
            "[007] line3",
            "[007] line4",
            "",
        ]
    )
    assert capsys.readouterr().out == exp_out
    assert capsys.readouterr().err == ""

    calls = [call()]
    assert run_case_runner_jobs.mock_calls == calls
    calls = [call(jobs[0]), call(jobs[1]), call(jobs[2])]
    assert build_command_note_grader.mock_calls == calls
    calls = [call.copy(), call.copy(), call.copy()]
    assert environ.mock_calls == calls
    calls = [
        call("cmd1", env="env1", stdout=-1, stderr=-2, text=True, bufsize=1, cwd="thePath"),
        call("cmd2", env="env2", stdout=-1, stderr=-2, text=True, bufsize=1, cwd="thePath"),
        call("cmd3", env="env3", stdout=-1, stderr=-2, text=True, bufsize=1, cwd="thePath"),
    ]
    assert popen.mock_calls == calls
    directory = Path(__file__).parent.parent.as_posix().replace("/tests", "")
    calls = [
        call(f"{directory}/scripts/experiment_runner.py"),
        call(f"{directory}/scripts/experiment_runner.py"),
        call(f"{directory}/scripts/experiment_runner.py"),
    ]
    assert path.mock_calls == calls

    calls = []
    for mock in jobs:
        assert mock.mock_calls == calls
    calls = [call.wait()]
    for mock in processes:
        assert mock.mock_calls == calls

    reset_mocks()


@patch("scripts.experiment_runner.Path")
@patch("scripts.experiment_runner.Popen")
@patch("scripts.experiment_runner.RubricStore")
@patch("scripts.experiment_runner.ExperimentResultStore")
@patch("scripts.experiment_runner.HelperEvaluation")
@patch.object(ExperimentRunner, "hyperscribe_tags")
@patch.object(ExperimentRunner, "hyperscribe_version")
@patch.object(ExperimentRunner, "_build_command_case_runner")
@patch.object(ExperimentRunner, "_build_environment")
@patch.object(ExperimentRunner, "_generate_jobs")
@patch.object(ExperimentRunner, "_parameters")
def test_run_case_runner_jobs(
    parameters,
    generate_jobs,
    build_environment,
    build_command_case_runner,
    hyperscribe_version,
    hyperscribe_tags,
    helper,
    experiment_result_store,
    rubric_store,
    popen,
    path,
    capsys,
):
    jobs = [
        ExperimentJob(
            job_index=1,
            experiment_id=731,
            experiment_name="theExperimentNameX",
            case_id=4561,
            case_name="theCaseNameA",
            model_id=31,
            model_vendor="theModelVendorX",
            model_name="theModelNameX",
            model_api_key="theModelKeyX",
            cycle_time=7,
            cycle_transcript_overlap=147,
            grade_replications=1,
        ),
        ExperimentJob(
            job_index=2,
            experiment_id=731,
            experiment_name="theExperimentNameX",
            case_id=4562,
            case_name="theCaseNameB",
            model_id=33,
            model_vendor="theModelVendorY",
            model_name="theModelNameY",
            model_api_key="theModelKeyY",
            cycle_time=5,
            cycle_transcript_overlap=151,
            grade_replications=3,
        ),
        ExperimentJob(
            job_index=2,
            experiment_id=731,
            experiment_name="theExperimentNameX",
            case_id=4563,
            case_name="theCaseNameC",
            model_id=31,
            model_vendor="theModelVendorX",
            model_name="theModelNameX",
            model_api_key="theModelKeyX",
            cycle_time=7,
            cycle_transcript_overlap=147,
            grade_replications=2,
        ),
        ExperimentJob(
            job_index=3,
            experiment_id=731,
            experiment_name="theExperimentNameX",
            case_id=4564,
            case_name="theCaseNameD",
            model_id=33,
            model_vendor="theModelVendorY",
            model_name="theModelNameY",
            model_api_key="theModelKeyY",
            cycle_time=5,
            cycle_transcript_overlap=151,
            grade_replications=3,
        ),
    ]
    processes = [
        MagicMock(stdout=["line1", "line2"]),
        MagicMock(stdout=["line3", "line4", "\n\r\n"]),
        MagicMock(stdout=["line5", "line6"]),
    ]

    def reset_mocks():
        parameters.reset_mock()
        generate_jobs.reset_mock()
        build_environment.reset_mock()
        build_command_case_runner.reset_mock()
        hyperscribe_version.reset_mock()
        hyperscribe_tags.reset_mock()
        helper.reset_mock()
        experiment_result_store.reset_mock()
        rubric_store.reset_mock()
        popen.reset_mock()
        path.reset_mock()
        map(lambda m: m.reset_mock(), jobs)
        map(lambda m: m.reset_mock(), processes)

    tested = ExperimentRunner

    parameters.side_effect = [Namespace(experiment_id=137)]
    generate_jobs.side_effect = [jobs]
    build_environment.side_effect = ["env1", "env2", "env3"]
    build_command_case_runner.side_effect = ["cmd1", "cmd2", "cmd3"]
    hyperscribe_version.side_effect = ["theVersion"]
    hyperscribe_tags.side_effect = [{"tag1": "value1", "tag2": "value2"}]
    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    experiment_result_store.return_value.insert.side_effect = [
        ExperimentResultRecord(id=412, experiment_id=371),
        ExperimentResultRecord(id=413, experiment_id=371),
        ExperimentResultRecord(id=414, experiment_id=371),
    ]
    experiment_result_store.return_value.get_generated_note_id.side_effect = [0, 790, 791, 797]
    rubric_store.return_value.get_last_accepted.side_effect = [590, 0, 591, 597]
    popen.side_effect = processes
    path.return_value.parent.parent = "thePath"

    result = [j for j in tested.run_case_runner_jobs()]
    expected = [
        NoteGraderJob(job_index=0, parent_index=2, rubric_id=591, generated_note_id=790, experiment_result_id=413),
        NoteGraderJob(job_index=1, parent_index=2, rubric_id=591, generated_note_id=790, experiment_result_id=413),
        NoteGraderJob(job_index=0, parent_index=3, rubric_id=597, generated_note_id=791, experiment_result_id=414),
        NoteGraderJob(job_index=1, parent_index=3, rubric_id=597, generated_note_id=791, experiment_result_id=414),
        NoteGraderJob(job_index=2, parent_index=3, rubric_id=597, generated_note_id=791, experiment_result_id=414),
    ]
    assert result == expected

    exp_out = "\n".join(
        [
            "[001] line1",
            "[001] line2",
            "[001] no note generated",
            "[002] no rubric accepted",
            "[002] line3",
            "[002] line4",
            "[003] line5",
            "[003] line6",
            "",
        ]
    )
    assert capsys.readouterr().out == exp_out
    assert capsys.readouterr().err == ""

    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call(137)]
    assert generate_jobs.mock_calls == calls
    calls = [
        call(
            ExperimentJob(
                job_index=1,
                experiment_id=731,
                experiment_name="theExperimentNameX",
                case_id=4561,
                case_name="theCaseNameA",
                model_id=31,
                model_vendor="theModelVendorX",
                model_name="theModelNameX",
                model_api_key="theModelKeyX",
                cycle_time=7,
                cycle_transcript_overlap=147,
                grade_replications=1,
            )
        ),
        call(
            ExperimentJob(
                job_index=2,
                experiment_id=731,
                experiment_name="theExperimentNameX",
                case_id=4563,
                case_name="theCaseNameC",
                model_id=31,
                model_vendor="theModelVendorX",
                model_name="theModelNameX",
                model_api_key="theModelKeyX",
                cycle_time=7,
                cycle_transcript_overlap=147,
                grade_replications=2,
            )
        ),
        call(
            ExperimentJob(
                job_index=3,
                experiment_id=731,
                experiment_name="theExperimentNameX",
                case_id=4564,
                case_name="theCaseNameD",
                model_id=33,
                model_vendor="theModelVendorY",
                model_name="theModelNameY",
                model_api_key="theModelKeyY",
                cycle_time=5,
                cycle_transcript_overlap=151,
                grade_replications=3,
            )
        ),
    ]
    assert build_environment.mock_calls == calls
    calls = [
        call(CaseRunnerJob(case_name="theCaseNameA", experiment_result_id=412)),
        call(CaseRunnerJob(case_name="theCaseNameC", experiment_result_id=413)),
        call(CaseRunnerJob(case_name="theCaseNameD", experiment_result_id=414)),
    ]
    assert build_command_case_runner.mock_calls == calls
    calls = [call()]
    assert hyperscribe_version.mock_calls == calls
    calls = [call()]
    assert hyperscribe_tags.mock_calls == calls
    calls = [call.postgres_credentials()]
    assert helper.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call().insert(
            ExperimentResultRecord(
                experiment_id=731,
                experiment_name="theExperimentNameX",
                hyperscribe_version="theVersion",
                hyperscribe_tags={"tag1": "value1", "tag2": "value2"},
                case_id=4561,
                case_name="theCaseNameA",
                model_id=31,
                text_llm_vendor="theModelVendorX",
                text_llm_name="theModelNameX",
                cycle_time=7,
                cycle_transcript_overlap=147,
                failed=False,
                errors={},
                generated_note_id=0,
                note_json=[],
                id=0,
            )
        ),
        call().get_generated_note_id(412),
        call().insert(
            ExperimentResultRecord(
                experiment_id=731,
                experiment_name="theExperimentNameX",
                hyperscribe_version="theVersion",
                hyperscribe_tags={"tag1": "value1", "tag2": "value2"},
                case_id=4563,
                case_name="theCaseNameC",
                model_id=31,
                text_llm_vendor="theModelVendorX",
                text_llm_name="theModelNameX",
                cycle_time=7,
                cycle_transcript_overlap=147,
                failed=False,
                errors={},
                generated_note_id=0,
                note_json=[],
                id=0,
            )
        ),
        call().get_generated_note_id(413),
        call().insert(
            ExperimentResultRecord(
                experiment_id=731,
                experiment_name="theExperimentNameX",
                hyperscribe_version="theVersion",
                hyperscribe_tags={"tag1": "value1", "tag2": "value2"},
                case_id=4564,
                case_name="theCaseNameD",
                model_id=33,
                text_llm_vendor="theModelVendorY",
                text_llm_name="theModelNameY",
                cycle_time=5,
                cycle_transcript_overlap=151,
                failed=False,
                errors={},
                generated_note_id=0,
                note_json=[],
                id=0,
            )
        ),
        call().get_generated_note_id(414),
    ]
    assert experiment_result_store.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call().get_last_accepted(4561),
        call().get_last_accepted(4562),
        call().get_last_accepted(4563),
        call().get_last_accepted(4564),
    ]
    assert rubric_store.mock_calls == calls
    calls = [
        call("cmd1", env="env1", stdout=-1, stderr=-2, text=True, bufsize=1, cwd="thePath"),
        call("cmd2", env="env2", stdout=-1, stderr=-2, text=True, bufsize=1, cwd="thePath"),
        call("cmd3", env="env3", stdout=-1, stderr=-2, text=True, bufsize=1, cwd="thePath"),
    ]
    assert popen.mock_calls == calls
    directory = Path(__file__).parent.parent.as_posix().replace("/tests", "")
    calls = [
        call(f"{directory}/scripts/experiment_runner.py"),
        call(f"{directory}/scripts/experiment_runner.py"),
        call(f"{directory}/scripts/experiment_runner.py"),
    ]
    calls = [call.wait()]
    for mock in processes:
        assert mock.mock_calls == calls

    reset_mocks()


@patch("scripts.experiment_runner.environ")
def test__build_environment(environ):
    def reset_mocks():
        environ.reset_mock()

    job = ExperimentJob(
        job_index=11,
        experiment_id=731,
        experiment_name="theExperimentName",
        case_id=4561,
        case_name="theCaseName",
        model_id=31,
        model_vendor="theModelVendor",
        model_name="theModelName",
        model_api_key="theModelKey",
        cycle_time=7,
        cycle_transcript_overlap=147,
        grade_replications=1,
    )

    tested = ExperimentRunner
    tests = [
        {
            "key1": "value1",
            "key2": "value2",
        },
        {
            "key1": "value1",
            "key2": "value2",
            "VendorTextLLM": "someValue",
            "KeyTextLLM": "someValue",
            "CycleTranscriptOverlap": "someValue",
            "AuditLLMDecisions": "someValue",
            "IsTuning": "someValue",
            "sendProgress": "someValue",
            "MaxWorkers": "someValue",
            "StructuredReasonForVisit": "someValue",
            "StaffersList": "someValue",
            "StaffersPolicy": "someValue",
            "CommandsList": "someValue",
            "CommandsPolicy": "someValue",
            "TrialStaffersList": "someValue",
            "APISigningKey": "someValue",
            "KeyAudioLLM": "someValue",
            "VendorAudioLLM": "someValue",
        },
    ]
    for environ_side_effect in tests:
        environ.copy.side_effect = [environ_side_effect]

        result = tested._build_environment(job)
        expected = {
            "APISigningKey": "",
            "AuditLLMDecisions": "n",
            "CommandsList": "",
            "CommandsPolicy": "n",
            "CycleTranscriptOverlap": "147",
            "IsTuning": "n",
            "KeyAudioLLM": "",
            "KeyTextLLM": "theModelKey",
            "MaxWorkers": "1",
            "StaffersList": "",
            "StaffersPolicy": "y",
            "StructuredReasonForVisit": "n",
            "TrialStaffersList": "",
            "VendorAudioLLM": "",
            "VendorTextLLM": "theModelVendor",
            "key1": "value1",
            "key2": "value2",
            "sendProgress": "",
        }
        assert result == expected

        calls = [call.copy()]
        assert environ.mock_calls == calls
        reset_mocks()


def test__build_command_case_runner():
    tested = ExperimentRunner
    job = CaseRunnerJob(case_name="theCaseName", experiment_result_id=417)
    result = tested._build_command_case_runner(job)
    expected = [
        "uv",
        "run",
        "python",
        "-m",
        "scripts.case_runner",
        "--case",
        "theCaseName",
        "--experiment_result_id",
        "417",
    ]
    assert result == expected


def test__build_command_note_grader():
    tested = ExperimentRunner
    job = NoteGraderJob(job_index=1, parent_index=3, rubric_id=597, generated_note_id=791, experiment_result_id=414)
    result = tested._build_command_note_grader(job)
    expected = [
        "uv",
        "run",
        "python",
        "-m",
        "evaluations.case_builders.note_grader",
        "--rubric_id",
        "597",
        "--generated_note_id",
        "791",
        "--experiment_result_id",
        "414",
    ]
    assert result == expected


@patch("scripts.experiment_runner.ExperimentStore")
@patch("scripts.experiment_runner.HelperEvaluation")
def test__generate_jobs(helper, experiment_store, capsys):
    def reset_mocks():
        helper.reset_mock()
        experiment_store.reset_mock()

    tested = ExperimentRunner

    experiment = ExperimentRecord(
        id=117,
        name="theName",
        cycle_times=[30, 45],
        cycle_transcript_overlaps=[95, 125],
        note_replications=2,
        grade_replications=11,
    )
    cases = [
        CaseIdRecord(id=756, name="theCaseNameX"),
        CaseIdRecord(id=789, name="theCaseNameY"),
    ]
    # all god
    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    experiment_store.return_value.get_experiment.side_effect = [experiment]
    experiment_store.return_value.get_cases.side_effect = [cases]
    experiment_store.return_value.get_models.side_effect = [
        [
            ModelRecord(id=756, name="theModelNameX", vendor="theVendorX", api_key="theApiKeyX"),
            ModelRecord(id=789, name="theModelNameY", vendor="theVendorY", api_key="theApiKeyY"),
        ]
    ]
    result = [j for j in tested._generate_jobs(117)]
    expected = [
        ExperimentJob(
            job_index=1,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            model_id=756,
            model_vendor="theVendorX",
            model_name="theModelNameX",
            model_api_key="theApiKeyX",
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=2,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            model_id=756,
            model_vendor="theVendorX",
            model_name="theModelNameX",
            model_api_key="theApiKeyX",
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=3,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            model_id=756,
            model_vendor="theVendorX",
            model_name="theModelNameX",
            model_api_key="theApiKeyX",
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=4,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            model_id=756,
            model_vendor="theVendorX",
            model_name="theModelNameX",
            model_api_key="theApiKeyX",
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=5,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            model_id=789,
            model_vendor="theVendorY",
            model_name="theModelNameY",
            model_api_key="theApiKeyY",
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=6,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            model_id=789,
            model_vendor="theVendorY",
            model_name="theModelNameY",
            model_api_key="theApiKeyY",
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=7,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            model_id=789,
            model_vendor="theVendorY",
            model_name="theModelNameY",
            model_api_key="theApiKeyY",
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=8,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            model_id=789,
            model_vendor="theVendorY",
            model_name="theModelNameY",
            model_api_key="theApiKeyY",
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=9,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            model_id=756,
            model_vendor="theVendorX",
            model_name="theModelNameX",
            model_api_key="theApiKeyX",
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=10,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            model_id=756,
            model_vendor="theVendorX",
            model_name="theModelNameX",
            model_api_key="theApiKeyX",
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=11,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            model_id=756,
            model_vendor="theVendorX",
            model_name="theModelNameX",
            model_api_key="theApiKeyX",
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=12,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            model_id=756,
            model_vendor="theVendorX",
            model_name="theModelNameX",
            model_api_key="theApiKeyX",
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=13,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            model_id=789,
            model_vendor="theVendorY",
            model_name="theModelNameY",
            model_api_key="theApiKeyY",
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=14,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            model_id=789,
            model_vendor="theVendorY",
            model_name="theModelNameY",
            model_api_key="theApiKeyY",
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=15,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            model_id=789,
            model_vendor="theVendorY",
            model_name="theModelNameY",
            model_api_key="theApiKeyY",
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
        ),
        ExperimentJob(
            job_index=16,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            model_id=789,
            model_vendor="theVendorY",
            model_name="theModelNameY",
            model_api_key="theApiKeyY",
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
        ),
    ]
    assert result == expected
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""

    calls = [call.postgres_credentials()]
    assert helper.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call().get_experiment(117),
        call().get_cases(117),
        call().get_models(117),
    ]
    assert experiment_store.mock_calls == calls
    reset_mocks()

    # experiment does not exist
    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    experiment_store.return_value.get_experiment.side_effect = [ExperimentRecord(id=0)]
    experiment_store.return_value.get_cases.side_effect = []
    experiment_store.return_value.get_models.side_effect = []
    result = [j for j in tested._generate_jobs(117)]
    assert result == []
    exp_out = "Experiment not found\n"
    assert capsys.readouterr().out == exp_out
    assert capsys.readouterr().err == ""

    calls = [call.postgres_credentials()]
    assert helper.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call().get_experiment(117),
    ]
    assert experiment_store.mock_calls == calls
    reset_mocks()

    # experiment has no cases
    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    experiment_store.return_value.get_experiment.side_effect = [experiment]
    experiment_store.return_value.get_cases.side_effect = [[]]
    experiment_store.return_value.get_models.side_effect = []
    result = [j for j in tested._generate_jobs(117)]
    assert result == []
    exp_out = "Experiment has no cases\n"
    assert capsys.readouterr().out == exp_out
    assert capsys.readouterr().err == ""

    calls = [call.postgres_credentials()]
    assert helper.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call().get_experiment(117),
        call().get_cases(117),
    ]
    assert experiment_store.mock_calls == calls
    reset_mocks()

    # experiment has no model
    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    experiment_store.return_value.get_experiment.side_effect = [experiment]
    experiment_store.return_value.get_cases.side_effect = [cases]
    experiment_store.return_value.get_models.side_effect = [[]]
    result = [j for j in tested._generate_jobs(117)]
    assert result == []
    exp_out = "Experiment has no models\n"
    assert capsys.readouterr().out == exp_out
    assert capsys.readouterr().err == ""

    calls = [call.postgres_credentials()]
    assert helper.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call().get_experiment(117),
        call().get_cases(117),
        call().get_models(117),
    ]
    assert experiment_store.mock_calls == calls
    reset_mocks()
