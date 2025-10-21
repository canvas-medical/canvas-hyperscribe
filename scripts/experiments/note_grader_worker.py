from multiprocessing import Queue
from os import environ
from pathlib import Path
from subprocess import Popen, PIPE, STDOUT
from typing import Optional

from evaluations.structures.note_grader_job import NoteGraderJob


class NoteGraderWorker:
    def __init__(self, note_grader_queue: Queue):
        self._note_grader_queue: Queue = note_grader_queue

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
    def _process_note_grader_job(cls, job: NoteGraderJob) -> None:
        env = environ.copy()
        cmd = cls._build_command_note_grader(job)
        process = Popen(
            cmd,
            env=env,
            stdout=PIPE,
            stderr=STDOUT,
            text=True,
            bufsize=1,
            cwd=Path(__file__).parent.parent.parent,
        )
        assert process.stdout is not None
        for line in process.stdout:
            if message := line.rstrip("\n\r"):
                print(f"[{job.parent_index:03d}.{job.job_index:03d}] {message}")
        process.wait()

    def run(self) -> None:
        while True:
            job: Optional[NoteGraderJob] = self._note_grader_queue.get()
            if job is None:
                break
            self._process_note_grader_job(job)
