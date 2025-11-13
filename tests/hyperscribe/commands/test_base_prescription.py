from decimal import Decimal
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands import AdjustPrescriptionCommand
from canvas_sdk.commands.commands.prescribe import PrescribeCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.base_prescription import BasePrescription
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.medication_detail import MedicationDetail
from hyperscribe.structures.medication_detail_quantity import MedicationDetailQuantity
from hyperscribe.structures.medication_search import MedicationSearch
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> BasePrescription:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        structured_rfv=False,
        audit_llm=False,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
        hierarchical_detection_threshold=5,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    cache = LimitedCache("patientUuid", "providerUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return BasePrescription(settings, cache, identification)


def test_class():
    tested = BasePrescription
    assert issubclass(tested, Base)


@patch.object(CanvasScience, "medication_details")
@patch.object(LimitedCache, "staged_commands_of")
@patch.object(LimitedCache, "current_allergies")
@patch.object(LimitedCache, "demographic__str__")
def test_medications_from(demographic, current_allergies, staged_commands_of, medication_details):
    chatter = MagicMock()

    def reset_mocks():
        demographic.reset_mock()
        current_allergies.reset_mock()
        staged_commands_of.reset_mock()
        medication_details.reset_mock()
        chatter.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant medication to prescribe to a patient out of a list of medications.",
        "CRITICAL: If a specific medication name and/or dose is mentioned in the comment, "
        "you MUST select the medication that exactly matches the name and dose.",
        "",
    ]
    user_prompts = {
        "with_conditions": [
            "Here is the comment provided by the healthcare provider in regards to the prescription:",
            "```text",
            "keywords: keyword1, keyword2, keyword3",
            " -- ",
            "theComment",
            "```",
            "",
            "The prescription is intended to the patient's condition: theCondition.",
            "",
            "The choice of the medication has to also take into account that:",
            " - the patient has this demographic,",
            " - the patient's medical record contains no information about allergies.",
            "",
            "Sort the following medications from most relevant to least, and return the first one:",
            "",
            " * labelA (fdbCode: code123)\n * labelB (fdbCode: code369)\n * labelC (fdbCode: code752)",
            "",
            "IMPORTANT: If a specific medication name and/or dose is mentioned in the comment, select the "
            "medication that exactly matches the name and dose. Do not substitute a different name or dose.",
            "",
            "Please, present your findings in a JSON format within a Markdown code block like:",
            "```json",
            '[{"fdbCode": "the fdb code, as int", "description": "the description"}]',
            "```",
            "",
        ],
        "no_condition": [
            "Here is the comment provided by the healthcare provider in regards to the prescription:",
            "```text",
            "keywords: keyword1, keyword2, keyword3",
            " -- ",
            "theComment",
            "```",
            "",
            "",
            "",
            "The choice of the medication has to also take into account that:",
            " - the patient has this demographic,",
            " - the patient's medical record contains no information about allergies.",
            "",
            "Sort the following medications from most relevant to least, and return the first one:",
            "",
            " * labelA (fdbCode: code123)\n * labelB (fdbCode: code369)\n * labelC (fdbCode: code752)",
            "",
            "IMPORTANT: If a specific medication name and/or dose is mentioned in the comment, select the "
            "medication that exactly matches the name and dose. Do not substitute a different name or dose.",
            "",
            "Please, present your findings in a JSON format within a Markdown code block like:",
            "```json",
            '[{"fdbCode": "the fdb code, as int", "description": "the description"}]',
            "```",
            "",
        ],
        "with_allergies": [
            "Here is the comment provided by the healthcare provider in regards to the prescription:",
            "```text",
            "keywords: keyword1, keyword2, keyword3",
            " -- ",
            "theComment",
            "```",
            "",
            "",
            "",
            "The choice of the medication has to also take into account that:",
            " - the patient has this demographic,",
            " - the patient is allergic to:\n * allergy1\n * allergy2\n * allergy3.",
            "",
            "Sort the following medications from most relevant to least, and return the first one:",
            "",
            " * labelA (fdbCode: code123)\n * labelB (fdbCode: code369)\n * labelC (fdbCode: code752)",
            "",
            "IMPORTANT: If a specific medication name and/or dose is mentioned in the comment, select the "
            "medication that exactly matches the name and dose. Do not substitute a different name or dose.",
            "",
            "Please, present your findings in a JSON format within a Markdown code block like:",
            "```json",
            '[{"fdbCode": "the fdb code, as int", "description": "the description"}]',
            "```",
            "",
        ],
    }
    schemas = [
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fdbCode": {"type": "integer", "minimum": 1},
                    "description": {"type": "string", "minLength": 1},
                },
                "required": ["fdbCode", "description"],
                "additionalProperties": False,
            },
            "minItems": 1,
            "maxItems": 1,
        },
    ]
    keywords = ["keyword1", "keyword2", "keyword3"]
    brands = ["brand1", "brand2", "brand3", "brand4"]
    medications = [
        MedicationDetail(fdb_code="code123", description="labelA", quantities=[]),
        MedicationDetail(fdb_code="code369", description="labelB", quantities=[]),
        MedicationDetail(fdb_code="code752", description="labelC", quantities=[]),
    ]
    allergies = [
        CodedItem(label="allergy1", uuid="uuid1", code="code1"),
        CodedItem(label="allergy2", uuid="uuid2", code="code2"),
        CodedItem(label="allergy3", uuid="uuid3", code="code3"),
    ]
    instruction = InstructionWithParameters(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=False,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
    )

    tested = helper_instance()

    # with condition
    demographic.side_effect = ["the patient has this demographic"]
    current_allergies.side_effect = [[]]
    staged_commands_of.side_effect = [[]]
    medication_details.side_effect = [medications]
    chatter.single_conversation.side_effect = [[{"fdbCode": "code369", "description": "labelB"}]]
    search = MedicationSearch(
        comment="theComment",
        keywords=keywords,
        brand_names=brands,
        related_condition="theCondition",
    )
    result = tested.medications_from(instruction, chatter, search)
    expected = [MedicationDetail(fdb_code="code369", description="labelB", quantities=[])]
    assert result == expected

    calls = [call(False)]
    assert demographic.mock_calls == calls
    calls = [call()]
    assert current_allergies.mock_calls == calls
    calls = [call(["allergy"])]
    assert staged_commands_of.mock_calls == calls
    calls = [call(brands)]
    assert medication_details.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompts["with_conditions"], schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # without condition
    demographic.side_effect = ["the patient has this demographic"]
    current_allergies.side_effect = [[]]
    staged_commands_of.side_effect = [[]]
    medication_details.side_effect = [medications]
    chatter.single_conversation.side_effect = [[{"fdbCode": "code369", "description": "labelB"}]]
    search = MedicationSearch(comment="theComment", keywords=keywords, brand_names=brands, related_condition="")
    result = tested.medications_from(instruction, chatter, search)
    expected = [MedicationDetail(fdb_code="code369", description="labelB", quantities=[])]
    assert result == expected

    calls = [call(False)]
    assert demographic.mock_calls == calls
    calls = [call()]
    assert current_allergies.mock_calls == calls
    calls = [call(["allergy"])]
    assert staged_commands_of.mock_calls == calls
    calls = [call(brands)]
    assert medication_details.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompts["no_condition"], schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # without allergies
    demographic.side_effect = ["the patient has this demographic"]
    current_allergies.side_effect = [allergies[:2]]
    staged_commands_of.side_effect = [allergies[2:]]
    medication_details.side_effect = [medications]
    chatter.single_conversation.side_effect = [[{"fdbCode": "code369", "description": "labelB"}]]
    search = MedicationSearch(comment="theComment", keywords=keywords, brand_names=brands, related_condition="")
    result = tested.medications_from(instruction, chatter, search)
    expected = [MedicationDetail(fdb_code="code369", description="labelB", quantities=[])]
    assert result == expected

    calls = [call(False)]
    assert demographic.mock_calls == calls
    calls = [call()]
    assert current_allergies.mock_calls == calls
    calls = [call(["allergy"])]
    assert staged_commands_of.mock_calls == calls
    calls = [call(brands)]
    assert medication_details.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompts["with_allergies"], schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # without response
    demographic.side_effect = ["the patient has this demographic"]
    current_allergies.side_effect = [[]]
    staged_commands_of.side_effect = [[]]
    medication_details.side_effect = [medications]
    chatter.single_conversation.side_effect = [[]]
    search = MedicationSearch(comment="theComment", keywords=keywords, brand_names=brands, related_condition="")
    result = tested.medications_from(instruction, chatter, search)
    assert result == []

    calls = [call(False)]
    assert demographic.mock_calls == calls
    calls = [call()]
    assert current_allergies.mock_calls == calls
    calls = [call(["allergy"])]
    assert staged_commands_of.mock_calls == calls
    calls = [call(brands)]
    assert medication_details.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompts["no_condition"], schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no medication
    demographic.side_effect = []
    current_allergies.side_effect = [[]]
    staged_commands_of.side_effect = [[]]
    medication_details.side_effect = [[]]
    chatter.single_conversation.side_effect = []
    search = MedicationSearch(
        comment="theComment",
        keywords=keywords,
        brand_names=brands,
        related_condition="theCondition",
    )
    result = tested.medications_from(instruction, chatter, search)
    assert result == []

    assert demographic.mock_calls == []
    assert current_allergies.mock_calls == []
    assert staged_commands_of.mock_calls == []
    calls = [call(brands)]
    assert medication_details.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


