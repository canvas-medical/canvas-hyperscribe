  # Source environment
  source local_env.sh

  # Get all case names from cases missing LLM rubrics and write to temp file
  echo "Fetching case names from database..."
  temp_file=$(mktemp)
  psql $DATABASE_URL -t -c "
  SELECT name 
  FROM public.case c
  WHERE NOT EXISTS (
      SELECT 1 FROM public.rubric r 
      WHERE r.case_id = c.id AND r.author = 'llm'
  )
  ORDER BY c.id;" > "$temp_file"

  # Check if we got any cases
  if [ ! -s "$temp_file" ]; then
      echo "No cases found missing LLM rubrics"
      rm "$temp_file"
      exit 1
  fi

  # Count cases
  total_cases=$(wc -l < "$temp_file")
  echo "Found $total_cases cases to generate LLM rubrics for..."

  # Path to canvas context file
  canvas_context_path="evaluations/case_builders/context_canvas_commands.json"

  # Check if context file exists
  if [[ ! -f "$canvas_context_path" ]]; then
      echo "Error: Canvas context file not found at $canvas_context_path"
      exit 1
  fi

  echo "Starting LLM rubric generation..."
  echo "Context file: $canvas_context_path"
  echo ""

  success_count=0
  error_count=0
  case_num=0

  # Read case names from temp file
  while IFS= read -r case_name; do
      # Skip empty lines and trim whitespace
      case_name=$(echo "$case_name" | xargs)
      if [ -z "$case_name" ]; then
          continue
      fi

      case_num=$((case_num + 1))
      echo "[$case_num/$total_cases] Generating LLM rubric for: $case_name"

      # Run rubric generator
      if PYTHONPATH=. uv run python evaluations/case_builders/rubric_generator.py \
          --case_name "$case_name" \
          --canvas_context_path "$canvas_context_path"; then

          echo "    ✓ LLM rubric generated successfully"
          success_count=$((success_count + 1))
      else
          echo "    ✗ LLM rubric generation failed"
          error_count=$((error_count + 1))
      fi

      echo ""
  done < "$temp_file"

  # Clean up temp file
  rm "$temp_file"

  echo "LLM rubric generation completed!"
  echo "Successfully generated: $success_count rubrics"
  echo "Failed: $error_count rubrics"
  echo "Total processed: $total_cases cases"

  # Show some stats from database
  echo ""
  echo "Database stats:"
  psql $DATABASE_URL -c "
  SELECT 
      COUNT(CASE WHEN author = 'llm' THEN 1 END) as llm_rubrics,
      COUNT(*) as total_rubrics 
  FROM public.rubric;"