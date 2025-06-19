import sys #added for rubric command that operates here. 
from sys import argv

from evaluations.case_builders.builder_audit_url import BuilderAuditUrl
from evaluations.case_builders.builder_delete import BuilderDelete
from evaluations.case_builders.builder_from_mp3 import BuilderFromMp3
from evaluations.case_builders.builder_from_transcript import BuilderFromTranscript
from evaluations.case_builders.builder_from_tuning import BuilderFromTuning
from evaluations.case_builders.builder_summarize import BuilderSummarize

from rubric_eval_sample.rubric_runner import run_rubric


class CaseBuilder:
    @classmethod
    def run(cls, arguments: list[str]) -> None:
        if "--delete" in arguments:
            #print("DEBUG: delete path")
            BuilderDelete.run()
        elif "--transcript" in arguments:
            #print("DEBUG: transcript path")
            BuilderFromTranscript.run()
        elif "--tuning-json" in arguments:
            BuilderFromTuning.run()
        elif "--mp3" in arguments:
            BuilderFromMp3.run()
        elif "--audit" in arguments:
            BuilderAuditUrl.run()
        elif "--summarize" in arguments:
            #print("DEBUG: summarize path")
            BuilderSummarize.run()
        
        else:
            print("no explicit action to perform")
        
        #edited control flow and pulled this out of elif to make sure it runs if in the argument, not dependent now on other builder files. 
        #because of this, we also don't need to have --rubric be parsed in any other builder files.
        if "--rubric" in arguments:
            #print("DEBUG: rubric path")
            try:
                case_index = arguments.index("--case")
                case_name = arguments[case_index + 1]

                transcript_index = arguments.index("--transcript")
                transcript_path = arguments[transcript_index + 1]

                rubric_index = arguments.index("--rubric")
                rubric_path = arguments[rubric_index + 1]
            except (ValueError, IndexError): #value/index correspond to issues with missing flags or value flags.
                print("Error: --case, --transcript, and --rubric flags must be provided with values.")
                sys.exit(1)

            run_rubric(case_name, transcript_path, rubric_path)


if __name__ == "__main__":
    CaseBuilder.run(argv)
