"""STEP 2 - Clean the raw CSVs and add calculated fields.

Run from the repo root:   python scripts/clean_data.py

Reads  data/raw/*.csv
Writes data/clean/*.csv   and   data/cleaning_log.md (every change, with row counts)
"""
import numpy as np
import pandas as pd

from paths import CLEAN_DIR, CLEANING_LOG, RAW_DIR, ensure_dirs

ensure_dirs()
LOG = []  # list of (table, issue, action, rows_affected)


def log(table, issue, action, n):
    """Record one cleaning step; printed and written to cleaning_log.md."""
    LOG.append((table, issue, action, int(n)))
    print(f"[{table}] {issue}: {int(n):,} rows -> {action}")


def standardize(series, canonical, table, col):
    """Map messy text (case / extra spaces) onto the official spelling."""
    lookup = {c.lower(): c for c in canonical}
    cleaned = series.map(lambda v: lookup.get(str(v).strip().lower(), v) if pd.notna(v) else v)
    changed = (cleaned.fillna("") != series.fillna("")).sum()
    unknown = (cleaned.notna() & ~cleaned.isin(canonical)).sum()
    log(table, f"Inconsistent capitalization/whitespace in `{col}`", "standardized to official spelling", changed)
    if unknown:
        raise ValueError(f"{col}: {unknown} values could not be matched")
    return cleaned


# --------------------------------------------------------------------------
# Load
# --------------------------------------------------------------------------
menu = pd.read_csv(RAW_DIR / "menu.csv")
spice = pd.read_csv(RAW_DIR / "spice_levels.csv")
events = pd.read_csv(RAW_DIR / "events.csv", parse_dates=["start_date", "end_date"])
orders = pd.read_csv(RAW_DIR / "orders.csv")
items = pd.read_csv(RAW_DIR / "order_items.csv")
customers = pd.read_csv(RAW_DIR / "customers.csv", dtype={"zip_code": "string"})
raw_counts = {"orders": len(orders), "order_items": len(items), "customers": len(customers)}

# --------------------------------------------------------------------------
# ORDERS
# --------------------------------------------------------------------------
n = orders.duplicated().sum()
orders = orders.drop_duplicates().reset_index(drop=True)
log("orders", "Exact duplicate rows (same order_id and values)", "dropped, kept first copy", n)
assert orders.order_id.is_unique, "order_id still not unique after dropping duplicates"

orders["channel"] = standardize(orders.channel, ["Storefront", "Night Market", "Vendor Event"], "orders", "channel")
orders["payment_method"] = standardize(orders.payment_method, ["Card", "Cash", "Apple Pay", "Online"], "orders", "payment_method")
orders["order_type"] = standardize(orders.order_type, ["Dine-in", "Takeout", "Delivery App"], "orders", "order_type")
orders["event_name"] = standardize(orders.event_name, events.event_name.tolist(), "orders", "event_name")

orders["order_datetime"] = pd.to_datetime(orders.order_datetime)

n = orders.discount_amount.isna().sum()
orders["discount_amount"] = orders.discount_amount.fillna(0.0)
log("orders", "Blank `discount_amount`", "filled with 0 (no discount recorded)", n)

bad_prep = (orders.prep_time_minutes <= 0) | (orders.prep_time_minutes > 120)
orders.loc[bad_prep, "prep_time_minutes"] = np.nan
log("orders", "Impossible `prep_time_minutes` (0 or > 120 min)", "set to blank so averages ignore them", bad_prep.sum())

# --------------------------------------------------------------------------
# ORDER ITEMS
# --------------------------------------------------------------------------
n = items.duplicated().sum()
items = items.drop_duplicates().reset_index(drop=True)
log("order_items", "Exact duplicate line items", "dropped, kept first copy", n)

neg = items.quantity < 0
items.loc[neg, "quantity"] = items.loc[neg, "quantity"].abs()
log("order_items", "Negative `quantity` (no matching refund records, so treated as sign-entry typo)",
    "converted to positive", neg.sum())

orphans = ~items.order_id.isin(orders.order_id)
items = items[~orphans].reset_index(drop=True)
log("order_items", "Line items whose order_id is not in orders", "dropped", orphans.sum())

items["level_id"] = items.level_id.astype("Int64")
price_mismatch = (items.merge(menu, on="item_id").eval("unit_price != base_price")).sum()
log("order_items", "unit_price differs from menu base_price", "none needed (validation passed)" if price_mismatch == 0 else "REVIEW", price_mismatch)

# Enrich lines with menu + spice info and line-level money fields
items = (items.merge(menu[["item_id", "item_name", "category", "food_cost"]], on="item_id", how="left")
              .merge(spice[["level_id", "level_name"]], on="level_id", how="left"))
