import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from canvas_sdk.v1.data import Note

from evaluations.constants import Constants
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.postgres_credentials import PostgresCredentials
from hyperscribe.libraries.helper import Helper
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.line import Line


def test_trace_error():
    def mistake(a_dict: dict, b_dict: dict, various: str):
        return a_dict["a"] == b_dict["x"] == various

    file_path = Path(__file__).as_posix()
    tested = HelperEvaluation
    try:
        mistake({"a": 1, "secret": "SecretA"}, {"b": 2}, "random var")
        assert False  # <-- ensure we go in the exception`
    except Exception as error:
        result = tested.trace_error(error)
        expected = {
            "error": "'x'",
            "files": [f"{file_path}.test_trace_error:28", f"{file_path}.mistake:20"],
            "variables": {"a_dict": "{'a': 1, 'secret': 'SecretA'}", "b_dict": "{'b': 2}", "various": "'random var'"},
        }
        assert result == expected


@patch("evaluations.helper_evaluation.AuditorFile")
@patch("evaluations.helper_evaluation.AuditorPostgres")
@patch.object(HelperEvaluation, "postgres_credentials")
@patch.object(HelperEvaluation, "aws_s3_credentials")
@patch.object(HelperEvaluation, "settings")
def test_get_auditor(settings, s3_credentials, psql_credentials, auditor_postgres, auditor_file):
    def reset_mocks():
        settings.reset_mock()
        s3_credentials.reset_mock()
        psql_credentials.reset_mock()
        auditor_postgres.reset_mock()
        auditor_file.reset_mock()

    tested = HelperEvaluation

    for is_ready in [True, False]:
        psql_credentials.return_value.is_ready.side_effect = [is_ready]
        settings.side_effect = ["theSettings"]
        s3_credentials.side_effect = ["theS3Credentials"]
        auditor_file.default_folder_base.side_effect = ["theDefaultFolder"]
        result = tested.get_auditor("theCase", 7)
        if is_ready:
            assert result is auditor_postgres.return_value
            calls = [call("theCase", 7, "theSettings", "theS3Credentials", psql_credentials.return_value)]
            assert auditor_postgres.mock_calls == calls
            assert auditor_file.mock_calls == []
        else:
            assert result is auditor_file.return_value
            assert auditor_postgres.mock_calls == []
            calls = [
                call.default_folder_base(),
                call("theCase", 7, "theSettings", "theS3Credentials", "theDefaultFolder"),
            ]
            assert auditor_file.mock_calls == calls

        calls = [call()]
        assert settings.mock_calls == calls
        calls = [call()]
        assert s3_credentials.mock_calls == calls
        calls = [call(), call().is_ready()]
        assert psql_credentials.mock_calls == calls
        reset_mocks()


@patch("evaluations.helper_evaluation.Settings")
def test_settings(settings):
    def reset_mocks():
        settings.reset_mock()

    with patch.dict("os.environ", {"variable1": "value1", "variable2": "value2"}, clear=True):
        tested = HelperEvaluation
        settings.from_dictionary.side_effect = ["theSettings"]

        result = tested.settings()
        expected = "theSettings"
        assert result == expected

        calls = [call.from_dictionary({"variable1": "value1", "variable2": "value2"})]
        assert settings.mock_calls == calls
        reset_mocks()


@patch("evaluations.helper_evaluation.Settings")
def test_settings_reasoning_allowed(settings):
    def reset_mocks():
        settings.reset_mock()

    with patch.dict("os.environ", {"variable1": "value1", "variable2": "value2"}, clear=True):
        tested = HelperEvaluation
        settings.from_dict_with_reasoning.side_effect = ["theSettings"]

        result = tested.settings_reasoning_allowed()
        expected = "theSettings"
        assert result == expected

        calls = [call.from_dict_with_reasoning({"variable1": "value1", "variable2": "value2"})]
        assert settings.mock_calls == calls
        reset_mocks()


