import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from dataclasses import dataclass


@dataclass
class RunResult:
    case_id: int
    run_number: int
    success: bool
    error_message: str = ""
    duration: float = 0.0


class CycleTimeCaseRunner:
    """
    Runs case_runner.py multiple times for each specified case ID to test cycle time effects.
    Uses parallel execution for speed.
    """
    
    RUNS_PER_CASE = 5
    DEFAULT_MAX_WORKERS = 10  # Parallel jobs
    
    def __init__(self, max_workers: int = DEFAULT_MAX_WORKERS):
        self.max_workers = max_workers
        self.lock = threading.Lock()
        self.completed_runs = 0
        self.total_runs = 0
    
    @classmethod
    def get_case_name_from_id(cls, case_id: int) -> str:
        """Get case name from case ID by querying the database."""
        import subprocess
        try:
            result = subprocess.run([
                "psql", "postgresql://aptible:h-5FO4MXav-DIXLlN_88KiFVpFELZzJY@localhost.aptible.in:61888/db",
                "-c", f"SELECT name FROM \"case\" WHERE id = {case_id};", "-t"
            ], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"case_{case_id}"
        except:
            return f"case_{case_id}"

    @classmethod
    def get_all_case_ids(cls) -> List[int]:
        """Get all case IDs from experiment_notes_mapping.csv"""
        experiment_mapping_path = Path(__file__).parent.parent / "experiment_notes_mapping.csv"
        
        if not experiment_mapping_path.exists():
            raise FileNotFoundError(f"Could not find experiment_notes_mapping.csv at {experiment_mapping_path}")
        
        case_ids = set()
        with open(experiment_mapping_path, 'r') as f:
            next(f)  # Skip header
            for line in f:
                if line.strip():
                    case_id = int(line.split(',')[0])
                    case_ids.add(case_id)
        
        return sorted(list(case_ids))
    
    def run_single_case_once(self, case_id: int, run_number: int, chunk_duration_seconds: int = None) -> RunResult:
        """
        Run a single case once.
        
        Args:
            case_id: The case ID to run
            run_number: Which run this is (1-5)
            
        Returns:
            RunResult with success status and details
        """
        import time
        start_time = time.time()
        
        case_runner_path = Path(__file__).parent / "case_runner.py"
        
        try:
            # Get case name from case ID
            case_name = self.__class__.get_case_name_from_id(case_id)
            
            # Build command arguments
            cmd_args = [
                "uv", "run", "python", str(case_runner_path),
                "--case", case_name
            ]
            
            # Add chunk duration parameter if specified
            if chunk_duration_seconds is not None:
                cmd_args.extend(["--chunk_duration_seconds", str(chunk_duration_seconds)])
            
            result = subprocess.run(cmd_args, capture_output=True, text=True, timeout=2400)  # 5 minute timeout
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                with self.lock:
                    self.completed_runs += 1
                    progress = (self.completed_runs / self.total_runs) * 100
                    print(f"✓ Case {case_id} run {run_number}/5 completed ({self.completed_runs}/{self.total_runs} - {progress:.1f}%)")
                    
                    # Print case_runner output for debugging (only show last few lines)
                    if result.stdout.strip():
                        stdout_lines = result.stdout.strip().split('\n')
                        if len(stdout_lines) > 3:
                            print(f"    Output: ...{stdout_lines[-1]}")
                        else:
                            print(f"    Output: {result.stdout.strip()}")
                
                return RunResult(
                    case_id=case_id,
                    run_number=run_number,
                    success=True,
                    duration=duration
                )
            else:
                error_msg = result.stderr.strip() if result.stderr else f"Return code: {result.returncode}"
                
                with self.lock:
                    self.completed_runs += 1
                    progress = (self.completed_runs / self.total_runs) * 100
                    print(f"✗ Case {case_id} run {run_number}/5 failed ({self.completed_runs}/{self.total_runs} - {progress:.1f}%) - {error_msg}")
                
                return RunResult(
                    case_id=case_id,
                    run_number=run_number,
                    success=False,
                    error_message=error_msg,
                    duration=duration
                )
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            with self.lock:
                self.completed_runs += 1
                progress = (self.completed_runs / self.total_runs) * 100
                print(f"✗ Case {case_id} run {run_number}/5 timeout ({self.completed_runs}/{self.total_runs} - {progress:.1f}%)")
            
            return RunResult(
                case_id=case_id,
                run_number=run_number,
                success=False,
                error_message="Timeout (>5 minutes)",
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            with self.lock:
                self.completed_runs += 1
                progress = (self.completed_runs / self.total_runs) * 100
                print(f"✗ Case {case_id} run {run_number}/5 exception ({self.completed_runs}/{self.total_runs} - {progress:.1f}%) - {str(e)}")
            
            return RunResult(
                case_id=case_id,
                run_number=run_number,
                success=False,
                error_message=str(e),
                duration=duration
            )
    
    def run_multiple_cases_parallel(self, case_ids: List[int], chunk_duration_seconds: int = None) -> List[RunResult]:
        """
        Run multiple cases in parallel, each case 5 times.
        
        Args:
            case_ids: List of case IDs to run
            
        Returns:
            List of all RunResults
        """
        # Create all tasks
        tasks = []
        for case_id in case_ids:
            for run_num in range(1, self.RUNS_PER_CASE + 1):
                tasks.append((case_id, run_num))
        
        self.total_runs = len(tasks)
        self.completed_runs = 0
        
        # Print environment configuration
        import os
        from hyperscribe.libraries.constants import Constants
        
        audio_interval = os.getenv('AudioIntervalSeconds', 'Not set')
        text_vendor = os.getenv('VendorTextLLM', os.getenv('TEXT_VENDOR', 'Not set'))
        text_model = os.getenv('TEXT_MODEL', 'Not set')
        audio_vendor = os.getenv('VendorAudioLLM', os.getenv('AUDIO_VENDOR', 'Not set'))
        max_audio_interval = Constants.MAX_AUDIO_INTERVAL_SECONDS
        
        print(f"{'='*60}")
        print(f"CYCLE TIME EXPERIMENT CONFIGURATION")
        print(f"{'='*60}")
        print(f"Audio Interval Seconds: {audio_interval}")
        print(f"Max Audio Interval (constants): {max_audio_interval}")
        print(f"Text LLM Vendor: {text_vendor}")
        print(f"Text Model: {text_model}")
        print(f"Audio LLM Vendor: {audio_vendor}")
        print(f"Cases: {len(case_ids)} cases")
        
        # Show case names
        print("Case details:")
        for case_id in case_ids[:5]:  # Show first 5 cases
            case_name = self.__class__.get_case_name_from_id(case_id)
            print(f"  Case {case_id}: {case_name}")
        if len(case_ids) > 5:
            print(f"  ... and {len(case_ids) - 5} more cases")
            
        if chunk_duration_seconds:
            target_words = int((chunk_duration_seconds / 60.0) * 140)
            print(f"Chunk Duration: {chunk_duration_seconds}s (~{target_words} words per chunk)")
            
        print(f"Runs per case: {self.RUNS_PER_CASE}")
        print(f"Total runs: {self.total_runs}")
        print(f"Max parallel workers: {self.max_workers}")
        print(f"{'='*60}")
        print(f"\nStarting experiment...")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self.run_single_case_once, case_id, run_num, chunk_duration_seconds): (case_id, run_num)
                for case_id, run_num in tasks
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_task):
                result = future.result()
                results.append(result)
        
        return results
    
    def print_summary(self, results: List[RunResult]) -> None:
        """Print experiment summary."""
        # Group results by case
        case_results = {}
        for result in results:
            if result.case_id not in case_results:
                case_results[result.case_id] = []
            case_results[result.case_id].append(result)
        
        total_runs = len(results)
        successful_runs = sum(1 for r in results if r.success)
        failed_cases = []
        
        for case_id, case_run_results in case_results.items():
            successes = sum(1 for r in case_run_results if r.success)
            if successes < self.RUNS_PER_CASE:
                failed_cases.append({
                    'case_id': case_id,
                    'successful_runs': successes,
                    'total_runs': self.RUNS_PER_CASE,
                    'failures': [r for r in case_run_results if not r.success]
                })
        
        # Calculate timing stats
        avg_duration = sum(r.duration for r in results) / len(results) if results else 0
        total_duration = sum(r.duration for r in results)
        
        print(f"\n{'='*60}")
        print(f"PARALLEL EXPERIMENT COMPLETE")
        print(f"{'='*60}")
        print(f"Total runs: {successful_runs}/{total_runs}")
        print(f"Success rate: {(successful_runs/total_runs)*100:.1f}%")
        print(f"Average run time: {avg_duration:.1f}s")
        print(f"Total compute time: {total_duration:.1f}s")
        print(f"Cases processed: {len(case_results)}")
        
        if failed_cases:
            print(f"\nCases with failures ({len(failed_cases)}):")
            for case_info in failed_cases[:10]:  # Show first 10
                print(f"  Case {case_info['case_id']}: {case_info['successful_runs']}/{case_info['total_runs']} successful")
                # Show first error
                if case_info['failures']:
                    first_error = case_info['failures'][0]
                    print(f"    Sample error: {first_error.error_message}")
            if len(failed_cases) > 10:
                print(f"    ... and {len(failed_cases) - 10} more cases with failures")
        else:
            print(f"\n🎉 All cases completed successfully!")
    
    @classmethod
    def parameters(cls) -> ArgumentParser:
        """Parse command line arguments."""
        parser = ArgumentParser(description="Run case_runner.py multiple times for cycle time experiments (parallelized)")
        parser.add_argument(
            "--cases", 
            nargs='+', 
            type=int,
            help="Case IDs to run (e.g., --cases 15 16 17 18 19 20)"
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Run all 107 cases from experiment_notes_mapping.csv"
        )
        parser.add_argument(
            "--list",
            action="store_true", 
            help="List all available case IDs and exit"
        )
        parser.add_argument(
            "--max-workers",
            type=int,
            default=cls.DEFAULT_MAX_WORKERS,
            help=f"Maximum parallel workers (default: {cls.DEFAULT_MAX_WORKERS})"
        )
        parser.add_argument(
            "--chunk_duration_seconds",
            type=int,
            help="Split transcript by word count based on duration (15 or 60 seconds)"
        )
        
        return parser
    
    @classmethod
    def run(cls) -> None:
        """Main entry point."""
        parser = cls.parameters()
        args = parser.parse_args()
        
        # Get all available case IDs
        try:
            all_case_ids = cls.get_all_case_ids()
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        
        # Handle --list option
        if args.list:
            print(f"Available case IDs ({len(all_case_ids)} total):")
            print(", ".join(map(str, all_case_ids)))
            return
        
        # Determine which cases to run
        if args.all:
            case_ids = all_case_ids
            print(f"Running ALL {len(case_ids)} cases")
        elif args.cases:
            # Validate provided case IDs
            invalid_cases = [c for c in args.cases if c not in all_case_ids]
            if invalid_cases:
                print(f"Error: Invalid case IDs: {invalid_cases}")
                print(f"Valid case IDs: {all_case_ids}")
                sys.exit(1)
            case_ids = sorted(args.cases)
        else:
            print("Error: Must specify either --cases or --all")
            parser.print_help()
            sys.exit(1)
        
        # Run the experiment
        runner = cls(max_workers=args.max_workers)
        results = runner.run_multiple_cases_parallel(case_ids, args.chunk_duration_seconds)
        runner.print_summary(results)


if __name__ == "__main__":
    CycleTimeCaseRunner.run()