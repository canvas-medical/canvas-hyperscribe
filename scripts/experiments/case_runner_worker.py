from multiprocessing import Queue
from os import environ
from subprocess import Popen, PIPE, STDOUT
from typing import Optional

from evaluations.datastores.postgres.experiment_result import ExperimentResult as ExperimentResultStore
from evaluations.datastores.postgres.rubric import Rubric as RubricStore
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.case_runner_job import CaseRunnerJob
from evaluations.structures.experiment_job import ExperimentJob
from evaluations.structures.note_grader_job import NoteGraderJob
from evaluations.structures.records.experiment_result import ExperimentResult as ExperimentResultRecord
from evaluations.structures.records.model import Model
from hyperscribe.libraries.constants import Constants


class CaseRunnerWorker:
    def __init__(
        self,
        case_runner_queue: Queue,
        note_grader_queue: Queue,
        hyperscribe_version: str,
        hyperscribe_tags: dict,
    ):
        self._case_runner_queue: Queue = case_runner_queue
        self._note_grader_queue: Queue = note_grader_queue
        self._hyperscribe_version: str = hyperscribe_version
        self._hyperscribe_tags: dict = hyperscribe_tags

    @classmethod
    def _build_environment(cls, job: ExperimentJob) -> dict[str, str]:
        env: dict[str, str] = environ.copy()

        env[Constants.SECRET_TEXT_LLM_VENDOR] = job.models.model_generator.vendor
        env[Constants.SECRET_TEXT_LLM_KEY] = job.models.model_generator.api_key
        env[Constants.SECRET_CYCLE_TRANSCRIPT_OVERLAP] = str(job.cycle_transcript_overlap)

        env[Constants.SECRET_AUDIT_LLM] = "n"
        env[Constants.SECRET_IS_TUNING] = "n"
        env[Constants.PROGRESS_SETTING_KEY] = ""
        env[Constants.SECRET_MAX_WORKERS] = "1"
        env[Constants.SECRET_STRUCTURED_RFV] = "n"
        env[Constants.SECRET_STAFFERS_LIST] = ""
        env[Constants.SECRET_STAFFERS_POLICY] = "y"
        env[Constants.SECRET_COMMANDS_LIST] = ""
        env[Constants.SECRET_COMMANDS_POLICY] = "n"
        env[Constants.SECRET_TRIAL_STAFFERS_LIST] = ""

        env[Constants.SECRET_API_SIGNING_KEY] = ""
        env[Constants.SECRET_AUDIO_LLM_VENDOR] = ""
        env[Constants.SECRET_AUDIO_LLM_KEY] = ""
        if "VIRTUAL_ENV" in env:
            del env["VIRTUAL_ENV"]

        return env

    @classmethod
    def _build_command_case_runner(cls, job: CaseRunnerJob) -> list[str]:
        command: list[str] = [
            "uv",
            "run",
            "python",
            "-m",
            "scripts.case_runner",
            "--case",
            job.case_name,
            "--experiment_result_id",
            str(job.experiment_result_id),
        ]
        return command

    def _process_case_runner_job(self, job: ExperimentJob) -> None:
        psql_credential = HelperEvaluation.postgres_credentials()
        result_store = ExperimentResultStore(psql_credential)
        rubric_store = RubricStore(psql_credential)

        rubric_id = rubric_store.get_last_accepted(job.case_id)
        if rubric_id == 0:
            print(f"[{job.job_index:03d}] no rubric accepted")
            return

        experiment_result = result_store.insert(
            ExperimentResultRecord(
                experiment_id=job.experiment_id,
                experiment_name=job.experiment_name,
                hyperscribe_version=self._hyperscribe_version,
                hyperscribe_tags=self._hyperscribe_tags,
                case_id=job.case_id,
                case_name=job.case_name,
                cycle_time=job.cycle_time,
                cycle_transcript_overlap=job.cycle_transcript_overlap,
            )
        )
        case_runner_job = CaseRunnerJob(
            case_name=job.case_name,
            experiment_result_id=experiment_result.id,
        )

        env = self._build_environment(job)
        cmd = self._build_command_case_runner(case_runner_job)
        process = Popen(
            cmd,
            env=env,
            stdout=PIPE,
            stderr=STDOUT,
            text=True,
            bufsize=1,
            cwd=job.cwd_path,
        )
        assert process.stdout is not None
        for line in process.stdout:
            if message := line.rstrip("\n\r"):
                print(f"[{job.job_index:03d}] {message}")
        process.wait()

        generated_note_id = result_store.get_generated_note_id(experiment_result.id)
        if generated_note_id == 0:
            print(f"[{job.job_index:03d}] no note generated")
            return

        for job_index in range(job.grade_replications):
            note_grader_job = NoteGraderJob(
                job_index=job_index,
                parent_index=job.job_index,
                rubric_id=rubric_id,
                generated_note_id=generated_note_id,
                model=Model(
                    id=job.models.model_grader.id,
                    vendor=job.models.model_grader.vendor,
                    api_key=job.models.model_grader.api_key,
                ),
                model_is_reasoning=job.models.grader_is_reasoning,
                experiment_result_id=experiment_result.id,
                cwd_path=job.cwd_path,
            )
            self._note_grader_queue.put(note_grader_job)

    def run(self) -> None:
        while True:
            job: Optional[ExperimentJob] = self._case_runner_queue.get()
            if job is None:
                break
            self._process_case_runner_job(job)
