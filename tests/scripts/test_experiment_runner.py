import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, call, MagicMock

from evaluations.structures.experiment_job import ExperimentJob
from evaluations.structures.experiment_models import ExperimentModels
from evaluations.structures.records.case_id import CaseId as CaseIdRecord
from evaluations.structures.records.experiment import Experiment as ExperimentRecord
from evaluations.structures.records.model import Model as ModelRecord
from scripts.experiment_runner import ExperimentRunner
from tests.helper import MockFile


@patch("scripts.experiment_runner.ArgumentParser")
def test__parameters(argument_parser):
    tested = ExperimentRunner
    argument_parser.return_value.parse_args.side_effect = ["parsed"]
    result = tested._parameters()
    expected = "parsed"
    assert result == expected

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
        call().add_argument(
            "--resume",
            action="store_true",
            help="Resume experiment by skipping already completed jobs",
        ),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls


def test_hyperscribe_tags():
    tested = ExperimentRunner

    json_string = json.dumps({"tags": {"tag1": "value1", "tag2": "value2"}})
    mock_read = MockFile(mode="r", content=json_string)

    repository = MagicMock()
    repository.__truediv__.return_value.__truediv__.return_value.open.side_effect = [mock_read]

    result = tested.hyperscribe_tags(repository)
    expected = {"tag1": "value1", "tag2": "value2"}
    assert result == expected

    calls = [
        call.__truediv__("hyperscribe"),
        call.__truediv__().__truediv__("CANVAS_MANIFEST.json"),
        call.__truediv__().__truediv__().open("r"),
    ]
    assert repository.mock_calls == calls


@patch("scripts.experiment_runner.ExperimentStore")
@patch("scripts.experiment_runner.HelperEvaluation")
def test__experiment_hyperscribe_version(helper, experiment_store):
    def reset_mocks():
        helper.reset_mock()
        experiment_store.reset_mock()

    tested = ExperimentRunner

    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    experiment_store.return_value.get_experiment_hyperscribe_version.side_effect = ["abc123version"]

    result = tested._experiment_hyperscribe_version(473)
    expected = "abc123version"
    assert result == expected

    calls = [call.postgres_credentials()]
    assert helper.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call().get_experiment_hyperscribe_version(473),
    ]
    assert experiment_store.mock_calls == calls
    reset_mocks()


@patch("scripts.experiment_runner.Popen")
def test_hyperscribe_version_exists(popen):
    def reset_mocks():
        popen.reset_mock()

    tested = ExperimentRunner

    tests = [
        (0, True),  # version exists
        (1, False),  # version doesn't exist
    ]
    for return_code, expected in tests:
        mock_process = MagicMock(returncode=return_code)
        popen.side_effect = [mock_process]

        result = tested.hyperscribe_version_exists("abc123")
        assert result == expected

        calls = [
            call(
                ["git", "rev-parse", "--quiet", "--verify", "abc123^{commit}"],
                stdout=-1,
                stderr=-1,
            )
        ]
        assert popen.mock_calls == calls
        reset_mocks()


@patch("scripts.experiment_runner.ExperimentResultStore")
@patch("scripts.experiment_runner.HelperEvaluation")
def test__get_completed_jobs(helper, experiment_result_store):
    def reset_mocks():
        helper.reset_mock()
        experiment_result_store.reset_mock()

    tested = ExperimentRunner

    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    experiment_result_store.return_value._select.side_effect = [
        [
            {"case_id": 756, "gen_id": 117, "grade_id": 217, "cycle_transcript_overlap": 95},
            {"case_id": 789, "gen_id": 132, "grade_id": 232, "cycle_transcript_overlap": 125},
        ]
    ]

    result = tested._get_completed_jobs(473)
    expected = {(756, 117, 217, 95), (789, 132, 232, 125)}
    assert result == expected

    calls = [call.postgres_credentials()]
    assert helper.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call()._select(
            (
                "\n        SELECT DISTINCT case_id,\n               "
                "(SELECT model_note_generator_id FROM experiment_model\n                 "
                "WHERE experiment_id = %(exp_id)s LIMIT 1) as gen_id,\n               "
                "(SELECT model_note_grader_id FROM experiment_model\n                 "
                "WHERE experiment_id = %(exp_id)s LIMIT 1) as grade_id,\n               "
                "cycle_transcript_overlap\n        FROM experiment_result\n        "
                "WHERE experiment_id = %(exp_id)s\n        "
            ),
            {"exp_id": 473},
        ),
    ]
    assert experiment_result_store.mock_calls == calls
    reset_mocks()


