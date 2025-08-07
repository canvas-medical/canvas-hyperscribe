# PYTHONPATH=. uv run python extract_top_records.py
# modify tables as needed.

import os
import argparse
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.datastores.postgres.postgres import Postgres

TABLES = [
    "case",
    #"generated_note",
    #"score",
    #"rubric",
    "synthetic_case",
    #"real_world_case"
]


def main():
    parser = argparse.ArgumentParser(description="Print top rows from each table.")
    parser.add_argument("--limit", "-n", type=int, default=3, help="How many rows to fetch per table")
    args = parser.parse_args()

    # Load & validate credentials
    creds = PostgresCredentials.from_dictionary(dict(os.environ))
    if not creds.is_ready():
        raise SystemExit("✖ Missing or invalid Postgres credentials")

    # Connect
    pg = Postgres(creds)

    for table in TABLES:
        print(f"\n=== Top {args.limit} from table '{table}' ===")
        sql = f'SELECT * FROM "{table}" ORDER BY updated DESC NULLS LAST LIMIT %(limit)s'
        rows = pg._select(sql, {"limit": args.limit})

        for i, row in enumerate(rows, 1):
            print(f"\n[{i}]")
            for key, val in row.items():
                print(f"  {key}: {val}")


if __name__ == "__main__":
    main()
