"""
test_sql_queries.py
--------------------
Executes every statement in sql/kpi_queries.sql and sql/analysis_queries.sql
(including the CREATE VIEW statements) against transport_operations.db and
verifies each one runs without error and returns a result.

This is the "run every query, confirm no errors, confirm sensible results"
requirement from the project spec.
"""

import sqlite3
import sys
import re

DB_NAME = "transport_operations.db"
FILES = ["sql/kpi_queries.sql", "sql/analysis_queries.sql"]


def split_statements(sql_text):
    """Split a .sql file into individual statements on semicolons,
    skipping full-line comments and blank lines."""
    # Strip full-line comments first (keeps inline logic simple/readable for a fresher)
    lines = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or stripped == "":
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    return statements


def main():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    total = 0
    failed = 0

    for path in FILES:
        with open(path, "r") as f:
            sql_text = f.read()
        statements = split_statements(sql_text)
        print(f"\n=== {path} :: {len(statements)} statements ===")

        for i, stmt in enumerate(statements, start=1):
            total += 1
            label = re.split(r"\s+", stmt.strip(), maxsplit=3)[0:3]
            label = " ".join(label)
            try:
                cur.execute(stmt)
                if stmt.strip().upper().startswith("SELECT") or "SELECT" in stmt.upper().split("VIEW", 1)[-1][:0]:
                    pass
                if stmt.strip().upper().startswith(("CREATE", "DROP")):
                    print(f"  [OK]   {i:2d}. {label} ... executed")
                else:
                    rows = cur.fetchall()
                    col_names = [d[0] for d in cur.description] if cur.description else []
                    preview = rows[:3]
                    print(f"  [OK]   {i:2d}. {label} ... {len(rows)} row(s) e.g. {preview}")
                    if len(rows) == 0:
                        print(f"         NOTE: query returned 0 rows (verify this is expected)")
            except Exception as ex:
                failed += 1
                print(f"  [FAIL] {i:2d}. {label} ... ERROR: {ex}")
                print(f"         Statement: {stmt[:200]}")

    conn.commit()
    conn.close()

    print(f"\n{total - failed}/{total} statements executed successfully.")
    if failed:
        print(f"{failed} statement(s) FAILED.")
        sys.exit(1)
    else:
        print("ALL SQL STATEMENTS (KPI + ANALYSIS + VIEWS) EXECUTED SUCCESSFULLY.")


if __name__ == "__main__":
    main()
