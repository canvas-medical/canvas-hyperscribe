from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.resolve_condition import ResolveConditionCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.resolve_condition import ResolveCondition
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> ResolveCondition:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
    )
    cache = LimitedCache("patientUuid", {})
    return ResolveCondition(settings, cache, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = ResolveCondition
    assert issubclass(tested, Base)


def test_schema_key():
    tested = ResolveCondition
    result = tested.schema_key()
    expected = "resolveCondition"
    assert result == expected


def test_staged_command_extract():
    tested = ResolveCondition
    tests = [
        ({}, None),
        ({
             "condition": {},
             "narrative": "better",
             "background": "theBackground",
         }, None),
        ({
             "condition": {
                 "text": "theCondition",
                 "annotations": ["theCode"],
             },
             "narrative": "theNarrative",
             "background": "theBackground",
         }, CodedItem(label="theCondition: theNarrative", code="", uuid="")),
        ({
             "condition": {
                 "text": "theCondition",
                 "annotations": ["theCode"],
             },
             "narrative": "",
             "background": "theBackground",
         }, CodedItem(label="theCondition: ", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(LimitedCache, "current_conditions")
def test_command_from_json(current_conditions):
    chatter = MagicMock()

    def reset_mocks():
        current_conditions.reset_mock()
        chatter.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [
        (1, "theUuid2"),
        (2, "theUuid3"),
        (4, ""),
    ]
    for idx, exp_uuid in tests:
        current_conditions.side_effect = [conditions, conditions]
        params = {
            'condition': 'display2a',
            'conditionIndex': idx,
            'rationale': 'theRationale',
        }
        result = tested.command_from_json(chatter, params)
        expected = ResolveConditionCommand(
            condition_id=exp_uuid,
            rationale="theRationale",
            note_uuid="noteUuid",
        )
        assert result == expected
        calls = [call()]
        assert current_conditions.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()


@patch.object(LimitedCache, "current_conditions")
def test_command_parameters(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.command_parameters()
    expected = {
        'condition': 'one of: display1a (index: 0)/display2a (index: 1)/display3a (index: 2)',
        "conditionIndex": "index of the Condition to set as resolved, or -1, as integer",
        "rationale": "rationale to set the condition as resolved, as free text",
    }
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_conditions")
def test_instruction_description(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.instruction_description()
    expected = ("Set as resolved a previously diagnosed condition (display1a, display2a, display3a). "
                "There can be only one resolved condition per instruction, and no instruction in the lack of.")
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_conditions")
def test_instruction_constraints(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.instruction_constraints()
    expected = ("'ResolveCondition' has to be related to one of the following conditions: "
                "display1a (ICD-10: CODE12.3), "
                "display2a (ICD-10: CODE45), "
                "display3a (ICD-10: CODE98.76)")
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_conditions")
def test_is_available(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [
        (conditions, True),
        ([], False),
    ]
    for side_effect, expected in tests:
        current_conditions.side_effect = [side_effect]
        result = tested.is_available()
        assert result is expected
        calls = [call()]
        assert current_conditions.mock_calls == calls
        reset_mocks()
