/*
 * Main Performance Analysis with Proper Normalization
 * 
 * Purpose: Calculates comprehensive performance statistics for cycle duration experiment
 * with proper score normalization. Normalizes raw scores as percentages of maximum 
 * possible rubric score by summing all criterion weights.
 * 
 * Usage: Primary analysis script for comparing cycle duration performance.
 * Run this to get mean, standard deviation, median, quartiles, and range statistics
 * for each cycle duration tested.
 * 
 * Key Features:
 * - Proper rubric normalization (sum of all criterion weights as max score)
 * - Comprehensive statistics (mean, std dev, median, Q1, Q3, min, max)
 * - Filtered to experiment data only
 * - Results as percentages (0-100% scale)
 * 
 * Expected Results: Performance statistics showing ~75% average performance
 * with 30s cycles typically performing best, and 180s+ cycles showing degradation.
 */

-- Calculate performance statistics with proper rubric normalization
WITH rubric_max_scores AS (
  SELECT 
    r.id as rubric_id,
    SUM((criterion->>'weight')::numeric) as max_possible_score
  FROM rubric r,
       LATERAL json_array_elements(r.rubric) as criterion
  WHERE criterion->>'weight' IS NOT NULL
  GROUP BY r.id
)
SELECT 
  gn.cycle_duration,
  COUNT(*) as score_count,
  AVG(s.overall_score * 100.0 / rms.max_possible_score)::numeric(10,2) as mean_pct,
  STDDEV(s.overall_score * 100.0 / rms.max_possible_score)::numeric(10,2) as std_dev_pct,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY s.overall_score * 100.0 / rms.max_possible_score)::numeric(10,2) as median_pct,
  PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY s.overall_score * 100.0 / rms.max_possible_score)::numeric(10,2) as q1_pct,
  PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY s.overall_score * 100.0 / rms.max_possible_score)::numeric(10,2) as q3_pct,
  MIN(s.overall_score * 100.0 / rms.max_possible_score)::numeric(10,2) as min_pct,
  MAX(s.overall_score * 100.0 / rms.max_possible_score)::numeric(10,2) as max_pct
FROM score s
JOIN generated_note gn ON s.generated_note_id = gn.id
JOIN rubric_max_scores rms ON s.rubric_id = rms.rubric_id
WHERE s.experiment = true 
  AND gn.cycle_duration IN (15, 30, 60, 90, 120, 180, 240)
  AND rms.max_possible_score > 0
GROUP BY gn.cycle_duration
ORDER BY gn.cycle_duration;