# file mainly created by Anthropic/CodeClaude
from argparse import Namespace
from unittest.mock import patch, call, MagicMock
import sys

from scripts.parallel_case_runner import ParallelCaseRunner
from evaluations.datastores.postgres.case import Case
from evaluations.helper_evaluation import HelperEvaluation


def test_init():
    tested = ParallelCaseRunner(cases_number=5, cycles=3, workers=2)

    assert tested.cases_number == 5
    assert tested.cycles == 3
    assert tested.max_workers == 2
    assert tested.results == {}
    assert tested.timings == {}
    assert tested.output_lock is not None
    assert tested.output_queue is not None


@patch("scripts.parallel_case_runner.subprocess.Popen")
@patch("scripts.parallel_case_runner.time.time")
def test_run_single_case(time_mock, popen_mock):
    process_mock = MagicMock()

    def reset_mocks():
        time_mock.reset_mock()
        popen_mock.reset_mock()
        process_mock.reset_mock()
        # Reset stdout to MagicMock for next test
        process_mock.stdout = MagicMock()

    tested = ParallelCaseRunner(cases_number=1, cycles=0, workers=1)

    # Test successful case without cycles
    process_mock.stdout.readline.side_effect = ["output line 1\n", "output line 2\n", ""]
    process_mock.wait.side_effect = [None]
    process_mock.returncode = 0
    popen_mock.side_effect = [process_mock]
    time_mock.side_effect = [1000.0, 1005.5]  # start_time, end_time

    result = tested.run_single_case("test_case")
    expected = ("test_case", True, "output line 1\noutput line 2", 5.5)
    assert result == expected

    calls = [
        call(
            [sys.executable, "case_runner.py", "--case", "test_case"],
            stdout=-1,
            stderr=-2,
            text=True,
            bufsize=1,
            universal_newlines=True,
        ),
    ]
    assert popen_mock.mock_calls == calls
    calls = [call(), call()]
    assert time_mock.mock_calls == calls
    calls = [call(), call(), call()]
    assert process_mock.stdout.readline.mock_calls == calls
    calls = [call()]
    assert process_mock.wait.mock_calls == calls
    reset_mocks()

    # Test successful case with cycles
    tested = ParallelCaseRunner(cases_number=1, cycles=3, workers=1)
    process_mock.stdout.readline.side_effect = ["cycle output\n", ""]
    process_mock.wait.side_effect = [None]
    process_mock.returncode = 0
    popen_mock.side_effect = [process_mock]
    time_mock.side_effect = [2000.0, 2002.3]

    result = tested.run_single_case("test_case_cycles")
    expected = ("test_case_cycles", True, "cycle output", 2.3)
    assert result == expected

    calls = [
        call(
            [sys.executable, "case_runner.py", "--case", "test_case_cycles", "--cycles", "3"],
            stdout=-1,
            stderr=-2,
            text=True,
            bufsize=1,
            universal_newlines=True,
        ),
    ]
    assert popen_mock.mock_calls == calls
    calls = [call(), call()]
    assert time_mock.mock_calls == calls
    calls = [call(), call()]
    assert process_mock.stdout.readline.mock_calls == calls
    calls = [call()]
    assert process_mock.wait.mock_calls == calls
    reset_mocks()

    # Test failed case
    tested = ParallelCaseRunner(cases_number=1, cycles=0, workers=1)
    process_mock.stdout.readline.side_effect = ["error output\n", ""]
    process_mock.wait.side_effect = [None]
    process_mock.returncode = 1
    popen_mock.side_effect = [process_mock]
    time_mock.side_effect = [3000.0, 3001.0]

    result = tested.run_single_case("failed_case")
    expected = ("failed_case", False, "error output", 1.0)
    assert result == expected

    calls = [
        call(
            [sys.executable, "case_runner.py", "--case", "failed_case"],
            stdout=-1,
            stderr=-2,
            text=True,
            bufsize=1,
            universal_newlines=True,
        ),
    ]
    assert popen_mock.mock_calls == calls
    calls = [call(), call()]
    assert time_mock.mock_calls == calls
    calls = [call(), call()]
    assert process_mock.stdout.readline.mock_calls == calls
    calls = [call()]
    assert process_mock.wait.mock_calls == calls
    reset_mocks()

    # Test exception case
    tested = ParallelCaseRunner(cases_number=1, cycles=0, workers=1)
    popen_mock.side_effect = [RuntimeError("Process error")]
    time_mock.side_effect = [4000.0, 4001.5]

    result = tested.run_single_case("exception_case")
    expected = ("exception_case", False, "Exception running case exception_case: Process error", 1.5)
    assert result == expected

    calls = [
        call(
            [sys.executable, "case_runner.py", "--case", "exception_case"],
            stdout=-1,
            stderr=-2,
            text=True,
            bufsize=1,
            universal_newlines=True,
        ),
    ]
    assert popen_mock.mock_calls == calls
    calls = [call(), call()]
    assert time_mock.mock_calls == calls
    reset_mocks()

    # Test case with None stdout
    tested = ParallelCaseRunner(cases_number=1, cycles=0, workers=1)
    process_mock.stdout = None
    process_mock.wait.side_effect = [None]
    process_mock.returncode = 0
    popen_mock.side_effect = [process_mock]
    time_mock.side_effect = [5000.0, 5001.0]

    result = tested.run_single_case("none_stdout_case")
    expected = ("none_stdout_case", True, "", 1.0)
    assert result == expected

    calls = [
        call(
            [sys.executable, "case_runner.py", "--case", "none_stdout_case"],
            stdout=-1,
            stderr=-2,
            text=True,
            bufsize=1,
            universal_newlines=True,
        ),
    ]
    assert popen_mock.mock_calls == calls
    calls = [call()]
    assert process_mock.wait.mock_calls == calls
    reset_mocks()

    # Test case with empty lines in output
    tested = ParallelCaseRunner(cases_number=1, cycles=0, workers=1)
    # Ensure stdout is properly set up after previous test
    process_mock.stdout = MagicMock()
    process_mock.stdout.readline.side_effect = ["line1\n", "\n", "", "line2\n", ""]
    process_mock.wait.side_effect = [None]
    process_mock.returncode = 0
    popen_mock.side_effect = [process_mock]
    time_mock.side_effect = [6000.0, 6002.0]

    result = tested.run_single_case("empty_lines_case")
    # The iterator stops at the first "" (empty string), so "line2\n" never gets processed
    # Only "line1\n" gets processed: rstrip() → "line1" → added to output_lines
    # "\n" gets processed: rstrip() → "" → filtered out by "if line:"
    expected = ("empty_lines_case", True, "line1", 2.0)
    assert result == expected

    calls = [
        call(
            [sys.executable, "case_runner.py", "--case", "empty_lines_case"],
            stdout=-1,
            stderr=-2,
            text=True,
            bufsize=1,
            universal_newlines=True,
        ),
    ]
    assert popen_mock.mock_calls == calls
    calls = [call(), call()]
    assert time_mock.mock_calls == calls
    calls = [call(), call(), call()]  # "line1\n", "\n", ""
    assert process_mock.stdout.readline.mock_calls == calls
    calls = [call()]
    assert process_mock.wait.mock_calls == calls
    reset_mocks()


