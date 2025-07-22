from argparse import ArgumentParser, Namespace
from webbrowser import open as browser_open

from evaluations.helper_evaluation import HelperEvaluation


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
        auditor = HelperEvaluation.get_auditor(parameters.case, 0)
        html = auditor.generate_html_summary()
        browser_open(html.as_uri())
