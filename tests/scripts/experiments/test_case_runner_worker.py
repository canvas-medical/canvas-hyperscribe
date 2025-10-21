from multiprocessing import Queue
from pathlib import Path
from unittest.mock import patch, call, MagicMock

from evaluations.structures.case_runner_job import CaseRunnerJob
from evaluations.structures.experiment_job import ExperimentJob
from evaluations.structures.experiment_models import ExperimentModels
from evaluations.structures.note_grader_job import NoteGraderJob
from evaluations.structures.records.experiment_result import ExperimentResult as ExperimentResultRecord
from evaluations.structures.records.model import Model
from scripts.experiments.case_runner_worker import CaseRunnerWorker


def test___init__():
    case_runner_queue = Queue()
    note_grader_queue = Queue()
    tags = {"tag1": "value1", "tag2": "value2"}
    tested = CaseRunnerWorker(case_runner_queue, note_grader_queue, "theVersion", tags)
    assert tested._case_runner_queue is case_runner_queue
    assert tested._note_grader_queue is note_grader_queue
    assert tested._hyperscribe_version == "theVersion"
    assert tested._hyperscribe_tags == tags


@patch("scripts.experiments.case_runner_worker.environ")
def test__build_environment(environ):
    def reset_mocks():
        environ.reset_mock()

    job = ExperimentJob(
        job_index=11,
        experiment_id=731,
        experiment_name="theExperimentName",
        case_id=4561,
        case_name="theCaseName",
        models=ExperimentModels(
            experiment_id=731,
            model_generator=Model(vendor="theVendor1", api_key="theApiKey1", id=33),
            model_grader=Model(vendor="theVendor2", api_key="theApiKey2", id=37),
            grader_is_reasoning=True,
        ),
        cycle_time=7,
        cycle_transcript_overlap=147,
        grade_replications=1,
    )

    tested = CaseRunnerWorker
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
            "KeyTextLLM": "theApiKey1",
            "MaxWorkers": "1",
            "StaffersList": "",
            "StaffersPolicy": "y",
            "StructuredReasonForVisit": "n",
            "TrialStaffersList": "",
            "VendorAudioLLM": "",
            "VendorTextLLM": "theVendor1",
            "key1": "value1",
            "key2": "value2",
            "sendProgress": "",
        }
        assert result == expected

        calls = [call.copy()]
        assert environ.mock_calls == calls
        reset_mocks()


def test__build_command_case_runner():
    tested = CaseRunnerWorker
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


