#!/usr/bin/env python3

from evaluations.datastores.postgres.generated_note import GeneratedNote
from evaluations.helper_evaluation import HelperEvaluation


class AnalyzeFailedNotes:
    def __init__(self):
        self.postgres_credentials = HelperEvaluation.postgres_credentials()
        self.generated_note_db = GeneratedNote(self.postgres_credentials)
    
    def analyze_notes_from_id(self, start_id: int = 458) -> dict:
        """Analyze generated_note table from a specific ID onwards."""
        # Query to get all notes from the start_id onwards
        sql = """
            SELECT id, case_id, text_llm_vendor, text_llm_name, failed, note_json, errors
            FROM generated_note 
            WHERE id >= %(start_id)s 
            ORDER BY id
        """
        
        failed_notes: list[dict] = []
        missing_notes: list[int] = []
        vendor_stats: dict[str, dict] = {"GPT-4o": {"total": 0, "failed": 0}, "Claude": {"total": 0, "failed": 0}}
        
        all_notes = list(self.generated_note_db._select(sql, {"start_id": start_id}))
        
        if not all_notes:
            print(f"No notes found from ID {start_id} onwards")
            return {}
            
        # Get the range of IDs we should have
        min_id = min(note["id"] for note in all_notes)
        max_id = max(note["id"] for note in all_notes)
        existing_ids = {note["id"] for note in all_notes}
        
        # Find missing IDs in the sequence
        for expected_id in range(min_id, max_id + 1):
            if expected_id not in existing_ids:
                missing_notes.append(expected_id)
        
        # Analyze each note
        for note in all_notes:
            note_id = note["id"]
            case_id = note["case_id"]
            vendor = note["text_llm_vendor"] or "Unknown"
            model = note["text_llm_name"] or "Unknown"
            failed = note["failed"]
            note_json = note["note_json"]
            errors = note["errors"]
            
            # Count vendor stats
            if vendor in vendor_stats:
                vendor_stats[vendor]["total"] += 1
                if failed:
                    vendor_stats[vendor]["failed"] += 1
            
            # Check if note failed or has issues
            is_problematic = False
            reasons: list[str] = []
            
            if failed:
                is_problematic = True
                reasons.append("failed=true")
            
            if not note_json or note_json == {} or note_json == "{}":
                is_problematic = True
                reasons.append("empty_note_json")
            
            if errors and errors != [] and errors != "[]":
                is_problematic = True
                reasons.append("has_errors")
            
            if is_problematic:
                failed_notes.append({
                    "id": note_id,
                    "case_id": case_id,
                    "vendor": vendor,
                    "model": model,
                    "failed": failed,
                    "reasons": reasons,
                    "errors": errors
                })
        
        return {
            "analysis_range": f"ID {min_id} to {max_id}",
            "total_notes_found": len(all_notes),
            "missing_note_ids": missing_notes,
            "failed_notes": failed_notes,
            "vendor_stats": vendor_stats,
            "notes_needing_rerun": list(set([note["case_id"] for note in failed_notes] + missing_notes))
        }
    
    def print_analysis(self, start_id: int = 458) -> None:
        """Print detailed analysis of failed notes."""
        result = self.analyze_notes_from_id(start_id)
        
        if not result:
            return
            
        print("=" * 80)
        print("FAILED NOTES ANALYSIS")
        print("=" * 80)
        print(f"Analysis range: {result['analysis_range']}")
        print(f"Total notes found: {result['total_notes_found']}")
        print()
        
        # Missing notes
        if result['missing_note_ids']:
            print(f"MISSING NOTE IDs ({len(result['missing_note_ids'])}): {result['missing_note_ids']}")
        else:
            print("No missing note IDs in sequence")
        print()
        
        # Vendor stats
        print("VENDOR STATISTICS:")
        for vendor, stats in result['vendor_stats'].items():
            total = stats['total']
            failed = stats['failed']
            success_rate = ((total - failed) / total * 100) if total > 0 else 0
            print(f"  {vendor}: {total - failed}/{total} ({success_rate:.1f}% success)")
        print()
        
        # Failed notes details
        print(f"FAILED NOTES DETAILS ({len(result['failed_notes'])}):")
        for note in result['failed_notes']:
            print(f"  ID {note['id']} (Case {note['case_id']}): {note['vendor']}/{note['model']}")
            print(f"    Reasons: {', '.join(note['reasons'])}")
            if note['errors'] and note['errors'] not in [[], "[]"]:
                print(f"    Errors: {note['errors']}")
        print()
        
        # Summary for rerun
        notes_to_rerun = result['notes_needing_rerun']
        print(f"NOTES/CASES NEEDING RE-RUN ({len(notes_to_rerun)}):")
        print(f"Case IDs: {sorted(set([n for n in notes_to_rerun if isinstance(n, int)]))}")
        print()
        
        print("=" * 80)


if __name__ == "__main__":
    analyzer = AnalyzeFailedNotes()
    analyzer.print_analysis(458)