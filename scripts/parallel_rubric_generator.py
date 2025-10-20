"""
Parallel Rubric Generator Script

Generates rubrics for specified case IDs using rubric_generator.py in parallel.
"""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from evaluations.datastores.postgres.case import Case
from evaluations.helper_evaluation import HelperEvaluation


class ParallelRubricGenerator:
    def __init__(self, max_workers: int = 10, batch_start: int = 399, batch_size: int = 100):
        self.max_workers = max_workers
        self.canvas_context_path = "./evaluations/case_builders/context_canvas_commands.json"
        self.batch_start = batch_start
        self.batch_size = batch_size
        
        # Generate case IDs for the current batch (399-3183 total range)
        batch_end = min(batch_start + batch_size - 1, 3183)
        self.case_ids = list(range(batch_start, batch_end + 1))
        
        print(f"Processing batch: cases {batch_start}-{batch_end} ({len(self.case_ids)} cases)")

    def get_case_name(self, case_id: int) -> str:
        """Get case name by ID from database"""
        credentials = HelperEvaluation.postgres_credentials()
        case_db = Case(credentials)
        
        sql = 'SELECT name FROM "case" WHERE id = %(case_id)s'
        for record in case_db._select(sql, {"case_id": case_id}):
            return record["name"]
        
        raise ValueError(f"No case found with ID {case_id}")

    def generate_rubric(self, case_id: int) -> tuple[int, bool, str]:
        """Generate rubric for a single case"""
        try:
            case_name = self.get_case_name(case_id)
        except Exception as e:
            error_msg = f"Failed to get case name: {e}"
            print(f"{error_msg}")
            return case_id, False, error_msg
        
        print(f"🔄 Generating rubric for case {case_id}: {case_name}")
        
        try:
            cmd = [
                sys.executable, 
                "evaluations/case_builders/rubric_generator.py",
                "--case_name", case_name,
                "--canvas_context_path", self.canvas_context_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                print(f"✅ Completed case {case_id}: {case_name}")
                return case_id, True, "Success"
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                print(f"❌ Failed case {case_id}: {case_name}")
                print(f"   Error: {error_msg}")
                return case_id, False, error_msg
                
        except subprocess.TimeoutExpired:
            error_msg = "Timeout after 5 minutes"
            print(f"❌ Failed case {case_id}: {case_name} - {error_msg}")
            return case_id, False, error_msg
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Failed case {case_id}: {case_name} - {error_msg}")
            return case_id, False, error_msg

    def run(self) -> None:
        """Run rubric generation for all cases in parallel"""
        print(f"🚀 Starting rubric generation for {len(self.case_ids)} cases with {self.max_workers} workers")
        print(f"Canvas context path: {self.canvas_context_path}")
        print("=" * 80)
        
        successful_cases = []
        failed_cases = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all cases
            future_to_case = {
                executor.submit(self.generate_rubric, case_id): case_id 
                for case_id in self.case_ids
            }
            
            # Process results as they complete
            for future in as_completed(future_to_case):
                case_id = future_to_case[future]
                try:
                    case_id, success, message = future.result()
                    if success:
                        successful_cases.append(case_id)
                    else:
                        failed_cases.append((case_id, message))
                except Exception as e:
                    print(f"❌ Exception for case {case_id}: {e}")
                    failed_cases.append((case_id, str(e)))
        
        # Print summary
        print("=" * 80)
        print("🏁 Rubric generation completed")
        print(f"Total cases: {len(self.case_ids)}")
        print(f"Successful: {len(successful_cases)}")
        print(f"Failed: {len(failed_cases)}")
        
        if failed_cases:
            print("\nFailed cases:")
            for case_id, error in failed_cases:
                print(f"  {case_id}: {error}")
        
        success_rate = len(successful_cases) / len(self.case_ids) * 100 if self.case_ids else 0
        print(f"Success rate: {success_rate:.1f}%")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate rubrics for cases in parallel batches")
    parser.add_argument("--batch-start", type=int, required=True, help="Starting case ID for batch")
    parser.add_argument("--batch-size", type=int, default=100, help="Number of cases per batch (default: 100)")
    parser.add_argument("--max-workers", type=int, default=10, help="Maximum number of parallel workers (default: 10)")
    
    args = parser.parse_args()
    
    generator = ParallelRubricGenerator(
        max_workers=args.max_workers,
        batch_start=args.batch_start, 
        batch_size=args.batch_size
    )
    generator.run()