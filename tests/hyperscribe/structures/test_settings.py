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
    }
    assert is_namedtuple(tested, fields)


def test_from_dictionary():
    tested = Settings

    tests = [
        ({}, False),
        ({"StructuredReasonForVisit": "yes"}, True),
        ({"StructuredReasonForVisit": "YES"}, True),
        ({"StructuredReasonForVisit": "y"}, True),
        ({"StructuredReasonForVisit": "Y"}, True),
        ({"StructuredReasonForVisit": "1"}, True),
        ({"StructuredReasonForVisit": "0"}, False),
        ({"StructuredReasonForVisit": "anything"}, False),
    ]
    for rfv, exp_rfv in tests:
        result = tested.from_dictionary({
                                            "VendorTextLLM": "textVendor",
                                            "KeyTextLLM": "textAPIKey",
                                            "VendorAudioLLM": "audioVendor",
                                            "KeyAudioLLM": "audioAPIKey",
                                            "ScienceHost": "theScienceHost",
                                            "OntologiesHost": "theOntologiesHost",
                                            "PreSharedKey": "thePreSharedKey",
                                        } | rfv)
        expected = Settings(
            llm_text=VendorKey(vendor="textVendor", api_key="textAPIKey"),
            llm_audio=VendorKey(vendor="audioVendor", api_key="audioAPIKey"),
            science_host="theScienceHost",
            ontologies_host="theOntologiesHost",
            pre_shared_key="thePreSharedKey",
            structured_rfv=exp_rfv,
        )
        assert result == expected

    # missing key
    with pytest.raises(KeyError):
        _ = tested.from_dictionary({})
