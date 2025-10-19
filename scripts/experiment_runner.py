import json
from os import environ
from subprocess import Popen, PIPE, STDOUT
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Generator

from evaluations.auditors.auditor_postgres import AuditorPostgres
from evaluations.datastores.postgres.experiment import Experiment as ExperimentStore
from evaluations.datastores.postgres.experiment_result import ExperimentResult as ExperimentResultStore
from evaluations.datastores.postgres.rubric import Rubric as RubricStore
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.case_runner_job import CaseRunnerJob
from evaluations.structures.experiment_job import ExperimentJob
from evaluations.structures.note_grader_job import NoteGraderJob
from evaluations.structures.records.experiment_result import ExperimentResult as ExperimentResultRecord
from hyperscribe.libraries.constants import Constants


class ExperimentRunner:
    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Run the provided experiment")
        parser.add_argument(
            "--experiment_id",
            type=int,
            required=True,
            help="The experiment id from the database",
        )
        parser.add_argument(
            "--max_workers",
            type=int,
            default=Constants.MAX_WORKERS_DEFAULT,
            help="Max cases run simultaneously",
        )
        args = parser.parse_args()

        return args

    @classmethod
    def hyperscribe_version(cls) -> str:
        return AuditorPostgres.get_plugin_commit()

    @classmethod
    def hyperscribe_tags(cls) -> dict:
        with (Path(__file__).parent.parent / "hyperscribe" / "CANVAS_MANIFEST.json").open("r") as f:
            manifest = json.load(f)
            return manifest.get("tags") or {}

    @classmethod
    def run(cls) -> None:
        for job in cls.run_case_runner_jobs():
            env = environ.copy()
            cmd = cls._build_command_note_grader(job)
            process = Popen(
                cmd,
                env=env,
                stdout=PIPE,
                stderr=STDOUT,
                text=True,
                bufsize=1,
                cwd=Path(__file__).parent.parent,
            )
            assert process.stdout is not None
            for line in process.stdout:
                if message := line.rstrip("\n\r"):
                    print(f"[{job.job_index:03d}] {message}")
            process.wait()

    @classmethod
    def run_case_runner_jobs(cls) -> Generator[NoteGraderJob, None, None]:
        args = cls._parameters()
        hyperscribe_version = cls.hyperscribe_version()
        hyperscribe_tags = cls.hyperscribe_tags()
        psql_credential = HelperEvaluation.postgres_credentials()
        result_store = ExperimentResultStore(psql_credential)
        rubric_store = RubricStore(psql_credential)

        for job in cls._generate_jobs(args.experiment_id):
            rubric_id = rubric_store.get_last_accepted(job.case_id)
            if rubric_id == 0:
                print(f"[{job.job_index:03d}] no rubric accepted")
                continue

            experiment_result = result_store.insert(
                ExperimentResultRecord(
                    experiment_id=job.experiment_id,
                    experiment_name=job.experiment_name,
                    hyperscribe_version=hyperscribe_version,
                    hyperscribe_tags=hyperscribe_tags,
                    case_id=job.case_id,
                    case_name=job.case_name,
                    model_id=job.model_id,
                    text_llm_name=job.model_name,
                    text_llm_vendor=job.model_vendor,
                    cycle_time=job.cycle_time,
                    cycle_transcript_overlap=job.cycle_transcript_overlap,
                )
            )
            case_runner_job = CaseRunnerJob(
                case_name=job.case_name,
                experiment_result_id=experiment_result.id,
            )

            env = cls._build_environment(job)
            cmd = cls._build_command_case_runner(case_runner_job)
            process = Popen(
                cmd,
                env=env,
                stdout=PIPE,
                stderr=STDOUT,
                text=True,
                bufsize=1,
                cwd=Path(__file__).parent.parent,
            )
            assert process.stdout is not None
            for line in process.stdout:
                if message := line.rstrip("\n\r"):
                    print(f"[{job.job_index:03d}] {message}")
            process.wait()

            # retrieve the generated note
            generated_note_id = result_store.get_generated_note_id(experiment_result.id)
            if generated_note_id == 0:
                print(f"[{job.job_index:03d}] no note generated")
                continue

            for job_index in range(job.grade_replications):
                yield NoteGraderJob(
                    job_index=job_index,
                    parent_index=job.job_index,
                    rubric_id=rubric_id,
                    generated_note_id=generated_note_id,
                    experiment_result_id=experiment_result.id,
                )

    @classmethod
    def _build_environment(cls, job: ExperimentJob) -> dict[str, str]:
        env: dict[str, str] = environ.copy()

        env[Constants.SECRET_TEXT_LLM_VENDOR] = job.model_vendor
        env[Constants.SECRET_TEXT_LLM_KEY] = job.model_api_key
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

    @classmethod
    def _build_command_note_grader(cls, job: NoteGraderJob) -> list[str]:
        command: list[str] = [
            "uv",
            "run",
            "python",
            "-m",
            "evaluations.case_builders.note_grader",
            "--rubric_id",
            str(job.rubric_id),
            "--generated_note_id",
            str(job.generated_note_id),
            "--experiment_result_id",
            str(job.experiment_result_id),
        ]
        return command

    @classmethod
    def _generate_jobs(cls, experiment_id: int) -> Generator[ExperimentJob, None, None]:
        psql_credential = HelperEvaluation.postgres_credentials()

        store = ExperimentStore(psql_credential)
        experiment = store.get_experiment(experiment_id)
        if not experiment.id:
            print("Experiment not found")
            return

        cases = store.get_cases(experiment.id)
        if not cases:
            print("Experiment has no cases")
            return

        models = store.get_models(experiment.id)
        if not models:
            print("Experiment has no models")
            return

        job_index = 0
        for case in cases:
            for model in models:
                for cycle_overlap in experiment.cycle_transcript_overlaps:
                    # Create note_replications copies of each job
                    for _ in range(experiment.note_replications):
                        job_index += 1
                        job: ExperimentJob = ExperimentJob(
                            job_index=job_index,
                            experiment_id=experiment_id,
                            experiment_name=experiment.name,
                            case_id=int(case.id),
                            case_name=case.name,
                            model_id=int(model.id),
                            model_vendor=model.vendor,
                            model_name=model.name,
                            model_api_key=model.api_key,
                            cycle_time=0,  # currently not available
                            cycle_transcript_overlap=cycle_overlap,
                            grade_replications=experiment.grade_replications,
                        )
                        yield job


if __name__ == "__main__":
    ExperimentRunner.run()