@patch.object(LimitedCache, "demographic__str__")
def test_set_medication_dosage(demographic):
    chatter = MagicMock()

    def reset_mocks():
        chatter.reset_mock()
        demographic.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to compute the quantity to dispense and the number of refills for a prescription.",
        "CRITICAL: If a specific frequency is mentioned in the comment (e.g. 'once weekly', 'twice daily'), "
        "you MUST preserve that exact frequency in the directions.",
        "",
    ]
    user_prompt = [
        "Here is the comment provided by the healthcare provider in regards to the prescription of the "
        "medication labelB:",
        "```text",
        "theComment",
        "```",
        "",
        "The medication is provided as 7, description1.",
        "",
        "Based on this information, what are the quantity to dispense and the number of refills in order "
        "to fulfill the 11 supply days?",
        "",
        "The exact quantities and refill have to also take into account that the patient has this demographic.",
        "",
        "IMPORTANT: If a specific frequency is mentioned in the comment (e.g. 'once weekly', 'twice daily'), "
        "preserve that exact frequency in the informationToPatient field. Calculate the quantity based on that "
        "stated frequency.",
        "",
        "Please, present your findings in a JSON format within a Markdown code block like:",
        "```json",
        '[{"quantityToDispense": -1, '
        '"refills": -1, '
        '"discreteQuantity": true, '
        '"noteToPharmacist": "", '
        '"informationToPatient": ""}]',
        "```",
        "",
        "Your response must be a JSON Markdown block validated with the schema:",
        "```json",
        '{"$schema": "http://json-schema.org/draft-07/schema#", '
        '"type": "array", '
        '"items": {"type": "object", "properties": {'
        '"quantityToDispense": {"type": "number", "exclusiveMinimum": 0.0, "description": "the quantity to dispense"}, '
        '"refills": {"type": "integer", "minimum": 0, "description": "the refills allowed"}, '
        '"discreteQuantity": {"type": "boolean", "description": "whether the medication form is discrete '
        "(e.g., tablets, capsules, patches, suppositories) as opposed to continuous "
        "(e.g., milliliters, grams, ounces). Interpret the ncpdp quantity qualifier description to determine this. "
        'Set to true for countable units, false for measurable quantities."}, '
        '"noteToPharmacist": {"type": "string", "description": "the note to the pharmacist, as free text"}, '
        '"informationToPatient": {"type": "string", "minLength": 1, "description": "the information to the patient '
        "on how to use the medication, specifying the quantity, the form (e.g. tablets, drops, puffs, etc), "
        "the frequency and/or max daily frequency, and the route of use "
        '(e.g. by mouth, applied to skin, dropped in eye, etc), as free text"}}, '
        '"required": ["quantityToDispense", "refills", "discreteQuantity", "informationToPatient"], '
        '"additionalProperties": false}, "minItems": 1, "maxItems": 1}',
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
                    "quantityToDispense": {
                        "type": "number",
                        "exclusiveMinimum": 0.0,
                        "description": "the quantity to dispense",
                    },
                    "refills": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "the refills allowed",
                    },
                    "discreteQuantity": {
                        "type": "boolean",
                        "description": "whether the medication form is discrete "
                        "(e.g., tablets, capsules, patches, suppositories) as opposed to continuous "
                        "(e.g., milliliters, grams, ounces). Interpret the ncpdp quantity qualifier "
                        "description to determine this. Set to true for countable units, "
                        "false for measurable quantities.",
                    },
                    "noteToPharmacist": {
                        "type": "string",
                        "description": "the note to the pharmacist, as free text",
                    },
                    "informationToPatient": {
                        "type": "string",
                        "minLength": 1,
                        "description": "the information to the patient on how to use the medication, "
                        "specifying the quantity, the form (e.g. tablets, drops, puffs, etc), "
                        "the frequency and/or max daily frequency, and the route of use "
                        "(e.g. by mouth, applied to skin, dropped in eye, etc), as free text",
                    },
                },
                "required": ["quantityToDispense", "refills", "discreteQuantity", "informationToPatient"],
                "additionalProperties": False,
            },
            "minItems": 1,
            "maxItems": 1,
        },
    ]
    medication = MedicationDetail(
        fdb_code="code369",
        description="labelB",
        quantities=[
            MedicationDetailQuantity(
                quantity="7",
                representative_ndc="ndc1",
                ncpdp_quantity_qualifier_code="qualifier1",
                ncpdp_quantity_qualifier_description="description1",
            ),
            MedicationDetailQuantity(
                quantity="3",
                representative_ndc="ndc2",
                ncpdp_quantity_qualifier_code="qualifier2",
                ncpdp_quantity_qualifier_description="description2",
            ),
        ],
    )

    tested = helper_instance()

    # with response
    tests = [
        (
            PrescribeCommand(days_supply=11),
            PrescribeCommand(
                days_supply=11,
                fdb_code="code369",
                type_to_dispense={"representative_ndc": "ndc1", "ncpdp_quantity_qualifier_code": "qualifier1"},
                quantity_to_dispense=Decimal("8.3"),
                refills=3,
                note_to_pharmacist="theNoteToPharmacist",
                sig="theInformationToPatient",
            ),
        ),
        (
            AdjustPrescriptionCommand(days_supply=11, fdb_code="code985"),
            AdjustPrescriptionCommand(
                days_supply=11,
                fdb_code="code985",
                new_fdb_code="code369",
                type_to_dispense={"representative_ndc": "ndc1", "ncpdp_quantity_qualifier_code": "qualifier1"},
                quantity_to_dispense=Decimal("8.3"),
                refills=3,
                note_to_pharmacist="theNoteToPharmacist",
                sig="theInformationToPatient",
            ),
        ),
    ]
    instruction = InstructionWithParameters(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=False,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
    )
    for command, expected in tests:
        demographic.side_effect = ["the patient has this demographic"]
        chatter.single_conversation.side_effect = [
            [
                {
                    "quantityToDispense": "8.3",
                    "refills": 3,
                    "discreteQuantity": False,
                    "noteToPharmacist": "theNoteToPharmacist",
                    "informationToPatient": "theInformationToPatient",
                },
            ],
        ]
        tested.set_medication_dosage(instruction, chatter, "theComment", command, medication)
        assert command == expected

        calls = [call(False)]
        assert demographic.mock_calls == calls
        calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
        assert chatter.mock_calls == calls
        reset_mocks()

    # discrete quantity (tablets) - should be integer format
    command = PrescribeCommand(days_supply=11)
    demographic.side_effect = ["the patient has this demographic"]
    chatter.single_conversation.side_effect = [
        [
            {
                "quantityToDispense": "60",
                "refills": 0,
                "discreteQuantity": True,  # tablets are discrete
                "noteToPharmacist": "Dispense 60 tablets",
                "informationToPatient": "Take 2 tablets by mouth once daily",
            },
        ],
    ]
    tested.set_medication_dosage(instruction, chatter, "theComment", command, medication)
    expected = PrescribeCommand(
        days_supply=11,
        fdb_code="code369",
        type_to_dispense={"representative_ndc": "ndc1", "ncpdp_quantity_qualifier_code": "qualifier1"},
        quantity_to_dispense=Decimal("60"),  # No .00 - integer format
        refills=0,
        note_to_pharmacist="Dispense 60 tablets",
        sig="Take 2 tablets by mouth once daily",
    )
    assert command == expected
    assert command.quantity_to_dispense == Decimal("60")  # Verify it's "60" not "60.00"

    calls = [call(False)]
    assert demographic.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no response
    command = PrescribeCommand(days_supply=11)
    demographic.side_effect = ["the patient has this demographic"]
    chatter.single_conversation.side_effect = [[]]
    tested.set_medication_dosage(instruction, chatter, "theComment", command, medication)
    expected = PrescribeCommand(
        days_supply=11,
        fdb_code="code369",
        type_to_dispense={"representative_ndc": "ndc1", "ncpdp_quantity_qualifier_code": "qualifier1"},
    )
    assert command == expected

    calls = [call(False)]
    assert demographic.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()
