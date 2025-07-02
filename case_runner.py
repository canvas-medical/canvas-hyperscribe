from argparse import ArgumentParser
from argparse import Namespace
from pathlib import Path
from shutil import rmtree
from uuid import uuid4

from evaluations.auditor_file import AuditorFile
from evaluations.datastores.store_cases import StoreCases
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
        parser.add_argument("--result_folder", type=str, required=True, help="Folder to store result files")
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls.parameters()

        # create/reset the folder to store the results
        case_name = f"{parameters.case}_run_{uuid4()}"
        folder = Path(parameters.result_folder) / case_name
        if not folder.exists():
            folder.mkdir(parents=True)
        rmtree(folder)

        # retrieve the settings and credentials
        settings = HelperEvaluation.settings()
        aws_s3 = HelperEvaluation.aws_s3_credentials()

        stored_case = StoreCases.get(parameters.case)
        cycles = stored_case.cycles
        identification = IdentificationParameters(
            patient_uuid=Constants.FAUX_PATIENT_UUID,
            note_uuid=Constants.FAUX_NOTE_UUID,
            provider_uuid=Constants.FAUX_PROVIDER_UUID,
            canvas_instance=stored_case.environment,
        )
        limited_cache = LimitedCache.load_from_json(stored_case.limited_cache)
        chatter = AudioInterpreter(settings, aws_s3, limited_cache, identification)
        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        discussion = CachedSdk.get_discussion(identification.note_uuid)

        # run the cycles
        for cycle in range(cycles):
            discussion.set_cycle(cycle + 1)
            previous, _ = Commander.transcript2commands(
                AuditorFile(case_name, cycle, folder),
                AuditorFile.default_instance(parameters.case, cycle).transcript(),
                chatter,
                previous,
            )
        recorder = AuditorFile(case_name, 0, folder)
        recorder.generate_commands_summary()
        recorder.generate_html_summary()


if __name__ == "__main__":
    CaseRunner.run()
