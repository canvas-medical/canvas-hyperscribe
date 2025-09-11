#!/usr/bin/env python3

import subprocess
import sys


def run_sql_query(query: str) -> list:
    """Run a SQL query using psql and return results."""
    db_url = "postgresql://aptible:h-5FO4MXav-DIXLlN_88KiFVpFELZzJY@localhost.aptible.in:61777/db"
    
    try:
        result = subprocess.run(
            ["psql", db_url, "-t", "-c", query],
            capture_output=True,
            text=True,
            check=True
        )
        
        lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        return lines
    except subprocess.CalledProcessError as e:
        print(f"Database query failed: {e}")
        sys.exit(1)


def check_remaining_cases():
    """Check which case-vendor pairs still need runs to reach 5 successful each."""
    
    # Query for remaining incomplete cases
    remaining_sql = """
    SELECT 
        c.id || '|' || c.name || '|' || incomplete.text_llm_vendor || '|' || 
        incomplete.successful_count || '|' || (5 - incomplete.successful_count) as data
    FROM "case" c
    JOIN (
        SELECT 
            case_id,
            text_llm_vendor,
            SUM(CASE WHEN failed = 'f' THEN 1 ELSE 0 END) as successful_count
        FROM generated_note 
        WHERE id >= 458
        GROUP BY case_id, text_llm_vendor
        HAVING SUM(CASE WHEN failed = 'f' THEN 1 ELSE 0 END) < 5
    ) incomplete ON c.id = incomplete.case_id
    ORDER BY (5 - incomplete.successful_count) DESC, case_id, text_llm_vendor;
    """
    
    remaining_lines = run_sql_query(remaining_sql)
    
    if not remaining_lines:
        print("🎉 ALL CASES COMPLETE! Dataset is ready.")
        return
    
    # Parse results
    remaining_cases = []
    for line in remaining_lines:
        parts = line.split('|')
        if len(parts) == 5:
            remaining_cases.append({
                'case_id': int(parts[0]),
                'case_name': parts[1],
                'vendor': parts[2],
                'successful_count': int(parts[3]),
                'runs_needed': int(parts[4])
            })
    
    print("=" * 80)
    print("REMAINING CASES TO COMPLETE")
    print("=" * 80)
    
    # Summary stats
    total_runs_needed = sum(case['runs_needed'] for case in remaining_cases)
    openai_runs = sum(case['runs_needed'] for case in remaining_cases if case['vendor'] == 'OpenAI')
    anthropic_runs = sum(case['runs_needed'] for case in remaining_cases if case['vendor'] == 'Anthropic')
    
    print(f"Total runs needed: {total_runs_needed}")
    print(f"OpenAI runs needed: {openai_runs}")
    print(f"Anthropic runs needed: {anthropic_runs}")
    print(f"Case-vendor pairs incomplete: {len(remaining_cases)}")
    print()
    
    # Group by vendor
    openai_cases = [case for case in remaining_cases if case['vendor'] == 'OpenAI']
    anthropic_cases = [case for case in remaining_cases if case['vendor'] == 'Anthropic']
    
    if openai_cases:
        print("OPENAI CASES NEEDED:")
        for case in openai_cases:
            print(f"  Case {case['case_id']}: {case['case_name']} -> {case['runs_needed']} runs needed")
        print()
    
    if anthropic_cases:
        print("ANTHROPIC CASES NEEDED:")
        for case in anthropic_cases:
            print(f"  Case {case['case_id']}: {case['case_name']} -> {case['runs_needed']} runs needed")
        print()
    
    print("=" * 80)
    
    # Current status
    status_sql = """
    SELECT 
        COUNT(*) || '|' || 
        SUM(CASE WHEN text_llm_vendor = 'OpenAI' THEN 1 ELSE 0 END) || '|' ||
        SUM(CASE WHEN text_llm_vendor = 'Anthropic' THEN 1 ELSE 0 END) as data
    FROM generated_note 
    WHERE id >= 458 AND failed = 'f';
    """
    
    status_lines = run_sql_query(status_sql)
    if status_lines:
        parts = status_lines[0].split('|')
        if len(parts) == 3:
            total_successful = int(parts[0])
            openai_successful = int(parts[1])
            anthropic_successful = int(parts[2])
            
            print(f"CURRENT DATASET STATUS:")
            print(f"  Total successful runs: {total_successful}/1060 ({total_successful/1060*100:.1f}%)")
            print(f"  OpenAI successful: {openai_successful}/530 ({openai_successful/530*100:.1f}%)")
            print(f"  Anthropic successful: {anthropic_successful}/530 ({anthropic_successful/530*100:.1f}%)")
            print()


if __name__ == "__main__":
    check_remaining_cases()