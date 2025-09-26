# with Code Claude help for the parallelism
import subprocess
from argparse import ArgumentParser, Namespace
from concurrent.futures import ThreadPoolExecutor
from os import environ
from pathlib import Path
from re import compile as re_compile, match as re_match
from typing import LiteralString

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.constants import Constants


class RealworldCaseOrchestrator:
    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Build the topical cases from the tuning files stored in AWS S3")
        parser.add_argument(
            "--customer",
            type=str,
            required=True,
            help="The customer as defined in AWS S3",
        )
        parser.add_argument(
            "--path_temp_files",
            type=str,
            required=True,
            help="Folder to store temporary files",
        )
        parser.add_argument(
            "--cycle_duration",
            type=int,
            required=True,
            help="Duration of each cycle, i.e. the duration of the audio chunks",
        )
        parser.add_argument(
            "--cycle_overlap",
            type=int,
            default=Constants.CYCLE_TRANSCRIPT_OVERLAP_DEFAULT,
            help="Amount of words provided to the LLM as context from the previous cycle",
        )
        parser.add_argument(
            "--max_workers",
            type=int,
            default=Constants.MAX_WORKERS_DEFAULT,
            help="Max cases built simultaneously",
        )
        args = parser.parse_args()

        # Validate path_temp_files is an existing directory
        temp_path = Path(args.path_temp_files)
        if not temp_path.exists():
            parser.error(f"The path_temp_files directory does not exist: {args.path_temp_files}")
        if not temp_path.is_dir():
            parser.error(f"The path_temp_files is not a directory: {args.path_temp_files}")

        return args

    @classmethod
    def notes(cls, customer: str) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        # list all patient/note tuples in AWS S3 without real_world_case records

        # - find the notes already parsed (that were successfully parsed or not)
        sql: LiteralString = """
                             select rwc.patient_note_hash, max(rwc.created) as created
                             from real_world_case rwc
                             where rwc.customer_identifier = %(customer)s
                             group by rwc.patient_note_hash
                             order by 2 desc"""
        postgres = Postgres(HelperEvaluation.postgres_credentials())
        pattern = re_compile(rf"patient_([a-z0-9-]+)/note_([a-z0-9-]+)")
        parsed_notes: list[str] = []
        for record in postgres._select(sql, {"customer": customer}):
            if found := re_match(pattern, record["patient_note_hash"]):
                parsed_notes.append(found.group(2))
        # - retrieve the existing notes and keep only those not already parsed
        s3_credentials = HelperEvaluation.aws_s3_credentials_tuning()
        client_s3 = AwsS3(s3_credentials)
        pattern = re_compile(rf"hyperscribe-{customer}/patient_([a-z0-9-]+)/note_([a-z0-9-]+)/limited_chart.json")
        for f in client_s3.list_s3_objects(f"hyperscribe-{customer}/patient_"):
            found = re_match(pattern, f.key)
            if found and found.group(2) not in parsed_notes:
                result.append((found.group(1), found.group(2)))

        return result

    @classmethod
    def run_for(
        cls,
        note_index: int,
        patient_uuid: str,
        note_uuid: str,
        parameters: Namespace,
    ) -> tuple[int, str, str, int]:
        # set the environment
        env = environ.copy()
        env[Constants.CUSTOMER_IDENTIFIER] = parameters.customer
        env[Constants.SECRET_CYCLE_TRANSCRIPT_OVERLAP] = str(parameters.cycle_overlap)
        env["PYTHONUNBUFFERED"] = "1"  # <-- force displays the prints immediately
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "scripts.case_builder",
            "--direct-split",
            "--patient",
            patient_uuid,
            "--note",
            note_uuid,
            "--cycle_duration",
            str(parameters.cycle_duration),
            "--path_temp_files",
            parameters.path_temp_files,
            "--force_rerun",
        ]

        print(f"[{note_index:03d}] processing patient {patient_uuid}, note {note_uuid}")
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=Path(__file__).parent.parent.parent,
        )

        # read output in real-time
        while True:
            if stdout := process.stdout:
                output = stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if message := output.rstrip("\n\r"):
                    print(f"[{note_index:03d}] {message}")

        # wait for the process to complete
        process.wait()
        print(f"[{note_index:03d}] completed with return code: {process.returncode}")

        return (note_index, patient_uuid, note_uuid, process.returncode)

    @classmethod
    def run(cls) -> None:
        parameters = cls._parameters()
        notes_list = cls.notes(parameters.customer)

        print(f"notes  : {len(notes_list)}")
        print(f"workers: {parameters.max_workers}")
        with ThreadPoolExecutor(max_workers=parameters.max_workers) as executor:
            futures = []
            for idx, (patient_uuid, note_uuid) in enumerate(notes_list, start=1):
                future = executor.submit(cls.run_for, idx, patient_uuid, note_uuid, parameters)
                futures.append(future)
            # wait for all tasks to complete and collect results
            results = []
            for future in futures:
                result = future.result()
                results.append(result)

        # sort results by note index
        results.sort(key=lambda x: x[0])
        # summary
        cls._summary(results)

    @classmethod
    def _summary(cls, executions: list[tuple[int, str, str, int]]) -> None:
        print("\n")
        print("=" * 80)
        print("summary")
        print("=" * 80)
        success_count = 0
        failure_count = 0
        for note_index, patient_uuid, note_uuid, return_code in executions:
            if return_code == 0:
                status_symbol = "✅"
                success_count += 1
            else:
                status_symbol = "❌"
                failure_count += 1

            print(
                f"{status_symbol} [{note_index:03d}] "
                f"Patient: {patient_uuid}, "
                f"Note: {note_uuid} "
                f"(exit code: {return_code})"
            )

        print("-" * 80)
        print(f"Total: {len(executions)} | Success: {success_count} | Failed: {failure_count}")
        print("=" * 80)


if __name__ == "__main__":
    RealworldCaseOrchestrator.run()
