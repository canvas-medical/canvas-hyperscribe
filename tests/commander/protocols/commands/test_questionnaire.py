from unittest.mock import patch, call

from canvas_sdk.commands.commands.questionnaire import QuestionnaireCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.questionnaire import Questionnaire
from commander.protocols.limited_cache import LimitedCache
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey


def helper_instance() -> Questionnaire:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
    )
    cache = LimitedCache("patientUuid")
    return Questionnaire(settings, cache, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = Questionnaire
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "questionnaire"
    assert result == expected


@patch.object(LimitedCache, "existing_questionnaires")
def test_command_from_json(current_goals):
    def reset_mocks():
        current_goals.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="questionnaire1", code=""),
        CodedItem(uuid="theUuid2", label="questionnaire2", code=""),
        CodedItem(uuid="theUuid3", label="questionnaire3", code=""),
    ]
    tests = [
        (1, "theUuid2"),
        (2, "theUuid3"),
        (4, ""),
    ]
    for idx, exp_uuid in tests:
        current_goals.side_effect = [goals, goals]
        params = {
            'questionnaire': 'questionnaire2',
            'questionnaireIndex': idx,
            "result": "theResult",
        }
        result = tested.command_from_json(params)
        expected = QuestionnaireCommand(
            questionnaire_id=exp_uuid,
            result="theResult",
            note_uuid="noteUuid",
        )
        assert result == expected
        calls = [call()]
        assert current_goals.mock_calls == calls
        reset_mocks()


@patch.object(LimitedCache, "existing_questionnaires")
def test_command_parameters(current_goals):
    def reset_mocks():
        current_goals.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="questionnaire1", code=""),
        CodedItem(uuid="theUuid2", label="questionnaire2", code=""),
        CodedItem(uuid="theUuid3", label="questionnaire3", code=""),
    ]
    current_goals.side_effect = [goals]
    result = tested.command_parameters()
    expected = {
        "questionnaire": "one of: questionnaire1 (index: 0)/questionnaire2 (index: 1)/questionnaire3 (index: 2), mandatory",
        "questionnaireIndex": "index of the questionnaire, as integer",
        "result": "the conclusion of the clinician based on the patient's answers, as free text",
    }
    assert result == expected
    calls = [call()]
    assert current_goals.mock_calls == calls
    reset_mocks()


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Questionnaire submitted by the clinician, including the questions and patient's responses. "
                "There can be only one questionnaire per instruction, and no instruction in the lack of. "
                "Each type of questionnaire can be submitted only once per discussion.")
    assert result == expected


@patch.object(LimitedCache, "existing_questionnaires")
def test_instruction_constraints(current_goals):
    def reset_mocks():
        current_goals.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="questionnaire1", code=""),
        CodedItem(uuid="theUuid2", label="questionnaire2", code=""),
        CodedItem(uuid="theUuid3", label="questionnaire3", code=""),
    ]
    current_goals.side_effect = [goals]
    result = tested.instruction_constraints()
    expected = ('"Questionnaire" has to be related to one of the following questionnaires: '
                '"questionnaire1", "questionnaire2", "questionnaire3"')
    assert result == expected
    calls = [call()]
    assert current_goals.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "existing_questionnaires")
def test_is_available(current_goals):
    def reset_mocks():
        current_goals.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="questionnaire1", code=""),
        CodedItem(uuid="theUuid2", label="questionnaire2", code=""),
        CodedItem(uuid="theUuid3", label="questionnaire3", code=""),
    ]
    tests = [
        (goals, True),
        ([], False),
    ]
    for side_effect, expected in tests:
        current_goals.side_effect = [side_effect]
        result = tested.is_available()
        assert result is expected
        calls = [call()]
        assert current_goals.mock_calls == calls
        reset_mocks()
