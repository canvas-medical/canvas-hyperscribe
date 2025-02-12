import json
from pathlib import Path

from canvas_sdk.commands.base import _BaseCommand as BaseCommand

from commander.protocols.auditor import Auditor
from commander.protocols.structures.instruction import Instruction
from commander.protocols.structures.line import Line


class AuditorFile(Auditor):
    def __init__(self, case: str):
        super().__init__()
        self.case = case
        self.reset()

    def reset(self):
        files = [
            f"audio2transcript/inputs_mp3/{self.case}.mp3",
            f"audio2transcript/expected_json/{self.case}.json",
            f"transcript2instructions/{self.case}.json",
            f"instruction2parameters/{self.case}.json",
            f"parameters2command/{self.case}.json",
        ]
        for file_path in files:
            (Path(__file__).parent / file_path).unlink(True)

    def identified_transcript(self, audio: bytes, transcript: list[Line]) -> bool:
        file = Path(__file__).parent / f"audio2transcript/inputs_mp3/{self.case}.mp3"
        with file.open("wb") as fp:
            fp.write(audio)
        file = Path(__file__).parent / f"audio2transcript/expected_json/{self.case}.json"
        with file.open("w") as fp:
            json.dump(transcript, fp, indent=2)  # type: ignore
        return file.exists()

    def found_instructions(self, transcript: list[Line], instructions: list[Instruction]) -> bool:
        file = Path(__file__).parent / f"transcript2instructions/{self.case}.json"
        with file.open("w") as fp:
            json.dump({
                "transcript": [line.to_json() for line in transcript],
                "instructions": {
                    "initial": [],
                    "result": [instruction.to_json(True) | {"isNew": True} for instruction in instructions],
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
            content["instructions"].append(instruction.to_json(True))
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
            content["instructions"].append(instruction.to_json(True))
            content["parameters"].append(parameters)
            content["commands"].append({
                "module": command.__module__,
                "class": command.__class__.__name__,
                "attributes": command.values,
            })

        with file.open("w") as fp:
            json.dump(content, fp, indent=2)  # type: ignore
        return file.exists()
