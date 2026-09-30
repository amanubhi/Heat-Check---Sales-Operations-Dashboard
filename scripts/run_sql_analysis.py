"""STEP 3b - Run every query in sql/analysis.sql and save each result as a CSV.

Run from the repo root:   python scripts/run_sql_analysis.py

Queries in analysis.sql are separated by marker lines like:
    -- @query Q01 revenue_profit_margin_by_channel_month
Each result is saved to outputs/sql_results/Q01_revenue_profit_margin_by_channel_month.csv
"""
import re
import sqlite3

import pandas as pd

from paths import DB_PATH, SQL_FILE, SQL_RESULTS_DIR, ensure_dirs

MARKER = re.compile(r"^-- @query (Q\d+) (\w+)\s*$", re.MULTILINE)


def split_queries(sql_text):
    """Return [(query_id, name, sql_text)] by cutting the file at each marker."""
    marks = list(MARKER.finditer(sql_text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(sql_text)
        out.append((m.group(1), m.group(2), sql_text[m.end():end].strip()))
    return out


def main():
    ensure_dirs()
    for old in SQL_RESULTS_DIR.glob("*.csv"):
        old.unlink()
    queries = split_queries(SQL_FILE.read_text())
    with sqlite3.connect(DB_PATH) as conn:
        for qid, name, sql in queries:
            df = pd.read_sql_query(sql, conn)
            df.to_csv(SQL_RESULTS_DIR / f"{qid}_{name}.csv", index=False)
            print(f"{qid} {name:<42} {len(df):>4} rows")
    print(f"\n{len(queries)} result files saved to {SQL_RESULTS_DIR}")


if __name__ == "__main__":
    main()