@patch("scripts.experiment_runner.run")
def test__clone_repository(mock_run):
    def reset_mocks():
        mock_run.reset_mock()

    tested = ExperimentRunner

    clone_repository = Path("/tmp/test_dir")
    hyperscribe_version = "abc123"

    with patch("scripts.experiment_runner.Path") as mock_path:
        mock_path.return_value.parent.parent = Path("/media/DATA/sdk_canvas/canvas-hyperscribe")
        tested._clone_repository(hyperscribe_version, clone_repository)

    calls = [
        call(
            ["git", "clone", Path("/media/DATA/sdk_canvas/canvas-hyperscribe").as_posix(), "/tmp/test_dir"],
            check=True,
            capture_output=True,
        ),
        call(
            ["git", "checkout", "abc123"],
            cwd="/tmp/test_dir",
            check=True,
            capture_output=True,
        ),
    ]
    assert mock_run.mock_calls == calls
    reset_mocks()


@patch("scripts.experiment_runner.TemporaryDirectory")
@patch("scripts.experiment_runner.Process")
@patch("scripts.experiment_runner.Queue")
@patch("scripts.experiment_runner.NoteGraderWorker")
@patch("scripts.experiment_runner.CaseRunnerWorker")
@patch.object(ExperimentRunner, "_clone_repository")
@patch.object(ExperimentRunner, "hyperscribe_tags")
@patch.object(ExperimentRunner, "_generate_jobs")
@patch.object(ExperimentRunner, "_get_completed_jobs")
@patch.object(ExperimentRunner, "hyperscribe_version_exists")
@patch.object(ExperimentRunner, "_experiment_hyperscribe_version")
@patch.object(ExperimentRunner, "_parameters")
def test_run(
    parameters,
    experiment_hyperscribe_version,
    hyperscribe_version_exists,
    get_completed_jobs,
    generate_jobs,
    hyperscribe_tags,
    clone_repository,
    case_runner_worker,
    note_grader_worker,
    queue,
    process,
    temporary_directory,
    capsys,
):
    processes = [
        MagicMock(run="RunCaseRunnerWorker0"),
        MagicMock(run="RunCaseRunnerWorker1"),
        MagicMock(run="RunCaseRunnerWorker2"),
        MagicMock(run="RunNoteGraderWorker0"),
        MagicMock(run="RunNoteGraderWorker1"),
        MagicMock(run="RunNoteGraderWorker2"),
    ]
    case_runner_workers = [
        MagicMock(run="CaseRunnerWorker0"),
        MagicMock(run="CaseRunnerWorker1"),
        MagicMock(run="CaseRunnerWorker2"),
    ]
    note_grader_workers = [
        MagicMock(run="NoteGraderWorker0"),
        MagicMock(run="NoteGraderWorker1"),
        MagicMock(run="NoteGraderWorker2"),
    ]

    def reset_mocks():
        parameters.reset_mock()
        experiment_hyperscribe_version.reset_mock()
        hyperscribe_version_exists.reset_mock()
        get_completed_jobs.reset_mock()
        clone_repository.reset_mock()
        hyperscribe_tags.reset_mock()
        generate_jobs.reset_mock()
        case_runner_worker.reset_mock()
        note_grader_worker.reset_mock()
        queue.reset_mock()
        process.reset_mock()
        temporary_directory.reset_mock()
        map(lambda m: m.reset_mock(), processes)
        map(lambda m: m.reset_mock(), case_runner_workers)
        map(lambda m: m.reset_mock(), note_grader_workers)

    tags = {"tag1": "value1", "tag2": "value2"}
    version = "theVersion"

    tested = ExperimentRunner

    # normal run without resume
    parameters.side_effect = [Namespace(max_workers=3, experiment_id=473, resume=False)]
    experiment_hyperscribe_version.side_effect = [version]
    hyperscribe_version_exists.side_effect = [True]
    get_completed_jobs.side_effect = [set()]
    temporary_directory.return_value.__enter__.return_value = "/tmp/test_dir"
    clone_repository.side_effect = [None]
    hyperscribe_tags.side_effect = [tags]
    case_runner_worker.side_effect = case_runner_workers
    note_grader_worker.side_effect = note_grader_workers
    process.side_effect = processes
    generate_jobs.side_effect = [["job0", "job1", "job2", "job3"]]
    tested.run()

    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call(473)]
    assert experiment_hyperscribe_version.mock_calls == calls
    calls = [call(version)]
    assert hyperscribe_version_exists.mock_calls == calls
    calls = [call(version, Path("/tmp/test_dir"))]
    assert clone_repository.mock_calls == calls
    calls = [call(Path("/tmp/test_dir"))]
    assert hyperscribe_tags.mock_calls == calls
    calls = [call(473, Path("/tmp/test_dir"), set())]
    assert generate_jobs.mock_calls == calls
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""
    reset_mocks()

    # hyperscribe version does not exist
    parameters.side_effect = [Namespace(max_workers=3, experiment_id=473, resume=False)]
    experiment_hyperscribe_version.side_effect = ["nonExistentVersion"]
    hyperscribe_version_exists.side_effect = [False]
    tested.run()

    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call(473)]
    assert experiment_hyperscribe_version.mock_calls == calls
    calls = [call("nonExistentVersion")]
    assert hyperscribe_version_exists.mock_calls == calls
    assert capsys.readouterr().out == "hyperscribe version does not exist: nonExistentVersion\n"
    assert capsys.readouterr().err == ""
    reset_mocks()

    # resume mode
    parameters.side_effect = [Namespace(max_workers=1, experiment_id=473, resume=True)]
    experiment_hyperscribe_version.side_effect = [version]
    hyperscribe_version_exists.side_effect = [True]
    get_completed_jobs.side_effect = [{(100, 1, 2, 95), (101, 1, 2, 125)}]
    temporary_directory.return_value.__enter__.return_value = "/tmp/test_dir"
    clone_repository.side_effect = [None]
    hyperscribe_tags.side_effect = [tags]
    case_runner_worker.side_effect = case_runner_workers[:1]
    note_grader_worker.side_effect = note_grader_workers[:1]
    process.side_effect = processes[:2]

    mock_jobs = []
    for i in range(15):
        mock_job = MagicMock()
        mock_job.case_name = f"test_case_{i}"
        mock_job.case_id = i
        mock_jobs.append(mock_job)
    generate_jobs.side_effect = [mock_jobs]

    tested.run()

    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call(473)]
    assert experiment_hyperscribe_version.mock_calls == calls
    calls = [call(version)]
    assert hyperscribe_version_exists.mock_calls == calls
    calls = [call(473)]
    assert get_completed_jobs.mock_calls == calls
    calls = [call(version, Path("/tmp/test_dir"))]
    assert clone_repository.mock_calls == calls
    calls = [call(Path("/tmp/test_dir"))]
    assert hyperscribe_tags.mock_calls == calls
    calls = [call(473, Path("/tmp/test_dir"), {(100, 1, 2, 95), (101, 1, 2, 125)})]
    assert generate_jobs.mock_calls == calls

    # Check resume mode output
    output = capsys.readouterr().out
    assert "Resume mode enabled - found 2 unique job combinations already completed" in output
    assert "Queued 10 jobs - Latest: Case test_case_9 (ID: 9)" in output
    assert "Final summary: Added 15 new jobs to queue" in output
    assert capsys.readouterr().err == ""
    reset_mocks()


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
    models_experiments = [
        ExperimentModels(
            experiment_id=123,
            model_generator=ModelRecord(id=117, vendor="theVendor1", api_key="theApiKey1", model="theModel1"),
            model_grader=ModelRecord(id=217, vendor="theVendor4", api_key="theApiKey4", model="theModel4"),
            grader_is_reasoning=True,
        ),
        ExperimentModels(
            experiment_id=123,
            model_generator=ModelRecord(id=132, vendor="theVendor2", api_key="theApiKey2", model="theModel2"),
            model_grader=ModelRecord(id=232, vendor="theVendor5", api_key="theApiKey5", model="theModel5"),
            grader_is_reasoning=True,
        ),
    ]
    repository = Path("/tmp/test_repo")

    # normal job generation
    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    experiment_store.return_value.get_experiment.side_effect = [experiment]
    experiment_store.return_value.get_cases.side_effect = [cases]
    experiment_store.return_value.get_models.side_effect = [models_experiments]
    result = list(tested._generate_jobs(117, repository, set()))

    # Should get all jobs: 2 cases * 2 models * 2 overlaps * 2 replications = 16 jobs
    expected = [
        ExperimentJob(
            job_index=1,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            models=models_experiments[0],
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=2,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            models=models_experiments[0],
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=3,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            models=models_experiments[0],
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=4,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            models=models_experiments[0],
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=5,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            models=models_experiments[1],
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=6,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            models=models_experiments[1],
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=7,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            models=models_experiments[1],
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=8,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            models=models_experiments[1],
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=9,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            models=models_experiments[0],
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=10,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            models=models_experiments[0],
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=11,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            models=models_experiments[0],
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=12,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            models=models_experiments[0],
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=13,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            models=models_experiments[1],
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=14,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            models=models_experiments[1],
            cycle_time=0,
            cycle_transcript_overlap=95,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=15,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            models=models_experiments[1],
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
            cwd_path=repository,
        ),
        ExperimentJob(
            job_index=16,
            experiment_id=117,
            experiment_name="theName",
            case_id=789,
            case_name="theCaseNameY",
            models=models_experiments[1],
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
            cwd_path=repository,
        ),
    ]
    assert result == expected
    assert capsys.readouterr().out == ""

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
    result = list(tested._generate_jobs(117, repository, set()))
    assert result == []
    assert capsys.readouterr().out == "Experiment not found\n"

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
    result = list(tested._generate_jobs(117, repository, set()))
    assert result == []
    assert capsys.readouterr().out == "Experiment has no cases\n"

    calls = [call.postgres_credentials()]
    assert helper.mock_calls == calls
    calls = [
        call("thePostgresCredentials"),
        call().get_experiment(117),
        call().get_cases(117),
    ]
    assert experiment_store.mock_calls == calls
    reset_mocks()

    # experiment has no models
    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    experiment_store.return_value.get_experiment.side_effect = [experiment]
    experiment_store.return_value.get_cases.side_effect = [cases]
    experiment_store.return_value.get_models.side_effect = [[]]
    result = list(tested._generate_jobs(117, repository, set()))
    assert result == []
    assert capsys.readouterr().out == "Experiment has no models\n"

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

    # with completed jobs (resume mode)
    completed_jobs = {(756, 117, 217, 95)}
    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    experiment_store.return_value.get_experiment.side_effect = [experiment]
    experiment_store.return_value.get_cases.side_effect = [cases]
    experiment_store.return_value.get_models.side_effect = [models_experiments]

    result = list(tested._generate_jobs(117, repository, completed_jobs))

    # Should skip (756, 117, 217, 95) - that's 2 replications skipped = 14 total jobs
    assert len(result) == 14
    # Verify skipped job is not in results
    skipped_jobs = [
        j
        for j in result
        if j.case_id == 756 and j.models.model_generator.id == 117 and j.cycle_transcript_overlap == 95
    ]
    assert len(skipped_jobs) == 0
    # Check resume mode output
    output = capsys.readouterr().out
    assert "Job generation complete:" in output
    assert "Jobs skipped due to completion: 2" in output
    assert "Cases processed: 2/2" in output

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

    # test with None completed_jobs (should default to empty set)
    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    experiment_store.return_value.get_experiment.side_effect = [experiment]
    experiment_store.return_value.get_cases.side_effect = [cases]
    experiment_store.return_value.get_models.side_effect = [models_experiments]

    result = list(tested._generate_jobs(117, repository, None))

    assert len(result) == 16
    assert capsys.readouterr().out == ""

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
