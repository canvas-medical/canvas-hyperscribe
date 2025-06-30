import json
from pathlib import Path
from typing import Generator

from canvas_sdk.commands.commands.questionnaire.question import ResponseOption

from evaluations.constants import Constants
from hyperscribe.libraries.auditor import Auditor
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.line import Line


class AuditorFile(Auditor):
    AUDIOS_FOLDER = "audios"
    AUDIO2TRANSCRIPT_FILE = "audio2transcript.json"
    INSTRUCTION2PARAMETERS_FILE = "instruction2parameters.json"
    PARAMETERS2COMMAND_FILE = "parameters2command.json"
    STAGED_QUESTIONNAIRES_FILE = "staged_questionnaires.json"
    TRANSCRIPT2INSTRUCTIONS_FILE = "transcript2instructions.json"
    SUMMARY_JSON_INITIAL_FILE = "summary_initial.json"
    SUMMARY_JSON_REVISED_FILE = "summary_revised.json"
    SUMMARY_HTML_FILE = "summary.html"

    def __init__(self, case: str, cycle: int):
        super().__init__()
        self.case = case
        self.cycle = cycle

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, AuditorFile)
        return bool(self.case == other.case and self.cycle == other.cycle)

    def case_folder(self) -> Path:
        result = Path(__file__).parent / f"cases/{self.case}"
        if result.exists() is False:
            result.mkdir()
        return result

    def case_file(self, file_name: str) -> Path:
        return self.case_folder() / file_name

    def audio_case_files(self) -> Generator[Path, None, None]:
        audio_folder = self.case_folder() / self.AUDIOS_FOLDER
        if audio_folder.exists():
            yield from audio_folder.glob(f"{Constants.CASE_CYCLE_SUFFIX}_???_??.mp3")

    def case_files(self, include_audio2transcript: bool) -> Generator[Path, None, None]:
        json_files = [
            self.INSTRUCTION2PARAMETERS_FILE,
            self.PARAMETERS2COMMAND_FILE,
            self.STAGED_QUESTIONNAIRES_FILE,
            self.TRANSCRIPT2INSTRUCTIONS_FILE,
            self.SUMMARY_JSON_INITIAL_FILE,
        ]

        if include_audio2transcript:
            yield from self.audio_case_files()
            json_files.append(self.AUDIO2TRANSCRIPT_FILE)

        for file_name in json_files:
            file = self.case_file(file_name)
            if file.exists():
                yield file

    def is_ready(self) -> bool:
        for _ in self.case_files(False):
            return False
        return True

    def is_complete(self) -> bool:
        folder = Path(__file__).parent / f"cases/{self.case}"
        if folder.exists() is False:
            return False
        file_names = [
            # self.AUDIO2TRANSCRIPT_FILE,
            self.INSTRUCTION2PARAMETERS_FILE,
            self.PARAMETERS2COMMAND_FILE,
            self.STAGED_QUESTIONNAIRES_FILE,
            self.TRANSCRIPT2INSTRUCTIONS_FILE,
            self.SUMMARY_JSON_INITIAL_FILE,
        ]
        for file_name in file_names:
            file = self.case_file(file_name)
            if file.exists() is False:
                return False
        return True

    def reset(self, delete_audios: bool) -> None:
        for case_file in self.case_files(delete_audios):
            case_file.unlink(True)
        if delete_audios:
            audio_folder = self.case_folder() / self.AUDIOS_FOLDER
            if audio_folder.exists():
                audio_folder.rmdir()

    def transcript(self) -> list[Line]:
        json_file = self.case_file(self.AUDIO2TRANSCRIPT_FILE)
        if json_file.exists():
            content = json.load(json_file.open("r"))
            if transcript := content.get(f"{Constants.CASE_CYCLE_SUFFIX}_{self.cycle:03d}"):
                return Line.load_from_json(transcript)
        return []


    def identified_transcript(self, audios: list[bytes], transcript: list[Line]) -> bool:
        audio_folder = self.case_folder() / self.AUDIOS_FOLDER
        if audio_folder.exists() is False:
            audio_folder.mkdir()

        for idx, audio in enumerate(audios):
            audio_file = audio_folder / f"{Constants.CASE_CYCLE_SUFFIX}_{self.cycle:03d}_{idx:02d}.mp3"
            with audio_file.open("wb") as fp:
                fp.write(audio)

        json_file = self.case_file(self.AUDIO2TRANSCRIPT_FILE)
        content = {}
        if json_file.exists():
            content = json.load(json_file.open("r"))
        content[f"{Constants.CASE_CYCLE_SUFFIX}_{self.cycle:03d}"] = [t.to_json() for t in transcript]
        with json_file.open("w") as fp:
            json.dump(content, fp, indent=2)

        return json_file.exists()

    def found_instructions(
            self,
            transcript: list[Line],
            initial_instructions: list[Instruction],
            cumulated_instructions: list[Instruction],
    ) -> bool:
        file = self.case_file(self.TRANSCRIPT2INSTRUCTIONS_FILE)
        content = {}
        if file.exists():
            content = json.load(file.open("r"))
        cycle_key = f"{Constants.CASE_CYCLE_SUFFIX}_{self.cycle:03d}"
        content[cycle_key] = {
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
        with file.open("w") as fp:
            json.dump(content, fp, indent=2)
        return file.exists()

    def computed_parameters(self, instructions: list[InstructionWithParameters]) -> bool:
        file = self.case_file(self.INSTRUCTION2PARAMETERS_FILE)
        content = {}
        if file.exists():
            content = json.load(file.open("r"))

        cycle_key = f"{Constants.CASE_CYCLE_SUFFIX}_{self.cycle:03d}"
        if cycle_key not in content:
            content[cycle_key] = {
                "instructions": [],
                "parameters": [],
            }
        for instruction in instructions:
            content[cycle_key]["instructions"].append(instruction.to_json(False))
            content[cycle_key]["parameters"].append(instruction.parameters)

        with file.open("w") as fp:
            json.dump(content, fp, indent=2)
        return file.exists()

    def computed_commands(self, instructions: list[InstructionWithCommand]) -> bool:
        file = self.case_file(self.PARAMETERS2COMMAND_FILE)
        content = {}
        if file.exists():
            content = json.load(file.open("r"))

        cycle_key = f"{Constants.CASE_CYCLE_SUFFIX}_{self.cycle:03d}"
        if cycle_key not in content:
            content[cycle_key] = {
                "instructions": [],
                "parameters": [],
                "commands": [],
            }
        for instruction in instructions:
            content[cycle_key]["instructions"].append(instruction.to_json(False))
            content[cycle_key]["parameters"].append(instruction.parameters)
            content[cycle_key]["commands"].append({
                "module": instruction.command.__module__,
                "class": instruction.command.__class__.__name__,
                "attributes": instruction.command.values | {
                    "command_uuid": Constants.IGNORED_KEY_VALUE,
                    "note_uuid": Constants.IGNORED_KEY_VALUE,
                },
            })

        with file.open("w") as fp:
            json.dump(content, fp, indent=2)
        return file.exists()

    def computed_questionnaires(
            self,
            transcript: list[Line],
            initial_instructions: list[Instruction],
            instructions_with_command: list[InstructionWithCommand],
    ) -> bool:
        file = self.case_file(self.STAGED_QUESTIONNAIRES_FILE)
        content = {}
        if file.exists():
            content = json.load(file.open("r"))
        content[f"{Constants.CASE_CYCLE_SUFFIX}_{self.cycle:03d}"] = {
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
        with file.open("w") as fp:
            json.dump(content, fp, indent=2)
        return file.exists()

    def summarized_generated_commands_as_instructions(self) -> list[Instruction]:
        result: dict[str, Instruction] = {}

        # common commands
        file = self.case_file(self.PARAMETERS2COMMAND_FILE)
        if file.exists():
            cycles = json.load(file.open("r"))
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
        file = self.case_file(self.STAGED_QUESTIONNAIRES_FILE)
        if file.exists():
            cycles = json.load(file.open("r"))
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

    def summarized_generated_commands(self) -> list[dict]:
        result: dict[str, dict] = {}

        # common commands
        summary_initial = self.case_file(self.PARAMETERS2COMMAND_FILE)
        if summary_initial.exists():
            cycles = json.load(summary_initial.open("r"))
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
        summary_initial = self.case_file(self.STAGED_QUESTIONNAIRES_FILE)
        if summary_initial.exists():
            cycles = json.load(summary_initial.open("r"))
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

    def generate_commands_summary(self) -> Path:
        data = self.summarized_generated_commands()
        summary_initial = self.case_file(self.SUMMARY_JSON_INITIAL_FILE)
        with summary_initial.open("w") as f:
            json.dump(data, f, indent=2)

        summary_revised = self.case_file(self.SUMMARY_JSON_REVISED_FILE)
        if summary_revised.exists() is False:
            with summary_revised.open("w") as f:
                json.dump(data, f, indent=2)

        return summary_initial

    def generate_html_summary(self) -> Path | None:
        if self.is_complete() is False:
            return None
        template_file = Path(__file__).parent / f"templates/summary.html"
        data_file = self.case_file(self.SUMMARY_JSON_REVISED_FILE)
        html_file = self.case_file(self.SUMMARY_HTML_FILE)
        with template_file.open("r") as source:
            with html_file.open("w") as target:
                target.write(source
                             .read()
                             .replace("{{theCase}}", self.case)
                             .replace("{{theData}}", data_file.open("r").read()))
        return html_file
