import json
from pathlib import Path
from typing import Generator

from canvas_sdk.commands.base import _BaseCommand as BaseCommand

from hyperscribe.handlers.auditor import Auditor
from hyperscribe.handlers.structures.instruction import Instruction
from hyperscribe.handlers.structures.line import Line


class AuditorFile(Auditor):
    def __init__(self, case: str):
        super().__init__()
        self.case = case

    def _case_files(self) -> Generator[Path, None, None]:
        mp3_dir = Path(__file__).parent / 'audio2transcript/inputs_mp3'
        for file in mp3_dir.glob(f"{self.case}*.mp3"):
            yield Path(file)

        files = [
            f"audio2transcript/expected_json/{self.case}.json",
            f"transcript2instructions/{self.case}.json",
            f"instruction2parameters/{self.case}.json",
            f"parameters2command/{self.case}.json",
        ]
        for file_path in files:
            if (file := Path(__file__).parent / file_path) and file.is_file():
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

    def found_instructions(self, transcript: list[Line], instructions: list[Instruction]) -> bool:
        file = Path(__file__).parent / f"transcript2instructions/{self.case}.json"
        with file.open("w") as fp:
            json.dump({
                "transcript": [line.to_json() for line in transcript],
                "instructions": {
                    "initial": [],
                    "result": [
                        instruction.to_json() | {"uuid": "", "isNew": True}
                        for instruction in instructions
                    ],
                },
            }, fp, indent=2)  # type: ignore
        return file.exists()

    def computed_parameters(self, sdk_parameters: list[tuple[Instruction, dict]]) -> bool:
        file = Path(__file__).parent / f"instruction2parameters/{self.case}.json"
        content = {
            "instructions": [],
            "parameters": [],
        }
        if file.exists():
            with file.open("r") as fp:
                content = json.load(fp)

        for instruction, parameters in sdk_parameters:
            content["instructions"].append(instruction.to_json())
            content["parameters"].append(parameters)

        with file.open("w") as fp:
            json.dump(content, fp, indent=2)  # type: ignore
        return file.exists()

    def computed_commands(self, sdk_parameters: list[tuple[Instruction, dict]], sdk_commands: list[BaseCommand]) -> bool:
        file = Path(__file__).parent / f"parameters2command/{self.case}.json"
        content = {
            "instructions": [],
            "parameters": [],
            "commands": [],
        }
        if file.exists():
            with file.open("r") as fp:
                content = json.load(fp)

        for (instruction, parameters), command in zip(sdk_parameters, sdk_commands):
            content["instructions"].append(instruction.to_json())
            content["parameters"].append(parameters)
            content["commands"].append({
                "module": command.__module__,
                "class": command.__class__.__name__,
                "attributes": command.values,
            })

        with file.open("w") as fp:
            json.dump(content, fp, indent=2)  # type: ignore
        return file.exists()
