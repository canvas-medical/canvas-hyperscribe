from unittest.mock import patch, call

import pytest

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
    }
    assert is_namedtuple(tested, fields)


@patch.object(Settings, "is_true")
def test_from_dictionary(is_true):
    def reset_mocks():
        is_true.reset_mock()

    tested = Settings

    tests = [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ]
    for rfv, audit in tests:
        is_true.side_effect = [rfv, audit]
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
        )
        assert result == expected
        calls = [call("rfv"), call("audit")]
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
