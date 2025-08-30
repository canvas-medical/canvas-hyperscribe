import subprocess
from concurrent.futures import as_completed, ThreadPoolExecutor
from os import environ
from pathlib import Path
from queue import Empty, Queue
from random import sample
from re import compile as re_compile
from re import match
from threading import Event, Thread
from time import time
from typing import IO, LiteralString, NamedTuple
import debug_helper
debug_helper.add_parent_path()
from evaluations.datastores.postgres.postgres import Postgres
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.constants import Constants
class CaseToRun(NamedTuple):
    env: dict
    patient_uuid: str
    note_uuid: str
    index: int
class Printer:
    OUT = " "
    ERR = "x"
    def _init_(self):
        self.output_queue = Queue()
        self.stop_event = Event()
        self.printer_thread = Thread(target=self._print_output)
        self.printer_thread.start()
    def _print_output(self):
        while not self.stop_event.is_set():
            try:
                index, output_type, line = self.output_queue.get(timeout=0.1)
                print(f"[{index:03d}] {output_type}: {line}")
                self.output_queue.task_done()
            except Empty:
                continue
    def add_output(self, index: int, output_type: str, line,):
        if text := line.strip():
            self.output_queue.put((index, output_type, text))
    def stop(self):
        self.stop_event.set()
        self.printer_thread.join()
class RandomRealWordCaseSplit:
    CUSTOMERS = [
        # "denis-bajet-phi",
        "praxishealth-apc",
        # "daymark",
        # "jasperhealth",
    ]
    CASE_TO_RUN = 10
    @classmethod
    def stream_to_handler(cls, pipe: IO, handler: Printer, case: CaseToRun, output_type: str,):
        for line in iter(pipe.readline, ''):
            handler.add_output(case.index, output_type, line)
    @classmethod
    def run_case_builder(cls, case: CaseToRun, printer: Printer,)-> dict:
        path_temp_files = Path("/media/DATA/from_s3_phi/")
        if not path_temp_files.exists():
            path_temp_files.mkdir(parents=True)
        cycle_duration = 60
        cmd = [
            'uv', 'run', 'python', 'case_builder.py',
            '--direct-split',
            '--patient', case.patient_uuid,
            '--note', case.note_uuid,
            '--cycle_duration', str(cycle_duration),
            '--path_temp_files', path_temp_files.as_posix(),
            '--force_rerun',
        ]
        start = time()
        result = {
            "patient": case.patient_uuid,
            "note": case.note_uuid,
        }
        try:
            printer.add_output(
                case.index,
                Printer.OUT,
                f"start hyperscribe-{case.env[Constants.CUSTOMER_IDENTIFIER]}/patient_{case.patient_uuid}/note_{case.note_uuid}",
            )
            process = subprocess.Popen(
                cmd,
                env=case.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=Path(_file_).parent.parent,
            )
            stdout_thread = Thread(
                target=cls.stream_to_handler,
                args=(process.stdout, printer, case, Printer.OUT)
            )
            stderr_thread = Thread(
                target=cls.stream_to_handler,
                args=(process.stderr, printer, case, Printer.ERR)
            )
            stdout_thread.start()
            stderr_thread.start()
            returned = process.wait()
            stdout_thread.join()
            stderr_thread.join()
            result |= {"success": bool(returned == 0)}
        except Exception as e:
            result |= {
                'success': False,
                'error': str(e),
            }
        return result | {"duration": int((time() - start))}
    @classmethod
    def run(cls) -> None:
        s3_credentials = HelperEvaluation.aws_s3_credentials()
        client_s3 = AwsS3(s3_credentials)
        runs: list[CaseToRun] = []
        for customer in cls.CUSTOMERS:
            patient_note: list[tuple[str, str]] = []
            sql: LiteralString = """
                                 select rwc.patient_note_hash, max(rwc.created) as created
                                 from real_world_case rwc
                                 where rwc.customer_identifier = %(customer)s
                                 group by rwc.patient_note_hash
                                 order by 2 desc"""
            postgres = Postgres(HelperEvaluation.postgres_credentials())
            pattern = re_compile(fr"patient_([a-z0-9-]+)/note_([a-z0-9-]+)")
            for record in postgres._select(sql, {"customer": customer}):
                if found := match(pattern, record['patient_note_hash']):
                    patient_note.append((found.group(1), found.group(2)))
            if not patient_note:
                # find all patient/note pairs
                pattern = re_compile(fr"hyperscribe-{customer}/patient_([a-z0-9-]+)/note_([a-z0-9-]+)/limited_chart.json")
                for f in client_s3.list_s3_objects(f"hyperscribe-{customer}/patient_"):
                    if found := match(pattern, f.key):
                        patient_note.append((found.group(1), found.group(2)))
            if not patient_note:
                print(f"No patient note found for {customer}")
                continue
            # set the environment
            env = environ.copy()
            env[Constants.CUSTOMER_IDENTIFIER] = customer
            env[Constants.SECRET_CYCLE_TRANSCRIPT_OVERLAP] = '100'
            # random pick case_to_run pairs
            indexes = sample(range(0, len(patient_note)), min(cls.CASE_TO_RUN, len(patient_note)))
            for idx in indexes:
                runs.append(CaseToRun(
                    env=env,
                    patient_uuid=patient_note[idx][0],
                    note_uuid=patient_note[idx][1],
                    index=idx,
                ))
        printer = Printer()
        try:
            max_workers = 5
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_case = {
                    executor.submit(cls.run_case_builder, case, printer): case
                    for case in runs
                }
            for future in as_completed(future_to_case):
                case = future_to_case[future]
                result = future.result()
                msg = f":white_check_mark:"
                if result['success'] is False:
                    msg = f":x: failed: {result.get('error', result.get('stderr'))}"
                print(f"{case.index:03d} - {result['patient']} - {result['note']} ({result['duration']}) {msg}")
        finally:
            printer.stop()
if _name_ == '_main_':
    RandomRealWordCaseSplit.run()