-- ALL CASES RANKED BY NORMALIZED PERFORMANCE (COMPLETE LIST)
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
        ers.experiment_result_id,
        s.rubric_id,
        s.overall_score,
        rms.max_possible_score,
        ROUND((s.overall_score * 100.0 / rms.max_possible_score)::numeric, 2) as normalized_score_pct
    FROM experiment_result_score ers
    JOIN score s ON ers.score_id = s.id
    JOIN rubric_max_scores rms ON s.rubric_id = rms.rubric_id
    JOIN experiment_result er ON ers.experiment_result_id = er.id
    WHERE er.experiment_id = 1 AND er.failed = false
)
SELECT 
    er.case_id,
    er.case_name,
    COUNT(ns.normalized_score_pct) as total_scores,
    ROUND(AVG(ns.normalized_score_pct)::numeric, 2) as avg_normalized_pct,
    ROUND(MIN(ns.normalized_score_pct)::numeric, 2) as min_normalized_pct,
    ROUND(MAX(ns.normalized_score_pct)::numeric, 2) as max_normalized_pct,
    ROUND(STDDEV(ns.normalized_score_pct)::numeric, 2) as stddev_normalized_pct
FROM experiment_result er
JOIN normalized_scores ns ON er.id = ns.experiment_result_id
WHERE er.experiment_id = 1 AND er.failed = false
GROUP BY er.case_id, er.case_name
ORDER BY avg_normalized_pct DESC;

-- CASE SUCCESS/FAILURE RATES WITH PERFORMANCE
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
        ers.experiment_result_id,
        ROUND((s.overall_score * 100.0 / rms.max_possible_score)::numeric, 2) as normalized_score_pct
    FROM experiment_result_score ers
    JOIN score s ON ers.score_id = s.id
    JOIN rubric_max_scores rms ON s.rubric_id = rms.rubric_id
    JOIN experiment_result er ON ers.experiment_result_id = er.id
    WHERE er.experiment_id = 1 AND er.failed = false
)
SELECT 
    er.case_id,
    er.case_name,
    COUNT(er.id) as total_attempts,
    COUNT(CASE WHEN er.failed = false THEN 1 END) as successful_attempts,
    COUNT(CASE WHEN er.failed = true THEN 1 END) as failed_attempts,
    ROUND((COUNT(CASE WHEN er.failed = false THEN 1 END) * 100.0 / COUNT(er.id))::numeric, 1) as success_rate_pct,
    COALESCE(ROUND(AVG(ns.normalized_score_pct)::numeric, 2), 0) as avg_normalized_pct_when_successful
FROM experiment_result er
LEFT JOIN normalized_scores ns ON er.id = ns.experiment_result_id
WHERE er.experiment_id = 1
GROUP BY er.case_id, er.case_name
ORDER BY success_rate_pct DESC, avg_normalized_pct_when_successful DESC;

-- =============================================================================
-- 3. CASES WITH PERFECT SCORES (100% NORMALIZED)
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
        ers.experiment_result_id,
        ROUND((s.overall_score * 100.0 / rms.max_possible_score)::numeric, 2) as normalized_score_pct
    FROM experiment_result_score ers
    JOIN score s ON ers.score_id = s.id
    JOIN rubric_max_scores rms ON s.rubric_id = rms.rubric_id
    WHERE ers.experiment_result_id IN (
        SELECT er.id FROM experiment_result er 
        WHERE er.experiment_id = 1 AND er.failed = false
    )
),
case_perfect_scores AS (
    SELECT 
        er.case_id,
        er.case_name,
        COUNT(ns.normalized_score_pct) as total_scores,
        COUNT(CASE WHEN ns.normalized_score_pct = 100.00 THEN 1 END) as perfect_scores
    FROM experiment_result er
    JOIN normalized_scores ns ON er.id = ns.experiment_result_id
    WHERE er.experiment_id = 1 AND er.failed = false
    GROUP BY er.case_id, er.case_name
)
SELECT 
    case_id,
    case_name,
    total_scores,
    perfect_scores,
    ROUND((perfect_scores * 100.0 / total_scores)::numeric, 1) as perfect_score_rate_pct
FROM case_perfect_scores
WHERE perfect_scores > 0
ORDER BY perfect_score_rate_pct DESC, perfect_scores DESC;


-- CASES WITH HIGH VARIABILITY (INCONSISTENT PERFORMANCE)
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
        ers.experiment_result_id,
        ROUND((s.overall_score * 100.0 / rms.max_possible_score)::numeric, 2) as normalized_score_pct
    FROM experiment_result_score ers
    JOIN score s ON ers.score_id = s.id
    JOIN rubric_max_scores rms ON s.rubric_id = rms.rubric_id
    JOIN experiment_result er ON ers.experiment_result_id = er.id
    WHERE er.experiment_id = 1 AND er.failed = false
)
SELECT 
    er.case_id,
    er.case_name,
    COUNT(ns.normalized_score_pct) as total_scores,
    ROUND(AVG(ns.normalized_score_pct)::numeric, 2) as avg_normalized_pct,
    ROUND(STDDEV(ns.normalized_score_pct)::numeric, 2) as stddev_normalized_pct,
    ROUND(MAX(ns.normalized_score_pct) - MIN(ns.normalized_score_pct)::numeric, 2) as score_range_pct
FROM experiment_result er
JOIN normalized_scores ns ON er.id = ns.experiment_result_id
WHERE er.experiment_id = 1 AND er.failed = false
GROUP BY er.case_id, er.case_name
HAVING STDDEV(ns.normalized_score_pct) > 15  -- high variability threshold
ORDER BY stddev_normalized_pct DESC;



-- BOTTOM 20 WORST PERFORMING CASES
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
        ers.experiment_result_id,
        ROUND((s.overall_score * 100.0 / rms.max_possible_score)::numeric, 2) as normalized_score_pct
    FROM experiment_result_score ers
    JOIN score s ON ers.score_id = s.id
    JOIN rubric_max_scores rms ON s.rubric_id = rms.rubric_id
    JOIN experiment_result er ON ers.experiment_result_id = er.id
    WHERE er.experiment_id = 1 AND er.failed = false
)
SELECT 
    er.case_id,
    er.case_name,
    COUNT(ns.normalized_score_pct) as total_scores,
    ROUND(AVG(ns.normalized_score_pct)::numeric, 2) as avg_normalized_pct,
    ROUND(MIN(ns.normalized_score_pct)::numeric, 2) as min_normalized_pct,
    ROUND(MAX(ns.normalized_score_pct)::numeric, 2) as max_normalized_pct
FROM experiment_result er
JOIN normalized_scores ns ON er.id = ns.experiment_result_id
WHERE er.experiment_id = 1 AND er.failed = false
GROUP BY er.case_id, er.case_name
ORDER BY avg_normalized_pct ASC
LIMIT 20;