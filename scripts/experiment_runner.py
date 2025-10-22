import json
from argparse import ArgumentParser, Namespace
from multiprocessing import Process, Queue
from pathlib import Path
from subprocess import Popen, PIPE
from subprocess import run
from tempfile import TemporaryDirectory
from typing import Generator

from evaluations.datastores.postgres.experiment import Experiment as ExperimentStore
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.experiment_job import ExperimentJob
from hyperscribe.libraries.constants import Constants
from scripts.experiments.case_runner_worker import CaseRunnerWorker
from scripts.experiments.note_grader_worker import NoteGraderWorker


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
    def hyperscribe_tags(cls, repository: Path) -> dict:
        with (repository / "hyperscribe" / "CANVAS_MANIFEST.json").open("r") as f:
            manifest = json.load(f)
            return manifest.get("tags") or {}

    @classmethod
    def _experiment_hyperscribe_version(cls, experiment_id: int) -> str:
        psql_credential = HelperEvaluation.postgres_credentials()
        store = ExperimentStore(psql_credential)
        return store.get_experiment_hyperscribe_version(experiment_id)

    @classmethod
    def hyperscribe_version_exists(cls, hyperscribe_version: str) -> bool:
        process = Popen(
            ["git", "rev-parse", "--quiet", "--verify", f"{hyperscribe_version}^{{commit}}"],
            stdout=PIPE,
            stderr=PIPE,
        )
        process.communicate()
        return process.returncode == 0

    @classmethod
    def _clone_repository(cls, hyperscribe_version: str, clone_repository: Path) -> None:
        repository = Path(__file__).parent.parent
        run(
            ["git", "clone", repository.as_posix(), clone_repository.as_posix()],
            check=True,
            capture_output=True,
        )
        run(
            ["git", "checkout", hyperscribe_version],
            cwd=clone_repository.as_posix(),
            check=True,
            capture_output=True,
        )

    @classmethod
    def run(cls) -> None:
        args = cls._parameters()

        hyperscribe_version = cls._experiment_hyperscribe_version(args.experiment_id)
        if not cls.hyperscribe_version_exists(hyperscribe_version):
            print(f"hyperscribe version does not exist: {hyperscribe_version}")
            return
        with TemporaryDirectory() as temp_dir:
            clone_repository = Path(temp_dir)
            cls._clone_repository(hyperscribe_version, clone_repository)
            hyperscribe_tags = cls.hyperscribe_tags(clone_repository)

            case_runner_queue: Queue = Queue()
            note_grader_queue: Queue = Queue()

            case_runner_workers: list[Process] = []
            note_grader_workers: list[Process] = []

            for _ in range(args.max_workers):
                worker = Process(
                    target=CaseRunnerWorker(
                        case_runner_queue,
                        note_grader_queue,
                        hyperscribe_version,
                        hyperscribe_tags,
                    ).run
                )
                worker.start()
                case_runner_workers.append(worker)

            for _ in range(args.max_workers):
                worker = Process(target=NoteGraderWorker(note_grader_queue).run)
                worker.start()
                note_grader_workers.append(worker)

            for job in cls._generate_jobs(args.experiment_id, clone_repository):
                case_runner_queue.put(job)

            for _ in range(args.max_workers):
                case_runner_queue.put(None)

            for worker in case_runner_workers:
                worker.join()

            for _ in range(args.max_workers):
                note_grader_queue.put(None)

            for worker in note_grader_workers:
                worker.join()

    @classmethod
    def _generate_jobs(cls, experiment_id: int, repository: Path) -> Generator[ExperimentJob, None, None]:
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
            for models_experiment in models:
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
                            models=models_experiment,
                            cycle_time=0,  # currently not available
                            cycle_transcript_overlap=cycle_overlap,
                            grade_replications=experiment.grade_replications,
                            cwd_path=repository,
                        )
                        yield job


if __name__ == "__main__":
    ExperimentRunner.run()
