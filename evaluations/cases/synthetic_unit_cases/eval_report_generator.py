import argparse
import json
import csv
from pathlib import Path
from typing import Any, cast

def load_json(path: str | Path) -> list[dict[str, Any]]:
    with open(path, 'r') as f:
        return cast(list[dict[str, Any]], json.load(f))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate evaluation CSV from rubric and scores.")
    parser.add_argument("--rubric", type=Path, required=True, help="Path to rubric.json")
    parser.add_argument("--scores", type=Path, required=True, help="Path to scores.json")
    parser.add_argument("--out", type=Path, required=True, help="Path to output CSV file")
    args = parser.parse_args()

    rubric = load_json(args.rubric)
    scores = load_json(args.scores)

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
        
    with open(args.out, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote CSV report to {args.out}")

