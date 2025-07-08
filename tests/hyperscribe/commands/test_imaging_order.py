from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.imaging_order import ImagingOrderCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.imaging_order import ImagingOrder
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.selector_chat import SelectorChat
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.imaging_report import ImagingReport
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> ImagingOrder:
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
    return ImagingOrder(settings, cache, identification)


def test_class():
    tested = ImagingOrder
    assert issubclass(tested, Base)


def test_schema_key():
    tested = ImagingOrder
    result = tested.schema_key()
    expected = "imagingOrder"
    assert result == expected


def test_staged_command_extract():
    tested = ImagingOrder
    tests = [
        ({}, None),
        ({
             "image": {"text": "theImaging"},
             "comment": "theComment",
             "priority": "thePriority",
             "indications": [
                 {"text": "indication1"},
                 {"text": "indication2"},
                 {"text": "indication3"},
             ],
             "additional_details": "additionalOrderDetails"
         }, CodedItem(
            label="theImaging: theComment (priority: thePriority, related conditions: indication1/indication2/indication3)",
            code="",
            uuid="",
        )),
        ({
             "image": {"text": "theImaging"},
             "comment": "theComment",
             "priority": "thePriority",
             "indications": [],
             "additional_details": "additionalOrderDetails"
         }, CodedItem(
            label="theImaging: theComment (priority: thePriority, related conditions: n/a)",
            code="",
            uuid="",
        )),
        ({
             "image": {"text": "theImaging"},
             "comment": "theComment",
             "priority": "",
             "indications": [
                 {"text": "indication1"},
                 {"text": "indication2"},
                 {"text": "indication3"},
             ],
             "additional_details": "additionalOrderDetails"
         }, CodedItem(
            label="theImaging: theComment (priority: n/a, related conditions: indication1/indication2/indication3)",
            code="",
            uuid="",
        )),
        ({
             "image": {"text": "theImaging"},
             "comment": "",
             "priority": "thePriority",
             "indications": [
                 {"text": "indication1"},
                 {"text": "indication2"},
                 {"text": "indication3"},
             ],
             "additional_details": "additionalOrderDetails"
         }, CodedItem(
            label="theImaging: n/a (priority: thePriority, related conditions: indication1/indication2/indication3)",
            code="",
            uuid="",
        )),
        ({
             "image": {"text": ""},
             "comment": "theComment",
             "priority": "thePriority",
             "indications": [
                 {"text": "indication1"},
                 {"text": "indication2"},
                 {"text": "indication3"},
             ],
             "additional_details": "additionalOrderDetails"
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(CanvasScience, "search_imagings")
@patch.object(SelectorChat, "condition_from")
def test_command_from_json(condition_from, search_imagings):
    chatter = MagicMock()

    def reset_mocks():
        condition_from.reset_mock()
        search_imagings.reset_mock()
        chatter.reset_mock()

    imaging_orders = [
        ImagingReport(code="code1", name="name1"),
        ImagingReport(code="code2", name="name2"),
        ImagingReport(code="code3", name="name3"),
    ]
    keywords = ['keyword1', 'keyword2', 'keyword3']
    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant imaging order for a patient out of a list of imaging orders.",
        "",
    ]
    user_prompt = [
        "Here is the comments provided by the healthcare provider in regards to the imaging to order for a patient:",
        "```text",
        "keywords: keyword1,keyword2,keyword3",
        " -- ",
        "note: theComment",
        " -- ",
        "note to the radiologist: keyword1,keyword2,keyword3",
        "```",
        "Among the following imaging orders, identify the most relevant one:",
        "",
        " * name1 (code1)\n * name2 (code2)\n * name3 (code3)",
        "",
        "Please, present your findings in a JSON format within a Markdown code block like:",
        "```json",
        '[{"conceptId": "the code ID", "term": "the name of the imaging"}]',
        "```",
        "",
    ]
    schemas = [{
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'conceptId': {'type': 'string', 'minLength': 1},
                'term': {'type': 'string', 'minLength': 1},
            },
            'required': ['conceptId', 'term'],
            'additionalProperties': False,
        },
        'minItems': 1,
        'maxItems': 1,
    }]

    tested = helper_instance()

    # all good
    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            "imagingKeywords": "keyword1,keyword2,keyword3",
            "conditions": [
                {"conditionKeywords": "condition1,condition2", "ICD10": "icd1,icd2"},
                {"conditionKeywords": "condition3", "ICD10": "icd3"},
                {"conditionKeywords": "condition4", "ICD10": "icd4"},
            ],
            "comment": "theComment",
            "noteToRadiologist": "theNoteToTheRadiologist",
            "priority": "Urgent",
        },
    }
    condition_from.side_effect = [
        CodedItem(uuid="uuid1", label="condition1", code="icd1"),
        CodedItem(uuid="uuid3", label="condition3", code=""),
        CodedItem(uuid="uuid4", label="condition4", code="icd3"),
    ]
    search_imagings.side_effect = [imaging_orders]
    chatter.single_conversation.side_effect = [[{"conceptId": "theCode", "name": "theName"}]]

    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = ImagingOrderCommand(
        note_uuid="noteUuid",
        image_code='theCode',
        ordering_provider_key="providerUuid",
        diagnosis_codes=["icd1", "icd3"],
        comment="theComment",
        additional_details="theNoteToTheRadiologist",
        priority=ImagingOrderCommand.Priority.URGENT,
        linked_items_urns=[],
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected

    calls = [
        call(instruction, chatter, tested.settings, ['condition1', 'condition2'], ['icd1', 'icd2'], "theComment"),
        call(instruction, chatter, tested.settings, ['condition3'], ['icd3'], "theComment"),
        call(instruction, chatter, tested.settings, ['condition4'], ['icd4'], "theComment"),
    ]
    assert condition_from.mock_calls == calls
    calls = [call('scienceHost', keywords)]
    assert search_imagings.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no condition + no code found
    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            "imagingKeywords": "keyword1,keyword2,keyword3",
            "conditions": [],
            "comment": "theComment",
            "noteToRadiologist": "theNoteToTheRadiologist",
            "priority": "Urgent",
        },
    }
    condition_from.side_effect = []
    search_imagings.side_effect = [imaging_orders]
    chatter.single_conversation.side_effect = [[]]

    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = ImagingOrderCommand(
        note_uuid="noteUuid",
        ordering_provider_key="providerUuid",
        diagnosis_codes=[],
        comment="theComment",
        additional_details="theNoteToTheRadiologist",
        priority=ImagingOrderCommand.Priority.URGENT,
        linked_items_urns=[],
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected

    assert condition_from.mock_calls == []
    calls = [call('scienceHost', keywords)]
    assert search_imagings.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no condition + no imaging from Science
    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            "imagingKeywords": "keyword1,keyword2,keyword3",
            "conditions": [],
            "comment": "theComment",
            "noteToRadiologist": "theNoteToTheRadiologist",
            "priority": "Urgent",
        },
    }
    condition_from.side_effect = []
    search_imagings.side_effect = [[]]
    chatter.single_conversation.side_effect = []

    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = ImagingOrderCommand(
        note_uuid="noteUuid",
        ordering_provider_key="providerUuid",
        diagnosis_codes=[],
        comment="theComment",
        additional_details="theNoteToTheRadiologist",
        priority=ImagingOrderCommand.Priority.URGENT,
        linked_items_urns=[],
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected

    assert condition_from.mock_calls == []
    calls = [call('scienceHost', keywords)]
    assert search_imagings.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "imagingKeywords": "comma separated keywords of up to 5 synonyms of the imaging to order",
        "conditions": [
            {
                "conditionKeywords": "comma separated keywords of up to 5 synonyms of each condition targeted by the imaging",
                "ICD10": "comma separated keywords of up to 5 ICD-10 codes of each condition targeted by the imaging",
            },
        ],
        "comment": "rationale of the imaging order, as free text",
        "noteToRadiologist": "information to be sent to the radiologist, as free text",
        "priority": "mandatory, one of: Routine/Urgent",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Imaging ordered, including all necessary comments and the targeted conditions. "
                "There can be only one imaging order per instruction, and no instruction in the lack of.")
    assert result == expected


def test_instruction_constraints():
    tested = helper_instance()
    result = tested.instruction_constraints()
    expected = ""
    assert result == expected


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
