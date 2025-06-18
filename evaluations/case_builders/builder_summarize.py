from argparse import ArgumentParser, Namespace
from webbrowser import open as browser_open

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
        auditor = AuditorFile(parameters.case, 0)
        if (html := auditor.generate_html_summary()) and html:
            browser_open(html.as_uri())
