from datetime import date
from unittest.mock import patch, call

from canvas_sdk.commands.commands.task import TaskCommand, TaskAssigner, AssigneeType
from canvas_sdk.v1.data import Staff, TaskLabel

from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.commands.task import Task
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.handlers.structures.coded_item import CodedItem
from hyperscribe.handlers.structures.settings import Settings
from hyperscribe.handlers.structures.vendor_key import VendorKey


def helper_instance() -> Task:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
    )
    cache = LimitedCache("patientUuid", {})
    return Task(settings, cache, "patientUuid", "noteUuid", "providerUuid")


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
        ({
             "title": "theTask",
             "labels": [
                 {"text": "label1"},
                 {"text": "label2"},
                 {"text": "label3"},
             ],
             "comment": "theComment",
             "due_date": "theDate",
         }, CodedItem(label="theTask: theComment (due on: theDate, labels: label1/label2/label3)", code="", uuid="")),
        ({
             "title": "",
             "labels": [
                 {"text": "label1"},
                 {"text": "label2"},
                 {"text": "label3"},
             ],
             "comment": "theComment",
             "due_date": "theDate",
         }, None),
        ({
             "title": "theTask",
             "labels": [],
             "comment": "theComment",
             "due_date": "theDate",
         }, CodedItem(label="theTask: theComment (due on: theDate, labels: n/a)", code="", uuid="")),
        ({
             "title": "theTask",
             "labels": [{"text": "label1"}],
             "comment": "",
             "due_date": "",
         }, CodedItem(label="theTask: n/a (due on: n/a, labels: label1)", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(Staff, 'objects')
@patch.object(Helper, "chatter")
def test_select_staff(chatter, staff):
    def reset_mocks():
        chatter.reset_mock()
        staff.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "The goal is to identify the most relevant staff member to assign a specific task to.",
        "",
    ]
    user_prompt = [
        'Here is the comment provided by the healthcare provider in regards to the task:',
        '```text',
        'assign to: assignedTo',
        ' -- ',
        'comment: theComment',
        '',
        '```',
        '',
        'Among the following staff members, identify the most relevant one:',
        '',
        ' * Joe Smith (staffId: 741)\n * Jane Doe (staffId: 596)\n * Jim Boy (staffId: 963)',
        '',
        'Please, present your findings in a JSON format within a Markdown code block like:',
        '```json',
        '[{"staffId": "the staff member id, as int", "name": "the name of the staff member"}]',
        '```',
        '',
    ]

    tested = helper_instance()

    # no staff (just theoretical)
    staff.filter.return_value.order_by.side_effect = [[]]
    chatter.return_value.single_conversation.side_effect = []
    result = tested.select_staff("assignedTo", "theComment")
    assert result is None
    calls = [call.filter(active=True), call.filter().order_by('last_name')]
    assert staff.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()

    # staff
    staffers = [
        Staff(dbid=741, first_name="Joe", last_name="Smith"),
        Staff(dbid=596, first_name="Jane", last_name="Doe"),
        Staff(dbid=963, first_name="Jim", last_name="Boy"),
    ]
    # -- response
    staff.filter.return_value.order_by.side_effect = [staffers]
    chatter.return_value.single_conversation.side_effect = [[{"staffId": 596, "name": "Jane Doe"}]]
    result = tested.select_staff("assignedTo", "theComment")
    expected = TaskAssigner(to=AssigneeType.STAFF, id=596)
    assert result == expected
    calls = [call.filter(active=True), call.filter().order_by('last_name')]
    assert staff.mock_calls == calls
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompt),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()
    # -- no response
    staff.filter.return_value.order_by.side_effect = [staffers]
    chatter.return_value.single_conversation.side_effect = [[]]
    result = tested.select_staff("assignedTo", "theComment")
    assert result is None
    calls = [call.filter(active=True), call.filter().order_by('last_name')]
    assert staff.mock_calls == calls
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompt),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()


