from canvas_sdk.commands.commands.task import TaskCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.task import Task
from commander.protocols.structures.settings import Settings


def helper_instance() -> Task:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return Task(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = Task
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "task"
    assert result == expected


def te0st_command_from_json():
    tested = helper_instance()
    result = tested.command_from_json({})
    expected = TaskCommand()
    assert result == expected


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
