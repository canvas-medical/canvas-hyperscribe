from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.datastores.postgres.postgres import Postgres
import os

creds = PostgresCredentials.from_dictionary(dict(os.environ))
print("Is Ready?  ->", creds.is_ready())
if not creds.is_ready():
    raise SystemExit("✖  Environment variables incomplete – cannot connect.")

pg = Postgres(creds)

TABLES = [
    "case",
    "synthetic_case",
    "real_world_case",
    "generated_note",
    "rubric",
    "score",
]

def preview_table(table: str, limit: int = 5) -> None:
    print(f"\n{'='*60}\n{table.upper()} — Top {limit} Rows\n{'='*60}")
    sql = f'SELECT * FROM "{table}" ORDER BY id DESC LIMIT {limit}'
    rows = list(pg._select(sql, {}))
    if not rows:
        print("  (no records)")
        return
    for i, row in enumerate(rows, 1):
        print(f"[{i}] { {k: v for k, v in row.items()} }")

print("\nPreviewing tables...")
for table in TABLES:
    preview_table(table)