@patch.object(TaskLabel, 'objects')
@patch.object(Helper, "chatter")
def test_select_labels(chatter, task_labels):
    def reset_mocks():
        chatter.reset_mock()
        task_labels.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "The goal is to identify the most relevant labels linked to a specific task.",
        "",
    ]
    user_prompt = [
        'Here is the comment provided by the healthcare provider in regards to the task:',
        '```text',
        'labels: theLabels',
        ' -- ',
        'comment: theComment',
        '',
        '```',
        '',
        'Among the following labels, identify all the most relevant to characterized the task:',
        '',
        ' * Label1 (labelId: 741)\n * Label2 (labelId: 596)\n * Label3 (labelId: 963)',
        '',
        'Please, present your findings in a JSON format within a Markdown code block like:',
        '```json',
        '[{"labelId": "the label id, as int", "name": "the name of the label"}]',
        '```',
        '',
    ]
    tested = helper_instance()

    # no labels
    task_labels.filter.return_value.order_by.side_effect = [[]]
    chatter.return_value.single_conversation.side_effect = []
    result = tested.select_labels("theLabels", "theComment")
    assert result is None
    calls = [call.filter(active=True), call.filter().order_by('name')]
    assert task_labels.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()

    # staff
    labels = [
        TaskLabel(dbid=741, name="Label1"),
        TaskLabel(dbid=596, name="Label2"),
        TaskLabel(dbid=963, name="Label3"),
    ]
    # -- response
    task_labels.filter.return_value.order_by.side_effect = [labels]
    chatter.return_value.single_conversation.side_effect = [[{"labelId": 596, "name": "Label2"}, {"labelId": 963, "name": "Label3"}]]
    result = tested.select_labels("theLabels", "theComment")
    expected = ["Label2", "Label3"]
    assert result == expected
    calls = [call.filter(active=True), call.filter().order_by('name')]
    assert task_labels.mock_calls == calls
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompt),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()
    # -- no response
    task_labels.filter.return_value.order_by.side_effect = [labels]
    chatter.return_value.single_conversation.side_effect = [[]]
    result = tested.select_labels("theLabels", "theComment")
    assert result is None
    calls = [call.filter(active=True), call.filter().order_by('name')]
    assert task_labels.mock_calls == calls
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompt),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()


@patch.object(Task, "select_labels")
@patch.object(Task, "select_staff")
def test_command_from_json(select_staff, select_labels):
    def reset_mocks():
        select_staff.reset_mock()
        select_labels.reset_mock()

    tested = helper_instance()

    assignee = TaskAssigner(to=AssigneeType.STAFF, id=584)
    labels = ["label1", "label2"]

    tests = [
        (assignee, labels),
        (None, labels),
        (assignee, None),
        (None, None),
    ]
    for side_effect_staff, side_effect_labels in tests:
        # all parameters
        parameters = {
            "title": "theTitle",
            "dueDate": "2025-02-04",
            "assignTo": "theAssignTo",
            "labels": "theLabels",
            "comment": "theComment",
        }
        select_staff.side_effect = [side_effect_staff]
        select_labels.side_effect = [side_effect_labels]
        result = tested.command_from_json(parameters)
        expected = TaskCommand(
            title="theTitle",
            due_date=date(2025, 2, 4),
            comment="theComment",
            assign_to=side_effect_staff,
            labels=side_effect_labels,
            note_uuid="noteUuid",
        )
        assert result == expected
        calls = [call("theAssignTo", 'theComment')]
        assert select_staff.mock_calls == calls
        calls = [call("theLabels", 'theComment')]
        assert select_labels.mock_calls == calls
        reset_mocks()

        # no assignee
        parameters = {
            "title": "theTitle",
            "dueDate": "2025-02-04",
            "assignTo": "",
            "labels": "theLabels",
            "comment": "theComment",
        }
        select_staff.side_effect = []
        select_labels.side_effect = [side_effect_labels]
        result = tested.command_from_json(parameters)
        expected = TaskCommand(
            title="theTitle",
            due_date=date(2025, 2, 4),
            comment="theComment",
            labels=side_effect_labels,
            note_uuid="noteUuid",
        )
        assert result == expected
        assert select_staff.mock_calls == []
        calls = [call("theLabels", 'theComment')]
        assert select_labels.mock_calls == calls
        reset_mocks()

        # no labels
        parameters = {
            "title": "theTitle",
            "dueDate": "2025-02-04",
            "assignTo": "theAssignTo",
            "labels": "",
            "comment": "theComment",
        }
        select_staff.side_effect = [side_effect_staff]
        select_labels.side_effect = []
        result = tested.command_from_json(parameters)
        expected = TaskCommand(
            title="theTitle",
            due_date=date(2025, 2, 4),
            comment="theComment",
            assign_to=side_effect_staff,
            note_uuid="noteUuid",
        )
        assert result == expected
        calls = [call("theAssignTo", 'theComment')]
        assert select_staff.mock_calls == calls
        assert select_labels.mock_calls == []
        reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "title": "title of the task",
        "dueDate": "YYYY-MM-DD",
        "assignTo": "information about the assignee for the task, or empty",
        "labels": "information about the labels to link to the task, or empty",
        "comment": "comment related to the task provided by the clinician",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Specific task assigned to someone at the healthcare facility, including the speaking clinician. "
                "A task might include a due date and a specific assignee. "
                "There can be only one task per instruction, and no instruction in the lack of.")
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
