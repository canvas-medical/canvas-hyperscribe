/*
 * Export Scores for Visualization
 * 
 * Purpose: Exports cycle duration and overall scores in a simple format suitable
 * for visualization tools like matplotlib, seaborn, or other plotting libraries.
 * This is the raw data export for creating boxplots and distribution charts.
 * 
 * Usage: Use this query with psql --csv option to export data for Python
 * visualization scripts. The output can be directly read by pandas or similar
 * data analysis tools.
 * 
 * Example command:
 * psql "connection_string" -c "$(cat export_scores_for_visualization.sql)" --csv > cycle_scores.csv
 * 
 * Key Features:
 * - Simple two-column format: cycle_duration, overall_score
 * - Filtered to experiment data only
 * - Ordered by cycle duration for consistent plotting
 * - Raw scores (not normalized) for flexibility in downstream analysis
 * 
 * Expected Output: ~6,040 rows of score data across 7 cycle durations
 */

-- Export cycle duration scores for visualization tools
SELECT 
  gn.cycle_duration, 
  s.overall_score 
FROM score s 
JOIN generated_note gn ON s.generated_note_id = gn.id 
WHERE s.experiment = true 
ORDER BY gn.cycle_duration;