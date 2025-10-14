import json
from datetime import date
from hashlib import md5
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.task import TaskCommand, TaskAssigner, AssigneeType

from hyperscribe.commands.base import Base
from hyperscribe.commands.task import Task
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Task:
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
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    cache = LimitedCache()
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return Task(settings, cache, identification)


def test_class():
    tested = Task
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Task
    result = tested.schema_key()
    expected = "task"
    assert result == expected


def test_staged_command_extract():
    tested = Task
    tests = [
        ({}, None),
        (
            {
                "title": "theTask",
                "labels": [{"text": "label1"}, {"text": "label2"}, {"text": "label3"}],
                "comment": "theComment",
                "due_date": "theDate",
            },
            CodedItem(label="theTask: theComment (due on: theDate, labels: label1/label2/label3)", code="", uuid=""),
        ),
        (
            {
                "title": "",
                "labels": [{"text": "label1"}, {"text": "label2"}, {"text": "label3"}],
                "comment": "theComment",
                "due_date": "theDate",
            },
            None,
        ),
        (
            {"title": "theTask", "labels": [], "comment": "theComment", "due_date": "theDate"},
            CodedItem(label="theTask: theComment (due on: theDate, labels: n/a)", code="", uuid=""),
        ),
        (
            {"title": "theTask", "labels": [{"text": "label1"}], "comment": "", "due_date": ""},
            CodedItem(label="theTask: n/a (due on: n/a, labels: label1)", code="", uuid=""),
        ),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(LimitedCache, "existing_teams")
@patch.object(LimitedCache, "existing_roles")
@patch.object(LimitedCache, "existing_staff_members")
@patch.object(Task, "add_code2description")
def test_select_assignee(add_code2description, existing_staff_members, existing_roles, existing_teams):
    chatter = MagicMock()

    def reset_mocks():
        add_code2description.reset_mock()
        existing_staff_members.reset_mock()
        existing_roles.reset_mock()
        existing_teams.reset_mock()
        chatter.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "The goal is to identify the most relevant staff member, team or role to assign a specific task to.",
        "",
    ]
    user_prompt = [
        "Here is the comment provided by the healthcare provider in regards to the task:",
        "```text",
        "assign to: assignedTo",
        " -- ",
        "comment: theComment",
        "",
        "```",
        "",
        "Among the following staff members, teams and roles, identify the most relevant one:",
        "",
        " * Joe Smith (type: staff, id: 741)\n * Jane Doe (type: staff, id: 596)\n * Jim Boy (type: staff, id: 963)",
        " * Administrative (type: team, id: 741)\n * Medical (type: team, id: 752)",
        " * Health Coach (type: role, id: 854)\n * Physician (type: role, id: 863)",
        "",
        "Please, present your findings in a JSON format within a Markdown code block like:",
        "```json",
        '[{"type": "staff, team or role", "id": "the id, as int", "name": "the entity"}]',
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
                    "type": {"type": "string", "enum": ["staff", "team", "role"]},
                    "id": {"type": "integer", "minimum": 1},
                    "name": {"type": "string", "minLength": 1},
                },
                "required": ["type", "id", "name"],
                "additionalProperties": False,
            },
            "minItems": 1,
            "maxItems": 1,
        },
    ]

    instruction = InstructionWithParameters(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=False,
        is_updated=True,
        parameters={"key": "value"},
    )

    tested = helper_instance()

    # no staff, no role, no team
    existing_roles.side_effect = [[]]
    existing_staff_members.side_effect = [[]]
    existing_teams.side_effect = [[]]
    chatter.single_conversation.side_effect = []
    result = tested.select_assignee(instruction, chatter, "assignedTo", "theComment")
    assert result is None
    calls = [call()]
    assert existing_roles.mock_calls == calls
    assert existing_staff_members.mock_calls == calls
    assert existing_teams.mock_calls == calls
    assert add_code2description.mock_calls == []
    assert chatter.mock_calls == []
    reset_mocks()

    # staffers, roles and teams
    roles = [
        CodedItem(uuid="854", label="Health Coach", code=""),
        CodedItem(uuid="863", label="Physician", code=""),
    ]
    staffers = [
        CodedItem(uuid="741", label="Joe Smith", code=""),
        CodedItem(uuid="596", label="Jane Doe", code=""),
        CodedItem(uuid="963", label="Jim Boy", code=""),
    ]
    teams = [
        CodedItem(uuid="741", label="Administrative", code=""),
        CodedItem(uuid="752", label="Medical", code=""),
    ]
    # -- response
    tests = [
        (
            [{"type": "role", "id": 854, "name": "Health Coach"}],
            TaskAssigner(to=AssigneeType.ROLE, id=854),
            [call("854", "Health Coach")],
        ),
        (
            [{"type": "staff", "id": 596, "name": "Jane Doe"}],
            TaskAssigner(to=AssigneeType.STAFF, id=596),
            [call("596", "Jane Doe")],
        ),
        (
            [{"type": "team", "id": 752, "name": "Medical"}],
            TaskAssigner(to=AssigneeType.TEAM, id=752),
            [call("752", "Medical")],
        ),
    ]
    for side_effect, expected, exp_calls in tests:
        existing_roles.side_effect = [roles]
        existing_staff_members.side_effect = [staffers]
        existing_teams.side_effect = [teams]
        chatter.single_conversation.side_effect = [side_effect]
        result = tested.select_assignee(instruction, chatter, "assignedTo", "theComment")
        assert result == expected
        calls = [call()]
        assert existing_roles.mock_calls == calls
        assert existing_staff_members.mock_calls == calls
        assert existing_teams.mock_calls == calls
        assert add_code2description.mock_calls == exp_calls
        calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
        assert chatter.mock_calls == calls
        reset_mocks()

    # -- no response
    existing_roles.side_effect = [roles]
    existing_staff_members.side_effect = [staffers]
    existing_teams.side_effect = [teams]
    chatter.single_conversation.side_effect = [[]]
    result = tested.select_assignee(instruction, chatter, "assignedTo", "theComment")
    assert result is None
    calls = [call()]
    assert existing_roles.mock_calls == calls
    assert existing_staff_members.mock_calls == calls
    assert existing_teams.mock_calls == calls
    calls = []
    assert add_code2description.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "existing_task_labels")
