/*
 * Mark Generated Notes as Experiment Records
 * 
 * Purpose: Marks all generated notes starting from ID 3282 as experiment records.
 * This is used to isolate cycle duration experiment data from regular production notes.
 * 
 * Usage: Run this after generating notes for the cycle duration experiment to properly
 * tag them for analysis. The ID 3282 represents the first note generated as part of
 * the experiment batch.
 * 
 * Expected Result: Updates the experiment flag to true for all notes >= ID 3282
 */

UPDATE generated_note 
SET experiment = true 
WHERE id >= 3282 AND experiment IS DISTINCT FROM true;