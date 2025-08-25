"""
Script to analyze rubric authors and extract their rubric and score data.
Usage: PYTHONPATH=. python analyze_rubric_authors.py
"""

import os
import csv
import json
from typing import List, Dict, Any
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.datastores.postgres.postgres import Postgres


def print_unique_authors(pg: Postgres) -> List[str]:
    """Print all unique authors from the rubric table and return them as a list."""
    sql = """
    SELECT DISTINCT author 
    FROM rubric 
    WHERE author IS NOT NULL AND author <> '' 
    ORDER BY author
    """
    
    rows = pg._select(sql, {})
    authors = [row['author'] for row in rows]
    
    print("Unique authors in the rubric table:")
    print("=" * 50)
    for i, author in enumerate(authors, 1):
        print(f"{i:2d}. {author}")
    print(f"\nTotal: {len(authors)} unique authors")
    print("=" * 50)
    
    return authors


def format_rubric_criteria(rubric_data: List[Dict]) -> str:
    """Format rubric criteria in a readable way."""
    if not rubric_data:
        return "No criteria"
    
    formatted_criteria = []
    for i, criterion in enumerate(rubric_data, 1):
        criterion_text = criterion.get('criterion', 'Unknown criterion')
        weight = criterion.get('weight', 0)
        sense = criterion.get('sense', 'unknown')
        formatted_criteria.append(f"[{i}] {criterion_text} (Weight: {weight}, Sense: {sense})")
    
    return " | ".join(formatted_criteria)


def format_scoring_results(scoring_result: List[Dict]) -> str:
    """Format scoring results in a readable way."""
    if not scoring_result:
        return "No scoring data"
    
    formatted_scores = []
    for i, result in enumerate(scoring_result, 1):
        # Handle case where result might be a list instead of dict
        if isinstance(result, list):
            # If it's a list, try to extract meaningful data or show the full content
            if len(result) >= 4:  # Assuming list has [id, rationale, satisfaction, score] format
                try:
                    criterion_id = result[0] if isinstance(result[0], (int, float)) else i
                    rationale = str(result[1]) if len(result) > 1 else 'No rationale'
                    satisfaction = result[2] if isinstance(result[2], (int, float)) and len(result) > 2 else 0
                    score = result[3] if isinstance(result[3], (int, float)) and len(result) > 3 else 0
                    formatted_scores.append(f"[{criterion_id+1}] Satisfaction: {satisfaction}% | Score: {score} | Rationale: {rationale}")
                except (IndexError, TypeError):
                    formatted_scores.append(f"[{i}] List data: {str(result)}")
            else:
                formatted_scores.append(f"[{i}] List data: {str(result)}")
            continue
        
        if not isinstance(result, dict):
            formatted_scores.append(f"[{i}] Unknown format: {str(result)}")
            continue
            
        criterion_id = result.get('id', i-1)
        rationale = result.get('rationale', 'No rationale')
        satisfaction = result.get('satisfaction', 0)
        score = result.get('score', 0)
        formatted_scores.append(f"[{criterion_id+1}] Satisfaction: {satisfaction}% | Score: {score} | Rationale: {rationale}")
    
    return " | ".join(formatted_scores)