def test_aws_s3_credentials(monkeypatch):
    monkeypatch.setenv("AwsKey", "theKey")
    monkeypatch.setenv("AwsSecret", "theSecret")
    monkeypatch.setenv("AwsRegion", "theRegion")
    monkeypatch.setenv("AwsBucketLogs", "theBucketLogs")

    tested = HelperEvaluation
    result = tested.aws_s3_credentials()
    expected = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucketLogs")
    assert result == expected


def test_aws_s3_credentials_tuning(monkeypatch):
    monkeypatch.setenv("AwsKey", "theKey")
    monkeypatch.setenv("AwsSecret", "theSecret")
    monkeypatch.setenv("AwsRegion", "theRegion")
    monkeypatch.setenv("AwsBucketTuning", "theBucketTuning")

    tested = HelperEvaluation
    result = tested.aws_s3_credentials_tuning()
    expected = AwsS3Credentials(aws_key="theKey", aws_secret="theSecret", region="theRegion", bucket="theBucketTuning")
    assert result == expected


def test_postgres_credentials(monkeypatch):
    monkeypatch.setenv("EVALUATIONS_DB_NAME", "theDatabase")
    monkeypatch.setenv("EVALUATIONS_DB_USERNAME", "theUser")
    monkeypatch.setenv("EVALUATIONS_DB_PASSWORD", "thePassword")
    monkeypatch.setenv("EVALUATIONS_DB_HOST", "theHost")
    monkeypatch.setenv("EVALUATIONS_DB_PORT", "1234")

    tested = HelperEvaluation
    result = tested.postgres_credentials()
    expected = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    assert result == expected


@patch.object(Note, "objects")
def test_get_note_uuid(note_db):
    mock_note = MagicMock()

    def reset_mocks():
        note_db.reset_mock()
        mock_note.reset_mock()

    note_db.filter.return_value.order_by.return_value.first.side_effect = [mock_note]
    mock_note.id = "noteUuid"

    tested = HelperEvaluation
    result = tested.get_note_uuid("patientUuid")
    expected = "noteUuid"
    assert result == expected

    calls = [call.filter(patient__id="patientUuid"), call.filter().order_by("-dbid"), call.filter().order_by().first()]
    assert note_db.mock_calls == calls
    assert mock_note.mock_calls == []
    reset_mocks()


@patch.object(Note, "objects")
def test_get_provider_uuid(note_db):
    mock_note = MagicMock()

    def reset_mocks():
        note_db.reset_mock()
        mock_note.reset_mock()

    note_db.filter.return_value.order_by.return_value.first.side_effect = [mock_note]
    mock_note.provider.id = "providerUuid"

    tested = HelperEvaluation
    result = tested.get_provider_uuid("patientUuid")
    expected = "providerUuid"
    assert result == expected

    calls = [call.filter(patient__id="patientUuid"), call.filter().order_by("-dbid"), call.filter().order_by().first()]
    assert note_db.mock_calls == calls
    assert mock_note.mock_calls == []
    reset_mocks()


def test_get_canvas_instance(monkeypatch):
    monkeypatch.setenv("CUSTOMER_IDENTIFIER", "theCanvasInstance")
    tested = HelperEvaluation
    result = tested.get_canvas_instance()
    expected = "theCanvasInstance"
    assert result == expected

    monkeypatch.delenv("CUSTOMER_IDENTIFIER")
    tested = HelperEvaluation
    result = tested.get_canvas_instance()
    expected = "EvaluationBuilderInstance"
    assert result == expected


def test_get_canvas_host(monkeypatch):
    monkeypatch.setenv("CUSTOMER_IDENTIFIER", "theCanvasInstance")
    tested = HelperEvaluation
    result = tested.get_canvas_host()
    expected = "https://theCanvasInstance.canvasmedical.com"
    assert result == expected

    monkeypatch.setenv("CUSTOMER_IDENTIFIER", "local")
    tested = HelperEvaluation
    result = tested.get_canvas_host()
    expected = "http://localhost:8000"
    assert result == expected

    monkeypatch.delenv("CUSTOMER_IDENTIFIER")
    tested = HelperEvaluation
    result = tested.get_canvas_host()
    expected = "https://EvaluationBuilderInstance.canvasmedical.com"
    assert result == expected


