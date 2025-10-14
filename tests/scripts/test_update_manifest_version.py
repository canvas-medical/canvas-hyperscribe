import json
from datetime import datetime, timezone
from subprocess import CalledProcessError
from unittest.mock import patch, call

import pytest

from scripts.update_manifest_version import (
<<<<<<< HEAD
    get_git_branch,
=======
    get_git_info,
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
    get_canvas_sdk_version,
    compare_versions,
    main,
    parse_semantic_version,
)
from tests.helper import MockClass, MockFile


<<<<<<< HEAD
@patch.dict("os.environ", {}, clear=True)
@patch("scripts.update_manifest_version.subprocess.run")
def test_get_git_branch(run, capsys):
=======
@patch("scripts.update_manifest_version.subprocess.run")
def test_get_git_info(run, capsys):
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
    def reset_mocks():
        run.reset_mock()

    calls = [
<<<<<<< HEAD
        call(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True),
    ]

    tested = get_git_branch

    # no error - local git command
    run.side_effect = [
        MockClass(stdout=" theBranchWithAVeryLongName \n"),
    ]
    result = tested()
    expected = "theBranchWithAVeryLo"
=======
        call(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True),
        call(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True),
    ]

    tested = get_git_info

    # no error
    run.side_effect = [
        MockClass(stdout=" theCommit \n"),
        MockClass(stdout=" theBranch \n"),
    ]
    result = tested()
    expected = ("theCommit", "theBranch")
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
    assert result == expected

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    assert run.mock_calls == calls
    reset_mocks()

    # with error
    with pytest.raises(SystemExit) as exc_info:
        run.side_effect = [
<<<<<<< HEAD
=======
            MockClass(stdout=" theCommit \n"),
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
            CalledProcessError(
                returncode=128,
                cmd=["theCommand", "theParam"],
                stderr="theError",
            ),
        ]
        result = tested()
        assert result is None

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    exp_out = (
<<<<<<< HEAD
        "❌ ERROR: Could not get git branch: Command '['theCommand', 'theParam']' returned non-zero exit status 128.\n"
=======
        "❌ ERROR: Could not get git information: "
        "Command '['theCommand', 'theParam']' returned non-zero exit status 128.\n"
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
    )
    assert captured.out == exp_out
    assert captured.err == ""

    assert run.mock_calls == calls
    reset_mocks()


<<<<<<< HEAD
@patch.dict("os.environ", {"GITHUB_HEAD_REF": "feature/my-awesome-feature-with-long-name"})
@patch("scripts.update_manifest_version.subprocess.run")
def test_get_git_branch_github_actions(run, capsys):
    """Test that GITHUB_HEAD_REF is used in CI/CD environment."""
    tested = get_git_branch

    # GitHub Actions environment - should not call git command
    result = tested()
    expected = "feature/my-awesome-f"  # Truncated to 20 chars
    assert result == expected

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    # Verify subprocess.run was NOT called
    assert run.mock_calls == []


=======
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
@patch("scripts.update_manifest_version.subprocess.run")
def test_get_canvas_sdk_version(run):
    def reset_mocks():
        run.reset_mock()

    calls = [
        call(["uv", "run", "canvas", "--version"], capture_output=True, text=True, check=True),
    ]

    tested = get_canvas_sdk_version

    # no error
    # -- valid version
    run.side_effect = [
        MockClass(stdout=" Version: 12.34.56 \n"),
    ]
    result = tested()
    expected = "12.34.56"
    assert result == expected

    assert run.mock_calls == calls
    reset_mocks()
    # -- invalid version
    run.side_effect = [
        MockClass(stdout=" Version: 1234.56 \n"),
    ]
    result = tested()
    assert result is None

    assert run.mock_calls == calls
    reset_mocks()

    # with error
    run.side_effect = [
        CalledProcessError(
            returncode=128,
            cmd=["theCommand", "theParam"],
            stderr="theError",
        ),
    ]
    result = tested()
    assert result is None

    assert run.mock_calls == calls
    reset_mocks()


