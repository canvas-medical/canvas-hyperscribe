from argparse import ArgumentParser, Namespace
from os import environ

from evaluations.datastores.datastore_case import DatastoreCase


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
                for case in DatastoreCase.all_names():
                    cases.append(case)
        elif parameters.case:
            cases.append(parameters.case)

        for case in cases:
            DatastoreCase.delete(case, parameters.audios)
            print(f"Evaluation Case '{case}' deleted")

        if not cases:
            print("No cases deleted")
