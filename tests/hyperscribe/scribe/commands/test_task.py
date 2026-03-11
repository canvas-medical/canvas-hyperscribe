from datetime import date

from canvas_sdk.commands.commands.task import AssigneeType

from hyperscribe.scribe.commands.task import TaskParser


def test_extract() -> None:
    parser = TaskParser()
    proposal = parser.extract("Follow up with cardiology")
    assert proposal is not None
    assert proposal.command_type == "task"
    assert proposal.data["title"] == "Follow up with cardiology"
    assert proposal.display == "Follow up with cardiology"


def test_extract_empty_returns_empty_title() -> None:
    parser = TaskParser()
    proposal = parser.extract("")
    assert proposal is not None
    assert proposal.data["title"] == ""


def test_build_full() -> None:
    parser = TaskParser()
    data = {
        "title": "Order blood work",
        "due_date": "2026-03-15",
        "assign_to": {"to": "staff", "id": 42},
    }
    cmd = parser.build(data, "note-uuid-123", "cmd-uuid")

    assert cmd.title == "Order blood work"
    assert cmd.due_date == date(2026, 3, 15)
    assert cmd.note_uuid == "note-uuid-123"
    assert cmd.assign_to is not None
    assert cmd.assign_to["to"] == AssigneeType("staff")
    assert cmd.assign_to["id"] == 42


def test_build_no_assignee_no_due_date() -> None:
    parser = TaskParser()
    cmd = parser.build({"title": "Call patient"}, "note-uuid", "cmd-uuid")

    assert cmd.title == "Call patient"
    assert cmd.due_date is None
    assert cmd.assign_to is None


def test_build_team_assignee() -> None:
    parser = TaskParser()
    data = {
        "title": "Review labs",
        "assign_to": {"to": "team", "id": 7},
    }
    cmd = parser.build(data, "note-uuid", "cmd-uuid")

    assert cmd.assign_to is not None
    assert cmd.assign_to["to"] == AssigneeType("team")
    assert cmd.assign_to["id"] == 7


def test_build_empty_data_defaults() -> None:
    parser = TaskParser()
    cmd = parser.build({}, "note-uuid", "cmd-uuid")

    assert cmd.title == ""
    assert cmd.due_date is None
    assert cmd.assign_to is None
