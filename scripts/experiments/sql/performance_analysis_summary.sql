-- OVERALL NORMALIZED SCORE STATISTICS
-- =============================================================================
WITH rubric_max_scores AS (
    SELECT 
        r.id as rubric_id,
        (
            SELECT SUM((criteria->>'weight')::integer)
            FROM jsonb_array_elements(r.rubric::jsonb) AS criteria
        ) as max_possible_score
    FROM rubric r
    WHERE r.id IN (
        SELECT DISTINCT s.rubric_id 
        FROM score s 
        WHERE s.id IN (
            SELECT ers.score_id 
            FROM experiment_result_score ers 
            JOIN experiment_result er ON ers.experiment_result_id = er.id 
            WHERE er.experiment_id = 1
        )
    )
),
normalized_scores AS (
    SELECT 
        s.id,
        s.rubric_id,
        s.overall_score,
        rms.max_possible_score,
        ROUND((s.overall_score * 100.0 / rms.max_possible_score)::numeric, 2) as normalized_score_pct
    FROM score s 
    JOIN rubric_max_scores rms ON s.rubric_id = rms.rubric_id
    WHERE s.id IN (
        SELECT ers.score_id 
        FROM experiment_result_score ers 
        JOIN experiment_result er ON ers.experiment_result_id = er.id 
        WHERE er.experiment_id = 1
    )
)
SELECT 
    COUNT(*) as total_scores,
    ROUND(AVG(normalized_score_pct)::numeric, 2) as avg_normalized_pct,
    ROUND(MIN(normalized_score_pct)::numeric, 2) as min_normalized_pct,
    ROUND(MAX(normalized_score_pct)::numeric, 2) as max_normalized_pct,
    ROUND(STDDEV(normalized_score_pct)::numeric, 2) as stddev_normalized_pct,
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY normalized_score_pct)::numeric, 2) as q1_normalized_pct,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY normalized_score_pct)::numeric, 2) as median_normalized_pct,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY normalized_score_pct)::numeric, 2) as q3_normalized_pct
FROM normalized_scores;

-- NORMALIZED SCORE DISTRIBUTION HISTOGRAM
-- =============================================================================
WITH rubric_max_scores AS (
    SELECT 
        r.id as rubric_id,
        (
            SELECT SUM((criteria->>'weight')::integer)
            FROM jsonb_array_elements(r.rubric::jsonb) AS criteria
        ) as max_possible_score
    FROM rubric r
    WHERE r.id IN (
        SELECT DISTINCT s.rubric_id 
        FROM score s 
        WHERE s.id IN (
            SELECT ers.score_id 
            FROM experiment_result_score ers 
            JOIN experiment_result er ON ers.experiment_result_id = er.id 
            WHERE er.experiment_id = 1
        )
    )
),
normalized_scores AS (
    SELECT 
        ROUND((s.overall_score * 100.0 / rms.max_possible_score)::numeric, 2) as normalized_score_pct
    FROM score s 
    JOIN rubric_max_scores rms ON s.rubric_id = rms.rubric_id
    WHERE s.id IN (
        SELECT ers.score_id 
        FROM experiment_result_score ers 
        JOIN experiment_result er ON ers.experiment_result_id = er.id 
        WHERE er.experiment_id = 1
    )
),
score_buckets AS (
    SELECT 
        CASE 
            WHEN normalized_score_pct < 10 THEN '0-10%'
            WHEN normalized_score_pct < 20 THEN '10-20%'  
            WHEN normalized_score_pct < 30 THEN '20-30%'
            WHEN normalized_score_pct < 40 THEN '30-40%'
            WHEN normalized_score_pct < 50 THEN '40-50%'
            WHEN normalized_score_pct < 60 THEN '50-60%'
            WHEN normalized_score_pct < 70 THEN '60-70%'
            WHEN normalized_score_pct < 80 THEN '70-80%'
            WHEN normalized_score_pct < 90 THEN '80-90%'
            ELSE '90-100%'
        END as score_range
    FROM normalized_scores
)
SELECT 
    score_range,
    COUNT(*) as frequency,
    ROUND((COUNT(*) * 100.0 / (SELECT COUNT(*) FROM score_buckets))::numeric, 1) as percentage
FROM score_buckets
GROUP BY score_range
ORDER BY 
    CASE score_range
        WHEN '0-10%' THEN 1
        WHEN '10-20%' THEN 2
        WHEN '20-30%' THEN 3
        WHEN '30-40%' THEN 4
        WHEN '40-50%' THEN 5
        WHEN '50-60%' THEN 6
        WHEN '60-70%' THEN 7
        WHEN '70-80%' THEN 8
        WHEN '80-90%' THEN 9
        WHEN '90-100%' THEN 10
    END;

-- EXPERIMENT COMPLETION AND SUCCESS RATES
-- =============================================================================
SELECT 
    COUNT(*) as total_jobs,
    COUNT(CASE WHEN er.failed = false THEN 1 END) as successful_jobs,
    COUNT(CASE WHEN er.failed = true THEN 1 END) as failed_jobs,
    ROUND((COUNT(CASE WHEN er.failed = false THEN 1 END) * 100.0 / COUNT(*))::numeric, 1) as success_rate_pct,
    COUNT(CASE WHEN er.generated_note_id > 0 THEN 1 END) as notes_generated,
    COUNT(DISTINCT er.case_id) as unique_cases_tested,
    (SELECT COUNT(*) FROM experiment_result_score ers2 
     JOIN experiment_result er2 ON ers2.experiment_result_id = er2.id 
     WHERE er2.experiment_id = 1) as total_grades_completed
FROM experiment_result er
WHERE er.experiment_id = 1;
