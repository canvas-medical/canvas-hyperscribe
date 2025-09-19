/*
 * StagedCommands Length Analysis
 * 
 * Purpose: Analyzes the length distribution of pre-existing chart content (stagedCommands)
 * for validated experiment cases. This reveals how much clinical context exists before
 * transcript processing begins, which may affect note generation performance.
 * 
 * Usage: Run this to understand the distribution of pre-existing content length
 * across experiment cases. Helps identify if cases start with minimal content
 * or substantial clinical history.
 * 
 * Key Features:
 * - Categorizes cases by stagedCommands length (empty, short, medium, long, very_long)
 * - Analyzes only validated experiment cases (>300 words)
 * - Provides statistics on content length distribution
 * - Shows percentage breakdown across categories
 * 
 * Expected Results: ~93% of cases have substantial pre-existing content (>2000 chars)
 * averaging ~6000 characters, indicating most notes start with rich clinical context.
 */

-- Analyze length distribution of staged commands for target cases
WITH target_cases AS (
  SELECT case_id FROM (VALUES 
    (102), (103), (104), (105), (106), (107), (108), (109), (110), (112), (113), (114), (115), (116), (117), (118),
    (120), (121), (122), (124), (131), (134), (141), (142), (144), (145), (26), (29), (30), (31), (32), (37), (38),
    (39), (40), (41), (43), (58), (59), (62), (63), (64), (65), (67), (68), (69), (70), (71), (72), (76), (79), (80),
    (81), (83), (85), (86), (88), (90), (92), (94), (95), (96), (98), (99)
  ) AS t(case_id)
),
staged_analysis AS (
  SELECT 
    c.id as case_id,
    LENGTH(COALESCE(c.limited_chart->>'stagedCommands', '')) as staged_commands_length,
    CASE 
      WHEN c.limited_chart->>'stagedCommands' IS NULL OR c.limited_chart->>'stagedCommands' = '' OR c.limited_chart->>'stagedCommands' = '{}' THEN 'empty'
      WHEN LENGTH(c.limited_chart->>'stagedCommands') < 100 THEN 'short'
      WHEN LENGTH(c.limited_chart->>'stagedCommands') < 500 THEN 'medium'  
      WHEN LENGTH(c.limited_chart->>'stagedCommands') < 2000 THEN 'long'
      ELSE 'very_long'
    END as length_category
  FROM "case" c
  JOIN target_cases tc ON c.id = tc.case_id
)
SELECT 
  length_category,
  COUNT(*) as case_count,
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM target_cases), 1) as percentage,
  ROUND(AVG(NULLIF(staged_commands_length, 0)), 0) as avg_length,
  MIN(NULLIF(staged_commands_length, 0)) as min_length,
  MAX(staged_commands_length) as max_length
FROM staged_analysis
GROUP BY length_category
ORDER BY 
  CASE length_category
    WHEN 'empty' THEN 1
    WHEN 'short' THEN 2
    WHEN 'medium' THEN 3
    WHEN 'long' THEN 4
    WHEN 'very_long' THEN 5
  END;