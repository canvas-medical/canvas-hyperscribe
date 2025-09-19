/*
 * Check Experiment Data Completeness
 * 
 * Purpose: Validates that experiment data is complete across all cycle durations.
 * Checks both generated notes and score records to ensure balanced experimental design.
 * 
 * Usage: Run this to verify experiment integrity before running analysis.
 * Should show equal counts across all cycle durations for fair comparison.
 * 
 * Expected Results:
 * - Generated Notes: 64 unique cases, 320 notes per cycle duration (90s-240s)
 * - Score Records: 1,510 scores per cycle duration for balanced comparison
 * - Any imbalances indicate missing or failed note generation/scoring
 */

-- Check generated notes completeness by cycle duration
SELECT 
  cycle_duration,
  COUNT(DISTINCT case_id) as unique_cases,
  COUNT(DISTINCT id) as unique_notes,
  COUNT(*) as total_notes
FROM generated_note 
WHERE experiment = true 
  AND cycle_duration IN (15, 30, 60, 90, 120, 180, 240)
GROUP BY cycle_duration
ORDER BY cycle_duration;

-- Check score records completeness  
SELECT 
  gn.cycle_duration,
  COUNT(*) as total_scores,
  COUNT(DISTINCT s.rubric_id) as unique_rubrics,
  COUNT(DISTINCT gn.case_id) as unique_cases
FROM score s 
JOIN generated_note gn ON s.generated_note_id = gn.id
WHERE s.experiment = true 
  AND gn.cycle_duration IN (15, 30, 60, 90, 120, 180, 240)
GROUP BY gn.cycle_duration
ORDER BY gn.cycle_duration;