#!/bin/bash

# Source environment
source local_env.sh

# List of all case names from IDs 187-236
cases=(
    "bipolar-stable-support-network-d60955ad"
    "treatment-resistant-depression-rural-access-telehealth-exploration-c133f742"
    "schizophrenia-stable-supportive-family-ebfb7762"
    "schizoaffective-housing-instability-unemployment-22172214"
    "depression-psychosis-family-support-ee8ca68f"
    "schizophrenia-stable-family-support-62e97b27"
    "bipolar-mood-swings-loneliness-e06d2b03"
    "depression-psychosis-housing-instability-60e846e5"
    "schizoaffective-stable-supportive-community-840cb84b"
    "treatment-resistant-depression-substance-use-legal-issues-1c7a8a03"
    "schizoaffective-stable-support-network-5f9a23e1"
    "bipolar-medication-sideeffects-unemployment-829b8c43"
    "schizophrenia-stable-teletherapy-ac6ca1ae"
    "depression-psychosis-housing-fb871773"
    "treatment-resistant-depression-support-system-a47dd0c8"
    "schizophrenia-stable-supportive-environment-ee24e2b1"
    "bipolar-mood-swings-housing-instability-73aef21e"
    "major-depression-stable-support-network-8e097966"
    "schizoaffective-medication-adherence-job-loss-ca5b8ffb"
    "treatment-resistant-depression-rural-telehealth-5fca59a0"
    "schizoaffective-stable-supportive-network-b83f2f8c"
    "bipolar-medication-side-effects-533b1339"
    "schizophrenia-stable-supportive-housing-eef9358b"
    "depression-psychosis-housing-ff0bd510"
    "treatment-resistant-depression-rural-barriers-telehealth-support-a4c101e6"
    "birth-control-access-rural-424c98ad"
    "high-cholesterol-aging-concerns-3203522d"
    "type2-diabetes-irregular-schedule-a7cbea47"
    "active-sports-healthy-d7526ac9"
    "breast-cancer-family-history-51c60aa0"
    "teen-athlete-fatigue-2cfd577c"
    "hypertension-rural-telehealth-a3926e04"
    "uninsured-persistent-cough-b5b45167"
    "family-history-colon-cancer-34e29437"
    "relocation-anxiety-new-job-291423d3"
    "family-history-cholesterol-rural-access-c6b7579d"
    "college-stress-sleep-649193c1"
    "hypertension-medication-cost-concern-0be0c129"
    "osteoporosis-joint-pain-home-safety-405e40c9"
    "routine-vaccination-healthy-70b8bd05"
    "rural-relocation-health-maintenance-8fb98271"
    "cholesterol-screening-family-heart-disease-limited-access-ad429ee8"
    "adolescent-athlete-vaccinations-854d4b84"
    "copd-shortness-breathing-d99d5203"
    "persistent-headache-uninsured-stress-0e812b2d"
    "lifestyle-diet-exercise-15971c1c"
    "high-cholesterol-primary-care-bb6268ec"
    "college-stress-management-43573d5a"
    "breast-cancer-history-hypertension-1421c689"
    "copd-medication-adherence-community-resources-c08d311a"
)

total_cases=${#cases[@]}
echo "Generating 3 notes for each of $total_cases cases..."

# Arrays to track cases
zero_command_cases=()
good_cases=()

for i in "${!cases[@]}"; do
    case_name="${cases[$i]}"
    case_num=$((i + 1))
    
    echo "[$case_num/$total_cases] Processing case: $case_name"
    
    total_commands=0
    notes_generated=0
    
    for note_num in {1..3}; do
        echo "  Note $note_num/3:"
        
        # Capture output to parse for commands
        output=$(PYTHONPATH=. uv run python case_runner.py --case "$case_name" --cycles 1 2>&1)
        exit_code=$?
        
        if [ $exit_code -eq 0 ]; then
            echo "    ✓ Note $note_num generated successfully"
            notes_generated=$((notes_generated + 1))
            
            # Extract total commands from output (sum of all "computed commands: X" lines)
            commands_this_note=$(echo "$output" | grep "computed commands:" | awk '{sum += $4} END {print sum+0}')
            total_commands=$((total_commands + commands_this_note))
            
            echo "    Commands in this note: $commands_this_note"
        else
            echo "    ✗ Note $note_num failed"
        fi
    done
    
    echo "  Total commands across all notes: $total_commands"
    
    # Classify the case
    if [ $total_commands -eq 0 ] && [ $notes_generated -gt 0 ]; then
        zero_command_cases+=("$case_name")
        echo "  ⚠️  ZERO COMMANDS - Case flagged for exclusion"
    elif [ $notes_generated -gt 0 ]; then
        good_cases+=("$case_name")
        echo "  ✓ GOOD - Case has commands"
    else
        echo "  ✗ FAILED - No notes generated"
    fi
    
    echo "  Completed case $case_num/$total_cases"
    echo ""
done

echo "=========================================="
echo "SUMMARY REPORT"
echo "=========================================="
echo "Total cases processed: $total_cases"
echo "Cases with commands: ${#good_cases[@]}"
echo "Cases with zero commands: ${#zero_command_cases[@]}"
echo ""

# Save zero-command cases to file
if [ ${#zero_command_cases[@]} -gt 0 ]; then
    echo "Cases with ZERO commands (exclude from clinician review):"
    zero_command_file="zero_command_cases.txt"
    > "$zero_command_file"  # Clear file
    
    for case in "${zero_command_cases[@]}"; do
        echo "  - $case"
        echo "$case" >> "$zero_command_file"
    done
    
    echo ""
    echo "Zero-command cases saved to: $zero_command_file"
fi

# Save good cases to file
if [ ${#good_cases[@]} -gt 0 ]; then
    echo ""
    echo "Cases WITH commands (ready for clinician review):"
    good_cases_file="good_cases.txt"
    > "$good_cases_file"  # Clear file
    
    for case in "${good_cases[@]}"; do
        echo "  - $case"
        echo "$case" >> "$good_cases_file"
    done
    
    echo ""
    echo "Good cases saved to: $good_cases_file"
fi

echo ""
echo "All done! Generated 3 notes for $total_cases cases."