import json
import re
from pathlib import Path
from typing import Generator

from evaluations.constants import Constants
from hyperscribe.libraries.auditor import Auditor
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.line import Line


class AuditorFile(Auditor):
    def __init__(self, case: str):
        super().__init__()
        self.case = case

    def _case_files(self) -> Generator[Path, None, None]:
        paths = [
            ('audio2transcript/inputs_mp3', 'mp3'),
            ('audio2transcript/expected_json', 'json'),
            ('transcript2instructions', 'json'),
            ('instruction2parameters', 'json'),
            ('parameters2command', 'json'),
            ('staged_questionnaires', 'json'),
        ]
        for folder, extension in paths:
            yield from self._case_files_from(folder, extension)

    def _case_files_from(self, folder: str, extension: str) -> Generator[Path, None, None]:
        pattern = re.compile(rf'^{self.case}(({Constants.CASE_CYCLE_SUFFIX}|\.)\d\d)?\.{extension}$')
        file_dir = Path(__file__).parent / folder
        for file in file_dir.glob(f"{self.case}*.{extension}"):
            if pattern.match(file.name):
                yield file

    def is_ready(self) -> bool:
        for _ in self._case_files():
            return False
        return True

    def reset(self) -> None:
        for case_file in self._case_files():
            case_file.unlink(True)

    def identified_transcript(self, audios: list[bytes], transcript: list[Line]) -> bool:
        for idx, audio in enumerate(audios):
            stem = self.case
            if idx > 0:
                stem = f"{self.case}.{idx:02d}"
            file = Path(__file__).parent / f"audio2transcript/inputs_mp3/{stem}.mp3"
            with file.open("wb") as fp:
                fp.write(audio)

        file = Path(__file__).parent / f"audio2transcript/expected_json/{self.case}.json"
        with file.open("w") as fp:
            json.dump([t.to_json() for t in transcript], fp, indent=2)  # type: ignore

        return file.exists()

    def found_instructions(
            self,
            transcript: list[Line],
            initial_instructions: list[Instruction],
            cumulated_instructions: list[Instruction],
    ) -> bool:
        file = Path(__file__).parent / f"transcript2instructions/{self.case}.json"
        with file.open("w") as fp:
            json.dump({
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
            }, fp, indent=2)  # type: ignore
        return file.exists()

    def computed_parameters(self, instructions: list[InstructionWithParameters]) -> bool:
        file = Path(__file__).parent / f"instruction2parameters/{self.case}.json"
        content = {
            "instructions": [],
            "parameters": [],
        }
        if file.exists():
            with file.open("r") as fp:
                content = json.load(fp)

        for instruction in instructions:
            content["instructions"].append(instruction.to_json(False))
            content["parameters"].append(instruction.parameters)

        with file.open("w") as fp:
            json.dump(content, fp, indent=2)  # type: ignore
        return file.exists()

    def computed_commands(self, instructions: list[InstructionWithCommand]) -> bool:
        file = Path(__file__).parent / f"parameters2command/{self.case}.json"
        content = {
            "instructions": [],
            "parameters": [],
            "commands": [],
        }
        if file.exists():
            with file.open("r") as fp:
                content = json.load(fp)

        for instruction in instructions:
            content["instructions"].append(instruction.to_json(False))
            content["parameters"].append(instruction.parameters)
            content["commands"].append({
                "module": instruction.command.__module__,
                "class": instruction.command.__class__.__name__,
                "attributes": instruction.command.values | {
                    "command_uuid": Constants.IGNORED_KEY_VALUE,
                    "note_uuid": Constants.IGNORED_KEY_VALUE,
                },
            })

        with file.open("w") as fp:
            json.dump(content, fp, indent=2)  # type: ignore
        return file.exists()

    def computed_questionnaires(
            self,
            transcript: list[Line],
            initial_instructions: list[Instruction],
            instructions_with_command: list[InstructionWithCommand],
    ) -> bool:
        file = Path(__file__).parent / f"staged_questionnaires/{self.case}.json"
        with file.open("w") as fp:
            json.dump({
                "transcript": [line.to_json() for line in transcript],
                "instructions": [
                    instruction.to_json(True) | {"uuid": Constants.IGNORED_KEY_VALUE}
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
            }, fp, indent=2)  # type: ignore
        return file.exists()
