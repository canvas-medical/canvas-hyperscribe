import json
from unittest.mock import patch, MagicMock, call

from canvas_sdk.v1.data import Note

from commander.protocols.helper import Helper
from commander.protocols.structures.json_extract import JsonExtract
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey
from integrations.helper_settings import HelperSettings
from tests.helper import is_constant


def test_helper_settings():
    tested = HelperSettings
    constants = {
        "DIFFERENCE_LEVELS": ["minor", "moderate", "severe", "critical"],
    }
    assert is_constant(tested, constants)


def test_settings(monkeypatch):
    monkeypatch.setenv("VendorTextLLM", "textVendor")
    monkeypatch.setenv("KeyTextLLM", "textAPIKey")
    monkeypatch.setenv("VendorAudioLLM", "audioVendor")
    monkeypatch.setenv("KeyAudioLLM", "audioAPIKey")
    monkeypatch.setenv("ScienceHost", "theScienceHost")
    monkeypatch.setenv("OntologiesHost", "theOntologiesHost")
    monkeypatch.setenv("PreSharedKey", "thePreSharedKey")

    tests = [
        ("y", True),
        ("yes", True),
        ("1", True),
        ("n", False),
        ("", False),
    ]
    for env_variable, exp_structured in tests:
        monkeypatch.setenv("StructuredReasonForVisit", env_variable)

        tested = HelperSettings
        result = tested.settings()
        expected = Settings(
            llm_text=VendorKey(vendor="textVendor", api_key="textAPIKey"),
            llm_audio=VendorKey(vendor="audioVendor", api_key="audioAPIKey"),
            science_host="theScienceHost",
            ontologies_host="theOntologiesHost",
            pre_shared_key="thePreSharedKey",
            structured_rfv=exp_structured,
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

    tested = HelperSettings
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

    tested = HelperSettings
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


@patch.object(HelperSettings, "nuanced_differences")
def test_json_nuanced_differences(nuanced_differences):
    def reset_mocks():
        nuanced_differences.reset_mock()

    accepted_levels = ["level1", "level2"]
    system_prompt = [
        "The user will provides two JSON objects.",
        "Your task is compare them and report the discrepancies as a JSON list in a Markdown block like:",
        "```json",
        '[{"level": "minor/moderate/severe/critical", "difference": "description of the difference between the JSONs"}]',
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
    tested = HelperSettings
    result = tested.json_nuanced_differences(["level1", "level2"], "theResultJson", "theExpectedJson")
    expected = (True, "some text")
    assert result == expected

    calls = [call(accepted_levels, system_prompt, user_prompt)]
    assert nuanced_differences.mock_calls == calls
    reset_mocks()


@patch.object(HelperSettings, "nuanced_differences")
def test_text_nuanced_differences(nuanced_differences):
    def reset_mocks():
        nuanced_differences.reset_mock()

    accepted_levels = ["level1", "level2"]
    system_prompt = [
        "The user will provides two texts.",
        "Your task is compare them *solely* from a medical meaning point of view and report the discrepancies as a JSON list in a Markdown block like:",
        "```json",
        '[{"level": "minor/moderate/severe/critical", "difference": "description of the difference between the texts"}]',
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
    tested = HelperSettings
    result = tested.text_nuanced_differences(["level1", "level2"], "theResultText", "theExpectedText")
    expected = (True, "some text")
    assert result == expected

    calls = [call(accepted_levels, system_prompt, user_prompt)]
    assert nuanced_differences.mock_calls == calls
    reset_mocks()


@patch.object(Helper, "chatter")
@patch.object(HelperSettings, "settings")
def test_nuanced_differences(settings, chatter):
    conversation = MagicMock()

    def reset_mocks():
        settings.reset_mock()
        chatter.reset_mock()
        conversation.reset_mock()

    tested = HelperSettings

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
    json_content = json.dumps(content, indent=1)

    # errors
    settings.side_effect = ["theSettings"]
    chatter.side_effect = [conversation]
    conversation.chat.side_effect = [JsonExtract(has_error=True, error="theError", content=content)]
    result = tested.nuanced_differences(["level1", "level2"], system_prompt, user_prompt)
    expected = (False, "encountered error: theError")
    assert result == expected

    calls = [call()]
    assert settings.mock_calls == calls
    calls = [call("theSettings")]
    assert chatter.mock_calls == calls
    calls = [
        call.set_system_prompt(system_prompt),
        call.set_user_prompt(user_prompt),
        call.chat(),
    ]
    assert conversation.mock_calls == calls
    reset_mocks()

    # no error
    # -- differences within the accepted levels
    settings.side_effect = ["theSettings"]
    chatter.side_effect = [conversation]
    conversation.chat.side_effect = [JsonExtract(has_error=False, error="theError", content=content)]
    result = tested.nuanced_differences(["level1", "level2", "level3", "level4"], system_prompt, user_prompt)
    expected = (True, json_content)
    assert result == expected

    calls = [call()]
    assert settings.mock_calls == calls
    calls = [call("theSettings")]
    assert chatter.mock_calls == calls
    calls = [
        call.set_system_prompt(system_prompt),
        call.set_user_prompt(user_prompt),
        call.chat(),
    ]
    assert conversation.mock_calls == calls
    reset_mocks()
    # -- differences out of the accepted levels
    settings.side_effect = ["theSettings"]
    chatter.side_effect = [conversation]
    conversation.chat.side_effect = [JsonExtract(has_error=False, error="theError", content=content)]
    result = tested.nuanced_differences(["level2", "level3"], system_prompt, user_prompt)
    expected = (False, json_content)
    assert result == expected

    calls = [call()]
    assert settings.mock_calls == calls
    calls = [call("theSettings")]
    assert chatter.mock_calls == calls
    calls = [
        call.set_system_prompt(system_prompt),
        call.set_user_prompt(user_prompt),
        call.chat(),
    ]
    assert conversation.mock_calls == calls
    reset_mocks()
