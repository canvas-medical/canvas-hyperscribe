import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from canvas_sdk.commands.commands.questionnaire.question import ResponseOption

from evaluations.constants import Constants
from hyperscribe.libraries.auditor import Auditor
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings


class AuditorStore(Auditor):
    def __init__(self, case: str, cycle: int, settings: Settings, s3_credentials: AwsS3Credentials) -> None:
        super().__init__()
        self.settings = settings
        self.s3_credentials = s3_credentials
        self.case = case
        self.cycle = max(0, cycle)
        self.cycle_key = f"{Constants.CASE_CYCLE_SUFFIX}_{self.cycle:03d}"

    def case_prepare(self) -> None:
        raise NotImplementedError

    def case_update_limited_cache(self, limited_cache: dict) -> None:
        raise NotImplementedError

    def case_finalize(self, errors: list[str]) -> None:
        raise NotImplementedError

    def upsert_audio(self, label: str, audio: bytes) -> None:
        raise NotImplementedError

    def upsert_json(self, label: str, content: dict) -> None:
        raise NotImplementedError

    def get_json(self, label: str) -> dict:
        raise NotImplementedError

    def limited_chart(self) -> dict:
        raise NotImplementedError

    def transcript(self) -> list[Line]:
        raise NotImplementedError

    def full_transcript(self) -> dict[str, list[Line]]:
        raise NotImplementedError

    def set_cycle(self, cycle: int) -> None:
        self.cycle = max(0, self.cycle, cycle)
        self.cycle_key = f"{Constants.CASE_CYCLE_SUFFIX}_{self.cycle:03d}"

    def identified_transcript(self, audios: list[bytes], transcript: list[Line]) -> bool:
        for idx, audio in enumerate(audios):
            audio_file = f"{self.cycle_key}_{idx:02d}"
            self.upsert_audio(audio_file, audio)

        label = Constants.AUDIO2TRANSCRIPT
        self.upsert_json(
            label,
            {self.cycle_key: [line.to_json() for line in transcript]},
        )
        return True

    def found_instructions(
            self,
            transcript: list[Line],
            initial_instructions: list[Instruction],
            cumulated_instructions: list[Instruction],
    ) -> bool:
        label = Constants.TRANSCRIPT2INSTRUCTIONS
        content = self.get_json(label)
        content[self.cycle_key] = {
            "transcript": [line.to_json() for line in transcript],
            "instructions": {
                "initial": [
                    instruction.to_json(True) | {"uuid": Constants.IGNORED_KEY_VALUE}
                    for instruction in initial_instructions
                ],
                "result": [
                    instruction.to_json(False) | {"uuid": Constants.IGNORED_KEY_VALUE}
                    for instruction in cumulated_instructions
                ],
            },
        }
        self.upsert_json(label, content)
        return True

    def computed_parameters(self, instructions: list[InstructionWithParameters]) -> bool:
        label = Constants.INSTRUCTION2PARAMETERS
        content: dict = self.get_json(label)
        if self.cycle_key not in content:
            content[self.cycle_key] = {
                "instructions": [],
                "parameters": [],
            }
        for instruction in instructions:
            content[self.cycle_key]["instructions"].append(instruction.to_json(False))
            content[self.cycle_key]["parameters"].append(instruction.parameters)
        #
        self.upsert_json(label, content)
        return True

    def computed_commands(self, instructions: list[InstructionWithCommand]) -> bool:
        label = Constants.PARAMETERS2COMMAND
        content: dict = self.get_json(label)
        if self.cycle_key not in content:
            content[self.cycle_key] = {
                "instructions": [],
                "parameters": [],
                "commands": [],
            }
        for instruction in instructions:
            content[self.cycle_key]["instructions"].append(instruction.to_json(False))
            content[self.cycle_key]["parameters"].append(instruction.parameters)
            content[self.cycle_key]["commands"].append({
                "module": instruction.command.__module__,
                "class": instruction.command.__class__.__name__,
                "attributes": instruction.command.values | {
                    "command_uuid": Constants.IGNORED_KEY_VALUE,
                    "note_uuid": Constants.IGNORED_KEY_VALUE,
                },
            })
        self.upsert_json(label, content)
        return True

    def computed_questionnaires(
            self,
            transcript: list[Line],
            initial_instructions: list[Instruction],
            instructions_with_command: list[InstructionWithCommand],
    ) -> bool:
        label = Constants.STAGED_QUESTIONNAIRES
        content = self.get_json(label)
        content[self.cycle_key] = {
            "transcript": [line.to_json() for line in transcript],
            "instructions": [
                instruction.to_json(False) | {"uuid": Constants.IGNORED_KEY_VALUE}
                for instruction in initial_instructions
            ],
            "commands": [
                {
                    "module": instruction.command.__module__,
                    "class": instruction.command.__class__.__name__,
                    "attributes": instruction.command.values | {
                        "command_uuid": Constants.IGNORED_KEY_VALUE,
                        "note_uuid": Constants.IGNORED_KEY_VALUE,
                    },
                }
                for instruction in instructions_with_command
            ],
        }
        self.upsert_json(label, content)
        return True

    def summarized_generated_commands(self) -> list[dict]:
        result: dict[str, dict] = {}

        # common commands
        cycles = self.get_json(Constants.PARAMETERS2COMMAND)
        for cycle, content in cycles.items():
            for instruction, command in zip(content["instructions"], content["commands"]):
                result[instruction["uuid"]] = {
                    "instruction": instruction["information"],
                    "command": {
                        "module": command["module"],
                        "class": command["class"],
                        "attributes": {
                            key: value
                            for key, value in command["attributes"].items()
                            if key not in ("note_uuid", "command_uuid")
                        },
                    },
                }

        # questionnaires - command is from the last cycle
        cycles = self.get_json(Constants.STAGED_QUESTIONNAIRES)
        if values := list(cycles.values()):
            content = values[-1]
            for index, command in enumerate(content["commands"]):
                attributes: dict[str, str] = {}
                instruction = content["instructions"][index]
                questionnaire = json.loads(instruction["information"])
                responses = command["attributes"]["questions"]
                for question in questionnaire["questions"]:
                    if f"question-{question['dbid']}" not in responses:
                        continue
                    response = responses[f"question-{question['dbid']}"]

                    if question["type"] == ResponseOption.TYPE_CHECKBOX:
                        attributes[question["label"]] = ", ".join([
                            f'{item["text"]} ({item["comment"]})' if item["comment"] else item["text"]
                            for item in response if item["selected"]
                        ])
                    elif question["type"] == ResponseOption.TYPE_RADIO:
                        for item in question["responses"]:
                            if item["dbid"] == response:
                                attributes[question["label"]] = item["value"]
                    elif question["type"] == ResponseOption.TYPE_INTEGER:
                        attributes[question["label"]] = response
                    else:  # question["type"] == ResponseOption.TYPE_TEXT:
                        attributes[question["label"]] = response

                result[f"questionnaire_{index:02d}"] = {
                    "instruction": f'{instruction["instruction"]}: {questionnaire["name"]}',
                    "command": {
                        "module": command["module"],
                        "class": command["class"],
                        "attributes": attributes,
                    },
                }
        return list(result.values())

    def summarized_generated_commands_as_instructions(self) -> list[Instruction]:
        result: dict[str, Instruction] = {}

        # common commands
        cycles = self.get_json(Constants.PARAMETERS2COMMAND)
        for cycle, content in cycles.items():
            for instruction in content["instructions"]:
                result[instruction["uuid"]] = Instruction(
                    uuid=instruction["uuid"],
                    index=instruction["index"],
                    instruction=instruction["instruction"],
                    information=instruction["information"],
                    is_new=instruction["isNew"],
                    is_updated=instruction["isUpdated"],
                )

        # questionnaires - result is from the last cycle
        cycles = self.get_json(Constants.STAGED_QUESTIONNAIRES)
        if values := list(cycles.values()):
            content = values[-1]
            for index, command in enumerate(content["commands"]):
                instruction = content["instructions"][index]
                questionnaire = json.loads(instruction["information"])
                responses = command["attributes"]["questions"]
                for question in questionnaire["questions"]:
                    if f"question-{question['dbid']}" not in responses:
                        continue
                    response = responses[f"question-{question['dbid']}"]

                    if question["type"] == ResponseOption.TYPE_CHECKBOX:
                        for option in response:
                            for item in question["responses"]:
                                if item["dbid"] == option["value"]:
                                    item["selected"] = option["selected"]
                                    item["comment"] = option["comment"]
                    elif question["type"] == ResponseOption.TYPE_RADIO:
                        for item in question["responses"]:
                            item["selected"] = bool(item["dbid"] == response)
                    elif question["type"] == ResponseOption.TYPE_INTEGER:
                        for item in question["responses"]:
                            item["selected"] = True
                            item["value"] = int(response)

                    else:  # question["type"] == ResponseOption.TYPE_TEXT:
                        for item in question["responses"]:
                            item["selected"] = True
                            item["value"] = response

                result[f"questionnaire_{index:02d}"] = Instruction(
                    uuid=instruction["uuid"],
                    index=instruction["index"],
                    instruction=instruction["instruction"],
                    information=json.dumps(questionnaire),
                    is_new=instruction["isNew"],
                    is_updated=instruction["isUpdated"],
                )

        return list(result.values())

    def generate_html_summary(self) -> Path:
        template_file = Path(__file__).parent / f"templates/summary.html"
        data = json.dumps(self.summarized_generated_commands())
        with template_file.open("r") as source:
            with NamedTemporaryFile(delete=False, suffix=".html", mode="w") as target:
                target.write(source
                             .read()
                             .replace("{{theCase}}", self.case)
                             .replace("{{theData}}", data))
                return Path(target.name)