items = items.rename(columns={"level_name": "spice_level", "food_cost": "unit_food_cost"})
items["spice_level"] = items.spice_level.fillna("Not Applicable")  # sides and drinks have no heat level
items["line_revenue"] = items.quantity * items.unit_price
items["line_food_cost"] = items.quantity * items.unit_food_cost

# Order-level subtotal so the discount can be spread across lines in proportion to line value
order_subtotal = items.groupby("order_id").line_revenue.sum().rename("subtotal")
items = items.join(order_subtotal, on="order_id").join(orders.set_index("order_id").discount_amount, on="order_id")
items["line_discount"] = items.discount_amount * items.line_revenue / items.subtotal
items["line_profit"] = items.line_revenue - items.line_discount - items.line_food_cost
items.insert(0, "line_id", np.arange(1, len(items) + 1))
items = items.drop(columns=["subtotal", "discount_amount"])
money_cols = ["line_revenue", "line_food_cost", "line_discount", "line_profit"]
items[money_cols] = items[money_cols].round(4)
log("order_items", "Added calculated fields", "line_revenue, line_food_cost, line_discount, line_profit, item_name, category, spice_level", len(items))

# --------------------------------------------------------------------------
# ORDERS: calculated fields
# --------------------------------------------------------------------------
totals = items.groupby("order_id").agg(subtotal=("line_revenue", "sum"), food_cost_total=("line_food_cost", "sum"),
                                        item_count=("quantity", "sum"))
orders = orders.join(totals, on="order_id")
no_lines = orders.subtotal.isna().sum()
orders = orders.dropna(subset=["subtotal"]).reset_index(drop=True)
log("orders", "Orders with no line items", "dropped (cannot value them)", no_lines)

orders["revenue"] = (orders.subtotal - orders.discount_amount).round(2)   # tips are NOT revenue
orders["food_cost_total"] = orders.food_cost_total.round(2)
orders["gross_profit"] = (orders.revenue - orders.food_cost_total).round(2)
orders["gross_margin_pct"] = (orders.gross_profit / orders.revenue * 100).round(2)
orders["subtotal"] = orders.subtotal.round(2)

dt = orders.order_datetime
orders["order_date"] = dt.dt.normalize()
orders["hour"] = dt.dt.hour
orders["day_of_week"] = dt.dt.day_name()
orders["day_of_week_num"] = dt.dt.dayofweek          # 0 = Monday ... 6 = Sunday
orders["month"] = dt.dt.month
orders["month_name"] = dt.dt.strftime("%b")
orders["quarter"] = "Q" + dt.dt.quarter.astype(str)
orders["is_weekend"] = dt.dt.dayofweek >= 5
orders["daypart"] = pd.cut(orders.hour, [-1, 10, 13, 16, 20, 24],
                           labels=["Early", "Lunch", "Afternoon", "Dinner", "Late Night"]).astype(str)
assert not (orders.daypart == "Early").any(), "unexpected orders before 11am"
log("orders", "Added calculated fields",
    "subtotal, revenue, food_cost_total, gross_profit, gross_margin_pct, hour, day_of_week, month, quarter, is_weekend, daypart",
    len(orders))

# --------------------------------------------------------------------------
# CUSTOMERS
# --------------------------------------------------------------------------
n = customers.duplicated().sum()
customers = customers.drop_duplicates().reset_index(drop=True)
log("customers", "Exact duplicate customer rows", "dropped, kept first copy", n)
assert customers.customer_id.is_unique

bad_zip = customers.zip_code.isna() | ~customers.zip_code.fillna("").str.fullmatch(r"\d{5}")
customers.loc[bad_zip, "zip_code"] = "Unknown"
log("customers", "Missing or invalid `zip_code` (blank / 'unknown')", "labelled 'Unknown' (cannot be guessed)", bad_zip.sum())

VENTURA = {"93001", "93003", "93004", "93010", "93012", "93030", "93033", "93035", "93036", "93060", "93065",
           "93063", "91360", "91362", "91320", "93021", "93015"}
customers["county"] = np.where(customers.zip_code == "Unknown", "Unknown",
                               np.where(customers.zip_code.isin(VENTURA), "Ventura", "Los Angeles"))
customers["loyalty_member"] = customers.loyalty_member.astype(bool)

# Bring customer facts onto orders, and compute repeat behaviour from the order history
orders = orders.merge(customers[["customer_id", "loyalty_member"]], on="customer_id", how="left")
orders = orders.sort_values(["order_datetime", "order_id"]).reset_index(drop=True)
per_cust = orders.dropna(subset=["customer_id"]).sort_values("order_datetime")
prev_date = per_cust.groupby("customer_id").order_date.shift(1)
orders.loc[per_cust.index, "days_to_repeat_order"] = (per_cust.order_date - prev_date).dt.days
log("orders", "Added `days_to_repeat_order`", "days since the same customer's previous order (blank for first orders / walk-ups)",
    orders.days_to_repeat_order.notna().sum())

