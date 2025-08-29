from datetime import date
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.immunization_statement import ImmunizationStatementCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.immunization_statement import ImmunizationStatement
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.immunization_cached import ImmunizationCached
from hyperscribe.structures.immunization_detail import ImmunizationDetail
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> ImmunizationStatement:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        structured_rfv=False,
        audit_llm=False,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
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
    return ImmunizationStatement(settings, cache, identification)


def test_class():
    tested = ImmunizationStatement
    assert issubclass(tested, Base)


def test_schema_key():
    tested = ImmunizationStatement
    result = tested.schema_key()
    expected = "immunizationStatement"
    assert result == expected


def test_staged_command_extract():
    tested = ImmunizationStatement
    tests = [
        ({}, None),
        (
            {
                "date": {"date": "2024-09-03"},
                "comments": "theComments",
                "statement": {
                    "text": "theText",
                    "extra": {
                        "coding": [
                            {"code": "theCptCode", "system": "theCptSystem", "display": "theCptDisplay"},
                            {"code": "theCvxCode", "system": "theCvxSystem", "display": "theCvxDisplay"},
                        ]
                    },
                    "value": "theValue",
                },
            },
            CodedItem(
                label="2024-09-03 - theText: ['theCptSystem: theCptCode', 'theCvxSystem: theCvxCode'] - theComments",
                code="",
                uuid="",
            ),
        ),
        (
            {
                "date": {"date": "2024-09-03"},
                "statement": {
                    "text": "theText",
                    "extra": {
                        "coding": [
                            {"code": "theCptCode", "system": "theCptSystem", "display": "theCptDisplay"},
                            {"code": "theCvxCode", "system": "theCvxSystem", "display": "theCvxDisplay"},
                        ]
                    },
                    "value": "theValue",
                },
            },
            CodedItem(
                label="2024-09-03 - theText: ['theCptSystem: theCptCode', 'theCvxSystem: theCvxCode'] - n/a",
                code="",
                uuid="",
            ),
        ),
        (
            {
                "date": {"date": "2024-09-03"},
                "comments": "theComments",
                "statement": {
                    "extra": {
                        "coding": [
                            {"code": "theCptCode", "system": "theCptSystem", "display": "theCptDisplay"},
                            {"code": "theCvxCode", "system": "theCvxSystem", "display": "theCvxDisplay"},
                        ]
                    },
                    "value": "theValue",
                },
            },
            CodedItem(
                label="2024-09-03 - n/a: ['theCptSystem: theCptCode', 'theCvxSystem: theCvxCode'] - theComments",
                code="",
                uuid="",
            ),
        ),
        (
            {
                "comments": "theComments",
                "statement": {
                    "text": "theText",
                    "extra": {
                        "coding": [
                            {"code": "theCptCode", "system": "theCptSystem", "display": "theCptDisplay"},
                            {"code": "theCvxCode", "system": "theCvxSystem", "display": "theCvxDisplay"},
                        ]
                    },
                    "value": "theValue",
                },
            },
            CodedItem(
                label="n/a - theText: ['theCptSystem: theCptCode', 'theCvxSystem: theCvxCode'] - theComments",
                code="",
                uuid="",
            ),
        ),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(ImmunizationStatement, "add_code2description")
@patch.object(CanvasScience, "search_immunization")
def test_command_from_json(search_immunization, add_code2description):
    chatter = MagicMock()

    def reset_mocks():
        search_immunization.reset_mock()
        add_code2description.reset_mock()
        chatter.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant immunization administrated to a patient "
        "out of a list of immunizations.",
        "",
    ]
    user_prompt = [
        "Here is the comment provided by the healthcare provider in regards to the immunization:",
        "```text",
        "keywords: keyword1,keyword2,keyword3",
        " -- ",
        "theComments",
        "```",
        "",
        "Among the following immunizations, identify the most relevant one:",
        "",
        " * labelA (cptCode: theCptA, cvxCode: theCvxA)\n"
        " * labelB (cptCode: theCptB, cvxCode: theCvxB)\n"
        " * labelC (cptCode: theCptC, cvxCode: theCvxC)",
        "",
        "Please, present your findings in a JSON format within a Markdown code block like:",
        "```json",
        '[{"cptCode": "the CPT code", "cvxCode": "the CVX code", "label": "the label"}]',
        "```",
        "",
    ]
    schemas = [
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cptCode": {"type": "string", "minimum": 1},
                    "cvxCode": {"type": "string", "minLength": 1},
                    "label": {"type": "string", "minLength": 1},
                },
                "required": ["cptCode", "cvxCode", "label"],
                "additionalProperties": False,
            },
            "minItems": 1,
            "maxItems": 1,
        },
    ]
    keywords = ["keyword1", "keyword2", "keyword3"]
    tested = helper_instance()

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            "keywords": "keyword1,keyword2,keyword3",
            "approximateImmunizationDate": "2024-09-23",
            "comments": "theComments",
        },
    }
    immunizations = [
        ImmunizationDetail(label="labelA", code_cpt="theCptA", code_cvx="theCvxA", cvx_description="theDescriptionA"),
        ImmunizationDetail(label="labelB", code_cpt="theCptB", code_cvx="theCvxB", cvx_description="theDescriptionB"),
        ImmunizationDetail(label="labelC", code_cpt="theCptC", code_cvx="theCvxC", cvx_description="theDescriptionC"),
    ]

    # all good
    search_immunization.side_effect = [immunizations]
    chatter.single_conversation.side_effect = [[{"cptCode": "theCptC", "cvxCode": "theCvxC", "label": "labelC"}]]

    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = ImmunizationStatementCommand(
        cpt_code="theCptC",
        cvx_code="theCvxC",
        approximate_date=date(2024, 9, 23),
        comments="theComments",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call(keywords)]
    assert search_immunization.mock_calls == calls
    calls = [
        call("theCptC", "labelC"),
        call("theCvxC", "labelC"),
    ]
    assert add_code2description.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no good response
    search_immunization.side_effect = [immunizations]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = ImmunizationStatementCommand(
        cpt_code="",
        cvx_code="",
        approximate_date=date(2024, 9, 23),
        comments="theComments",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call(keywords)]
    assert search_immunization.mock_calls == calls
    assert add_code2description.mock_calls == []
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no immunization
    search_immunization.side_effect = [[]]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = ImmunizationStatementCommand(
        cpt_code="",
        cvx_code="",
        approximate_date=date(2024, 9, 23),
        comments="theComments",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call(keywords)]
    assert search_immunization.mock_calls == calls
    assert add_code2description.mock_calls == []
    assert chatter.mock_calls == []
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "comma separated keywords of up to 5 synonyms of the immunization",
        "approximateImmunizationDate": "YYYY-MM-DD",
        "comments": "provided information related to the immunization, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Any past immunization. There can be only one immunization per instruction, and no instruction in the lack of."
    )
    assert result == expected


