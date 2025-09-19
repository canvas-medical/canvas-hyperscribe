#!/usr/bin/env python3

"""
Parallel Note Grading for Cycle Duration Experiments

This script runs note grading in parallel across multiple cases for experiment analysis.
It coordinates between two key CSV files:

1. experiment_notes_mapping.csv - Maps generated notes to their metadata
   Format: case_id,note_id,vendor,model
   Purpose: Identifies which notes were generated as part of the experiment
   
2. rubric_mapping.csv - Maps cases to their evaluation rubrics  
   Format: case_id,author,rubric_id
   Purpose: Identifies which rubrics should be used to evaluate each case
   
The script generates all possible note-rubric pairs from these mappings and runs
each pair through the note grader twice (for reliability). This produces the 
comprehensive scoring dataset needed for cycle duration performance analysis.

Example usage:
  python run_notes_parallel.py --cases 15 16 17 --max-workers 8

This would score all experiment notes for cases 15, 16, and 17 using 8 parallel workers.
Each note gets scored against all applicable rubrics, with 2 runs per rubric.
"""

import csv
import subprocess
import time
from argparse import ArgumentParser
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple


class NoteRubricPair(NamedTuple):
    case_id: int
    note_id: int
    vendor: str
    model: str
    rubric_id: int
    author: str
    run_number: int


class RunNotesParallel:
    def __init__(self, case_ids: list[int]):
        self.case_ids = case_ids
        self.base_path = Path(__file__).parent.parent
        self.experiment_notes_csv = self.base_path / "experiment_notes_mapping.csv"
        self.rubric_mapping_csv = self.base_path / "rubric_mapping.csv"

    @classmethod
    def parameters(cls):
        parser = ArgumentParser(description="Run note grading in parallel for multiple cases")
        parser.add_argument("--cases", nargs='+', type=int, required=True, help="Case IDs to process (e.g., --cases 15 16 17)")
        parser.add_argument("--max-workers", type=int, default=10, help="Maximum number of parallel workers")
        return parser.parse_args()

    def load_notes_for_cases(self) -> list[dict]:
        """Load all notes for the specified case IDs."""
        notes = []
        with open(self.experiment_notes_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if int(row['case_id']) in self.case_ids:
                    notes.append({
                        'case_id': int(row['case_id']),
                        'note_id': int(row['note_id']),
                        'vendor': row['vendor'],
                        'model': row['model']
                    })
        return notes

    def load_rubrics_for_cases(self) -> list[dict]:
        """Load all rubric IDs for the specified case IDs."""
        rubrics = []
        with open(self.rubric_mapping_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if int(row['case_id']) in self.case_ids:
                    rubrics.append({
                        'case_id': int(row['case_id']),
                        'author': row['author'],
                        'rubric_id': int(row['rubric_id'])
                    })
        return rubrics

    def generate_tasks(self) -> list[NoteRubricPair]:
        """Generate all note-rubric pairs with 2 runs each."""
        notes = self.load_notes_for_cases()
        rubrics = self.load_rubrics_for_cases()
        
        if not notes:
            raise ValueError(f"No notes found for cases {self.case_ids}")
        if not rubrics:
            raise ValueError(f"No rubrics found for cases {self.case_ids}")
        
        tasks = []
        for note in notes:
            # Find rubrics for this specific case
            case_rubrics = [r for r in rubrics if r['case_id'] == note['case_id']]
            for rubric in case_rubrics:
                # Run each pair twice
                for run_number in [1, 2]:
                    task = NoteRubricPair(
                        case_id=note['case_id'],
                        note_id=note['note_id'],
                        vendor=note['vendor'],
                        model=note['model'],
                        rubric_id=rubric['rubric_id'],
                        author=rubric['author'],
                        run_number=run_number
                    )
                    tasks.append(task)
        
        return tasks

    @staticmethod
    def run_single_grading(task: NoteRubricPair) -> dict:
        """Run a single note grading task."""
        cmd = [
            "uv", "run", "python", 
            "evaluations/case_builders/note_grader.py",
            "--rubric_id", str(task.rubric_id),
            "--generated_note_id", str(task.note_id)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout per task (increased for rate limits)
                cwd="/Users/aaryanshah/canvas-hyperscribe"
            )
            
            return {
                'task': task,
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                'task': task,
                'success': False,
                'stdout': '',
                'stderr': 'Task timed out after 5 minutes',
                'returncode': -1
            }
        except Exception as e:
            return {
                'task': task,
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': -2
            }

    def run_parallel(self, max_workers: int = 8) -> None:
        """Run all note grading tasks in parallel."""
        tasks = self.generate_tasks()
        
        print(f"Generated {len(tasks)} grading tasks for cases {self.case_ids}")
        print(f"Notes: {len(self.load_notes_for_cases())}")
        print(f"Rubrics: {len(self.load_rubrics_for_cases())}")
        print(f"Expected scores: {len(tasks)} (each note-rubric pair run twice)")
        print(f"Using {max_workers} parallel workers\n")
        
        completed = 0
        successful = 0
        failed = 0
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_task = {executor.submit(self.run_single_grading, task): task for task in tasks}
            
            # Process results as they complete
            for future in as_completed(future_to_task):
                result = future.result()
                task = result['task']
                completed += 1
                
                if result['success']:
                    successful += 1
                    print(f"✓ [{completed}/{len(tasks)}] Case {task.case_id} | Note {task.note_id} ({task.vendor}) | Rubric {task.rubric_id} | Run {task.run_number}")
                    if result['stdout'].strip():
                        print(f"   Output: {result['stdout'].strip()}")
                else:
                    failed += 1
                    print(f"✗ [{completed}/{len(tasks)}] FAILED Case {task.case_id} | Note {task.note_id} ({task.vendor}) | Rubric {task.rubric_id} | Run {task.run_number}")
                    print(f"   Error (code {result['returncode']}): {result['stderr'].strip()}")
                    if result['stdout'].strip():
                        print(f"   Stdout: {result['stdout'].strip()}")
        
        print(f"\nCompleted: {completed}/{len(tasks)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        
        if failed > 0:
            print(f"\nWARNING: {failed} tasks failed. Check the error messages above.")

    @classmethod
    def run(cls) -> None:
        args = cls.parameters()
        runner = cls(args.cases)
        runner.run_parallel(args.max_workers)


if __name__ == "__main__":
    RunNotesParallel.run()