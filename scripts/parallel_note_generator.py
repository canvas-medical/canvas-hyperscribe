#!/usr/bin/env python3
"""
Parallel Note Generator Script

Generates notes for specified case IDs using case_runner.py in parallel.
"""

import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

from evaluations.datastores.postgres.case import Case
from evaluations.helper_evaluation import HelperEvaluation


class ParallelNoteGenerator:
    def __init__(self, cycles: int, workers: int, vendor: str = "all"):
        self.cycles = cycles
        self.max_workers = workers
        self.vendor = vendor
        self.output_lock = threading.Lock()
        self.results: dict[str, bool] = {}
        self.timings: dict[str, float] = {}
        
        # LLM vendors to use
        if vendor == "all":
            self.vendors = ["openai", "anthropic", "gemini"]
        else:
            self.vendors = [vendor]
        
        # Case IDs to process - specific ranges requested
        case_ranges = [
            range(329, 379)
        ]
        
        self.case_ids = []
        for case_range in case_ranges:
            self.case_ids.extend(list(case_range))

    def get_case_name(self, case_id: int) -> str:
        """Get case name by ID from database"""
        credentials = HelperEvaluation.postgres_credentials()
        case_db = Case(credentials)
        
        sql = 'SELECT name FROM "case" WHERE id = %(case_id)s'
        for record in case_db._select(sql, {"case_id": case_id}):
            return record["name"]
        
        raise ValueError(f"No case found with ID {case_id}")

    def check_generated_note_by_vendor(self, case_id: int, vendor: str) -> tuple[bool, str]:
        """Check if the generated note was created successfully for specific vendor"""
        try:
            credentials = HelperEvaluation.postgres_credentials()
            case_db = Case(credentials)
            
            # Map vendor names to database values
            vendor_mapping = {
                "openai": "OpenAI",
                "anthropic": "Anthropic", 
                "gemini": "Google"  # Gemini maps to "Google" in database
            }
            db_vendor = vendor_mapping.get(vendor, vendor)
            
            sql = '''SELECT failed, errors, text_llm_vendor
                     FROM generated_note 
                     WHERE case_id = %(case_id)s 
                     AND text_llm_vendor = %(vendor)s
                     ORDER BY created DESC 
                     LIMIT 1'''
            
            for record in case_db._select(sql, {"case_id": case_id, "vendor": db_vendor}):
                failed = record["failed"]
                errors = record["errors"]
                
                if failed:
                    error_msg = f"Note generation failed. Errors: {errors}"
                    return False, error_msg
                elif errors and len(errors) > 0:
                    error_msg = f"Note generated with warnings: {errors}"
                    return True, error_msg  # Success but with warnings
                else:
                    return True, f"Note generated successfully with {db_vendor}"
            
            return False, f"No generated note found for vendor {db_vendor}"
            
        except Exception as e:
            return False, f"Database check failed: {e}"

    def run_single_case_vendor(self, case_id: int, vendor: str) -> tuple[str, bool, str, float]:
        """Run case_runner.py for a single case with specific vendor"""
        start_time = time.time()
        case_vendor_key = f"{case_id}_{vendor}"
        
        try:
            case_name = self.get_case_name(case_id)
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Failed to get case name: {e}"
            with self.output_lock:
                print(f"[{case_id}:{vendor}] ERROR: {error_msg}")
            return case_vendor_key, False, error_msg, duration
        
        cmd = [sys.executable, "scripts/case_runner.py", "--case", case_name]
        if self.cycles > 0:
            cmd.extend(["--cycles", str(self.cycles)])

        # Set environment variable for vendor using correct variable names
        import os
        env = os.environ.copy()
        
        # Set vendor and API key based on vendor
        if vendor == "openai":
            env["VendorTextLLM"] = "OpenAI" 
            env["KeyTextLLM"] = env.get("OPENAI_API_KEY", env.get("KeyTextLLM", ""))
        elif vendor == "anthropic":
            env["VendorTextLLM"] = "Anthropic"
            env["KeyTextLLM"] = env.get("ANTHROPIC_API_KEY", "")
        elif vendor == "gemini":
            env["VendorTextLLM"] = "Google"  # Should be "Google", not "Gemini"!
            env["KeyTextLLM"] = env.get("GEMINI_API_KEY", "")

        try:
            # Run the case_runner.py script with vendor-specific environment
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env,
            )

            output_lines = []

            # Read output line by line for real-time display
            if process.stdout is not None:
                for line in iter(process.stdout.readline, ""):
                    line = line.rstrip()
                    if line:
                        output_lines.append(line)
                        # Queue the output for real-time display
                        with self.output_lock:
                            print(f"[{case_id}:{vendor}:{case_name}] {line}")

            process.wait()
            process_success = process.returncode == 0
            duration = round(time.time() - start_time, 1)
            
            # Check the database to see if note was actually generated successfully
            if process_success:
                db_success, db_message = self.check_generated_note_by_vendor(case_id, vendor)
                with self.output_lock:
                    if db_success:
                        print(f"[{case_id}:{vendor}] ✅ DATABASE: {db_message}")
                    else:
                        print(f"[{case_id}:{vendor}] ❌ DATABASE: {db_message}")
                return case_vendor_key, db_success, db_message, duration
            else:
                return case_vendor_key, False, "\n".join(output_lines), duration

        except Exception as e:
            duration = round(time.time() - start_time, 1)
            error_msg = f"Exception running case {case_id} with {vendor}: {str(e)}"
            with self.output_lock:
                print(f"[{case_id}:{vendor}] ERROR: {error_msg}")
            return case_vendor_key, False, error_msg, duration

    def run_cases(self) -> dict[str, bool]:
        """Run note generation for all cases with all vendors in parallel"""
        total_jobs = len(self.case_ids) * len(self.vendors)
        print(f"Starting parallel note generation for {len(self.case_ids)} cases x {len(self.vendors)} vendors = {total_jobs} total jobs")
        print(f"Using up to {self.max_workers} workers...")
        print(f"Vendors: {', '.join(self.vendors)}")
        print("=" * 80)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all case-vendor combinations to the executor
            future_to_job = {}
            for case_id in self.case_ids:
                for vendor in self.vendors:
                    future = executor.submit(self.run_single_case_vendor, case_id, vendor)
                    future_to_job[future] = (case_id, vendor)

            # Process completed futures as they finish
            for future in as_completed(future_to_job):
                case_id, vendor = future_to_job[future]
                try:
                    case_vendor_key, success, output, duration = future.result()
                    self.results[case_vendor_key] = success
                    self.timings[case_vendor_key] = duration

                    with self.output_lock:
                        status = "✅ COMPLETED" if success else "❌ FAILED"
                        print(f"[{case_id}:{vendor}] {status} ({duration:.1f}s)")
                        if not success and output:
                            print(f"[{case_id}:{vendor}] OUTPUT:")
                            for line in output.split("\n"):
                                if line.strip():
                                    print(f"[{case_id}:{vendor}] {line}")
                        print("-" * 40)

                except Exception as e:
                    case_vendor_key = f"{case_id}_{vendor}"
                    with self.output_lock:
                        print(f"[{case_id}:{vendor}] ❌ EXCEPTION: {str(e)}")
                        print("-" * 40)
                    self.results[case_vendor_key] = False
                    self.timings[case_vendor_key] = 0.0

        return self.results

    def display_summary(self) -> None:
        """Display final summary with green checks and red crosses"""
        print("\n" + "=" * 80)
        print("NOTE GENERATION SUMMARY")
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
        parser = ArgumentParser(description="Run case_runner.py on multiple cases in parallel with multiple LLM vendors")
        parser.add_argument(
            "cycles",
            type=int,
            help="Split the transcript in as many cycles (passed to case_runner.py)",
        )
        parser.add_argument("workers", type=int, help="Maximum number of parallel workers")
        parser.add_argument(
            "--vendor", 
            type=str, 
            choices=["openai", "anthropic", "gemini", "all"],
            default="all",
            help="LLM vendor to use (default: all - runs all three vendors)"
        )
        return parser.parse_args()

    @classmethod
    def validate_environment(cls) -> None:
        """Validate that required files exist"""
        case_runner_path = Path("scripts/case_runner.py")
        if not case_runner_path.exists():
            print("❌ Error: scripts/case_runner.py not found")
            sys.exit(1)

    def run(self) -> None:
        """Main execution method"""
        args = self.parse_arguments()

        # Update instance variables with parsed arguments
        self.cycles = args.cycles
        self.max_workers = args.workers
        self.vendor = args.vendor
        
        # Update vendors based on argument
        if self.vendor == "all":
            self.vendors = ["openai", "anthropic", "gemini"]
        else:
            self.vendors = [self.vendor]

        # Validate environment
        self.validate_environment()

        total_jobs = len(self.case_ids) * len(self.vendors)
        print(f"Running {len(self.case_ids)} cases x {len(self.vendors)} vendors = {total_jobs} total jobs")
        print(f"Using {self.max_workers} parallel workers")
        if self.cycles > 0:
            print(f"Using {self.cycles} cycles per case")
        print()

        try:
            self.run_cases()
            self.display_summary()

            # Exit with non-zero code if any cases failed
            if any(not success for success in self.results.values()):
                sys.exit(1)

        except KeyboardInterrupt:
            print("\n❌ Execution interrupted by user")
            sys.exit(1)


if __name__ == "__main__":
    runner = ParallelNoteGenerator(cycles=0, workers=5)
    runner.run()