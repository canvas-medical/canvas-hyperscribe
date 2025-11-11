from argparse import ArgumentParser
from argparse import Namespace

from evaluations.datastores.datastore_case import DatastoreCase
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.commander import Commander
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line


class CaseRunner:
    @classmethod
    def parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Run the case based on the local settings")
        parser.add_argument("--case", type=str, required=True, help="The case to run")
        parser.add_argument(
            "--cycles",
            type=int,
            default=0,
            help="Split the transcript in as many cycles, use the stored cycles if not provided.",
        )
        parser.add_argument(
            "--experiment_result_id",
            type=int,
            default=0,
            help="The ID of the experiment_resul table record where to store the results",
        )
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls.parameters()

        # retrieve the settings and credentials
        if not DatastoreCase.already_generated(parameters.case):
            print(f"Case '{parameters.case}' not generated yet")
            return
        auditor = HelperEvaluation.get_auditor(parameters.case, 0)
        full_transcript = cls.prepare_cycles(auditor.full_transcript(), parameters.cycles)

        identification = IdentificationParameters(
            patient_uuid=Constants.FAUX_PATIENT_UUID,
            note_uuid=auditor.note_uuid(),
            provider_uuid=Constants.FAUX_PROVIDER_UUID,
            canvas_instance="runner-environment",
        )

        limited_cache = LimitedCache.load_from_json(auditor.limited_chart())
        chatter = AudioInterpreter(auditor.settings, auditor.s3_credentials, limited_cache, identification)
        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        discussion = CachedSdk.get_discussion(chatter.identification.note_uuid)
        # run the cycles
        errors: dict = {}
        try:
            for cycle, transcript in enumerate(full_transcript.values(), start=1):
                discussion.set_cycle(cycle)
                auditor.set_cycle(cycle)
                previous, _ = Commander.transcript2commands(auditor, transcript, chatter, previous)
        except Exception as e:
            errors = HelperEvaluation.trace_error(e)
        finally:
            auditor.case_finalize(
                errors,
                parameters.experiment_result_id,
                MemoryLog.token_counts(identification.note_uuid),
            )

    @classmethod
    def prepare_cycles(cls, full_transcript: dict[str, list[Line]], cycles: int) -> dict[str, list[Line]]:
        if cycles <= 0:
            return full_transcript

        uncycled_transcript = [line for key, lines in full_transcript.items() for line in lines]
        fenced_cycles = min(max(1, cycles), len(uncycled_transcript))
        length, extra = divmod(len(uncycled_transcript), fenced_cycles)
        result = {}
        start = 0
        for cycle in range(fenced_cycles):
            size = length + (1 if cycle < extra else 0)
            result[f"cycle_{(cycle + 1):03d}"] = uncycled_transcript[start : start + size]
            start += size
        return result


if __name__ == "__main__":
    CaseRunner.run()