# Customer history: recompute first order from the data so it always agrees with orders
hist = per_cust.groupby("customer_id").agg(
    true_first=("order_date", "min"), total_orders=("order_id", "count"), total_revenue=("revenue", "sum"))
second = per_cust.groupby("customer_id").order_date.apply(lambda s: s.iloc[1] if len(s) > 1 else pd.NaT)
customers = customers.merge(hist, on="customer_id", how="left")
customers["days_to_second_order"] = (second.reindex(customers.customer_id).values - customers.true_first).dt.days
customers["first_order_date"] = pd.to_datetime(customers.first_order_date)
mismatch = (customers.first_order_date != customers.true_first).sum()
customers["first_order_date"] = customers.true_first
customers = customers.drop(columns="true_first")
customers["first_order_month"] = customers.first_order_date.dt.strftime("%Y-%m")
no_orders = customers.total_orders.isna().sum()
customers = customers.dropna(subset=["total_orders"]).reset_index(drop=True)
customers["total_orders"] = customers.total_orders.astype(int)
customers["total_revenue"] = customers.total_revenue.round(2)
log("customers", "`first_order_date` disagrees with order history", "recomputed from orders", mismatch)
log("customers", "Customers with no orders", "dropped", no_orders)
log("customers", "Added calculated fields", "county, total_orders, total_revenue, days_to_second_order, first_order_month", len(customers))

# --------------------------------------------------------------------------
# EVENTS
# --------------------------------------------------------------------------
events["event_days"] = (events.end_date - events.start_date).dt.days + 1
log("events", "Added `event_days`", "end_date - start_date + 1", len(events))

# --------------------------------------------------------------------------
# Final integrity checks, then save
# --------------------------------------------------------------------------
assert items.order_id.isin(orders.order_id).all()
assert orders.customer_id.dropna().isin(customers.customer_id).all()
assert (orders.revenue > 0).all()

order_cols = ["order_id", "order_datetime", "order_date", "channel", "event_name", "payment_method", "order_type",
              "customer_id", "loyalty_member", "discount_amount", "tip_amount", "prep_time_minutes", "item_count",
              "subtotal", "revenue", "food_cost_total", "gross_profit", "gross_margin_pct", "hour", "day_of_week",
              "day_of_week_num", "month", "month_name", "quarter", "is_weekend", "daypart", "days_to_repeat_order"]
orders[order_cols].assign(order_date=orders.order_date.dt.strftime("%Y-%m-%d")).to_csv(CLEAN_DIR / "orders.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")
items.to_csv(CLEAN_DIR / "order_items.csv", index=False)
customers.to_csv(CLEAN_DIR / "customers.csv", index=False, date_format="%Y-%m-%d")
events.to_csv(CLEAN_DIR / "events.csv", index=False, date_format="%Y-%m-%d")
menu.to_csv(CLEAN_DIR / "menu.csv", index=False)
spice.to_csv(CLEAN_DIR / "spice_levels.csv", index=False)

# --------------------------------------------------------------------------
# Write the cleaning log
# --------------------------------------------------------------------------
lines = ["# Data Cleaning Log", "",
         "Generated by `scripts/clean_data.py`. Every change made to the raw CSVs in `data/raw/` is listed below.", "",
         "## Row counts", "", "| Table | Raw rows | Clean rows |", "|---|---:|---:|",
         f"| orders | {raw_counts['orders']:,} | {len(orders):,} |",
         f"| order_items | {raw_counts['order_items']:,} | {len(items):,} |",
         f"| customers | {raw_counts['customers']:,} | {len(customers):,} |", "",
         "## Changes", "", "| # | Table | Issue | Action | Rows affected |", "|--:|---|---|---|--:|"]
for i, (t, issue, action, rows) in enumerate(LOG, 1):
    lines.append(f"| {i} | {t} | {issue} | {action} | {rows:,} |")
lines += ["", "## Assumptions", "",
          "- **Revenue** = sum of line revenue minus order discount. Tips are excluded (they go to staff).",
          "- **Gross profit** = revenue - food cost. Labor, rent and booth fees are handled in the SQL/Excel analysis.",
          "- **Negative quantities** have no matching refund records, so they are treated as sign typos.",
          "- **Sides and drinks** have no spice level; they are labelled `Not Applicable`.",
          "- **Discount** is spread across an order's lines in proportion to line value, so line profit sums to order profit."]
CLEANING_LOG.write_text("\n".join(lines) + "\n")
print(f"\nClean files written to {CLEAN_DIR}")
