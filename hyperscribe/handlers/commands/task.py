import json

from canvas_sdk.commands.commands.task import TaskCommand, TaskAssigner, AssigneeType
from canvas_sdk.v1.data import TaskLabel, Staff

from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.structures.coded_item import CodedItem


class Task(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_TASK

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        comment = data.get("comment") or "n/a"
        due_date = data.get("due_date") or "n/a"
        if task := data.get("title"):
            labels = "/".join([
                label
                for item in data.get("labels") or []
                if (label := item.get("text"))
            ]) or "n/a"
            return CodedItem(label=f"{task}: {comment} (due on: {due_date}, labels: {labels})", code="", uuid="")
        return None

    def select_staff(self, assigned_to: str, comment: str) -> None | TaskAssigner:
        staff_members = Staff.objects.filter(active=True).order_by("last_name")
        if not staff_members:
            return None

        system_prompt = [
            "The conversation is in the medical context.",
            "",
            "The goal is to identify the most relevant staff member to assign a specific task to.",
            "",
        ]
        user_prompt = [
            'Here is the comment provided by the healthcare provider in regards to the task:',
            '```text',
            f"assign to: {assigned_to}",
            " -- ",
            f'comment: {comment}',
            "",
            '```',
            "",
            'Among the following staff members, identify the most relevant one:',
            '',
            "\n".join(f' * {staff.first_name} {staff.last_name} (staffId: {staff.dbid})' for staff in staff_members),
            '',
            'Please, present your findings in a JSON format within a Markdown code block like:',
            '```json',
            json.dumps([{"staffId": "the staff member id, as int", "name": "the name of the staff member"}]),
            '```',
            '',
        ]
        if response := Helper.chatter(self.settings).single_conversation(system_prompt, user_prompt):
            staff_id = int(response[0]["staffId"])
            return TaskAssigner(to=AssigneeType.STAFF, id=staff_id)
        return None

    def select_labels(self, labels: str, comment: str) -> None | list[str]:
        label_db = TaskLabel.objects.filter(active=True).order_by("name")
        if not label_db:
            return None

        system_prompt = [
            "The conversation is in the medical context.",
            "",
            "The goal is to identify the most relevant labels linked to a specific task.",
            "",
        ]
        user_prompt = [
            'Here is the comment provided by the healthcare provider in regards to the task:',
            '```text',
            f"labels: {labels}",
            " -- ",
            f'comment: {comment}',
            "",
            '```',
            "",
            'Among the following labels, identify all the most relevant to characterized the task:',
            '',
            "\n".join(f' * {label.name} (labelId: {label.dbid})' for label in label_db),
            '',
            'Please, present your findings in a JSON format within a Markdown code block like:',
            '```json',
            json.dumps([{"labelId": "the label id, as int", "name": "the name of the label"}]),
            '```',
            '',
        ]
        if response := Helper.chatter(self.settings).single_conversation(system_prompt, user_prompt):
            return [label["name"] for label in response]
        return None

    def command_from_json(self, parameters: dict) -> None | TaskCommand:
        result = TaskCommand(
            title=parameters["title"],
            due_date=Helper.str2date(parameters["dueDate"]),
            comment=parameters["comment"],
            note_uuid=self.note_uuid,
        )
        if parameters["assignTo"]:
            result.assign_to = self.select_staff(parameters["assignTo"], parameters["comment"])

        if parameters["labels"]:
            result.labels = self.select_labels(parameters["labels"], parameters["comment"])

        return result

    def command_parameters(self) -> dict:
        return {
            "title": "title of the task",
            "dueDate": "YYYY-MM-DD",
            "assignTo": "information about the assignee for the task, or empty",
            "labels": "information about the labels to link to the task, or empty",
            "comment": "comment related to the task provided by the clinician",
        }

    def instruction_description(self) -> str:
        return ("Specific task assigned to someone at the healthcare facility, including the speaking clinician. "
                "A task might include a due date and a specific assignee. "
                "There can be only one task per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
