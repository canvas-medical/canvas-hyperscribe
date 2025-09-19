/*
 * Generate Experiment Notes Mapping
 * 
 * Purpose: Creates the experiment_notes_mapping.csv file by querying all generated notes
 * marked as experiment records. This mapping is essential for the scoring phase as it
 * identifies which notes were generated as part of the cycle duration experiment.
 * 
 * Usage: Export this query to CSV format to create the mapping file used by run_notes_parallel.py
 * 
 * Command:
 * psql "postgresql://aptible:h-5FO4MXav-DIXLlN_88KiFVpFELZzJY@localhost.aptible.in:61777/db" \
 *   -c "$(cat generate_experiment_notes_mapping.sql)" \
 *   --csv > experiment_notes_mapping.csv
 * 
 * Output Format: case_id,note_id,vendor,model
 * - case_id: The case ID the note was generated for
 * - note_id: The generated_note.id in the database  
 * - vendor: The LLM vendor used (e.g., 'openai')
 * - model: The specific model used (e.g., 'gpt-4')
 * 
 * Expected Output: ~1,280 rows (64 cases × 20 notes per case) for complete experiment
 */

SELECT 
    case_id,
    id as note_id,
    vendor,
    model
FROM generated_note
WHERE experiment = true
ORDER BY case_id, cycle_duration, id;