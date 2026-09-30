"""Turn a real POS (point-of-sale) sales export into the raw tables the pipeline expects.

Run from the repo root:
    python scripts/import_real_data.py --sales path/to/pos_export.csv [--events path/to/events.csv] [--costs path/to/item_costs.csv]

Everything is written to private/data/raw/ (git-ignored) so real business data can never be
committed or published. Afterwards run the whole pipeline on it with:
    python run_all.py --real

Sales file: ONE ROW PER ITEM SOLD. Required columns:
    order_id, order_datetime, channel, item_name, quantity, unit_price
Optional columns (more columns = better analysis):
    event_name, payment_method, order_type, customer_id, discount_amount (per order), tip_amount (per order),
    prep_time_minutes, spice_level, category, unit_food_cost, zip_code, loyalty_member
See data/templates/ and REAL_DATA_GUIDE.md. PRIVACY: use an anonymous customer_id (for example a hash);
never include names, phone numbers or emails.
"""
import argparse
import os
import sys

os.environ["HEATCHECK_DATASET"] = "real"   # must be set before paths is imported: write to private/ only

import numpy as np
import pandas as pd

from paths import RAW_DIR, ensure_dirs

CHANNELS = {"storefront": "Storefront", "store": "Storefront", "restaurant": "Storefront", "brick and mortar": "Storefront",
            "night market": "Night Market", "market": "Night Market", "vendor event": "Vendor Event", "event": "Vendor Event",
            "festival": "Vendor Event", "popup": "Vendor Event"}
PAYMENTS = {"card": "Card", "credit": "Card", "debit": "Card", "credit card": "Card", "visa": "Card", "mastercard": "Card",
            "cash": "Cash", "apple pay": "Apple Pay", "applepay": "Apple Pay", "online": "Online", "app": "Online", "web": "Online"}
ORDER_TYPES = {"dine-in": "Dine-in", "dine in": "Dine-in", "here": "Dine-in", "takeout": "Takeout", "take out": "Takeout",
               "to go": "Takeout", "pickup": "Takeout", "delivery app": "Delivery App", "delivery": "Delivery App",
               "doordash": "Delivery App", "uber eats": "Delivery App", "ubereats": "Delivery App", "grubhub": "Delivery App"}
SPICE = ["No Heat", "Mild", "Medium", "Hot", "Extra Hot", "Reaper"]
REQUIRED = ["order_id", "order_datetime", "channel", "item_name", "quantity", "unit_price"]
WARNINGS = []


def warn(msg):
    WARNINGS.append(msg)
    print("WARNING:", msg)


