from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.close_goal import CloseGoalCommand
from canvas_sdk.commands.commands.goal import GoalCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.close_goal import CloseGoal
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> CloseGoal:
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
    return CloseGoal(settings, cache, identification)


def test_class():
    tested = CloseGoal
    assert issubclass(tested, Base)


def test_schema_key():
    tested = CloseGoal
    result = tested.schema_key()
    expected = "closeGoal"
    assert result == expected


def test_staged_command_extract():
    tested = CloseGoal
    tests = [
        ({}, None),
        ({"goal_id": {}, "progress": "the Progress", "achievement_status": "in-progress"}, None),
        (
            {"goal_id": {"text": "theGoal"}, "progress": "theProgress", "achievement_status": "in-progress"},
            CodedItem(label="theGoal (theProgress)", code="", uuid=""),
        ),
        (
            {"goal_id": {"text": "theGoal"}, "progress": "", "achievement_status": "in-progress"},
            CodedItem(label="theGoal (n/a)", code="", uuid=""),
        ),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(LimitedCache, "current_goals")
def test_command_from_json(current_goals):
    chatter = MagicMock()

    def reset_mocks():
        current_goals.reset_mock()
        chatter.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="display1a", code="123"),
        CodedItem(uuid="theUuid2", label="display2a", code="45"),
        CodedItem(uuid="theUuid3", label="display3a", code="9876"),
    ]
    tests = [(1, 45), (2, 9876), (4, 0)]
    for idx, exp_uuid in tests:
        current_goals.side_effect = [goals, goals]
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {
                "goal": "display2a",
                "goalIndex": idx,
                "progressAndBarriers": "theProgressAndBarriers",
                "status": "improving",
            },
        }
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = CloseGoalCommand(
            goal_id=exp_uuid,
            achievement_status=GoalCommand.AchievementStatus.IMPROVING,
            progress="theProgressAndBarriers",
            note_uuid="noteUuid",
        )
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        calls = [call()]
        assert current_goals.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()


@patch.object(LimitedCache, "current_goals")
def test_command_parameters(current_goals):
    def reset_mocks():
        current_goals.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    current_goals.side_effect = [goals]
    result = tested.command_parameters()
    expected = {
        "goal": "one of: display1a (index: 0)/display2a (index: 1)/display3a (index: 2)",
        "goalIndex": "index of the Goal to close, or -1, as integer",
        "progressAndBarriers": "progress and barriers, as free text",
        "status": "one of: in-progress/improving/worsening/no-change/achieved/sustaining/not-achieved/"
        "no-progress/not-attainable",
    }
    assert result == expected
    calls = [call()]
    assert current_goals.mock_calls == calls
    reset_mocks()


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = "Ending of a previously set goal, including status, progress, barriers, priority or due date."
    assert result == expected


@patch.object(LimitedCache, "current_goals")
def test_instruction_constraints(current_goals):
    def reset_mocks():
        current_goals.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    current_goals.side_effect = [goals]
    result = tested.instruction_constraints()
    expected = '"CloseGoal" has to be related to one of the following goals: "display1a", "display2a", "display3a"'
    assert result == expected
    calls = [call()]
    assert current_goals.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_goals")
def test_is_available(current_goals):
    def reset_mocks():
        current_goals.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    tests = [(goals, True), ([], False)]
    for side_effect, expected in tests:
        current_goals.side_effect = [side_effect]
        result = tested.is_available()
        assert result is expected
        calls = [call()]
        assert current_goals.mock_calls == calls
        reset_mocks()
