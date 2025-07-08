from unittest.mock import MagicMock, patch, call

from canvas_sdk.commands import PerformCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.perform import Perform
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.charge_description import ChargeDescription
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
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
    )
    cache = LimitedCache("patientUuid", "providerUuid", {})
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


@patch.object(LimitedCache, "charge_descriptions")
def test_command_from_json(charge_descriptions):
    chatter = MagicMock()

    def reset_mocks():
        charge_descriptions.reset_mock()
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
    system_prompt = [
        'The conversation is in the medical context.',
        '',
        'Your task is to select the most relevant procedure performed on a patient out of a list of procedures.',
        '',
    ]
    user_prompt = [
        'Here is the comment provided by the healthcare provider in regards to the procedure performed on the patient:',
        '```text',
        'keywords: procedure1,procedure2,procedure3',
        ' -- ',
        'theComment',
        '```',
        '',
        'Among the following procedures, select the most relevant one:',
        '',
        ' * shortName1 (code: code1)\n * shortName2 (code: code2)\n * shortName3 (code: code3)',
        '',
        'Please, present your findings in a JSON format within a Markdown code block like:',
        '```json',
        '[{"code": "the procedure code", "label": "the procedure label"}]',
        '```',
        '',
    ]
    schemas = [
        {
            '$schema': 'http://json-schema.org/draft-07/schema#',
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'code': {'type': 'string', 'minLength': 1},
                    'label': {'type': 'string', 'minLength': 1},
                },
                'required': ['code', 'label'],
                'additionalProperties': False,
            },
            'minItems': 1,
            'maxItems': 1,
        },
    ]

    tested = helper_instance()
    # no charge
    charge_descriptions.side_effect = [[]]
    chatter.single_conversation.side_effect = [[]]
    instruction = InstructionWithParameters(**arguments)
    command = PerformCommand(cpt_code="", notes="theComment", note_uuid="noteUuid")
    result = tested.command_from_json(instruction, chatter)
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected

    calls = [call()]
    assert charge_descriptions.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()

    # some charges
    # -- with response
    charge_descriptions.side_effect = [[
        ChargeDescription(short_name="shortName1", full_name="fullName1", cpt_code="code1"),
        ChargeDescription(short_name="shortName2", full_name="fullName2", cpt_code="code2"),
        ChargeDescription(short_name="shortName3", full_name="fullName3", cpt_code="code3"),
    ]]
    chatter.single_conversation.side_effect = [[{"code": "theCode", "label": "theLabel"}]]
    instruction = InstructionWithParameters(**arguments)
    command = PerformCommand(cpt_code="theCode", notes="theComment", note_uuid="noteUuid")
    result = tested.command_from_json(instruction, chatter)
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected

    calls = [call()]
    assert charge_descriptions.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # -- with no response
    charge_descriptions.side_effect = [[
        ChargeDescription(short_name="shortName1", full_name="fullName1", cpt_code="code1"),
        ChargeDescription(short_name="shortName2", full_name="fullName2", cpt_code="code2"),
        ChargeDescription(short_name="shortName3", full_name="fullName3", cpt_code="code3"),
    ]]
    chatter.single_conversation.side_effect = [[]]
    instruction = InstructionWithParameters(**arguments)
    command = PerformCommand(cpt_code="", notes="theComment", note_uuid="noteUuid")
    result = tested.command_from_json(instruction, chatter)
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected

    calls = [call()]
    assert charge_descriptions.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
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
