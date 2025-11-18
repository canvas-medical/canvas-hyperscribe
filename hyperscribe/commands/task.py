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
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_PLAN

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        comment = data.get("comment") or "n/a"
        due_date = data.get("due_date") or "n/a"
        if task := data.get("title"):
            labels = "/".join([label for item in data.get("labels") or [] if (label := item.get("text"))]) or "n/a"
            return CodedItem(label=f"{task}: {comment} (due on: {due_date}, labels: {labels})", code="", uuid="")
        return None

    def select_assignee(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
        assigned_to: str,
        comment: str,
    ) -> None | TaskAssigner:
        staffs = self.cache.existing_staff_members()
        roles = self.cache.existing_roles()
        teams = self.cache.existing_teams()
        if not (staffs or roles or teams):
            return None

        system_prompt = [
            "Medical context: identify the single most relevant staff member, team or role for task assignment.",
            "",
        ]
        user_prompt = [
            "Provider data:",
            "```text",
            f"assign to: {assigned_to}",
            f"comment: {comment}",
            "```",
            "",
            "Staff, teams and roles:",
            "\n".join(f" * {staff.label} (type: staff, id: {staff.uuid})" for staff in staffs),
            "\n".join(f" * {team.label} (type: team, id: {team.uuid})" for team in teams),
            "\n".join(f" * {role.label} (type: role, id: {role.uuid})" for role in roles),
            "",
            "Return the ONE most relevant assignee as JSON in Markdown code block:",
            "```json",
            json.dumps([{"type": "staff/team/role", "id": "int", "name": "entity name"}]),
            "```",
            "",
        ]
        schemas = JsonSchema.get(["selector_assignee"])
        if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
            entity_id = int(response[0]["id"])
            entity_name = response[0]["name"]
            entity_type = response[0]["type"]
            self.add_code2description(str(entity_id), entity_name)
            return TaskAssigner(to=AssigneeType(entity_type), id=entity_id)
        return None

    def select_labels(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
        labels: str,
        comment: str,
    ) -> None | list[str]:
        task_labels = self.cache.existing_task_labels()
        if not task_labels:
            return None

        system_prompt = [
            "Medical context: identify all relevant labels for the task.",
            "",
        ]
        user_prompt = [
            "Provider data:",
            "```text",
            f"labels: {labels}",
            f"comment: {comment}",
            "```",
            "",
            "Available labels:",
            "\n".join(f" * {label.label} (labelId: {label.uuid})" for label in task_labels),
            "",
            "Return all relevant labels as JSON in Markdown code block:",
            "```json",
            json.dumps([{"labelId": "int", "name": "label name"}]),
            "```",
            "",
        ]
        schemas = JsonSchema.get(["selector_labels"])
        if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
            return [label["name"] for label in response]
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = TaskCommand(
            title=instruction.parameters["title"],
            due_date=Helper.str2date(instruction.parameters["dueDate"]),
            comment=instruction.parameters["comment"],
            note_uuid=self.identification.note_uuid,
        )
        if instruction.parameters["assignTo"]:
            result.assign_to = self.select_assignee(
                instruction,
                chatter,
                instruction.parameters["assignTo"],
                instruction.parameters["comment"],
            )

        if instruction.parameters["labels"]:
            result.labels = self.select_labels(
                instruction,
                chatter,
                instruction.parameters["labels"],
                instruction.parameters["comment"],
            )

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "title": "",
            "dueDate": "",
            "assignTo": "",
            "labels": "",
            "comment": "",
        }

    def command_parameters_schemas(self) -> list[dict]:
        return [
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Task title",
                        },
                        "dueDate": {
                            "type": "string",
                            "format": "date",
                            "description": "Due date YYYY-MM-DD",
                        },
                        "assignTo": {
                            "type": "string",
                            "description": "Task assignee (person/team/role); empty if unassigned",
                        },
                        "labels": {
                            "type": "string",
                            "description": "Task labels; empty if none",
                        },
                        "comment": {
                            "type": "string",
                            "description": "Clinician's task comment",
                        },
                    },
                    "required": ["title", "dueDate", "assignTo", "labels", "comment"],
                },
            },
        ]

    def instruction_description(self) -> str:
        return (
            "Specific task assigned to someone or a group at the healthcare facility, "
            "including the speaking clinician. "
            "A task might include a due date and a specific assignee. "
            "There can be one and only one task per instruction, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
