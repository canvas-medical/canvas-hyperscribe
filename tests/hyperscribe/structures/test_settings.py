from unittest.mock import patch, call

import pytest

from hyperscribe.structures.commands_policy import CommandsPolicy
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import is_namedtuple


def test_class():
    tested = Settings
    fields = {
        "llm_text": VendorKey,
        "llm_audio": VendorKey,
        "science_host": str,
        "ontologies_host": str,
        "pre_shared_key": str,
        "structured_rfv": bool,
        "audit_llm": bool,
        "api_signing_key": str,
        "send_progress": bool,
        "commands_policy": CommandsPolicy,
    }
    assert is_namedtuple(tested, fields)


@patch.object(Settings, "is_true")
def test_from_dictionary(is_true):
    def reset_mocks():
        is_true.reset_mock()

    tested = Settings

    tests = [
        (True, True, False, True),
        (True, False, False, False),
        (False, True, True, False),
        (False, False, True, True),
    ]
    for rfv, audit, policy, progress in tests:
        is_true.side_effect = [rfv, audit, policy]
        result = tested.from_dictionary({
            "VendorTextLLM": "textVendor",
            "KeyTextLLM": "textAPIKey",
            "VendorAudioLLM": "audioVendor",
            "KeyAudioLLM": "audioAPIKey",
            "ScienceHost": "theScienceHost",
            "OntologiesHost": "theOntologiesHost",
            "PreSharedKey": "thePreSharedKey",
            "StructuredReasonForVisit": "rfv",
            "AuditLLMDecisions": "audit",
            "APISigningKey": "theApiSigningKey",
            "sendProgress": progress,
            "CommandsList": "ReasonForVisit,StopMedication Task Vitals",
            "CommandsPolicy": "policy",
        })
        expected = Settings(
            llm_text=VendorKey(vendor="textVendor", api_key="textAPIKey"),
            llm_audio=VendorKey(vendor="audioVendor", api_key="audioAPIKey"),
            science_host="theScienceHost",
            ontologies_host="theOntologiesHost",
            pre_shared_key="thePreSharedKey",
            structured_rfv=rfv,
            audit_llm=audit,
            api_signing_key="theApiSigningKey",
            send_progress=progress,
            commands_policy=CommandsPolicy(policy=policy, commands=["ReasonForVisit", "StopMedication", "Task", "Vitals"]),
        )
        assert result == expected
        calls = [call("rfv"), call("audit"), call("policy")]
        assert is_true.mock_calls == calls
        reset_mocks()

    # missing key
    with pytest.raises(KeyError):
        _ = tested.from_dictionary({})


def test_is_true():
    tested = Settings
    tests = [
        ("", False),
        ("yes", True),
        ("YES", True),
        ("y", True),
        ("Y", True),
        ("1", True),
        ("0", False),
        ("anything", False),
    ]
    for string, expected in tests:
        result = tested.is_true(string)
        assert result == expected, f"---> {string}"


def test_list_from():
    tested = Settings
    tests = [
        ("", []),
        ("command", ["command"]),
        ("command1 command2    command3, command4,,command5\ncommand6",
         ["command1", "command2", "command3", "command4", "command5", "command6"]),
    ]
    for string, expected in tests:
        result = tested.list_from(string)
        assert result == expected, f"---> {string}"
