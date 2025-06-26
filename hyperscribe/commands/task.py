import json

from canvas_sdk.commands.commands.task import TaskCommand, TaskAssigner, AssigneeType

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


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

    def select_staff(self, instruction: InstructionWithParameters, chatter: LlmBase, assigned_to: str, comment: str) -> None | TaskAssigner:
        staff_members = self.cache.existing_staff_members()
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
            "\n".join(f' * {staff.label} (staffId: {staff.uuid})' for staff in staff_members),
            '',
            'Please, present your findings in a JSON format within a Markdown code block like:',
            '```json',
            json.dumps([{"staffId": "the staff member id, as int", "name": "the name of the staff member"}]),
            '```',
            '',
        ]
        schemas = JsonSchema.get(["selector_staff"])
        if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
            staff_id = int(response[0]["staffId"])
            return TaskAssigner(to=AssigneeType.STAFF, id=staff_id)
        return None

    def select_labels(self, instruction: InstructionWithParameters, chatter: LlmBase, labels: str, comment: str) -> None | list[str]:
        task_labels = self.cache.existing_task_labels()
        if not task_labels:
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
            "\n".join(f' * {label.label} (labelId: {label.uuid})' for label in task_labels),
            '',
            'Please, present your findings in a JSON format within a Markdown code block like:',
            '```json',
            json.dumps([{"labelId": "the label id, as int", "name": "the name of the label"}]),
            '```',
            '',
        ]
        schemas = JsonSchema.get(["selector_label"])
        if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
            return [label["name"] for label in response]
        return None

    def command_from_json(self, instruction: InstructionWithParameters, chatter: LlmBase) -> InstructionWithCommand | None:
        result = TaskCommand(
            title=instruction.parameters["title"],
            due_date=Helper.str2date(instruction.parameters["dueDate"]),
            comment=instruction.parameters["comment"],
            note_uuid=self.identification.note_uuid,
        )
        if instruction.parameters["assignTo"]:
            result.assign_to = self.select_staff(instruction, chatter, instruction.parameters["assignTo"], instruction.parameters["comment"])

        if instruction.parameters["labels"]:
            result.labels = self.select_labels(instruction, chatter, instruction.parameters["labels"], instruction.parameters["comment"])

        return InstructionWithCommand.add_command(instruction, result)

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
