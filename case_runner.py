from argparse import ArgumentParser
from argparse import Namespace

from evaluations.auditor_postgres import AuditorPostgres
from evaluations.datastores.postgres.case import Case as CaseStore
from evaluations.datastores.postgres.generated_note import GeneratedNote as GeneratedNoteStore
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.records.generated_note import GeneratedNote as GeneratedNoteRecord
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
        parser.add_argument("--case_name", type=str, required=True, help="The case to run")
        parser.add_argument("--cycles", type=int, required=True, help="Split the transcript in as many cycles")
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls.parameters()

        # retrieve the settings and credentials
        settings = HelperEvaluation.settings()
        aws_s3 = HelperEvaluation.aws_s3_credentials()
        credentials = HelperEvaluation.postgres_credentials()
        case = CaseStore(credentials).get_case(parameters.case_name)
        if case.id < 1:
            return
        cycles = min(max(1, parameters.cycles), len(case.transcript))

        identification = IdentificationParameters(
            patient_uuid=Constants.FAUX_PATIENT_UUID,
            note_uuid=Constants.FAUX_NOTE_UUID,
            provider_uuid=Constants.FAUX_PROVIDER_UUID,
            canvas_instance="runner-environment",
        )
        generated_note = GeneratedNoteStore(credentials)
        generated_note_id = generated_note.insert(GeneratedNoteRecord(
            case_id=case.id,
            cycle_duration=0,
            cycle_count=cycles,
            note_json=[],  # <-- updated at the end
            cycle_transcript_overlap=Constants.CYCLE_TRANSCRIPT_OVERLAP,  # TODO to be defined in the settings
            text_llm_vendor=settings.llm_text.vendor,
            text_llm_name=settings.llm_text_model(),
            hyperscribe_version="",  # TODO <-- commit or version declared in the manifest
            failed=True,  # <-- will be changed to False at the end
        )).id

        limited_cache = LimitedCache.load_from_json(case.limited_chart)
        chatter = AudioInterpreter(settings, aws_s3, limited_cache, identification)
        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        discussion = CachedSdk.get_discussion(chatter.identification.note_uuid)
        # run the cycles
        auditor = AuditorPostgres(case.name, 0, generated_note_id)
        length, extra = divmod(len(case.transcript), cycles)
        length += (1 if extra else 0)
        try:
            for cycle in range(cycles):
                idx = cycle * length
                transcript = case.transcript[idx:idx + length]
                cycle += 1
                discussion.set_cycle(cycle)
                auditor.set_cycle(cycle)
                previous, _ = Commander.transcript2commands(auditor, transcript, chatter, previous)
        finally:
            auditor.finalize([])  # TODO retrieve the errors


if __name__ == "__main__":
    CaseRunner.run()
