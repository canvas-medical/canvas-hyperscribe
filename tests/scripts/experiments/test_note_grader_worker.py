from multiprocessing import Queue
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from evaluations.structures.note_grader_job import NoteGraderJob
from evaluations.structures.records.model import Model
from scripts.experiments.note_grader_worker import NoteGraderWorker


def test___init__():
    note_grader_queue = Queue()
    tested = NoteGraderWorker(note_grader_queue)
    assert tested._note_grader_queue is note_grader_queue


def test__build_command_note_grader():
    tested = NoteGraderWorker
    job = NoteGraderJob(
        job_index=1,
        parent_index=3,
        rubric_id=597,
        generated_note_id=791,
        experiment_result_id=414,
        cwd_path=Path("/tmp/test_repo"),
        model=Model(vendor="theVendor", api_key="theApiKey", id=31),
        model_is_reasoning=False,
    )
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


@patch("scripts.experiments.note_grader_worker.environ")
def test__build_environment(environ):
    def reset_mocks():
        environ.reset_mock()

    tested = NoteGraderWorker
    tests = [
        (
            {
                "key1": "value1",
                "key2": "value2",
            },
            True,
            "reasoning",
        ),
        (
            {
                "key1": "value1",
                "key2": "value2",
                "VIRTUAL_ENV": "someValue",
                "VendorTextLLM": "someValue",
                "KeyTextLLM": "someValue",
                "TextModelType": "someValue",
            },
            False,
            "chat",
        ),
    ]
    for environ_side_effect, model_is_reasoning, exp_model_type in tests:
        environ.copy.side_effect = [environ_side_effect]

        job = NoteGraderJob(
            job_index=71,
            parent_index=3,
            rubric_id=597,
            generated_note_id=791,
            experiment_result_id=414,
            cwd_path=Path("/tmp/test_repo"),
            model=Model(vendor="theVendor", api_key="theApiKey", id=33),
            model_is_reasoning=model_is_reasoning,
        )
        result = tested._build_environment(job)
        expected = {
            "key1": "value1",
            "key2": "value2",
            "VendorTextLLM": "theVendor",
            "KeyTextLLM": "theApiKey",
            "TextModelType": exp_model_type,
        }
        assert result == expected

        calls = [call.copy()]
        assert environ.mock_calls == calls
        reset_mocks()


@patch("scripts.experiments.note_grader_worker.Popen")
@patch.object(NoteGraderWorker, "_build_environment")
@patch.object(NoteGraderWorker, "_build_command_note_grader")
def test__process_note_grader_job(build_command_note_grader, build_environment, popen, capsys):
    process = MagicMock(stdout=["\nline1\n", "\nline2\r\n", "\n\r\n"])

    def reset_mocks():
        build_command_note_grader.reset_mock()
        build_environment.reset_mock()
        popen.reset_mock()
        process.reset_mock()

    tested = NoteGraderWorker

    build_command_note_grader.side_effect = ["theCommand"]
    build_environment.side_effect = ["theEnvironment"]
    popen.side_effect = [process]

    job = NoteGraderJob(
        job_index=71,
        parent_index=3,
        rubric_id=597,
        generated_note_id=791,
        experiment_result_id=414,
        cwd_path=Path("/tmp/test_repo"),
        model=Model(vendor="theVendor", api_key="theApiKey", id=31),
        model_is_reasoning=False,
    )
    tested._process_note_grader_job(job)
    exp_out = "\n".join(
        [
            "[003.071] \nline1",
            "[003.071] \nline2",
            "",
        ]
    )
    assert capsys.readouterr().out == exp_out
    assert capsys.readouterr().err == ""

    calls = [call(job)]
    assert build_command_note_grader.mock_calls == calls
    calls = [call(job)]
    assert build_environment.mock_calls == calls
    calls = [
        call(
            "theCommand",
            env="theEnvironment",
            stdout=-1,
            stderr=-2,
            text=True,
            bufsize=1,
            cwd=Path("/tmp/test_repo"),
        )
    ]
    assert popen.mock_calls == calls

    calls = [call.wait()]
    assert process.mock_calls == calls

    reset_mocks()


@patch.object(NoteGraderWorker, "_process_note_grader_job")
def test_run(process_note_grader_job):
    def reset_mocks():
        process_note_grader_job.reset_mock()

    note_grader_queue = Queue()
    tested = NoteGraderWorker(note_grader_queue)
    jobs = [
        NoteGraderJob(
            job_index=71,
            parent_index=3,
            rubric_id=597,
            generated_note_id=791,
            experiment_result_id=414,
            cwd_path=Path("/tmp/test_repo"),
            model=Model(vendor="theVendor1", api_key="theApiKey1", id=31),
            model_is_reasoning=False,
        ),
        NoteGraderJob(
            job_index=77,
            parent_index=5,
            rubric_id=597,
            generated_note_id=793,
            experiment_result_id=415,
            cwd_path=Path("/tmp/test_repo"),
            model=Model(vendor="theVendor3", api_key="theApiKey3", id=33),
            model_is_reasoning=False,
        ),
        NoteGraderJob(
            job_index=71,
            parent_index=6,
            rubric_id=597,
            generated_note_id=797,
            experiment_result_id=417,
            cwd_path=Path("/tmp/test_repo"),
            model=Model(vendor="theVendor7", api_key="theApiKey7", id=37),
            model_is_reasoning=True,
        ),
    ]
    for job in jobs:
        note_grader_queue.put(job)
    note_grader_queue.put(None)
    tested.run()

    calls = [
        call(jobs[0]),
        call(jobs[1]),
        call(jobs[2]),
    ]
    assert process_note_grader_job.mock_calls == calls
    reset_mocks()