def test_parse_semantic_version():
    tested = parse_semantic_version
    tests = [
        ("0.1.127", "0.1.127"),
<<<<<<< HEAD
        ("2024-10-13 v0.1.122 (next)", "0.1.122"),
        ("2024-10-13 v0.1.123", "0.1.123"),
        ("0.1.124 (next)", "0.1.124"),
=======
        ("2024-10-13 v0.1.122 (next abc1234)", "0.1.122"),
        ("2024-10-13 v0.1.123", "0.1.123"),
        ("0.1.124 (next abc1234)", "0.1.124"),
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
        ("v0.1.125", "0.1.125"),
        ("nope", None),
    ]
    for version, expected in tests:
        result = tested(version)
        if expected is None:
            assert result is None
        else:
            assert result == expected


def test_compare_versions():
    tested = compare_versions
    tests = [
        ("12.34.56", "12.34.56", 0),
        ("12.34.56", "12.34.57", -1),
        ("12.34.57", "12.34.56", 1),
        ("12.34.56", "22.34.56", -1),
        ("22.34.56", "12.34.56", 1),
        ("12.34.56", "11.34.57", 1),
        ("11.34.57", "12.34.56", -1),
    ]
    for v1, v2, expected in tests:
        result = tested(v1, v2)
        assert result == expected


@patch("scripts.update_manifest_version.datetime", wraps=datetime)
@patch("scripts.update_manifest_version.parse_semantic_version")
@patch("scripts.update_manifest_version.compare_versions")
@patch("scripts.update_manifest_version.get_canvas_sdk_version")
<<<<<<< HEAD
@patch("scripts.update_manifest_version.get_git_branch")
@patch("scripts.update_manifest_version.Path")
def test_main(
    path,
    function_get_git_branch,
=======
@patch("scripts.update_manifest_version.get_git_info")
@patch("scripts.update_manifest_version.Path")
def test_main(
    path,
    function_get_git_info,
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
    function_get_canvas_sdk_version,
    function_compare_versions,
    function_parse_semantic_version,
    mock_datetime,
    capsys,
):
    def reset_mocks():
        path.reset_mock()
<<<<<<< HEAD
        function_get_git_branch.reset_mock()
=======
        function_get_git_info.reset_mock()
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
        function_get_canvas_sdk_version.reset_mock()
        function_compare_versions.reset_mock()
        function_parse_semantic_version.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 10, 11, 7, 48, 21, tzinfo=timezone.utc)

    tested = main

    # all good
    tests = [
        (1, "📦 Updated sdk_version: 0.67.1 → theVersion", '  "sdk_version": "theVersion",'),
        (0, "✓ sdk_version is up-to-date: theVersion", '  "sdk_version": "0.67.1",'),
        (
            -1,
            "⚠️  WARNING: Detected Canvas SDK version (theVersion) is lower than manifest (0.67.1)\n"
            "   Not downgrading. Please update your Canvas SDK: uv sync",
            '  "sdk_version": "0.67.1",',
        ),
    ]
    for comparison, exp_out_line_0, exp_write_line_1 in tests:
        json_string = json.dumps(
            {
                "sdk_version": "0.67.1",
<<<<<<< HEAD
                "plugin_version": "2025-10-09 v0.1.76 (main)",
=======
                "plugin_version": "2025-10-09 v0.1.76 (main abc123)",
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
                "tags": {
                    "version_semantic": "0.1.76",
                },
            }
        )
        mock_read = MockFile(mode="r", content=json_string)
        mock_write = MockFile(mode="w")

        path.return_value.exists.side_effect = [True]
        path.return_value.open.side_effect = [mock_read, mock_write]
<<<<<<< HEAD
        function_get_git_branch.side_effect = ["theBranch"]
