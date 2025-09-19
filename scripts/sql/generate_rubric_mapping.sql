/*
 * Generate Rubric Mapping
 * 
 * Purpose: Creates the rubric_mapping.csv file by querying the rubric table for all
 * rubrics associated with the validated experiment cases. This mapping identifies
 * which rubrics should be used to evaluate each case during scoring.
 * 
 * Usage: Export this query to CSV format to create the mapping file used by run_notes_parallel.py
 * 
 * Command:
 * psql "postgresql://aptible:h-5FO4MXav-DIXLlN_88KiFVpFELZzJY@localhost.aptible.in:61777/db" \
 *   -c "$(cat generate_rubric_mapping.sql)" \
 *   --csv > rubric_mapping.csv
 * 
 * Output Format: case_id,author,rubric_id
 * - case_id: The case ID to be evaluated
 * - author: The email/identifier of the rubric author
 * - rubric_id: The rubric.id in the database
 * 
 * Expected Output: ~151 rows (rubric mappings across the 64 validated cases)
 * Note: Each case may have multiple rubrics from different authors
 */

SELECT 
    case_id,
    author,
    id as rubric_id
FROM rubric
WHERE case_id IN (
    -- The 59 validated cases from validated_cases_over_300.csv
    102, 103, 104, 105, 106, 107, 108, 109, 110, 112, 113, 114, 115, 116, 117, 118,
    120, 121, 122, 124, 131, 134, 141, 142, 144, 145, 26, 29, 30, 31, 32, 37, 38,
    39, 40, 41, 43, 58, 59, 62, 63, 64, 65, 67, 68, 69, 70, 71, 72, 76, 79, 80,
    81, 83, 85, 86, 88, 90, 92, 94, 95, 96, 98, 99
)
ORDER BY case_id, author, rubric_id;