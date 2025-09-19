/*
 * Find Missing Cases by Cycle Duration
 * 
 * Purpose: Identifies cases that don't have complete data across all 7 cycle durations.
 * This is critical for ensuring balanced experimental design where each case has
 * notes generated for all tested cycle durations (15s, 30s, 60s, 90s, 120s, 180s, 240s).
 * 
 * Usage: Run this when some cycle durations have fewer cases than expected.
 * Helps identify which specific cases need additional note generation.
 * 
 * Expected Result: Should show 64 cases present for all cycle durations.
 * Any missing cases indicate incomplete experiment runs that need to be fixed.
 */

-- Find cases that don't have all 7 cycle durations
WITH complete_cases AS (
  SELECT DISTINCT gn.case_id
  FROM score s 
  JOIN generated_note gn ON s.generated_note_id = gn.id
  WHERE s.experiment = true 
    AND gn.cycle_duration IN (15, 30, 60, 90, 120, 180, 240)
  GROUP BY gn.case_id
  HAVING COUNT(DISTINCT gn.cycle_duration) = 7
)
SELECT 
  cycle_duration,
  COUNT(DISTINCT gn.case_id) as cases_present,
  64 - COUNT(DISTINCT gn.case_id) as cases_missing
FROM score s 
JOIN generated_note gn ON s.generated_note_id = gn.id
LEFT JOIN complete_cases cc ON gn.case_id = cc.case_id
WHERE s.experiment = true 
  AND gn.cycle_duration IN (15, 30, 60, 90, 120, 180, 240)
GROUP BY cycle_duration
ORDER BY cycle_duration;