@patch.object(LimitedCache, "current_immunizations")
def test_instruction_constraints(current_immunizations):
    def reset_mocks():
        current_immunizations.reset_mock()

    tested = helper_instance()

    immunizations = [
        ImmunizationCached(
            uuid="theUuid1",
            label="display1",
            code_cpt="theCptC1",
            code_cvx="theCvxC1",
            comments="theComments1",
            approximate_date=date(2024, 9, 21),
        ),
        ImmunizationCached(
            uuid="theUuid2",
            label="display2",
            code_cpt="theCptC2",
            code_cvx="theCvxC2",
            comments="theComments2",
            approximate_date=date(2024, 9, 22),
        ),
        ImmunizationCached(
            uuid="theUuid3",
            label="display3",
            code_cpt="theCptC3",
            code_cvx="theCvxC3",
            comments="theComments3",
            approximate_date=date(2024, 9, 23),
        ),
    ]
    tests = [
        (
            immunizations,
            "'ImmunizationStatement' cannot include: "
            "display1 (CPT: theCptC1, CVX: theCvxC1) on 2024-09-21, "
            "display2 (CPT: theCptC2, CVX: theCvxC2) on 2024-09-22, "
            "display3 (CPT: theCptC3, CVX: theCvxC3) on 2024-09-23.",
        ),
        ([], ""),
    ]
    for side_effect, expected in tests:
        current_immunizations.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert current_immunizations.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is False