=======
        function_get_git_info.side_effect = [("theCommit", "theBranch")]
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
        function_get_canvas_sdk_version.side_effect = ["theVersion"]
        function_compare_versions.side_effect = [comparison]
        function_parse_semantic_version.side_effect = []
        mock_datetime.now.side_effect = [date_0]

        result = tested()
        expected = 0
        assert result == expected

        exp_out = "\n".join(
            [
                exp_out_line_0,
                "✅ Updated manifest:",
<<<<<<< HEAD
                "   plugin_version: 2025-10-11 v0.1.76 (theBranch)",
                "   tags.version_semantic: 0.1.76",
                "   tags.version_branch: theBranch",
                "   tags.version_date: 2025-10-11",
=======
                "   plugin_version: 2025-10-11 v0.1.76 (theBranch theComm)",
                "   tags.version_semantic: 0.1.76",
                "   tags.version_branch: theBranch",
                "   tags.version_date: 2025-10-11",
                "   tags.version_commit_hash: theComm",
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
                "",
            ]
        )
        assert capsys.readouterr().out == exp_out
        assert capsys.readouterr().err == ""

        exp_json = "\n".join(
            [
                "{",
                exp_write_line_1,
<<<<<<< HEAD
                '  "plugin_version": "2025-10-11 v0.1.76 (theBranch)",',
                '  "tags": {',
                '    "version_semantic": "0.1.76",',
                '    "version_date": "2025-10-11",',
=======
                '  "plugin_version": "2025-10-11 v0.1.76 (theBranch theComm)",',
                '  "tags": {',
                '    "version_semantic": "0.1.76",',
                '    "version_date": "2025-10-11",',
                '    "version_commit_hash": "theCommit",',
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
                '    "version_branch": "theBranch"',
                "  }",
                "}",
                "",
            ]
        )
        assert mock_write.content == exp_json

        calls = [
            call("hyperscribe/CANVAS_MANIFEST.json"),
            call().exists(),
            call().open("r"),
            call().open("w"),
        ]
        assert path.mock_calls == calls
        calls = [call()]
<<<<<<< HEAD
        assert function_get_git_branch.mock_calls == calls
=======
        assert function_get_git_info.mock_calls == calls
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
        assert function_get_canvas_sdk_version.mock_calls == calls
        calls = [call("theVersion", "0.67.1")]
        assert function_compare_versions.mock_calls == calls
        calls = []
        assert function_parse_semantic_version.mock_calls == calls
        calls = [call.now()]
        assert mock_datetime.mock_calls == calls
        reset_mocks()

    # manifest does not exist
    path.return_value.as_posix.side_effect = ["theFilePath"]
    path.return_value.exists.side_effect = [False]
<<<<<<< HEAD
    function_get_git_branch.side_effect = []
=======
    function_get_git_info.side_effect = []
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
    function_get_canvas_sdk_version.side_effect = []
    function_compare_versions.side_effect = []
    function_parse_semantic_version.side_effect = []
    mock_datetime.now.side_effect = []

    result = tested()
    expected = 1
    assert result == expected

    exp_out = "\n".join(
        [
            "❌ ERROR: theFilePath not found",
            "",
        ]
    )
    assert capsys.readouterr().out == exp_out
    assert capsys.readouterr().err == ""

    calls = [
        call("hyperscribe/CANVAS_MANIFEST.json"),
        call().exists(),
        call().as_posix(),
    ]
    assert path.mock_calls == calls
    calls = []
<<<<<<< HEAD
    assert function_get_git_branch.mock_calls == calls
=======
    assert function_get_git_info.mock_calls == calls
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
    assert function_get_canvas_sdk_version.mock_calls == calls
    assert function_compare_versions.mock_calls == calls
    assert function_parse_semantic_version.mock_calls == calls
    assert mock_datetime.mock_calls == calls
    reset_mocks()

    # in the manifest.json: no current SDK version + tags doesn't exist
    json_string = json.dumps(
        {
<<<<<<< HEAD
            "plugin_version": "2025-10-09 v0.1.76 (main)",
=======
            "plugin_version": "2025-10-09 v0.1.76 (main abc123)",
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
        }
    )
    mock_read = MockFile(mode="r", content=json_string)
    mock_write = MockFile(mode="w")

    path.return_value.exists.side_effect = [True]
    path.return_value.open.side_effect = [mock_read, mock_write]
<<<<<<< HEAD
    function_get_git_branch.side_effect = ["theBranch"]
