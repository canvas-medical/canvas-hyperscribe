import json
from argparse import ArgumentParser, Namespace
from pathlib import Path
from tempfile import NamedTemporaryFile
from webbrowser import open as browser_open

from canvas_sdk.commands.commands.questionnaire.question import ResponseOption

from evaluations.auditor_file import AuditorFile


class BuilderSummarize:

    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Generate a single document with all instructions and generated commands")
        parser.add_argument("--summarize", action="store_true")
        parser.add_argument("--case", type=str, required=True, help="Evaluation case")
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls._parameters()
        summary = cls.summary_generated_commands(parameters.case)

        template_file = Path(__file__).parent / "summary.html"
        with (template_file.open("r") as source):
            with NamedTemporaryFile(delete=False, suffix=".html", mode="w") as target:
                target.write(source
                             .read()
                             .replace("{{theCase}}", parameters.case)
                             .replace("{{theData}}", json.dumps(summary)))
                browser_open(f"file://{target.name}")

    @classmethod
    def summary_generated_commands(cls, case: str) -> list[dict]:
        result: dict[str, dict] = {}

        recorder = AuditorFile(case)
        # common commands
        files = sorted(
            [f for f in recorder.case_files_from("parameters2command", "json")],
            key=lambda item: item.name,
        )
        for file in files:
            with file.open("r") as f:
                content = json.load(f)
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
        files = sorted(
            [f for f in recorder.case_files_from("staged_questionnaires", "json")],
            key=lambda item: item.name,
        )
        if files:
            with files[-1].open("r") as f:
                content = json.load(f)
                for index, command in enumerate(content["commands"]):
                    attributes: dict[str, str] = {}
                    instruction = content["instructions"][index]
                    questionnaire = json.loads(instruction["information"])
                    for question in questionnaire["questions"]:
                        response = command["attributes"]["questions"][f"question-{question['dbid']}"]

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
