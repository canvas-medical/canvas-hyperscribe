from argparse import ArgumentParser, Namespace
from os import environ

from evaluations.auditor_file import AuditorFile
from evaluations.datastores.store_cases import StoreCases


class BuilderDelete:

    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Delete all files and case record related to the built case.")
        parser.add_argument("--delete", action="store_true")
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--case", type=str)
        parser.add_argument("--audios", action="store_true", default=False, help="delete audio files")
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls._parameters()

        cases = []
        if parameters.all:
            if environ.get("CanDeleteAllCases", "") == "danger":
                for record in StoreCases.all():
                    cases.append(record.case_name)
        elif parameters.case:
            cases.append(parameters.case)

        for case in cases:
            AuditorFile.default_instance(case, 0).reset(parameters.audios)
            StoreCases.delete(case)
            print(f"Evaluation Case '{case}' deleted (files and record)")

        if not cases:
            print("No cases deleted")