=======
    function_get_git_info.side_effect = [("theCommit", "theBranch")]
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
    function_get_canvas_sdk_version.side_effect = ["theVersion"]
    function_compare_versions.side_effect = [1]
    function_parse_semantic_version.side_effect = ["theSemanticVersion"]
    mock_datetime.now.side_effect = [date_0]

    result = tested()
    expected = 0
    assert result == expected

    exp_out = "\n".join(
        [
            "📦 Set sdk_version: theVersion",
            "✅ Updated manifest:",
<<<<<<< HEAD
            "   plugin_version: 2025-10-11 vtheSemanticVersion (theBranch)",
            "   tags.version_semantic: theSemanticVersion",
            "   tags.version_branch: theBranch",
            "   tags.version_date: 2025-10-11",
=======
            "   plugin_version: 2025-10-11 vtheSemanticVersion (theBranch theComm)",
            "   tags.version_semantic: theSemanticVersion",
            "   tags.version_branch: theBranch",
            "   tags.version_date: 2025-10-11",
            "   tags.version_commit_hash: theComm",
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
            "",
        ]
    )
    assert capsys.readouterr().out == exp_out
    assert capsys.readouterr().err == ""

    exp_json = "\n".join(
        [
            "{",
<<<<<<< HEAD
            '  "plugin_version": "2025-10-11 vtheSemanticVersion (theBranch)",',
            '  "sdk_version": "theVersion",',
            '  "tags": {',
            '    "version_date": "2025-10-11",',
=======
            '  "plugin_version": "2025-10-11 vtheSemanticVersion (theBranch theComm)",',
            '  "sdk_version": "theVersion",',
            '  "tags": {',
            '    "version_date": "2025-10-11",',
            '    "version_commit_hash": "theCommit",',
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
            '    "version_branch": "theBranch",',
            '    "version_semantic": "theSemanticVersion"',
            "  }",
            "}",
            "",
        ]
    )
    assert mock_write.content == exp_json

    calls = [
        call("hyperscribe/CANVAS_MANIFEST.json"),
        call().exists(),
        call().open("r"),
        call().open("w"),
    ]
    assert path.mock_calls == calls
    calls = [call()]
<<<<<<< HEAD
    assert function_get_git_branch.mock_calls == calls
    assert function_get_canvas_sdk_version.mock_calls == calls
    calls = []
    assert function_compare_versions.mock_calls == calls
    calls = [call("2025-10-09 v0.1.76 (main)")]
=======
    assert function_get_git_info.mock_calls == calls
    assert function_get_canvas_sdk_version.mock_calls == calls
    calls = []
    assert function_compare_versions.mock_calls == calls
    calls = [call("2025-10-09 v0.1.76 (main abc123)")]
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
    assert function_parse_semantic_version.mock_calls == calls
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    reset_mocks()

    # no SDK version
    json_string = json.dumps(
        {
            "sdk_version": "0.67.1",
<<<<<<< HEAD
            "plugin_version": "2025-10-09 v0.1.76 (main)",
=======
            "plugin_version": "2025-10-09 v0.1.76 (main abc123)",
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
            "tags": {
                "version_semantic": "0.1.76",
            },
        }
    )
    mock_read = MockFile(mode="r", content=json_string)
    mock_write = MockFile(mode="w")

    path.return_value.exists.side_effect = [True]
    path.return_value.open.side_effect = [mock_read, mock_write]
<<<<<<< HEAD
    function_get_git_branch.side_effect = ["theBranch"]
