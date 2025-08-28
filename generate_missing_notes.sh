#!/bin/bash

# Source environment
source local_env.sh

echo "=========================================="
echo "GENERATING MISSING NOTES"
echo "=========================================="

# Part 1: Generate notes for ALL cases without any notes
echo "Part 1: Fetching ALL cases without notes..."
temp_file1=$(mktemp)
psql $DATABASE_URL -t -c "
SELECT c.name 
FROM public.case c
LEFT JOIN public.generated_note gn ON c.id = gn.case_id
WHERE gn.case_id IS NULL
ORDER BY c.id;
" > "$temp_file1"

cases_without_notes=$(wc -l < "$temp_file1")
echo "Found $cases_without_notes cases without any notes"

# Part 2: Generate additional notes for cases 187-236 that already have notes
echo "Part 2: Fetching cases 187-236 that already have notes..."
temp_file2=$(mktemp)
psql $DATABASE_URL -t -c "
SELECT DISTINCT c.name 
FROM public.case c
JOIN public.generated_note gn ON c.id = gn.case_id
WHERE c.id BETWEEN 187 AND 236
ORDER BY c.name;
" > "$temp_file2"

cases_with_notes=$(wc -l < "$temp_file2")
echo "Found $cases_with_notes cases (187-236) that already have notes"

# Combine both files
temp_file_combined=$(mktemp)
cat "$temp_file1" "$temp_file2" > "$temp_file_combined"

total_cases=$(wc -l < "$temp_file_combined")
echo ""
echo "Total cases to generate notes for: $total_cases"
echo "  - Cases without any notes: $cases_without_notes"
echo "  - Cases (187-236) getting additional notes: $cases_with_notes"
echo ""

success_count=0
error_count=0
case_num=0

# Generate one note per case
while IFS= read -r case_name; do
    # Skip empty lines and trim whitespace
    case_name=$(echo "$case_name" | xargs)
    if [ -z "$case_name" ]; then
        continue
    fi
    
    case_num=$((case_num + 1))
    echo "[$case_num/$total_cases] Generating note for: $case_name"
    
    # Generate single note with 1 cycle
    if PYTHONPATH=. uv run python case_runner.py --case "$case_name" --cycles 1; then
        echo "    ✓ Note generated successfully"
        success_count=$((success_count + 1))
    else
        echo "    ✗ Note generation failed"
        error_count=$((error_count + 1))
    fi
    
    echo ""
done < "$temp_file_combined"

# Clean up temp files
rm "$temp_file1" "$temp_file2" "$temp_file_combined"

echo "=========================================="
echo "NOTE GENERATION COMPLETE"
echo "=========================================="
echo "Total cases processed: $total_cases"
echo "Successfully generated: $success_count notes"
echo "Failed: $error_count notes"
echo ""