def canon(series, mapping, default, label):
    """Map messy POS labels onto the official spellings; unknown labels become `default` (and are reported)."""
    key = series.astype(str).str.strip().str.lower()
    out = key.map(mapping)
    unknown = sorted(set(series[out.isna() & series.notna()].astype(str)))
    if unknown:
        warn(f"{label}: unrecognized values {unknown[:8]} were set to '{default}'. Edit the mapping dictionaries at the top of this script to fix.")
    return out.fillna(default)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sales", required=True, help="POS export, one row per item sold")
    ap.add_argument("--events", help="events CSV: event_name,start_date,end_date,booth_fee,staff_count,city")
    ap.add_argument("--costs", help="optional CSV of item_name,unit_food_cost (recipe costs)")
    a = ap.parse_args()
    ensure_dirs()

    df = pd.read_csv(a.sales)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        sys.exit(f"Sales file is missing required columns: {missing}. See data/templates/pos_export_template.csv")
    df["order_datetime"] = pd.to_datetime(df.order_datetime, errors="coerce")
    bad = df.order_datetime.isna().sum()
    if bad:
        warn(f"{bad} rows with an unreadable order_datetime were dropped")
        df = df.dropna(subset=["order_datetime"])
    df["channel"] = canon(df.channel, CHANNELS, "Storefront", "channel")
    df["order_id"] = df.order_id.astype(str)

    # ---- menu ----
    if "category" not in df.columns:
        df["category"] = "Uncategorized"
        warn("no `category` column: every item is 'Uncategorized', so category charts will be uninteresting")
    if a.costs:
        costs = pd.read_csv(a.costs)
        df = df.merge(costs[["item_name", "unit_food_cost"]].rename(columns={"unit_food_cost": "_cost"}), on="item_name", how="left")
        df["unit_food_cost"] = df["_cost"].combine_first(df.get("unit_food_cost"))
        df = df.drop(columns="_cost")
    if "unit_food_cost" not in df.columns or df.unit_food_cost.isna().any():
        df["unit_food_cost"] = df.get("unit_food_cost", pd.Series(np.nan, index=df.index))
        n = int(df.unit_food_cost.isna().sum())
        df["unit_food_cost"] = df.unit_food_cost.fillna(df.unit_price * 0.30)
        warn(f"{n} lines had no food cost; 30% of price was assumed. Profit figures are only as good as your real recipe costs: provide --costs.")
    menu = (df.groupby("item_name").agg(category=("category", "first"), base_price=("unit_price", "median"),
                                        food_cost=("unit_food_cost", "median")).reset_index())
    menu.insert(0, "item_id", np.arange(1, len(menu) + 1))
    menu["is_combo"] = menu.category.str.lower().str.contains("combo")
    menu = menu[["item_id", "item_name", "category", "base_price", "food_cost", "is_combo"]]
    item_id = dict(zip(menu.item_name, menu.item_id))

    # ---- order items ----
    spice = pd.DataFrame({"level_id": range(1, 7), "level_name": SPICE, "heat_rank": range(6)})
    level_id = {n.lower(): i for n, i in zip(spice.level_name, spice.level_id)}
    if "spice_level" in df.columns:
        lvl = df.spice_level.astype(str).str.strip().str.lower().map(level_id)
        unk = sorted(set(df.spice_level[lvl.isna() & df.spice_level.notna()].astype(str)))
        if unk:
            warn(f"spice_level: unrecognized values {unk[:8]} were left blank (expected {SPICE})")
    else:
        lvl = pd.Series(np.nan, index=df.index)
        warn("no `spice_level` column: spice charts will be empty")
    order_items = pd.DataFrame({"order_id": df.order_id, "item_id": df.item_name.map(item_id), "level_id": lvl.astype("Int64"),
                                "quantity": df.quantity, "unit_price": df.unit_price})

    # ---- orders (one row per order: first line's attributes) ----
    first = df.sort_values("order_datetime").groupby("order_id").first()
    orders = pd.DataFrame({"order_id": first.index, "order_datetime": first.order_datetime.values, "channel": first.channel.values})
    def optional(col, mapping=None, default=None, label=None):
        if col not in first.columns:
            if default is not None:
                warn(f"no `{col}` column: assumed '{default}' for every order")
            return pd.Series(default, index=first.index)
        s = first[col]
        return canon(s, mapping, default, label) if mapping else s
    orders["event_name"] = optional("event_name").values
    orders["payment_method"] = optional("payment_method", PAYMENTS, "Card", "payment_method").values
    orders["order_type"] = optional("order_type", ORDER_TYPES, "Takeout", "order_type").values
    orders["customer_id"] = optional("customer_id").values
    orders["discount_amount"] = pd.to_numeric(optional("discount_amount", default=0.0), errors="coerce").values
    orders["tip_amount"] = pd.to_numeric(optional("tip_amount", default=0.0), errors="coerce").fillna(0).values
    orders["prep_time_minutes"] = pd.to_numeric(optional("prep_time_minutes", default=np.nan), errors="coerce").values
    orders["order_datetime"] = pd.to_datetime(orders.order_datetime).dt.strftime("%Y-%m-%d %H:%M:%S")

    # ---- events ----
    if a.events:
        events = pd.read_csv(a.events)
    else:
        events = pd.DataFrame(columns=["event_name", "start_date", "end_date", "booth_fee", "staff_count", "city"])
        if (orders.channel == "Vendor Event").any():
            sys.exit("Your sales include 'Vendor Event' rows, so --events is required (booth fee and staff count per event).")
    if (orders.channel == "Vendor Event").any():
        names = set(events.event_name)
        mism = sorted(set(orders.loc[orders.channel == "Vendor Event", "event_name"].dropna()) - names)
        if mism:
            sys.exit(f"event_name values not found in the events file: {mism}. Names must match exactly.")

    # ---- customers ----
    known = orders.dropna(subset=["customer_id"])
    if len(known):
        cust = known.groupby("customer_id").order_datetime.min().str[:10].rename("first_order_date").reset_index()
        extra = first.reset_index()[["order_id"]]
        cust["zip_code"] = cust.customer_id.map(first.dropna(subset=["customer_id"]).set_index("customer_id").get("zip_code", pd.Series(dtype=object)))
        lm = first.dropna(subset=["customer_id"]).set_index("customer_id").get("loyalty_member", pd.Series(dtype=object))
        cust["loyalty_member"] = cust.customer_id.map(lm).astype(str).str.lower().isin(["true", "1", "yes", "y"]) if len(lm) else False
        cust = cust[["customer_id", "first_order_date", "zip_code", "loyalty_member"]]
    else:
        cust = pd.DataFrame(columns=["customer_id", "first_order_date", "zip_code", "loyalty_member"])
        warn("no customer_id values: customer, loyalty and cohort analysis will be empty")

    menu.to_csv(RAW_DIR / "menu.csv", index=False)
    spice.to_csv(RAW_DIR / "spice_levels.csv", index=False)
    orders.to_csv(RAW_DIR / "orders.csv", index=False)
    order_items.to_csv(RAW_DIR / "order_items.csv", index=False)
    cust.to_csv(RAW_DIR / "customers.csv", index=False)
    events.to_csv(RAW_DIR / "events.csv", index=False)
    print(f"\nImported {len(orders):,} orders / {len(order_items):,} lines / {len(menu)} items / {len(cust):,} customers / {len(events)} events")
    print(f"Raw tables written to {RAW_DIR}\nNext step:  python run_all.py --real")


if __name__ == "__main__":
    main()
