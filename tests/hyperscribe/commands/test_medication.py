from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.medication_statement import MedicationStatementCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.medication import Medication
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.medication_cached import MedicationCached
from hyperscribe.structures.medication_detail import MedicationDetail
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Medication:
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
    )
    cache = LimitedCache("patientUuid", "providerUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return Medication(settings, cache, identification)


def test_class():
    tested = Medication
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Medication
    result = tested.schema_key()
    expected = "medicationStatement"
    assert result == expected


def test_staged_command_extract():
    tested = Medication
    tests = [
        ({}, None),
        ({
             "sig": "theSig",
             "medication": {"text": "theMedication"}
         }, CodedItem(label="theMedication: theSig", code="", uuid="")),
        ({
             "sig": "theSig",
             "medication": {"text": ""}
         }, None),
        ({
             "sig": "",
             "medication": {"text": "theMedication"}
         }, CodedItem(label="theMedication: n/a", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(CanvasScience, "medication_details")
def test_command_from_json(medication_details):
    chatter = MagicMock()

    def reset_mocks():
        medication_details.reset_mock()
        chatter.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant medication to prescribe to a patient out of a list of medications.",
        "",
    ]
    user_prompt = [
        'Here is the comment provided by the healthcare provider in regards to the prescription:',
        '```text',
        'keywords: keyword1,keyword2,keyword3',
        ' -- ',
        'theSig',
        '```',
        '', 'Among the following medications, identify the most relevant one:',
        '',
        ' * labelA (fdbCode: code123)\n * labelB (fdbCode: code369)\n * labelC (fdbCode: code752)',
        '',
        'Please, present your findings in a JSON format within a Markdown code block like:',
        '```json',
        '[{"fdbCode": "the fdb code, as int", "description": "the description"}]',
        '```',
        '',
    ]
    schemas = [{
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'fdbCode': {'type': 'integer', 'minimum': 1},
                'description': {'type': 'string', 'minLength': 1},
            },
            'required': ['fdbCode', 'description'],
            'additionalProperties': False,
        },
        'minItems': 1,
        'maxItems': 1,
    }]
    keywords = ['keyword1', 'keyword2', 'keyword3']
    tested = helper_instance()

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            'keywords': 'keyword1,keyword2,keyword3',
            'sig': 'theSig',
        },
    }
    medications = [
        MedicationDetail(fdb_code="code123", description="labelA", quantities=[]),
        MedicationDetail(fdb_code="code369", description="labelB", quantities=[]),
        MedicationDetail(fdb_code="code752", description="labelC", quantities=[]),
    ]

    # all good
    medication_details.side_effect = [medications]
    chatter.single_conversation.side_effect = [[{"fdbCode": "code369", "description": "labelB"}]]

    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = MedicationStatementCommand(
        sig="theSig",
        fdb_code="code369",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert medication_details.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no good response
    medication_details.side_effect = [medications]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = MedicationStatementCommand(
        sig="theSig",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert medication_details.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no medical concept
    medication_details.side_effect = [[]]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = MedicationStatementCommand(
        sig="theSig",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert medication_details.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "comma separated keywords of up to 5 synonyms of the taken medication",
        "sig": "directions, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Current medication. "
                "There can be only one medication per instruction, and no instruction in the lack of.")
    assert result == expected


@patch.object(LimitedCache, "current_medications")
def test_instruction_constraints(current_medications):
    def reset_mocks():
        current_medications.reset_mock()

    tested = helper_instance()

    medications = [
        MedicationCached(
            uuid="theUuid",
            label="display1",
            code_rx_norm="rxNorm1",
            code_fdb="fdb1",
            national_drug_code="ndc1",
            potency_unit_code="puc1",
        ),
        MedicationCached(
            uuid="theUuid2",
            label="display2",
            code_rx_norm="rxNorm2",
            code_fdb="fdb2",
            national_drug_code="ndc2",
            potency_unit_code="puc2",
        ),
        MedicationCached(
            uuid="theUuid3",
            label="display3",
            code_rx_norm="rxNorm3",
            code_fdb="fdb3",
            national_drug_code="ndc3",
            potency_unit_code="puc3",
        ),
    ]
    tests = [
        (medications, "'Medication' cannot include: display1, display2, display3."),
        ([], ""),
    ]
    for side_effect, expected in tests:
        current_medications.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert current_medications.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