@patch.object(ParallelCaseRunner, "run_single_case")
@patch("scripts.parallel_case_runner.ThreadPoolExecutor")
def test_run_cases(thread_pool_mock, run_single_case_mock, capsys):
    executor_mock = MagicMock()
    future1_mock = MagicMock()
    future2_mock = MagicMock()
    future_mock = MagicMock()

    def reset_mocks():
        thread_pool_mock.reset_mock()
        run_single_case_mock.reset_mock()
        executor_mock.reset_mock()
        future1_mock.reset_mock()
        future2_mock.reset_mock()
        future_mock.reset_mock()

    tested = ParallelCaseRunner(cases_number=2, cycles=0, workers=2)

    # Test successful execution
    future1_mock.result.side_effect = [("case1", True, "output1", 1.0)]
    future2_mock.result.side_effect = [("case2", False, "output2", 2.0)]

    executor_mock.submit.side_effect = [future1_mock, future2_mock]
    executor_mock.__enter__.side_effect = [executor_mock]
    executor_mock.__exit__.side_effect = [None]

    thread_pool_mock.side_effect = [executor_mock]

    # Mock as_completed to return futures in order
    with patch("scripts.parallel_case_runner.as_completed") as as_completed_mock:
        as_completed_mock.side_effect = [[future1_mock, future2_mock]]

        result = tested.run_cases(["case1", "case2"])
        expected = {"case1": True, "case2": False}
        assert result == expected
        assert tested.results == {"case1": True, "case2": False}
        assert tested.timings == {"case1": 1.0, "case2": 2.0}

    calls = [call(max_workers=2)]
    assert thread_pool_mock.mock_calls == calls
    calls = [call(tested.run_single_case, "case1"), call(tested.run_single_case, "case2")]
    assert executor_mock.submit.mock_calls == calls
    calls = [call()]
    assert future1_mock.result.mock_calls == calls
    assert future2_mock.result.mock_calls == calls
    reset_mocks()

    # Test exception during execution
    tested = ParallelCaseRunner(cases_number=1, cycles=0, workers=1)

    future_mock.result.side_effect = [RuntimeError("Future error")]
    executor_mock.submit.side_effect = [future_mock]
    executor_mock.__enter__.side_effect = [executor_mock]
    executor_mock.__exit__.side_effect = [None]

    thread_pool_mock.side_effect = [executor_mock]

    with patch("scripts.parallel_case_runner.as_completed") as as_completed_mock:
        as_completed_mock.side_effect = [[future_mock]]

        result = tested.run_cases(["exception_case"])
        expected = {"exception_case": False}
        assert result == expected
        assert tested.timings == {"exception_case": 0.0}

    calls = [call(max_workers=1)]
    assert thread_pool_mock.mock_calls == calls
    calls = [call(tested.run_single_case, "exception_case")]
    assert executor_mock.submit.mock_calls == calls
    calls = [call()]
    assert future_mock.result.mock_calls == calls
    reset_mocks()

    # Test failed case with output containing empty lines (for line 102->101 coverage)
    tested = ParallelCaseRunner(cases_number=1, cycles=0, workers=1)

    future_mock.result.side_effect = [("failed_case", False, "Error line 1\n  \n\nError line 2\n  \n", 2.5)]
    executor_mock.submit.side_effect = [future_mock]
    executor_mock.__enter__.side_effect = [executor_mock]
    executor_mock.__exit__.side_effect = [None]

    thread_pool_mock.side_effect = [executor_mock]

    with patch("scripts.parallel_case_runner.as_completed") as as_completed_mock:
        as_completed_mock.side_effect = [[future_mock]]

        result = tested.run_cases(["failed_case"])
        expected = {"failed_case": False}
        assert result == expected
        assert tested.timings == {"failed_case": 2.5}

    calls = [call(max_workers=1)]
    assert thread_pool_mock.mock_calls == calls
    calls = [call(tested.run_single_case, "failed_case")]
    assert executor_mock.submit.mock_calls == calls
    calls = [call()]
    assert future_mock.result.mock_calls == calls
    reset_mocks()


