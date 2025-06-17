import json
from pathlib import Path
from typing import Generator

from evaluations.constants import Constants
from hyperscribe.libraries.auditor import Auditor
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.line import Line


class AuditorFile(Auditor):
    def __init__(self, case: str, cycle: int):
        super().__init__()
        self.case = case
        self.cycle = cycle

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, AuditorFile)
        return bool(self.case == other.case and self.cycle == other.cycle)

    def case_files(self, include_audio2transcript: bool) -> Generator[Path, None, None]:
        paths = [
            ('transcript2instructions', 'json'),
            ('instruction2parameters', 'json'),
            ('parameters2command', 'json'),
            ('staged_questionnaires', 'json'),
        ]
        if include_audio2transcript:
            paths.append(('audio2transcript/expected_json', 'json'))

        for folder, extension in paths:
            file = self.case_file_from(folder, extension)
            if file.exists():
                yield file

        if include_audio2transcript:
            audio_folder = Path(__file__).parent / f"audio2transcript/inputs_mp3/{self.case}"
            if audio_folder.exists():
                yield from audio_folder.glob(f"{Constants.CASE_CYCLE_SUFFIX}_???_??.mp3")

    def case_file_from(self, folder: str, extension: str) -> Path:
        return Path(__file__).parent / f"{folder}/{self.case}.{extension}"

    def is_ready(self) -> bool:
        for _ in self.case_files(False):
            return False
        return True

    def reset(self, delete_audios: bool) -> None:
        for case_file in self.case_files(delete_audios):
            case_file.unlink(True)
        if delete_audios:
            audio_folder = Path(__file__).parent / f"audio2transcript/inputs_mp3/{self.case}"
            if audio_folder.exists():
                audio_folder.rmdir()

    def transcript(self) -> list[Line]:
        file = Path(__file__).parent / f"audio2transcript/expected_json/{self.case}.json"
        if file.exists():
            content = json.load(file.open("r"))
            if transcript := content.get(f"{Constants.CASE_CYCLE_SUFFIX}_{self.cycle:03d}"):
                return Line.load_from_json(transcript)
        return []

    def identified_transcript(self, audios: list[bytes], transcript: list[Line]) -> bool:
        # audios are saved in a directory named with the case
        # transcripts are saved in a file named with the case

        audio_folder = Path(__file__).parent / f"audio2transcript/inputs_mp3/{self.case}"
        if audio_folder.exists() is False:
            audio_folder.mkdir()

        for idx, audio in enumerate(audios):
            audio_file = audio_folder / f"{Constants.CASE_CYCLE_SUFFIX}_{self.cycle:03d}_{idx:02d}.mp3"
            with audio_file.open("wb") as fp:
                fp.write(audio)

        json_file = Path(__file__).parent / f"audio2transcript/expected_json/{self.case}.json"
        content = {}
        if json_file.exists():
            content = json.load(json_file.open("r"))
        content[f"{Constants.CASE_CYCLE_SUFFIX}_{self.cycle:03d}"] = [t.to_json() for t in transcript]
        json.dump(content, json_file.open("w"), indent=2)

        return json_file.exists()

    def found_instructions(
            self,
            transcript: list[Line],
            initial_instructions: list[Instruction],
            cumulated_instructions: list[Instruction],
    ) -> bool:
        file = Path(__file__).parent / f"transcript2instructions/{self.case}.json"
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
        json.dump(content, file.open("w"), indent=2)
        return file.exists()

    def computed_parameters(self, instructions: list[InstructionWithParameters]) -> bool:
        file = Path(__file__).parent / f"instruction2parameters/{self.case}.json"
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

        json.dump(content, file.open("w"), indent=2)
        return file.exists()

    def computed_commands(self, instructions: list[InstructionWithCommand]) -> bool:
        file = Path(__file__).parent / f"parameters2command/{self.case}.json"
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

        json.dump(content, file.open("w"), indent=2)
        return file.exists()

    def computed_questionnaires(
            self,
            transcript: list[Line],
            initial_instructions: list[Instruction],
            instructions_with_command: list[InstructionWithCommand],
    ) -> bool:
        file = Path(__file__).parent / f"staged_questionnaires/{self.case}.json"
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
        json.dump(content, file.open("w"), indent=2)
        return file.exists()
