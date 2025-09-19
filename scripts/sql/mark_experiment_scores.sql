/*
 * Mark Score Records as Experiment Records
 * 
 * Purpose: Marks all score records starting from ID 18558 as experiment records.
 * This isolates scores generated for the cycle duration experiment from regular
 * production scoring data.
 * 
 * Usage: Run this after scoring all experiment notes to properly tag the scores
 * for analysis. The ID 18558 represents the first score generated for experiment notes.
 * 
 * Expected Result: Updates the experiment flag to true for all scores >= ID 18558
 * Should affect approximately 6,040 score records (64 cases × 151 rubrics × 2 runs)
 */

UPDATE score 
SET experiment = true 
WHERE id >= 18558 AND experiment IS DISTINCT FROM true;