=======
    function_get_git_info.side_effect = [("theCommit", "theBranch")]
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
    function_get_canvas_sdk_version.side_effect = [None]  # <--- here
    function_compare_versions.side_effect = []
    function_parse_semantic_version.side_effect = []
    mock_datetime.now.side_effect = [date_0]

    result = tested()
    expected = 0
    assert result == expected

    exp_out = "\n".join(
        [
            "⚠️  WARNING: Could not determine Canvas SDK version from 'uv run canvas --version'",
            "✅ Updated manifest:",
<<<<<<< HEAD
            "   plugin_version: 2025-10-11 v0.1.76 (theBranch)",
            "   tags.version_semantic: 0.1.76",
            "   tags.version_branch: theBranch",
            "   tags.version_date: 2025-10-11",
=======
            "   plugin_version: 2025-10-11 v0.1.76 (theBranch theComm)",
            "   tags.version_semantic: 0.1.76",
            "   tags.version_branch: theBranch",
            "   tags.version_date: 2025-10-11",
            "   tags.version_commit_hash: theComm",
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
            "",
        ]
    )
    assert capsys.readouterr().out == exp_out
    assert capsys.readouterr().err == ""

    exp_json = "\n".join(
        [
            "{",
            '  "sdk_version": "0.67.1",',
<<<<<<< HEAD
            '  "plugin_version": "2025-10-11 v0.1.76 (theBranch)",',
            '  "tags": {',
            '    "version_semantic": "0.1.76",',
            '    "version_date": "2025-10-11",',
=======
            '  "plugin_version": "2025-10-11 v0.1.76 (theBranch theComm)",',
            '  "tags": {',
            '    "version_semantic": "0.1.76",',
            '    "version_date": "2025-10-11",',
            '    "version_commit_hash": "theCommit",',
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
            '    "version_branch": "theBranch"',
            "  }",
            "}",
            "",
        ]
    )
    assert mock_write.content == exp_json

    calls = [
        call("hyperscribe/CANVAS_MANIFEST.json"),
        call().exists(),
        call().open("r"),
        call().open("w"),
    ]
    assert path.mock_calls == calls
    calls = [call()]
<<<<<<< HEAD
    assert function_get_git_branch.mock_calls == calls
=======
    assert function_get_git_info.mock_calls == calls
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
    assert function_get_canvas_sdk_version.mock_calls == calls
    calls = []
    assert function_compare_versions.mock_calls == calls
    assert function_parse_semantic_version.mock_calls == calls
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    reset_mocks()

    # no tags.version_semantic with parse_semantic_version incorrect
    json_string = json.dumps(
        {
            "sdk_version": "0.67.1",
<<<<<<< HEAD
            "plugin_version": "2025-10-09 v0.1.76 (main)",
=======
            "plugin_version": "2025-10-09 v0.1.76 (main abc123)",
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
            "tags": {},
        }
    )
    mock_read = MockFile(mode="r", content=json_string)
    mock_write = MockFile(mode="w")

    path.return_value.exists.side_effect = [True]
    path.return_value.open.side_effect = [mock_read, mock_write]
<<<<<<< HEAD
    function_get_git_branch.side_effect = ["theBranch"]
=======
    function_get_git_info.side_effect = [("theCommit", "theBranch")]
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
    function_get_canvas_sdk_version.side_effect = ["theVersion"]
    function_compare_versions.side_effect = [1]
    function_parse_semantic_version.side_effect = [None]
    mock_datetime.now.side_effect = [date_0]

    result = tested()
    expected = 1
    assert result == expected

    exp_out = "\n".join(
        [
            "📦 Updated sdk_version: 0.67.1 → theVersion",
            "❌ ERROR: Could not determine semantic version",
<<<<<<< HEAD
            "   Current plugin_version: '2025-10-09 v0.1.76 (main)'",
=======
            "   Current plugin_version: '2025-10-09 v0.1.76 (main abc123)'",
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
            "   Please set tags.version_semantic manually (e.g., '0.1.128')",
            "",
        ]
    )
    assert capsys.readouterr().out == exp_out
    assert capsys.readouterr().err == ""

    exp_json = "\n".join([])
    assert mock_write.content == exp_json

    calls = [
        call("hyperscribe/CANVAS_MANIFEST.json"),
        call().exists(),
        call().open("r"),
    ]
    assert path.mock_calls == calls
    calls = [call()]
<<<<<<< HEAD
    assert function_get_git_branch.mock_calls == calls
    assert function_get_canvas_sdk_version.mock_calls == calls
    calls = [call("theVersion", "0.67.1")]
    assert function_compare_versions.mock_calls == calls
    calls = [call("2025-10-09 v0.1.76 (main)")]
=======
    assert function_get_git_info.mock_calls == calls
    assert function_get_canvas_sdk_version.mock_calls == calls
    calls = [call("theVersion", "0.67.1")]
    assert function_compare_versions.mock_calls == calls
    calls = [call("2025-10-09 v0.1.76 (main abc123)")]
>>>>>>> b8ef7fa (add tests to scripts/update_manifest_version.py)
    assert function_parse_semantic_version.mock_calls == calls
    calls = []
    assert mock_datetime.mock_calls == calls
    reset_mocks()
