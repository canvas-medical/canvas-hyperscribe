# Experiment Runner Setup Guide

## Quick Start

To run an experiment, you need to:
1. Create an experiment record
2. Add cases to the experiment  
3. Add model combinations
4. Run the experiment

---

## Step 1: Create Experiment Record

```PYTHONPATH=. uv run python
from evaluations.datastores.postgres.experiment import Experiment
from evaluations.structures.records.experiment import Experiment as ExperimentRecord
from evaluations.helper_evaluation import HelperEvaluation

credentials = HelperEvaluation.postgres_credentials()
experiment_store = Experiment(credentials)

# Create experiment
experiment_record = ExperimentRecord(
    name='your_experiment_name',
    hyperscribe_version='commit_hash',  # e.g., '3b0c6ce'
    cycle_times=[],
    cycle_transcript_overlaps=[100],    # Usually 100
    note_replications=5,                # Notes per case
    grade_replications=2                # Grades per rubric per note
)

result = experiment_store.upsert(experiment_record)
experiment_id = result.id
```

---

## Step 2: Add Cases to Experiment

### Find eligible cases (2+ validated human rubrics):
```sql
WITH rubric_authors AS (
    SELECT case_id, COUNT(DISTINCT author) as validated_human_authors
    FROM rubric
    WHERE validation = 'accepted' AND author != 'llm' AND author IS NOT NULL
    GROUP BY case_id
)
SELECT case_id FROM rubric_authors WHERE validated_human_authors >= 2;
```

### Add cases to experiment:
```PYTHONPATH=. uv run python
# Add all eligible cases
eligible_cases = [3, 4, 15, 16, ...]  # From SQL query above
for case_id in eligible_cases:
    experiment_store.add_case(experiment_id, case_id)
```

---

## Step 3: Add Model Combinations

### Check available models:
```sql
SELECT id, vendor, name FROM model ORDER BY vendor, name;
```

### Add model combination:
```python
# Add model combination (generator_id, grader_id, reasoning_flag)
experiment_store.add_model(
    experiment_id=experiment_id,
    model_note_generator_id=2,    # Usually OpenAI (id=2)
    model_note_grader_id=2,       # Usually OpenAI (id=2) 
    model_note_grader_is_reasoning=False
)
```

---

## Step 4: Run Experiment

```bash
PYTHONPATH=. uv run python scripts/experiment_runner.py --experiment_id YOUR_ID
```

Optional parameters:
- `--workers N` (default: 3)
- `--max_attempts N` (default: 3)

---

## Expected Workload

For an experiment with:
- 198 cases × 5 note replications = **990 notes**
- 990 notes × 2 rubrics × 2 grade replications = **3,960 grades**

---

## Model Management

If models don't exist, create them first. Currently, two models exist in our DB: openai and anthropic, which is why the model_combination
can use the specific id=2 within the add_model function call in the experiment_store class.

```bash
# Create OpenAI models
PYTHONPATH=. uv run python scripts/experiments/models_management.py --vendor openai

# Create Anthropic models  
PYTHONPATH=. uv run python scripts/experiments/models_management.py --vendor anthropic
```

---

## Monitoring Progress

```sql
-- Check experiment progress
SELECT 
    COUNT(*) as total_notes,
    COUNT(CASE WHEN failed = false THEN 1 END) as successful_notes,
    COUNT(CASE WHEN failed = true THEN 1 END) as failed_notes
FROM experiment_result 
WHERE experiment_id = YOUR_ID;

-- Check recent activity
SELECT case_id, failed, created FROM experiment_result 
WHERE experiment_id = YOUR_ID 
ORDER BY created DESC LIMIT 10;
```

---

## Common Issues
**No eligible cases**: Make sure cases have 2+ validated human rubrics using the eligibility SQL query above.

**Model not found**: Run models_management.py to create model records first.