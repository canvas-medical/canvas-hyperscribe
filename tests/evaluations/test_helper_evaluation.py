import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from canvas_sdk.v1.data import Note

from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.postgres_credentials import PostgresCredentials
from hyperscribe.libraries.helper import Helper
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def test_trace_error():
    def mistake(a_dict: dict, b_dict: dict, various: str):
        return a_dict['a'] == b_dict['x'] == various

    file_path = Path(__file__).as_posix()
    tested = HelperEvaluation
    try:
        mistake({'a': 1, 'secret': 'SecretA'}, {'b': 2}, 'random var')
        assert False  # <-- ensure we go in the exception`
    except Exception as error:
        result = tested.trace_error(error)
        expected = {
            'error': "'x'",
            'files': [
                f'{file_path}.test_trace_error:29',
                f'{file_path}.mistake:21',
            ],
            'variables': {'a_dict': "{'a': 1, 'secret': 'SecretA'}", 'b_dict': "{'b': 2}", 'various': "'random var'"},
        }
        assert result == expected

@patch('evaluations.helper_evaluation.AuditorFile')
@patch('evaluations.helper_evaluation.AuditorPostgres')
@patch.object(HelperEvaluation, 'postgres_credentials')
@patch.object(HelperEvaluation, 'aws_s3_credentials')
@patch.object(HelperEvaluation, 'settings')
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
                call('theCase', 7, 'theSettings', 'theS3Credentials', 'theDefaultFolder'),
            ]
            assert auditor_file.mock_calls == calls

        calls = [call()]
        assert settings.mock_calls == calls
        calls = [call()]
        assert s3_credentials.mock_calls == calls
        calls = [call(), call().is_ready()]
        assert psql_credentials.mock_calls == calls
        reset_mocks()

def test_settings(monkeypatch):
    monkeypatch.setenv("VendorTextLLM", "textVendor")
    monkeypatch.setenv("KeyTextLLM", "textAPIKey")
    monkeypatch.setenv("VendorAudioLLM", "audioVendor")
    monkeypatch.setenv("KeyAudioLLM", "audioAPIKey")
    monkeypatch.setenv("ScienceHost", "theScienceHost")
    monkeypatch.setenv("OntologiesHost", "theOntologiesHost")
    monkeypatch.setenv("PreSharedKey", "thePreSharedKey")
    monkeypatch.setenv("APISigningKey", "theApiSigningKey")
    monkeypatch.setenv("CommandsList", "Command1 Command2, Command3")
    monkeypatch.setenv("StaffersList", "41, 32 56")

    tests = [
        ("y", True),
        ("yes", True),
        ("1", True),
        ("n", False),
        ("", False),
    ]
    for env_variable, exp_bool in tests:
        monkeypatch.setenv("StructuredReasonForVisit", env_variable)
        monkeypatch.setenv("AuditLLMDecisions", env_variable)
        monkeypatch.setenv("IsTuning", env_variable)
        monkeypatch.setenv("CommandsPolicy", env_variable)
        monkeypatch.setenv("StaffersPolicy", env_variable)

        tested = HelperEvaluation
        result = tested.settings()
        expected = Settings(
            llm_text=VendorKey(vendor="textVendor", api_key="textAPIKey"),
            llm_audio=VendorKey(vendor="audioVendor", api_key="audioAPIKey"),
            science_host="theScienceHost",
            ontologies_host="theOntologiesHost",
            pre_shared_key="thePreSharedKey",
            structured_rfv=exp_bool,
            audit_llm=exp_bool,
            is_tuning=exp_bool,
            api_signing_key="theApiSigningKey",
            send_progress=False,
            commands_policy=AccessPolicy(policy=exp_bool, items=["Command1", "Command2", "Command3"]),
            staffers_policy=AccessPolicy(policy=exp_bool, items=["32", "41", "56"]),
        )
        assert result == expected