def test_display_summary(capsys):
    tested = ParallelCaseRunner(cases_number=3, cycles=0, workers=1)

    # Test with mixed success/failure cases
    tested.results = {"case1": True, "case2": False, "case3": True}
    tested.timings = {"case1": 1.5, "case2": 2.3, "case3": 0.8}

    tested.display_summary()

    result = capsys.readouterr().out
    expected_lines = [
        "",
        "=" * 80,
        "EXECUTION SUMMARY",
        "=" * 80,
        "✅ case1 (1.5s)",
        "❌ case2 (2.3s)",
        "✅ case3 (0.8s)",
        "",
        "-" * 80,
        "Total cases: 3",
        "Successful: 2",
        "Failed: 1",
        "Total execution time: 4.6s",
        "Average time per case: 1.5s",
        "",
        "Failed cases: case2",
        "Success rate: 66.7%",
        "",
    ]
    expected = "\n".join(expected_lines)
    assert result == expected

    # Test with empty results (no cases)
    tested = ParallelCaseRunner(cases_number=0, cycles=0, workers=1)
    tested.results = {}
    tested.timings = {}

    tested.display_summary()

    result = capsys.readouterr().out
    expected_lines = [
        "",
        "=" * 80,
        "EXECUTION SUMMARY",
        "=" * 80,
        "",
        "-" * 80,
        "Total cases: 0",
        "Successful: 0",
        "Failed: 0",
        "Total execution time: 0.0s",
        "Success rate: 0.0%",
        "",
    ]
    expected = "\n".join(expected_lines)
    assert result == expected

    # Test with all successful cases (no failed cases section)
    tested = ParallelCaseRunner(cases_number=2, cycles=0, workers=1)
    tested.results = {"case1": True, "case2": True}
    tested.timings = {"case1": 1.0, "case2": 2.0}

    tested.display_summary()

    result = capsys.readouterr().out
    expected_lines = [
        "",
        "=" * 80,
        "EXECUTION SUMMARY",
        "=" * 80,
        "✅ case1 (1.0s)",
        "✅ case2 (2.0s)",
        "",
        "-" * 80,
        "Total cases: 2",
        "Successful: 2",
        "Failed: 0",
        "Total execution time: 3.0s",
        "Average time per case: 1.5s",
        "Success rate: 100.0%",
        "",
    ]
    expected = "\n".join(expected_lines)
    assert result == expected