@patch("scripts.experiments.case_runner_worker.Path")
@patch("scripts.experiments.case_runner_worker.Popen")
@patch("scripts.experiments.case_runner_worker.RubricStore")
@patch("scripts.experiments.case_runner_worker.ExperimentResultStore")
@patch("scripts.experiments.case_runner_worker.HelperEvaluation")
@patch.object(CaseRunnerWorker, "_build_command_case_runner")
@patch.object(CaseRunnerWorker, "_build_environment")
def test__process_case_runner_job(
    build_environment,
    build_command_case_runner,
    helper,
    experiment_result_store,
    rubric_store,
    popen,
    path,
    capsys,
):
    job = ExperimentJob(
        job_index=1,
        experiment_id=731,
        experiment_name="theExperimentName",
        case_id=4561,
        case_name="theCaseName",
        models=ExperimentModels(
            experiment_id=731,
            model_generator=Model(vendor="theVendor1", api_key="theApiKey1", id=33),
            model_grader=Model(vendor="theVendor2", api_key="theApiKey2", id=37),
            grader_is_reasoning=True,
        ),
        cycle_time=7,
        cycle_transcript_overlap=147,
        grade_replications=1,
    )
    process = MagicMock(stdout=["\rline1\r\n", "\nline2\r\n", "\n\r\n"])
    note_grader_queue = MagicMock()

    def reset_mocks():
        build_environment.reset_mock()
        build_command_case_runner.reset_mock()
        helper.reset_mock()
        experiment_result_store.reset_mock()
        rubric_store.reset_mock()
        popen.reset_mock()
        path.reset_mock()
        process.reset_mock()
        note_grader_queue.reset_mock()

    tags = {"tag1": "value1", "tag2": "value2"}
    version = "theVersion"

    tests = [
        (
            0,
            590,
            ["[001] \rline1", "[001] \nline2", "[001] no note generated", ""],
            True,
            [],
        ),
        (
            790,
            0,
            ["[001] no rubric accepted", ""],
            False,
            [],
        ),
        (
            790,
            590,
            ["[001] \rline1", "[001] \nline2", ""],
            True,
            [
                call.put(
                    NoteGraderJob(
                        job_index=0,
                        parent_index=1,
                        rubric_id=590,
                        generated_note_id=790,
                        experiment_result_id=412,
                        model=Model(vendor="theVendor2", api_key="theApiKey2", id=37),
                        model_is_reasoning=True,
                    )
                )
            ],
        ),
    ]
    for generated_note_id, rubric_id, exp_out, exp_calls, exp_call_queue in tests:
        build_environment.side_effect = ["theEnvironment"]
        build_command_case_runner.side_effect = ["theCommand"]
        helper.postgres_credentials.side_effect = ["thePostgresCredentials"]
        experiment_result_store.return_value.insert.side_effect = [ExperimentResultRecord(id=412, experiment_id=371)]
        experiment_result_store.return_value.get_generated_note_id.side_effect = [generated_note_id]
        rubric_store.return_value.get_last_accepted.side_effect = [rubric_id]
        popen.side_effect = [process]
        path.return_value.parent.parent.parent = "thePath"

        tested = CaseRunnerWorker(Queue(), note_grader_queue, version, tags)
        tested._process_case_runner_job(job)

        assert note_grader_queue.mock_calls == exp_call_queue

        assert capsys.readouterr().out == "\n".join(exp_out)
        assert capsys.readouterr().err == ""

        calls = []
        if exp_calls:
            calls = [call(job)]
        assert build_environment.mock_calls == calls
        if exp_calls:
            calls = [call(CaseRunnerJob(case_name="theCaseName", experiment_result_id=412))]
        assert build_command_case_runner.mock_calls == calls
        calls = [call.postgres_credentials()]
        assert helper.mock_calls == calls
        calls = [call("thePostgresCredentials")]
        if exp_calls:
            calls.extend(
                [
                    call().insert(
                        ExperimentResultRecord(
                            experiment_id=731,
                            experiment_name="theExperimentName",
                            hyperscribe_version=version,
                            hyperscribe_tags=tags,
                            case_id=4561,
                            case_name="theCaseName",
                            text_llm_vendor="",
                            text_llm_name="",
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
                ]
            )
        assert experiment_result_store.mock_calls == calls
        calls = [
            call("thePostgresCredentials"),
            call().get_last_accepted(4561),
        ]
        assert rubric_store.mock_calls == calls
        calls = []
        if exp_calls:
            calls = [
                call(
                    "theCommand",
                    env="theEnvironment",
                    stdout=-1,
                    stderr=-2,
                    text=True,
                    bufsize=1,
                    cwd="thePath",
                )
            ]
        assert popen.mock_calls == calls
        if exp_calls:
            directory = Path(__file__).parent.parent.parent.as_posix().replace("/tests", "")
            calls = [call(f"{directory}/scripts/experiments/case_runner_worker.py")]
        assert path.mock_calls == calls
        if exp_calls:
            calls = [call.wait()]
        assert process.mock_calls == calls
        reset_mocks()


@patch.object(CaseRunnerWorker, "_process_case_runner_job")
def test_run(process_case_runner_job):
    note_grader_queue = MagicMock()

    def reset_mocks():
        process_case_runner_job.reset_mock()
        note_grader_queue.reset_mock()

    case_runner_queue = Queue()
    tested = CaseRunnerWorker(case_runner_queue, note_grader_queue, "theVersion", {"tag1": "value1", "tag2": "value2"})
    jobs = [
        ExperimentJob(
            job_index=1,
            experiment_id=117,
            experiment_name="theName",
            case_id=756,
            case_name="theCaseNameX",
            models=ExperimentModels(
                experiment_id=731,
                model_generator=Model(vendor="theVendor1", api_key="theApiKey1", id=33),
                model_grader=Model(vendor="theVendor2", api_key="theApiKey2", id=37),
                grader_is_reasoning=True,
            ),
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
            models=ExperimentModels(
                experiment_id=731,
                model_generator=Model(vendor="theVendor1", api_key="theApiKey1", id=33),
                model_grader=Model(vendor="theVendor2", api_key="theApiKey2", id=37),
                grader_is_reasoning=True,
            ),
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
            models=ExperimentModels(
                experiment_id=731,
                model_generator=Model(vendor="theVendor1", api_key="theApiKey1", id=33),
                model_grader=Model(vendor="theVendor2", api_key="theApiKey2", id=37),
                grader_is_reasoning=True,
            ),
            cycle_time=0,
            cycle_transcript_overlap=125,
            grade_replications=11,
        ),
    ]
    for job in jobs:
        case_runner_queue.put(job)
    case_runner_queue.put(None)
    tested.run()

    calls = [
        call(jobs[0]),
        call(jobs[1]),
        call(jobs[2]),
    ]
    assert process_case_runner_job.mock_calls == calls
    assert note_grader_queue.mock_calls == []
    reset_mocks()
