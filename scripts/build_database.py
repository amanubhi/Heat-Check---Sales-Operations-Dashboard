"""STEP 3a - Load the clean CSVs into a SQLite database (data/heatcheck.db).

Run from the repo root:   python scripts/build_database.py
"""
import sqlite3

import pandas as pd

from paths import CLEAN_DIR, DB_PATH, ensure_dirs

TABLES = ["menu", "spice_levels", "events", "customers", "orders", "order_items"]
INDEXES = [
    "CREATE INDEX idx_orders_channel ON orders(channel)",
    "CREATE INDEX idx_orders_date ON orders(order_date)",
    "CREATE INDEX idx_orders_customer ON orders(customer_id)",
    "CREATE INDEX idx_items_order ON order_items(order_id)",
    "CREATE INDEX idx_items_item ON order_items(item_id)",
]


def main():
    ensure_dirs()
    DB_PATH.unlink(missing_ok=True)  # start fresh so re-runs are identical
    with sqlite3.connect(DB_PATH) as conn:
        for name in TABLES:
            df = pd.read_csv(CLEAN_DIR / f"{name}.csv", dtype={"zip_code": "string"})
            # SQLite has no boolean type: store True/False as 1/0 (blank stays NULL)
            for col in df.columns[df.columns.isin(["loyalty_member", "is_weekend", "is_combo"])]:
                df[col] = df[col].map({True: 1, False: 0, "True": 1, "False": 0}).astype("Int64")
            df.to_sql(name, conn, index=False, if_exists="replace")
            print(f"loaded {name:<13} {len(df):>7,} rows")
        for stmt in INDEXES:
            conn.execute(stmt)
    print(f"\nDatabase written to {DB_PATH}")


if __name__ == "__main__":
    main()
