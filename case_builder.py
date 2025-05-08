from sys import argv

from evaluations.case_builders.builder_delete import BuilderDelete
from evaluations.case_builders.builder_from_mp3 import BuilderFromMp3
from evaluations.case_builders.builder_from_transcript import BuilderFromTranscript
from evaluations.case_builders.builder_from_tuning import BuilderFromTuning


class CaseBuilder:
    @classmethod
    def run(cls, arguments):
        if "--delete" in arguments:
            BuilderDelete.run()
        elif "--transcript" in arguments:
            BuilderFromTranscript.run()
        elif "--tuning-json" in arguments:
            BuilderFromTuning.run()
        elif "--mp3" in arguments:
            BuilderFromMp3.run()
        else:
            print("no explicit action to perform")


if __name__ == "__main__":
    CaseBuilder.run(argv)