def extract_author_data(pg: Postgres, authors: List[str]) -> None:
    """
    Extract rubric and score data for each author and save to separate CSV files.
    
    Args:
        pg: Postgres connection object
        authors: List of author email addresses to analyze
    """
    
    for author in authors:
        print(f"\nProcessing data for: {author}")
        
        # Query to get all rubrics and associated scores for this specific author
        sql = """
        SELECT 
            r.id as rubric_id,
            r.author,
            r.case_id,
            c.name as case_name,
            r.created as rubric_created,
            r.updated as rubric_updated,
            r.validation,
            r.rubric as rubric_data,
            r.case_provenance_classification,
            r.comments as rubric_comments,
            r.text_llm_vendor as rubric_llm_vendor,
            r.text_llm_name as rubric_llm_name,
            r.temperature as rubric_temperature,
            s.id as score_id,
            s.generated_note_id,
            s.overall_score,
            s.created as score_created,
            s.updated as score_updated,
            s.scoring_result,
            s.text_llm_vendor as score_llm_vendor
        FROM rubric r
        LEFT JOIN score s ON s.rubric_id = r.id
        LEFT JOIN "case" c ON r.case_id = c.id
        WHERE r.author = %(author)s
        ORDER BY r.id, s.generated_note_id NULLS LAST
        """
        
        rows = list(pg._select(sql, {"author": author}))
        
        if not rows:
            print(f"No data found for author: {author}")
            continue
        
        # Create readable filename
        author_name = author.split('@')[0]
        output_file = f"rubric_data_{author_name}.csv"
        
        # Prepare CSV data with readable field names
        fieldnames = [
            'Rubric_ID',
            'Author_Email',
            'Case_ID', 
            'Case_Name',
            'Rubric_Created_Date',
            'Rubric_Updated_Date',
            'Validation_Status',
            'Rubric_Criteria_Details',
            'Case_Classification',
            'Rubric_Comments',
            'Rubric_LLM_Vendor',
            'Rubric_LLM_Model',
            'Rubric_Temperature',
            'Score_ID',
            'Generated_Note_ID',
            'Overall_Score',
            'Score_Created_Date',
            'Score_Updated_Date',
            'Scoring_Details',
            'Score_LLM_Vendor'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in rows:
                # Format the data for readability
                csv_row = {
                    'Rubric_ID': row.get('rubric_id'),
                    'Author_Email': row.get('author'),
                    'Case_ID': row.get('case_id'),
                    'Case_Name': row.get('case_name'),
                    'Rubric_Created_Date': str(row.get('rubric_created'))[:19] if row.get('rubric_created') else None,
                    'Rubric_Updated_Date': str(row.get('rubric_updated'))[:19] if row.get('rubric_updated') else None,
                    'Validation_Status': row.get('validation'),
                    'Rubric_Criteria_Details': format_rubric_criteria(row.get('rubric_data', [])),
                    'Case_Classification': row.get('case_provenance_classification'),
                    'Rubric_Comments': row.get('rubric_comments'),
                    'Rubric_LLM_Vendor': row.get('rubric_llm_vendor'),
                    'Rubric_LLM_Model': row.get('rubric_llm_name'),
                    'Rubric_Temperature': row.get('rubric_temperature'),
                    'Score_ID': row.get('score_id'),
                    'Generated_Note_ID': row.get('generated_note_id'),
                    'Overall_Score': row.get('overall_score'),
                    'Score_Created_Date': str(row.get('score_created'))[:19] if row.get('score_created') else None,
                    'Score_Updated_Date': str(row.get('score_updated'))[:19] if row.get('score_updated') else None,
                    'Scoring_Details': format_scoring_results(row.get('scoring_result', [])),
                    'Score_LLM_Vendor': row.get('score_llm_vendor')
                }
                
                writer.writerow(csv_row)
        
        print(f"✓ Data saved to: {output_file}")
        print(f"✓ Total records: {len(rows)}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze rubric authors and extract their data")
    parser.add_argument("--authors", nargs="*", help="Email addresses of authors to analyze")
    parser.add_argument("--list-only", action="store_true", help="Only list unique authors and exit")
    args = parser.parse_args()
    
    # Load & validate credentials
    creds = PostgresCredentials.from_dictionary(dict(os.environ))
    if not creds.is_ready():
        raise SystemExit("✖ Missing or invalid Postgres credentials. Make sure to run 'source local_env.sh' first.")
    
    # Connect to database
    pg = Postgres(creds)
    print("✓ Connected to database successfully")
    
    # Step 1: Print all unique authors
    authors_list = print_unique_authors(pg)
    
    if args.list_only:
        return
    
    # Step 2: Process author selection
    if not args.authors:
        print("\nUsage examples:")
        print("  # List all authors:")
        print("  PYTHONPATH=. uv run python analyze_rubric_authors.py --list-only")
        print("\n  # Analyze specific authors:")
        print("  PYTHONPATH=. uv run python analyze_rubric_authors.py --authors author1@example.com author2@example.com")
        return
    
    # Validate selected authors
    selected_authors = []
    for author in args.authors:
        if author in authors_list:
            selected_authors.append(author)
            print(f"✓ Found author: {author}")
        else:
            print(f"✗ Author '{author}' not found in database.")
    
    if not selected_authors:
        print("No valid authors selected. Use --list-only to see available authors.")
        return
    
    print(f"\nAnalyzing data for {len(selected_authors)} author(s): {', '.join(selected_authors)}")
    
    # Step 3: Extract data for selected authors (creates separate CSV for each)
    extract_author_data(pg, selected_authors)


if __name__ == "__main__":
    main()