def test_json_schema_differences():
    tested = HelperEvaluation
    result = tested.json_schema_differences()
    expected = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "level": {"type": "string", "enum": ["minor", "moderate", "severe", "critical"]},
                "difference": {"type": "string", "description": "description of the difference between the JSONs"},
            },
            "required": ["level", "difference"],
        },
    }
    assert result == expected


@patch.object(HelperEvaluation, "nuanced_differences")
def test_json_nuanced_differences(nuanced_differences):
    def reset_mocks():
        nuanced_differences.reset_mock()

    accepted_levels = ["level1", "level2"]
    system_prompt = [
        "The user will provides two JSON objects.",
        "Your task is compare them and report the discrepancies as a JSON list in a Markdown block like:",
        "```json",
        '[{"level": "one of: minor,moderate,severe,critical", '
        '"difference": "description of the difference between the JSONs"}]',
        "```",
        "",
        "All text values should be evaluated together and on the level scale to effectively convey the impact of "
        "the changes in meaning from a medical point of view.",
        "Any key with the value '>?<' should be ignored.",
        "Unless otherwise specified, dates and numbers must be presented identically.",
    ]
    user_prompt = [
        "First JSON, called 'automated': ",
        "```json",
        "theResultJson",
        "```",
        "",
        "Second JSON, called 'reviewed': ",
        "```json",
        "theExpectedJson",
        "```",
        "",
        "Please, review both JSONs and report as instructed all differences.",
    ]

    nuanced_differences.side_effect = [(True, "some text")]
    tested = HelperEvaluation
    result = tested.json_nuanced_differences(
        "theCase",
        ["level1", "level2"],
        "theResultJson",
        "theExpectedJson",
    )
    expected = (True, "some text")
    assert result == expected

    calls = [call("theCase", accepted_levels, system_prompt, user_prompt)]
    assert nuanced_differences.mock_calls == calls
    reset_mocks()


@patch.object(HelperEvaluation, "nuanced_differences")
def test_text_nuanced_differences(nuanced_differences):
    def reset_mocks():
        nuanced_differences.reset_mock()

    accepted_levels = ["level1", "level2"]
    system_prompt = [
        "The user will provides two texts.",
        "Your task is compare them *solely* from a medical meaning point of view and report the discrepancies as a "
        "JSON list in a Markdown block like:",
        "```json",
        '[{"level": "one of: minor,moderate,severe,critical", '
        '"difference": "description of the difference between the texts"}]',
        "```",
    ]
    user_prompt = [
        "First text, called 'automated': ",
        "```text",
        "theResultText",
        "```",
        "",
        "Second text, called 'reviewed': ",
        "```text",
        "theExpectedText",
        "```",
        "",
        "Please, review both texts and report as instructed all differences from a meaning point of view.",
    ]

    nuanced_differences.side_effect = [(True, "some text")]
    tested = HelperEvaluation
    result = tested.text_nuanced_differences("theCase", ["level1", "level2"], "theResultText", "theExpectedText")
    expected = (True, "some text")
    assert result == expected

    calls = [call("theCase", accepted_levels, system_prompt, user_prompt)]
    assert nuanced_differences.mock_calls == calls
    reset_mocks()


