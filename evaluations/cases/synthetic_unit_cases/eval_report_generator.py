import sys
import json
import csv
from pathlib import Path

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def main(rubric_path, score_path, output_path):
    rubric = load_json(rubric_path)
    scores = load_json(score_path)

    if len(rubric) != len(scores):
        raise ValueError("Rubric and score arrays must have the same length.")

    rows = []
    for idx, (r, s) in enumerate(zip(rubric, scores), 1):
        rows.append({
            "Criterion #": idx,
            "Criterion": r["criterion"],
            "Max Score": r["weight"],
            "Satisfaction (%)": round(s["satisfaction"], 1),
            "Score Awarded": round(s["score"], 2),
            "Rationale": s["rationale"]
        })

    # Write to CSV
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote CSV report to {output_path}")

if __name__ == "__main__":
    rubric_path = sys.argv[1]
    score_path = sys.argv[2]
    output_path = sys.argv[3]
    main(rubric_path, score_path, output_path)
