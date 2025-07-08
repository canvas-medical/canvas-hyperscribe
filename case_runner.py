from argparse import ArgumentParser
from argparse import Namespace

from evaluations.datastores.datastore_case import DatastoreCase
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.handlers.commander import Commander
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.identification_parameters import IdentificationParameters


class CaseRunner:
    @classmethod
    def parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Run the case based on the local settings")
        parser.add_argument("--case", type=str, required=True, help="The case to run")
        parser.add_argument("--cycles", type=int, required=True, help="Split the transcript in as many cycles")
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls.parameters()

        # retrieve the settings and credentials
        if not DatastoreCase.already_generated(parameters.case):
            print(f"Case '{parameters.case}' not generated yet")
            return
        auditor = HelperEvaluation.get_auditor(parameters.case, 0)
        full_transcript = [
            line
            for key, lines in auditor.full_transcript().items()
            for line in lines
        ]
        cycles = min(max(1, parameters.cycles), len(full_transcript))

        identification = IdentificationParameters(
            patient_uuid=Constants.FAUX_PATIENT_UUID,
            note_uuid=Constants.FAUX_NOTE_UUID,
            provider_uuid=Constants.FAUX_PROVIDER_UUID,
            canvas_instance="runner-environment",
        )

        limited_cache = LimitedCache.load_from_json(auditor.limited_chart())
        chatter = AudioInterpreter(auditor.settings, auditor.s3_credentials, limited_cache, identification)
        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        discussion = CachedSdk.get_discussion(chatter.identification.note_uuid)
        # run the cycles
        length, extra = divmod(len(full_transcript), cycles)
        length += (1 if extra else 0)
        errors: dict = {}
        try:
            for cycle in range(cycles):
                idx = cycle * length
                transcript = full_transcript[idx:idx + length]
                cycle += 1
                discussion.set_cycle(cycle)
                auditor.set_cycle(cycle)
                previous, _ = Commander.transcript2commands(auditor, transcript, chatter, previous)
        except Exception as e:
            errors = HelperEvaluation.trace_error(e)
        finally:
            auditor.case_finalize(errors)

if __name__ == "__main__":
    CaseRunner.run()
