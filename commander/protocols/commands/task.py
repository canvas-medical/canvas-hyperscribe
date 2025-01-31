import json

from canvas_sdk.commands.commands.task import TaskCommand, TaskAssigner, AssigneeType
from canvas_sdk.v1.data import TaskLabel, Staff
from commander.protocols.commands.base import Base

from commander.protocols.constants import Constants
from commander.protocols.helper import Helper
from commander.protocols.openai_chat import OpenaiChat


class Task(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "task"

    def command_from_json(self, parameters: dict) -> None | TaskCommand:
        result = TaskCommand(
            title=parameters["title"],
            due_date=Helper.str2date(parameters["dueDate"]),
            comment=parameters["comment"],
            note_uuid=self.note_uuid,
        )

        conversation = OpenaiChat(self.settings.openai_key, Constants.OPENAI_CHAT_TEXT)
        if parameters["assignTo"]:
            staff_members = Staff.objects.filter(active=True).order_by("last_name")
            conversation.system_prompt = [
                "The conversation is in the medical context.",
                "",
                "The goal is to identify the most relevant staff member to assign a specific task to.",
                "",
            ]
            conversation.user_prompt = [
                'Here is the comment provided by the healthcare provider in regards to the task:',
                '```text',
                f"assign to: {parameters['assignTo']}",
                " -- ",
                f'comment: {parameters["comment"]}',
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
            response = conversation.chat()
            if response.has_error is False and response.content:
                staff_id = int(response.content[0]["staffId"])
                result.assign_to = TaskAssigner(
                    to=AssigneeType.STAFF,
                    id=staff_id,
                )
        if parameters["labels"]:
            labels = TaskLabel.objects.filter(active=True).order_by("name")
            conversation.system_prompt = [
                "The conversation is in the medical context.",
                "",
                "The goal is to identify the most relevant labels linked to a specific task.",
                "",
            ]
            conversation.user_prompt = [
                'Here is the comment provided by the healthcare provider in regards to the task:',
                '```text',
                f"labels: {parameters['labels']}",
                " -- ",
                f'comment: {parameters["comment"]}',
                "",
                '```',
                "",
                'Among the following labels, identify all the most relevant to characterized the task:',
                '',
                "\n".join(f' * {label.name} (labelId: {label.dbid})' for label in labels),
                '',
                'Please, present your findings in a JSON format within a Markdown code block like:',
                '```json',
                json.dumps([{"labelId": "the label id, as int", "name": "the name of the label"}]),
                '```',
                '',
            ]
            response = conversation.chat(True)
            if response.has_error is False and response.content:
                result.labels = [l["name"] for l in response.content]

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
