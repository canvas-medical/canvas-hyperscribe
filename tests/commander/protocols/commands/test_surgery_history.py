from unittest.mock import patch, call

from canvas_sdk.commands.commands.past_surgical_history import PastSurgicalHistoryCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.surgery_history import SurgeryHistory
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings


def helper_instance() -> SurgeryHistory:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return SurgeryHistory(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = SurgeryHistory
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "surgicalHistory"
    assert result == expected


def te0st_command_from_json():
    tested = helper_instance()
    result = tested.command_from_json()
    expected = PastSurgicalHistoryCommand({})
    assert result == expected


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "comma separated keywords of up to 5 synonyms of the surgery",
        "approximateDate": "YYYY-MM-DD",
        "comment": "description of the surgery, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Any past surgery. "
                "There can be only one surgery per instruction, and no instruction in the lack of.")
    assert result == expected


@patch.object(SurgeryHistory, "surgery_history")
def test_instruction_constraints(surgery_history):
    def reset_mocks():
        surgery_history.reset_mock()

    tested = helper_instance()
    surgeries = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    tests = [
        ([], ""),
        (surgeries, '"SurgeryHistory" cannot include: "display1a", "display2a", "display3a".'),
    ]
    for side_effect, expected in tests:
        surgery_history.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert surgery_history.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
