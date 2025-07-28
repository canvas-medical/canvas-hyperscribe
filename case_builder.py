from sys import argv

from evaluations.case_builders.builder_audit_url import BuilderAuditUrl
from evaluations.case_builders.builder_delete import BuilderDelete
from evaluations.case_builders.builder_direct_from_tuning_full import BuilderDirectFromTuningFull
from evaluations.case_builders.builder_direct_from_tuning_split import BuilderDirectFromTuningSplit
from evaluations.case_builders.builder_from_mp3 import BuilderFromMp3
from evaluations.case_builders.builder_from_transcript import BuilderFromTranscript
from evaluations.case_builders.builder_from_tuning import BuilderFromTuning
from evaluations.case_builders.builder_summarize import BuilderSummarize
from evaluations.case_builders.builder_from_chart_transcript import BuilderFromChartTranscript


class CaseBuilder:
    @classmethod
    def run(cls, arguments: list[str]) -> None:
        if "--delete" in arguments:
            BuilderDelete.run()
        elif "--chart" in arguments and "--transcript" in arguments:
            BuilderFromChartTranscript.run()
        elif "--transcript" in arguments:
            BuilderFromTranscript.run()
        elif "--tuning-json" in arguments:
            BuilderFromTuning.run()
        elif "--mp3" in arguments:
            BuilderFromMp3.run()
        elif "--audit" in arguments:
            BuilderAuditUrl.run()
        elif "--summarize" in arguments:
            BuilderSummarize.run()
        elif "--direct-split" in arguments:
            BuilderDirectFromTuningSplit.run()
        elif "--direct-full" in arguments:
            BuilderDirectFromTuningFull.run()
        else:
            print("no explicit action to perform")


if __name__ == "__main__":
    CaseBuilder.run(argv)
