import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, call, MagicMock

from evaluations.auditors.auditor_postgres import AuditorPostgres
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


@patch("scripts.experiment_runner.Process")
@patch("scripts.experiment_runner.Queue")
@patch("scripts.experiment_runner.NoteGraderWorker")
@patch("scripts.experiment_runner.CaseRunnerWorker")
@patch.object(ExperimentRunner, "hyperscribe_tags")
@patch.object(ExperimentRunner, "hyperscribe_version")
@patch.object(ExperimentRunner, "_generate_jobs")
@patch.object(ExperimentRunner, "_parameters")
def test_run(
    parameters,
    generate_jobs,
    hyperscribe_version,
    hyperscribe_tags,
    case_runner_worker,
    note_grader_worker,
    queue,
    process,
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
        hyperscribe_version.reset_mock()
        hyperscribe_tags.reset_mock()
        generate_jobs.reset_mock()
        case_runner_worker.reset_mock()
        note_grader_worker.reset_mock()
        queue.reset_mock()
        process.reset_mock()
        map(lambda m: m.reset_mock(), processes)
        map(lambda m: m.reset_mock(), case_runner_workers)
        map(lambda m: m.reset_mock(), note_grader_workers)

    tags = {"tag1": "value1", "tag2": "value2"}
    version = "theVersion"

    tested = ExperimentRunner
    parameters.side_effect = [Namespace(max_workers=3, experiment_id=473)]
    generate_jobs.side_effect = [["generateJob0", "generateJob1", "generateJob2"]]
    case_runner_worker.side_effect = case_runner_workers
    note_grader_worker.side_effect = note_grader_workers
    hyperscribe_version.side_effect = [version]
    hyperscribe_tags.side_effect = [tags]
    process.side_effect = processes
    generate_jobs.side_effect = [["job0", "job1", "job2", "job3"]]
    tested.run()

    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call()]
    assert hyperscribe_version.mock_calls == calls
    calls = [call()]
    assert hyperscribe_tags.mock_calls == calls
    calls = [call(473)]
    assert generate_jobs.mock_calls == calls
    calls = [
        call(),
        call(),
        call().put("job0"),
        call().put("job1"),
        call().put("job2"),
        call().put("job3"),
        call().put(None),
        call().put(None),
        call().put(None),
        call().put(None),
        call().put(None),
        call().put(None),
    ]
    assert queue.mock_calls == calls
    calls = [
        call(target="CaseRunnerWorker0"),
        call(target="CaseRunnerWorker1"),
        call(target="CaseRunnerWorker2"),
        call(target="NoteGraderWorker0"),
        call(target="NoteGraderWorker1"),
        call(target="NoteGraderWorker2"),
    ]
    assert process.mock_calls == calls
    calls = [call.start(), call.join()]
    for mock in processes:
        assert mock.mock_calls == calls
    calls = []
    for mock in case_runner_workers:
        assert mock.mock_calls == calls
    calls = []
    for mock in note_grader_workers:
        assert mock.mock_calls == calls
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
            model_generator=ModelRecord(id=117, vendor="theVendor1", api_key="theApiKey1"),
            model_grader=ModelRecord(id=217, vendor="theVendor4", api_key="theApiKey4"),
            grader_is_reasoning=True,
        ),
        ExperimentModels(
            experiment_id=123,
            model_generator=ModelRecord(id=132, vendor="theVendor2", api_key="theApiKey2"),
            model_grader=ModelRecord(id=232, vendor="theVendor5", api_key="theApiKey5"),
            grader_is_reasoning=True,
        ),
    ]
    # all god
    helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
    experiment_store.return_value.get_experiment.side_effect = [experiment]
    experiment_store.return_value.get_cases.side_effect = [cases]
    experiment_store.return_value.get_models.side_effect = [models_experiments]
    result = [j for j in tested._generate_jobs(117)]
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