@patch("scripts.parallel_case_runner.ArgumentParser")
def test_parse_arguments(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    tested = ParallelCaseRunner
    argument_parser.return_value.parse_args.side_effect = ["parse_args_called"]

    result = tested.parse_arguments()
    expected = "parse_args_called"
    assert result == expected

    calls = [
        call(description="Run case_runner.py on multiple cases in parallel"),
        call().add_argument("cases_number", type=int, help="Number of first N cases to run (sorted by database id)"),
        call().add_argument(
            "cycles",
            type=int,
            help="Split the transcript in as many cycles (passed to case_runner.py)",
        ),
        call().add_argument("workers", type=int, help="Maximum number of parallel workers"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("scripts.parallel_case_runner.Path")
def test_validate_environment(path_mock):
    path_instance_mock = MagicMock()

    def reset_mocks():
        path_mock.reset_mock()
        path_instance_mock.reset_mock()

    tested = ParallelCaseRunner
    path_mock.side_effect = [path_instance_mock]

    # Test when case_runner.py exists
    path_instance_mock.exists.side_effect = [True]

    tested.validate_environment()  # Should not raise or exit

    calls = [call("case_runner.py")]
    assert path_mock.mock_calls == calls
    calls = [call()]
    assert path_instance_mock.exists.mock_calls == calls
    reset_mocks()

    # Test when case_runner.py does not exist
    path_instance_mock.exists.side_effect = [False]
    path_mock.side_effect = [path_instance_mock]

    try:
        with patch("scripts.parallel_case_runner.sys.exit") as exit_mock:
            exit_mock.side_effect = [SystemExit(1)]
            tested.validate_environment()
    except SystemExit:
        pass

    calls = [call("case_runner.py")]
    assert path_mock.mock_calls == calls
    calls = [call()]
    assert path_instance_mock.exists.mock_calls == calls
    calls = [call(1)]
    assert exit_mock.mock_calls == calls
    reset_mocks()


@patch.object(Case, "__init__")
@patch.object(Case, "get_first_n_cases")
@patch.object(HelperEvaluation, "postgres_credentials")
def test_get_cases_from_database(postgres_credentials_mock, get_first_n_cases_mock, case_init_mock):
    def reset_mocks():
        postgres_credentials_mock.reset_mock()
        get_first_n_cases_mock.reset_mock()
        case_init_mock.reset_mock()

    tested = ParallelCaseRunner(cases_number=3, cycles=0, workers=1)

    # Test successful retrieval
    postgres_credentials_mock.side_effect = [{"host": "localhost", "port": 5432}]
    case_init_mock.side_effect = [None]
    get_first_n_cases_mock.side_effect = [["case1", "case2", "case3"]]

    result = tested.get_cases_from_database()
    expected = ["case1", "case2", "case3"]
    assert result == expected

    calls = [call()]
    assert postgres_credentials_mock.mock_calls == calls
    calls = [call({"host": "localhost", "port": 5432})]
    assert case_init_mock.mock_calls == calls
    calls = [call(3)]
    assert get_first_n_cases_mock.mock_calls == calls
    reset_mocks()

    # Test no cases found
    postgres_credentials_mock.side_effect = [{"host": "localhost", "port": 5432}]
    case_init_mock.side_effect = [None]
    get_first_n_cases_mock.side_effect = [[]]

    try:
        with patch("scripts.parallel_case_runner.sys.exit") as exit_mock:
            exit_mock.side_effect = [SystemExit(1)]
            tested.get_cases_from_database()
    except SystemExit:
        pass

    calls = [call(1)]
    assert exit_mock.mock_calls == calls
    reset_mocks()

    # Test database exception
    postgres_credentials_mock.side_effect = [RuntimeError("DB connection failed")]

    try:
        with patch("scripts.parallel_case_runner.sys.exit") as exit_mock:
            exit_mock.side_effect = [SystemExit(1)]
            tested.get_cases_from_database()
    except SystemExit:
        pass

    calls = [call(1)]
    assert exit_mock.mock_calls == calls
    reset_mocks()


@patch.object(ParallelCaseRunner, "parse_arguments")
@patch.object(ParallelCaseRunner, "validate_environment")
@patch.object(ParallelCaseRunner, "get_cases_from_database")
@patch.object(ParallelCaseRunner, "run_cases")
@patch.object(ParallelCaseRunner, "display_summary")
def test_run(
    display_summary_mock,
    run_cases_mock,
    get_cases_from_database_mock,
    validate_environment_mock,
    parse_arguments_mock,
    capsys,
):
    def reset_mocks():
        display_summary_mock.reset_mock()
        run_cases_mock.reset_mock()
        get_cases_from_database_mock.reset_mock()
        validate_environment_mock.reset_mock()
        parse_arguments_mock.reset_mock()

    tested = ParallelCaseRunner(cases_number=0, cycles=0, workers=5)

    # Test successful run with all passing cases
    parse_arguments_mock.side_effect = [Namespace(cases_number=2, cycles=3, workers=4)]
    validate_environment_mock.side_effect = [None]
    get_cases_from_database_mock.side_effect = [["case1", "case2"]]
    run_cases_mock.side_effect = [{"case1": True, "case2": True}]
    display_summary_mock.side_effect = [None]

    tested.run()

    assert tested.cases_number == 2
    assert tested.cycles == 3
    assert tested.max_workers == 4

    calls = [call()]
    assert parse_arguments_mock.mock_calls == calls
    assert validate_environment_mock.mock_calls == calls
    assert get_cases_from_database_mock.mock_calls == calls
    calls = [call(["case1", "case2"])]
    assert run_cases_mock.mock_calls == calls
    calls = [call()]
    assert display_summary_mock.mock_calls == calls
    reset_mocks()

    # Test run with some failed cases
    parse_arguments_mock.side_effect = [Namespace(cases_number=2, cycles=0, workers=1)]
    validate_environment_mock.side_effect = [None]
    get_cases_from_database_mock.side_effect = [["case1", "case2"]]
    run_cases_mock.side_effect = [{"case1": True, "case2": False}]
    display_summary_mock.side_effect = [None]
    tested.results = {"case1": True, "case2": False}

    try:
        with patch("scripts.parallel_case_runner.sys.exit") as exit_mock:
            exit_mock.side_effect = [SystemExit(1)]
            tested.run()
    except SystemExit:
        pass

    calls = [call(1)]
    assert exit_mock.mock_calls == calls
    reset_mocks()

    # Test keyboard interrupt
    parse_arguments_mock.side_effect = [Namespace(cases_number=1, cycles=0, workers=1)]
    validate_environment_mock.side_effect = [None]
    get_cases_from_database_mock.side_effect = [["case1"]]
    run_cases_mock.side_effect = [KeyboardInterrupt()]

    try:
        with patch("scripts.parallel_case_runner.sys.exit") as exit_mock:
            exit_mock.side_effect = [SystemExit(1)]
            tested.run()
    except SystemExit:
        pass

    calls = [call(1)]
    assert exit_mock.mock_calls == calls
    reset_mocks()
