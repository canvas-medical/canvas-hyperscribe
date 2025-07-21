# file mainly created by Anthropic/CodeClaude
"""
Parallel Case Runner Script

Runs case_runner.py on a list of cases in parallel with up to 5 threads/processes.
Displays real-time output and provides a summary with success/failure indicators.
"""

import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from argparse import ArgumentParser, Namespace
from queue import Queue
from pathlib import Path
from typing import Any

from evaluations.datastores.postgres.case import Case
from evaluations.helper_evaluation import HelperEvaluation


class ParallelCaseRunner:
    def __init__(self, cases_number: int, cycles: int, workers: int):
        self.cases_number = cases_number
        self.cycles = cycles
        self.max_workers = workers
        self.output_queue: Queue[Any] = Queue()
        self.results: dict[str, bool] = {}
        self.timings: dict[str, float] = {}
        self.output_lock = threading.Lock()

    def run_single_case(self, case: str) -> tuple[str, bool, str, float]:
        """Run a single case and return (case_name, success, output, duration)"""
        start_time = time.time()
        cmd = [sys.executable, "case_runner.py", "--case", case]
        if self.cycles > 0:
            cmd.extend(["--cycles", str(self.cycles)])
        
        try:
            # Run the case_runner.py script
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            output_lines = []
            
            # Read output line by line for real-time display
            if process.stdout is not None:
                for line in iter(process.stdout.readline, ''):
                    line = line.rstrip()
                    if line:
                        output_lines.append(line)
                        # Queue the output for real-time display
                        with self.output_lock:
                            print(f"[{case}] {line}")
            
            process.wait()
            success = process.returncode == 0
            duration = round(time.time() - start_time, 1)
            
            return case, success, '\n'.join(output_lines), duration
            
        except Exception as e:
            duration = round(time.time() - start_time, 1)
            error_msg = f"Exception running case {case}: {str(e)}"
            with self.output_lock:
                print(f"[{case}] ERROR: {error_msg}")
            return case, False, error_msg, duration

    def run_cases(self, cases: list[str]) -> dict[str, bool]:
        """Run multiple cases in parallel"""
        print(f"Starting parallel execution of {len(cases)} cases with up to {self.max_workers} workers...")
        print("=" * 80)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all cases to the executor
            future_to_case = {
                executor.submit(self.run_single_case, case): case 
                for case in cases
            }
            
            # Process completed futures as they finish
            for future in as_completed(future_to_case):
                case = future_to_case[future]
                try:
                    case_name, success, output, duration = future.result()
                    self.results[case_name] = success
                    self.timings[case_name] = duration
                    
                    with self.output_lock:
                        status = "✅ COMPLETED" if success else "❌ FAILED"
                        print(f"[{case_name}] {status} ({duration:.1f}s)")
                        if not success and output:
                            print(f"[{case_name}] OUTPUT:")
                            for line in output.split('\n'):
                                if line.strip():
                                    print(f"[{case_name}] {line}")
                        print("-" * 40)
                        
                except Exception as e:
                    with self.output_lock:
                        print(f"[{case}] ❌ EXCEPTION: {str(e)}")
                        print("-" * 40)
                    self.results[case] = False
                    self.timings[case] = 0.0
        
        return self.results

    def display_summary(self) -> None:
        """Display final summary with green checks and red crosses"""
        print("\n" + "=" * 80)
        print("EXECUTION SUMMARY")
        print("=" * 80)
        
        successful_cases = []
        failed_cases = []
        total_time = 0.0
        
        for case, success in self.results.items():
            duration = self.timings.get(case, 0.0)
            total_time += duration
            
            if success:
                successful_cases.append(case)
                print(f"✅ {case} ({duration:.1f}s)")
            else:
                failed_cases.append(case)
                print(f"❌ {case} ({duration:.1f}s)")
        
        print("\n" + "-" * 80)
        print(f"Total cases: {len(self.results)}")
        print(f"Successful: {len(successful_cases)}")
        print(f"Failed: {len(failed_cases)}")
        print(f"Total execution time: {total_time:.1f}s")
        
        if self.results:
            avg_time = total_time / len(self.results)
            print(f"Average time per case: {avg_time:.1f}s")
        
        if failed_cases:
            print(f"\nFailed cases: {', '.join(failed_cases)}")
        
        success_rate = len(successful_cases) / len(self.results) * 100 if self.results else 0
        print(f"Success rate: {success_rate:.1f}%")

    @classmethod
    def parse_arguments(cls) -> Namespace:
        """Parse command line arguments"""
        parser = ArgumentParser(description="Run case_runner.py on multiple cases in parallel")
        parser.add_argument(
            "cases_number", 
            type=int,
            help="Number of first N cases to run (sorted by database id)"
        )
        parser.add_argument(
            "cycles", 
            type=int,
            help="Split the transcript in as many cycles (passed to case_runner.py)"
        )
        parser.add_argument(
            "workers", 
            type=int,
            help="Maximum number of parallel workers"
        )
        return parser.parse_args()

    @classmethod
    def validate_environment(cls) -> None:
        """Validate that required files exist"""
        case_runner_path = Path("case_runner.py")
        if not case_runner_path.exists():
            print("❌ Error: case_runner.py not found in current directory")
            sys.exit(1)

    def get_cases_from_database(self) -> list[str]:
        """Get the first N cases from database"""
        try:
            psql_credential = HelperEvaluation.postgres_credentials()
            case_db = Case(psql_credential)
            cases = case_db.get_first_n_cases(self.cases_number)
            
            if not cases:
                print(f"❌ Error: No cases found in database")
                sys.exit(1)
                
            return cases
            
        except Exception as e:
            print(f"❌ Error retrieving cases from database: {str(e)}")
            sys.exit(1)

    def run(self) -> None:
        """Main execution method"""
        args = self.parse_arguments()
        
        # Update instance variables with parsed arguments
        self.cases_number = args.cases_number
        self.cycles = args.cycles
        self.max_workers = args.workers
        
        # Validate environment
        self.validate_environment()
        
        # Get cases from database
        cases = self.get_cases_from_database()
        
        print(f"Retrieved {len(cases)} cases from database")
        print(f"Running {len(cases)} cases with {self.max_workers} parallel workers")
        if self.cycles > 0:
            print(f"Using {self.cycles} cycles per case")
        print()
        
        try:
            self.run_cases(cases)
            self.display_summary()
            
            # Exit with non-zero code if any cases failed
            if any(not success for success in self.results.values()):
                sys.exit(1)
                
        except KeyboardInterrupt:
            print("\n❌ Execution interrupted by user")
            sys.exit(1)



if __name__ == "__main__":
    runner = ParallelCaseRunner(cases_number=0, cycles=0, workers=5)
    runner.run()
