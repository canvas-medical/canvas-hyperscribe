from unittest.mock import MagicMock, patch, call

from canvas_sdk.commands import PerformCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.perform import Perform
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.selector_chat import SelectorChat
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Perform:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
        audit_llm=False,
        api_signing_key="theApiSigningKey",
    )
    cache = LimitedCache("patientUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return Perform(settings, cache, identification)


def test_class():
    tested = Perform
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Perform
    result = tested.schema_key()
    expected = "perform"
    assert result == expected


def test_staged_command_extract():
    tested = Perform
    tests = [
        ({}, None),
        ({
             "notes": "theNotes",
             "perform": {"text": "theProcedure"}
         }, CodedItem(label="theProcedure: theNotes", code="", uuid="")),
        ({
             "notes": "theNotes",
             "perform": {"text": ""}
         }, None),
        ({
             "notes": "",
             "perform": {"text": "theProcedure"}
         }, CodedItem(label="theProcedure: n/a", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(SelectorChat, "procedure_from")
def test_command_from_json(procedure_from):
    chatter = MagicMock()

    def reset_mocks():
        procedure_from.reset_mock()
        chatter.reset_mock()

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            "comment": "theComment",
            "procedureKeywords": "procedure1,procedure2,procedure3",
        },
    }
    tested = helper_instance()
    tests = [
        ("theCode", PerformCommand(cpt_code="theCode", notes="theComment", note_uuid="noteUuid")),
        ("", PerformCommand(cpt_code="", notes="theComment", note_uuid="noteUuid")),
    ]
    for code, command in tests:
        procedure_from.side_effect = [CodedItem(uuid="theUuid", label="theLabel", code=code)]
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected

        calls = [
            call(instruction, chatter, tested.settings, ["procedure1", "procedure2", "procedure3"], "theComment"),
        ]
        assert procedure_from.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "procedureKeywords": "comma separated keywords of up to 5 synonyms of the procedure or action performed",
        "comment": "information related to the procedure or action performed, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Medical procedure, which is not an auscultation, performed during the encounter. "
                "There can be only one procedure performed per instruction, and no instruction in the lack of.")
    assert result == expected


def test_instruction_constraints():
    tested = helper_instance()
    result = tested.instruction_constraints()
    expected = '"Perform" supports only one procedure per instruction, auscultation are prohibited.'
    assert result == expected


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