def test_aws_s3_credentials(monkeypatch):
    monkeypatch.setenv("AwsKey", "theKey")
    monkeypatch.setenv("AwsSecret", "theSecret")
    monkeypatch.setenv("AwsRegion", "theRegion")
    monkeypatch.setenv("AwsBucketLogs", "theBucketLogs")

    tested = HelperEvaluation
    result = tested.aws_s3_credentials()
    expected = AwsS3Credentials(
        aws_key="theKey",
        aws_secret="theSecret",
        region="theRegion",
        bucket="theBucketLogs",
    )
    assert result == expected


def test_aws_s3_credentials_tuning(monkeypatch):
    monkeypatch.setenv("AwsKey", "theKey")
    monkeypatch.setenv("AwsSecret", "theSecret")
    monkeypatch.setenv("AwsRegion", "theRegion")
    monkeypatch.setenv("AwsBucketTuning", "theBucketTuning")

    tested = HelperEvaluation
    result = tested.aws_s3_credentials_tuning()
    expected = AwsS3Credentials(
        aws_key="theKey",
        aws_secret="theSecret",
        region="theRegion",
        bucket="theBucketTuning",
    )
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

    calls = [
        call.filter(patient__id='patientUuid'),
        call.filter().order_by('-dbid'),
        call.filter().order_by().first()
    ]
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

    calls = [
        call.filter(patient__id='patientUuid'),
        call.filter().order_by('-dbid'),
        call.filter().order_by().first()
    ]
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
    expected = "https://theCanvasInstance"
    assert result == expected

    monkeypatch.setenv("CUSTOMER_IDENTIFIER", "local")
    tested = HelperEvaluation
    result = tested.get_canvas_host()
    expected = "http://localhost:8000"
    assert result == expected

    monkeypatch.delenv("CUSTOMER_IDENTIFIER")
    tested = HelperEvaluation
    result = tested.get_canvas_host()
    expected = "https://EvaluationBuilderInstance"
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
        }
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
        '[{"level": "one of: minor,moderate,severe,critical", "difference": "description of the difference between the JSONs"}]',
        "```",
        "",
        "All text values should be evaluated together and on the level scale to effectively convey the impact of the changes in meaning from a medical point of view.",
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
        "Your task is compare them *solely* from a medical meaning point of view and report the discrepancies as a JSON list in a Markdown block like:",
        "```json",
        '[{"level": "one of: minor,moderate,severe,critical", "difference": "description of the difference between the texts"}]',
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
    result = tested.text_nuanced_differences(
        "theCase",
        ["level1", "level2"],
        "theResultText",
        "theExpectedText",
    )
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
        }
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
    calls = [
        call.set_system_prompt(system_prompt),
        call.set_user_prompt(user_prompt),
        call.chat([schema]),
    ]
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
    calls = [
        call.set_system_prompt(system_prompt),
        call.set_user_prompt(user_prompt),
        call.chat([schema]),
    ]
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
    calls = [
        call.set_system_prompt(system_prompt),
        call.set_user_prompt(user_prompt),
        call.chat([schema]),
    ]
    assert conversation.mock_calls == calls
    reset_mocks()


def test_list_case_files():
    path = MagicMock()
    files = [
        MagicMock(stem="file1"),
        MagicMock(stem="file2"),
        MagicMock(stem="file3"),
    ]

    def reset_mocks():
        path.reset_mock()
        for item in files:
            item.reset_mock()

    tested = HelperEvaluation

    # no file
    path.glob.side_effect = [[]]
    result = tested.list_case_files(path)
    assert result == []
    calls = [call.glob('*.json')]
    assert path.mock_calls == calls
    reset_mocks()

    # with files
    path.glob.side_effect = [files]
    files[0].open.side_effect = [StringIO(json.dumps({"cycle_002": {}, "cycle_001": {}}))]
    files[1].open.side_effect = [StringIO(json.dumps({"cycle_003": {}}))]
    files[2].open.side_effect = [StringIO(json.dumps({}))]

    result = tested.list_case_files(path)
    expected = [
        ('file1', 'cycle_002', files[0]),
        ('file1', 'cycle_001', files[0]),
        ('file2', 'cycle_003', files[1]),
    ]

    assert result == expected
    calls = [call.glob('*.json')]
    assert path.mock_calls == calls
    calls = [call.open('r')]
    for item in files:
        assert item.mock_calls == calls
    reset_mocks()