def test_select_labels(existing_task_labels):
    chatter = MagicMock()

    def reset_mocks():
        chatter.reset_mock()
        existing_task_labels.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "The goal is to identify the most relevant labels linked to a specific task.",
        "",
    ]
    user_prompt = [
        "Here is the comment provided by the healthcare provider in regards to the task:",
        "```text",
        "labels: theLabels",
        " -- ",
        "comment: theComment",
        "",
        "```",
        "",
        "Among the following labels, identify all the most relevant to characterized the task:",
        "",
        " * Label1 (labelId: 741)\n * Label2 (labelId: 596)\n * Label3 (labelId: 963)",
        "",
        "Please, present your findings in a JSON format within a Markdown code block like:",
        "```json",
        '[{"labelId": "the label id, as int", "name": "the name of the label"}]',
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
                    "labelId": {"type": "integer", "minimum": 1},
                    "name": {"type": "string", "minLength": 1},
                },
                "required": ["labelId", "name"],
                "additionalProperties": False,
            },
            "minItems": 1,
            "maxItems": 1,
        },
    ]
    tested = helper_instance()

    instruction = InstructionWithParameters(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=False,
        is_updated=True,
        parameters={"key": "value"},
    )

    # no labels
    existing_task_labels.side_effect = [[]]
    chatter.single_conversation.side_effect = []
    result = tested.select_labels(instruction, chatter, "theLabels", "theComment")
    assert result is None
    calls = [call()]
    assert existing_task_labels.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()

    # staff
    labels = [
        CodedItem(uuid="741", label="Label1", code=""),
        CodedItem(uuid="596", label="Label2", code=""),
        CodedItem(uuid="963", label="Label3", code=""),
    ]
    # -- response
    existing_task_labels.side_effect = [labels]
    chatter.single_conversation.side_effect = [[{"labelId": 596, "name": "Label2"}, {"labelId": 963, "name": "Label3"}]]
    result = tested.select_labels(instruction, chatter, "theLabels", "theComment")
    expected = ["Label2", "Label3"]
    assert result == expected
    calls = [call()]
    assert existing_task_labels.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()
    # -- no response
    existing_task_labels.side_effect = [labels]
    chatter.single_conversation.side_effect = [[]]
    result = tested.select_labels(instruction, chatter, "theLabels", "theComment")
    assert result is None
    calls = [call()]
    assert existing_task_labels.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()


