import json
from argparse import ArgumentParser, Namespace
from multiprocessing import Process, Queue
from pathlib import Path
from typing import Generator

from evaluations.auditors.auditor_postgres import AuditorPostgres
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
    def hyperscribe_version(cls) -> str:
        return AuditorPostgres.get_plugin_commit()

    @classmethod
    def hyperscribe_tags(cls) -> dict:
        with (Path(__file__).parent.parent / "hyperscribe" / "CANVAS_MANIFEST.json").open("r") as f:
            manifest = json.load(f)
            return manifest.get("tags") or {}

    @classmethod
    def run(cls) -> None:
        args = cls._parameters()
        hyperscribe_version = cls.hyperscribe_version()
        hyperscribe_tags = cls.hyperscribe_tags()

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

        for job in cls._generate_jobs(args.experiment_id):
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
                        )
                        yield job


if __name__ == "__main__":
    ExperimentRunner.run()