@patch("evaluations.helper_evaluation.MemoryLog")
@patch.object(Helper, "chatter")
@patch.object(HelperEvaluation, "get_canvas_instance")
@patch.object(HelperEvaluation, "settings")
def test_nuanced_differences(settings, get_canvas_instance, chatter, memory_log):
    conversation = MagicMock()

    def reset_mocks():
        settings.reset_mock()
        get_canvas_instance.reset_mock()
        memory_log.reset_mock()
        chatter.reset_mock()
        conversation.reset_mock()

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "level": {"type": "string", "enum": ["minor", "moderate", "severe", "critical"]},
                "difference": {"type": "string", "description": "description of the difference between the JSONs"},
            },
            "required": ["level", "difference"],
        },
    }
    identification = IdentificationParameters(
        patient_uuid="_PatientUuid",
        note_uuid="_NoteUuid",
        provider_uuid="_ProviderUuid",
        canvas_instance="theCanvasInstance",
    )

    tested = HelperEvaluation

    system_prompt = ["systemLine1", "systemLine2"]
    user_prompt = ["userLine1", "userLine2"]
    content = [
        {"level": "level1", "difference": "theDifferenceA"},
        {"level": "level2", "difference": "theDifferenceB"},
        {"level": "level1", "difference": "theDifferenceC"},
        {"level": "level2", "difference": "theDifferenceD"},
        {"level": "level3", "difference": "theDifferenceE"},
        {"level": "level4", "difference": "theDifferenceF"},
    ]
    json_content = json.dumps([content], indent=1)

    # errors
    settings.side_effect = ["theSettings"]
    get_canvas_instance.side_effect = ["theCanvasInstance"]
    memory_log.side_effect = ["MemoryLogInstance"]
    chatter.side_effect = [conversation]
    conversation.chat.side_effect = [JsonExtract(has_error=True, error="theError", content=content)]
    result = tested.nuanced_differences("theCase", ["level1", "level2"], system_prompt, user_prompt)
    expected = (False, "encountered error: theError")
    assert result == expected

    calls = [call()]
    assert settings.mock_calls == calls
    assert get_canvas_instance.mock_calls == calls
    calls = [call(identification, "theCase")]
    assert memory_log.mock_calls == calls
    calls = [call("theSettings", "MemoryLogInstance")]
    assert chatter.mock_calls == calls
    calls = [call.set_system_prompt(system_prompt), call.set_user_prompt(user_prompt), call.chat([schema])]
    assert conversation.mock_calls == calls
    reset_mocks()

    # no error
    # -- differences within the accepted levels
    settings.side_effect = ["theSettings"]
    get_canvas_instance.side_effect = ["theCanvasInstance"]
    memory_log.side_effect = ["MemoryLogInstance"]
    chatter.side_effect = [conversation]
    conversation.chat.side_effect = [JsonExtract(has_error=False, error="theError", content=[content])]
    result = tested.nuanced_differences("theCase", ["level1", "level2", "level3", "level4"], system_prompt, user_prompt)
    expected = (True, json_content)
    assert result == expected

    calls = [call()]
    assert settings.mock_calls == calls
    assert get_canvas_instance.mock_calls == calls
    calls = [call(identification, "theCase")]
    assert memory_log.mock_calls == calls
    calls = [call("theSettings", "MemoryLogInstance")]
    assert chatter.mock_calls == calls
    calls = [call.set_system_prompt(system_prompt), call.set_user_prompt(user_prompt), call.chat([schema])]
    assert conversation.mock_calls == calls
    reset_mocks()
    # -- differences out of the accepted levels
    settings.side_effect = ["theSettings"]
    get_canvas_instance.side_effect = ["theCanvasInstance"]
    memory_log.side_effect = ["MemoryLogInstance"]
    chatter.side_effect = [conversation]
    conversation.chat.side_effect = [JsonExtract(has_error=False, error="theError", content=[content])]
    result = tested.nuanced_differences("theCase", ["level2", "level3"], system_prompt, user_prompt)
    expected = (False, json_content)
    assert result == expected

    calls = [call()]
    assert settings.mock_calls == calls
    assert get_canvas_instance.mock_calls == calls
    calls = [call(identification, "theCase")]
    assert memory_log.mock_calls == calls
    calls = [call("theSettings", "MemoryLogInstance")]
    assert chatter.mock_calls == calls
    calls = [call.set_system_prompt(system_prompt), call.set_user_prompt(user_prompt), call.chat([schema])]
    assert conversation.mock_calls == calls
    reset_mocks()


