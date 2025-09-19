/*
 * StagedCommands Content Analysis - All Unique Keys
 * 
 * Purpose: Identifies all unique JSON keys/sections present in stagedCommands
 * across the entire database. This reveals what types of clinical content
 * are typically pre-populated before transcript processing begins.
 * 
 * Usage: Run this to understand the structure and frequency of different
 * clinical sections in pre-existing chart content. Helpful for understanding
 * what information is available as context during note generation.
 * 
 * Key Features:
 * - Analyzes all cases in database with stagedCommands content
 * - Shows frequency and percentage of each JSON key/section type
 * - Ordered by frequency (most common sections first)
 * - Covers all 18 unique section types found in the system
 * 
 * Expected Results: 
 * - 5 universal sections: reasonForVisit, hpi, questionnaire, followUp, labOrder (90%+)
 * - Common clinical sections: exam, familyHistory, medicalHistory (70-80%)
 * - Variable action sections: instruct, prescribe, diagnose (20-50%)
 * - Rare sections: task, surgicalHistory (15-20%)
 */

-- Get all unique keys in stagedCommands across entire database
SELECT 
  key,
  COUNT(*) as frequency,
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM "case" WHERE limited_chart->>'stagedCommands' IS NOT NULL AND limited_chart->>'stagedCommands' != '' AND limited_chart->>'stagedCommands' != '{}'), 1) as percentage
FROM "case" c,
     LATERAL json_object_keys(c.limited_chart->'stagedCommands') as key
WHERE c.limited_chart->>'stagedCommands' IS NOT NULL 
  AND c.limited_chart->>'stagedCommands' != ''
  AND c.limited_chart->>'stagedCommands' != '{}'
GROUP BY key
ORDER BY frequency DESC, key;