@patch.object(Task, "select_labels")
@patch.object(Task, "select_assignee")
def test_command_from_json(select_assignee, select_labels):
    chatter = MagicMock()

    def reset_mocks():
        select_assignee.reset_mock()
        select_labels.reset_mock()

    tested = helper_instance()

    assignee = TaskAssigner(to=AssigneeType.STAFF, id=584)
    labels = ["label1", "label2"]

    tests = [(assignee, labels), (None, labels), (assignee, None), (None, None)]
    for side_effect_staff, side_effect_labels in tests:
        # all parameters
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {
                "title": "theTitle",
                "dueDate": "2025-02-04",
                "assignTo": "theAssignTo",
                "labels": "theLabels",
                "comment": "theComment",
            },
        }
        select_assignee.side_effect = [side_effect_staff]
        select_labels.side_effect = [side_effect_labels]
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = TaskCommand(
            title="theTitle",
            due_date=date(2025, 2, 4),
            comment="theComment",
            assign_to=side_effect_staff,
            labels=side_effect_labels,
            note_uuid="noteUuid",
        )
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        calls = [call(instruction, chatter, "theAssignTo", "theComment")]
        assert select_assignee.mock_calls == calls
        calls = [call(instruction, chatter, "theLabels", "theComment")]
        assert select_labels.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()

        # no assignee
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {
                "title": "theTitle",
                "dueDate": "2025-02-04",
                "assignTo": "",
                "labels": "theLabels",
                "comment": "theComment",
            },
        }
        select_assignee.side_effect = []
        select_labels.side_effect = [side_effect_labels]
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = TaskCommand(
            title="theTitle",
            due_date=date(2025, 2, 4),
            comment="theComment",
            labels=side_effect_labels,
            note_uuid="noteUuid",
        )
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        assert select_assignee.mock_calls == []
        calls = [call(instruction, chatter, "theLabels", "theComment")]
        assert select_labels.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()

        # no labels
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {
                "title": "theTitle",
                "dueDate": "2025-02-04",
                "assignTo": "theAssignTo",
                "labels": "",
                "comment": "theComment",
            },
        }
        select_assignee.side_effect = [side_effect_staff]
        select_labels.side_effect = []
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = TaskCommand(
            title="theTitle",
            due_date=date(2025, 2, 4),
            comment="theComment",
            assign_to=side_effect_staff,
            note_uuid="noteUuid",
        )
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        calls = [call(instruction, chatter, "theAssignTo", "theComment")]
        assert select_assignee.mock_calls == calls
        assert select_labels.mock_calls == []
        assert chatter.mock_calls == []
        reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "title": "",
        "dueDate": "",
        "assignTo": "",
        "labels": "",
        "comment": "",
    }
    assert result == expected


def test_command_parameters_schemas():
    tested = helper_instance()
    result = tested.command_parameters_schemas()
    expected = "3792c107a65b706bc29080bfa3e2ab0a"
    assert md5(json.dumps(result).encode()).hexdigest() == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Specific task assigned to someone or a group at the healthcare facility, "
        "including the speaking clinician. "
        "A task might include a due date and a specific assignee. "
        "There can be one and only one task per instruction, and no instruction in the lack of."
    )
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