def test_split_lines_into_cycles():
    tested = HelperEvaluation

    # test cases: 1) empty
    result = tested.split_lines_into_cycles([])
    expected = {}
    assert result == expected

    # 2) short line
    lines = [Line(speaker="Doctor", text="Hello", start=0.0, end=1.3)]
    result = tested.split_lines_into_cycles(lines)
    expected = {f"{Constants.CASE_CYCLE_PREFIX}_001": lines}
    assert result == expected

    # 3) multiple lines within limit
    lines = [
        Line(speaker="Doctor", text="Good morning", start=0.0, end=1.3),
        Line(speaker="Patient", text="Hello doctor", start=1.3, end=2.5),
        Line(speaker="Doctor", text="How are you feeling today?", start=2.5, end=3.6),
    ]
    result = tested.split_lines_into_cycles(lines)
    expected = {f"{Constants.CASE_CYCLE_PREFIX}_001": lines}
    assert result == expected

    # 4) exceed cycle limit
    with patch.object(Constants, "MAX_CHARACTERS_PER_CYCLE", 600):
        with patch.object(Constants, "CASE_CYCLE_PREFIX", "test_cycle"):
            lines = [
                Line(speaker="Doctor", text="A" * 200, start=0.0, end=1.3),
                Line(speaker="Patient", text="B" * 200, start=1.3, end=2.5),
                Line(speaker="Doctor", text="C" * 200, start=2.5, end=3.6),
                Line(speaker="Patient", text="Short", start=3.6, end=4.7),
            ]
            result = tested.split_lines_into_cycles(lines)
            expected = {
                "test_cycle_001": [lines[0], lines[1]],
                "test_cycle_002": [lines[2], lines[3]],
            }
            assert result == expected

    # 5) boundary conditions
    with patch.object(Constants, "MAX_CHARACTERS_PER_CYCLE", 100):
        with patch.object(Constants, "CASE_CYCLE_PREFIX", "boundary_test"):
            line1 = Line(speaker="Doctor", text="X" * 50, start=0.0, end=1.3)
            line2 = Line(speaker="Patient", text="Y" * 50, start=1.3, end=2.5)
            lines = [line1, line2]

            result = tested.split_lines_into_cycles(lines)
            expected = {"boundary_test_001": [line1], "boundary_test_002": [line2]}
            assert result == expected

    # 6) one very long Line object
    with patch.object(Constants, "MAX_CHARACTERS_PER_CYCLE", 100):
        with patch.object(Constants, "CASE_CYCLE_PREFIX", "long_line_test"):
            long_line = Line(speaker="Doctor", text="Very long text " * 100, start=0.0, end=1.3)
            result = tested.split_lines_into_cycles([long_line])
            expected = {"long_line_test_001": [long_line]}
            assert result == expected


def test_list_case_files():
    path = MagicMock()
    files = [MagicMock(stem="file1"), MagicMock(stem="file2"), MagicMock(stem="file3")]

    def reset_mocks():
        path.reset_mock()
        for item in files:
            item.reset_mock()

    tested = HelperEvaluation

    # no file
    path.glob.side_effect = [[]]
    result = tested.list_case_files(path)
    assert result == []
    calls = [call.glob("*.json")]
    assert path.mock_calls == calls
    reset_mocks()

    # with files
    path.glob.side_effect = [files]
    files[0].open.side_effect = [StringIO(json.dumps({"cycle_002": {}, "cycle_001": {}}))]
    files[1].open.side_effect = [StringIO(json.dumps({"cycle_003": {}}))]
    files[2].open.side_effect = [StringIO(json.dumps({}))]

    result = tested.list_case_files(path)
    expected = [("file1", "cycle_002", files[0]), ("file1", "cycle_001", files[0]), ("file2", "cycle_003", files[1])]

    assert result == expected
    calls = [call.glob("*.json")]
    assert path.mock_calls == calls
    calls = [call.open("r")]
    for item in files:
        assert item.mock_calls == calls
    reset_mocks()
