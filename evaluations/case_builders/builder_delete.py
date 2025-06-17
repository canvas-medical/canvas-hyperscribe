from argparse import ArgumentParser, Namespace

from evaluations.auditor_file import AuditorFile
from evaluations.datastores.store_cases import StoreCases


class BuilderDelete:

    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Delete all files and case record related to the built case.")
        parser.add_argument("--delete", action="store_true")
        parser.add_argument("--case", type=str)
        parser.add_argument("--audios", action="store_true", default=False, help="delete audio files")
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls._parameters()
        AuditorFile(parameters.case, 0).reset(parameters.audios)
        StoreCases.delete(parameters.case)
        print(f"Evaluation Case '{parameters.case}' deleted (files and record)")
