"""STEP 1 - Generate synthetic raw data for the Heat Check hot chicken restaurant.

Run from the repo root:   python scripts/generate_data.py

Writes six CSV files to data/raw/. A fixed random seed makes every run
identical. A handful of *deliberate* data-quality problems are injected at
the end (duplicates, blanks, negative quantities, messy capitalization) so
that clean_data.py has real work to do.

Business patterns built in:
  * Storefront: open Tue-Sun, lunch rush 11:30-1:30, Fri/Sat evening peak,
    Fri/Sat late-night window. Closed Mondays and 3 holidays.
  * Night Market: a booth every Friday night, stronger in summer.
  * Vendor Events: 8 multi-day festivals; Q3 events are the biggest, and a
    couple of small events are barely worth their booth fee.
  * Bigger parties (higher average order value) at events.
  * Medium / Hot are the most popular spice levels.
  * Prep time rises with order volume in the same 30-minute window.
"""
import numpy as np
import pandas as pd

from paths import RAW_DIR, ensure_dirs

SEED = 42
YEAR = 2025
N_CUSTOMER_POOL = 6500

rng = np.random.default_rng(SEED)

# --------------------------------------------------------------------------
# 1. Reference tables
# --------------------------------------------------------------------------
# (item_id, item_name, category, base_price, food_cost, is_combo)
MENU_ROWS = [
    (1, "Classic Hot Chicken Sandwich", "Sandwich", 12.50, 3.85, False),
    (2, "Double Stack Sandwich", "Sandwich", 15.50, 5.90, False),
    (3, "Chicken & Waffle Sandwich", "Sandwich", 13.50, 4.30, False),
    (4, "Tenders 3pc", "Tenders", 9.50, 2.85, False),
    (5, "Tenders 5pc", "Tenders", 14.00, 4.30, False),
    (6, "Tenders 8pc", "Tenders", 19.50, 6.40, False),
    (7, "Wings 6pc", "Wings", 11.00, 4.60, False),
    (8, "Wings 10pc", "Wings", 17.00, 7.20, False),
    (9, "Wings 20pc", "Wings", 32.00, 14.00, False),
    (10, "Seasoned Fries", "Sides", 4.50, 1.10, False),
    (11, "Mac & Cheese", "Sides", 5.50, 1.70, False),
    (12, "Coleslaw", "Sides", 4.00, 0.85, False),
    (13, "Pickle Chips", "Sides", 3.00, 0.55, False),
    (14, "Cornbread", "Sides", 3.50, 0.80, False),
    (15, "Lemonade", "Drinks", 4.00, 0.65, False),
    (16, "Sweet Tea", "Drinks", 3.50, 0.40, False),
    (17, "Fountain Soda", "Drinks", 3.00, 0.45, False),
    (18, "Banana Pudding Shake", "Drinks", 7.00, 2.20, False),
    (19, "Sandwich Combo", "Combos", 17.50, 5.80, True),
    (20, "Tender Combo", "Combos", 18.00, 6.10, True),
    (21, "Wing Combo", "Combos", 20.50, 8.30, True),
    (22, "Family Pack", "Combos", 58.00, 21.50, True),
]
menu = pd.DataFrame(MENU_ROWS, columns=["item_id", "item_name", "category", "base_price", "food_cost", "is_combo"])
PRICE = dict(zip(menu.item_id, menu.base_price))

spice_levels = pd.DataFrame({
    "level_id": [1, 2, 3, 4, 5, 6],
    "level_name": ["No Heat", "Mild", "Medium", "Hot", "Extra Hot", "Reaper"],
    "heat_rank": [0, 1, 2, 3, 4, 5],
})

# Vendor events: name, start, end, booth_fee, staff_count, city, avg orders/day
EVENT_ROWS = [
    ("Ventura Winter Food Fest", "2025-02-14", "2025-02-16", 600, 4, "Ventura", 240),
    ("Oxnard Spring Street Eats", "2025-03-28", "2025-03-29", 450, 3, "Oxnard", 210),
    ("Santa Paula Chili Cookoff", "2025-05-09", "2025-05-11", 900, 5, "Santa Paula", 330),
    ("Camarillo Craft & Bites", "2025-06-06", "2025-06-07", 1200, 4, "Camarillo", 70),
    ("Long Beach Street Food Fest", "2025-07-18", "2025-07-20", 2200, 7, "Long Beach", 480),
    ("Ventura Summer Heat Fest", "2025-08-01", "2025-08-03", 1500, 6, "Ventura", 420),
    ("Thousand Oaks Fall Food Truck Fest", "2025-09-26", "2025-09-28", 800, 4, "Thousand Oaks", 260),
    ("Santa Clarita Holiday Market", "2025-12-05", "2025-12-06", 900, 4, "Santa Clarita", 80),
]
events_full = pd.DataFrame(EVENT_ROWS, columns=["event_name", "start_date", "end_date", "booth_fee",
                                                "staff_count", "city", "orders_per_day"])
events_full["start_date"] = pd.to_datetime(events_full.start_date)
events_full["end_date"] = pd.to_datetime(events_full.end_date)
events = events_full.drop(columns="orders_per_day")

# Map each event date -> (event name, expected daily orders)
EVENT_DAYS = {}
for _, e in events_full.iterrows():
    for d in pd.date_range(e.start_date, e.end_date):
        EVENT_DAYS[d.normalize()] = (e.event_name, e.orders_per_day)

CLOSED_DATES = {pd.Timestamp(f"{YEAR}-01-01"), pd.Timestamp(f"{YEAR}-11-27"), pd.Timestamp(f"{YEAR}-12-25")}

# --------------------------------------------------------------------------
# 2. Customer pool (who *could* order; only those who do are kept later)
# --------------------------------------------------------------------------
ZIPS = {  # Ventura County (mostly) + LA County
    "93001": 10, "93003": 9, "93004": 7, "93010": 8, "93012": 6, "93030": 8, "93033": 7, "93035": 5,
    "93036": 4, "93060": 4, "93065": 6, "93063": 5, "91360": 7, "91362": 6, "91320": 4, "93021": 4,
    "93015": 2, "91355": 3, "91381": 2, "91301": 2, "91311": 2, "90802": 2, "91101": 1,
}
zip_codes = np.array(list(ZIPS))
zip_p = np.array(list(ZIPS.values()), dtype=float)
zip_p /= zip_p.sum()

pool_loyal = rng.random(N_CUSTOMER_POOL) < 0.30
# ~30% of the pool are existing customers from before Jan 1; the rest arrive during the year
pool_arrival = np.where(rng.random(N_CUSTOMER_POOL) < 0.30,
                        rng.integers(-150, 0, N_CUSTOMER_POOL),
                        rng.integers(0, 365, N_CUSTOMER_POOL))
# Customers stay active for a while and then churn (members stay ~2.5x longer)
pool_life = rng.exponential(110, N_CUSTOMER_POOL) * np.where(pool_loyal, 2.5, 1.0) + 7
pool_activity = rng.gamma(0.7, 1.0, N_CUSTOMER_POOL) * np.where(pool_loyal, 2.0, 1.0) + 0.02
pool_pref = rng.choice(["Storefront", "Night Market", "Vendor Event"], N_CUSTOMER_POOL, p=[0.72, 0.22, 0.06])
pool_zip = rng.choice(zip_codes, N_CUSTOMER_POOL, p=zip_p)

# --------------------------------------------------------------------------
# 3. Order-building helpers
# --------------------------------------------------------------------------
MAIN_IDS = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 19, 20, 21, 22])
BASE_MAIN_W = np.array([.15, .06, .05, .05, .10, .03, .05, .07, .015, .12, .13, .06, .012])
MAIN_TILT = {
    "Storefront": np.ones(13),
    "Night Market": np.array([1.3, 1.3, 1.3, 1.2, 1.2, 1, .7, .7, .4, 1, 1, .7, .2]),
    "Vendor Event": np.array([1, 1, 1, 1, 1, 1, 1, 1, 1.5, 1.4, 1.4, 1.4, 2.5]),
}
MAIN_P = {c: (BASE_MAIN_W * t) / (BASE_MAIN_W * t).sum() for c, t in MAIN_TILT.items()}
SIDE_IDS, SIDE_P = np.array([10, 11, 12, 13, 14]), np.array([.40, .25, .15, .10, .10])
DRINK_IDS, DRINK_P = np.array([15, 16, 17, 18]), np.array([.30, .30, .25, .15])
SPICED_CATEGORIES = {"Sandwich", "Tenders", "Wings", "Combos"}
CATEGORY = dict(zip(menu.item_id, menu.category))

SPICE_P = {
    "Storefront": np.array([.07, .17, .30, .27, .14, .05]),
    "Night Market": np.array([.06, .15, .29, .29, .15, .06]),
    "Vendor Event": np.array([.05, .13, .27, .28, .19, .08]),  # festival crowds go hotter
}
LATE_NIGHT_TILT = np.array([.6, .7, .9, 1.1, 1.3, 1.5])  # late-night guests go hotter still


def spice_probs(channel, hour):
    p = SPICE_P[channel] * (LATE_NIGHT_TILT if hour >= 21 else 1.0)
    return p / p.sum()


# Half-hour slots: (start hour, start minute) -> relative traffic weight
def _slots(start_hour, weights):
    return [(start_hour * 60 + 30 * i, w) for i, w in enumerate(weights)]


STORE_WEEKDAY = _slots(11, [.5, 1.6, 2.0, 1.8, 1.4, .8, .5, .4, .4, .4, .5, .8, 1.2, 1.6, 1.8, 1.8, 1.5, 1.1, .7, .4])
STORE_FRISAT_LATE = _slots(21, [.9, .8, .6, .4, .25])
NIGHT_MARKET = _slots(17, [.5, .9, 1.5, 1.9, 2.0, 1.8, 1.4, 1.0, .6, .3])
EVENT_SLOTS = _slots(11, [.6, 1.2, 1.8, 1.9, 1.6, 1.2, 1.0, .9, .9, .9, 1.0, 1.3, 1.7, 1.8, 1.7, 1.4, 1.0, .7, .4, .2])


def slot_table(channel, dow):
    """Return (start_minutes array, probability array) for a channel/day-of-week."""
    if channel == "Storefront":
        slots = list(STORE_WEEKDAY)
        if dow in (4, 5):  # Fri/Sat: stronger dinner + late-night window
            slots = [(m, w * (1.35 if m >= 17 * 60 else 1.0)) for m, w in slots] + STORE_FRISAT_LATE
    elif channel == "Night Market":
        slots = NIGHT_MARKET
    else:
        slots = EVENT_SLOTS
    starts = np.array([s[0] for s in slots])
    w = np.array([s[1] for s in slots], dtype=float)
    return starts, w / w.sum()


STORE_DOW = {1: .75, 2: .80, 3: .90, 4: 1.35, 5: 1.50, 6: 1.10}  # Mon(0) closed
STORE_SEASON = [.92, .95, 1.0, 1.03, 1.05, 1.12, 1.18, 1.15, 1.05, 1.0, .98, .95]
NM_SEASON = [.80, .85, .95, 1.05, 1.10, 1.25, 1.35, 1.30, 1.15, 1.0, .85, .80]
EVENT_DOW = {4: .90, 5: 1.15, 6: .95}
STORE_BASE, NM_BASE = 40, 92
PARTY_LAMBDA = {"Storefront": .35, "Night Market": .55, "Vendor Event": .80}
SIDE_ATTACH = {"Storefront": .50, "Night Market": .50, "Vendor Event": .55}


def build_lines(channel, order_type, hour):
    """Random basket for one order -> dict {(item_id, level_id or None): qty}."""
    lam = .6 if order_type == "Delivery App" else PARTY_LAMBDA[channel]
    n_people = 1 + rng.poisson(lam)
    lines = {}
    for _ in range(n_people):
        main = int(rng.choice(MAIN_IDS, p=MAIN_P[channel]))
        level = int(rng.choice(spice_levels.level_id, p=spice_probs(channel, hour)))
        lines[(main, level)] = lines.get((main, level), 0) + 1
        is_combo = CATEGORY[main] == "Combos"
        if rng.random() < (.15 if is_combo else SIDE_ATTACH[channel]):
            side = int(rng.choice(SIDE_IDS, p=SIDE_P))
            lines[(side, None)] = lines.get((side, None), 0) + 1
        if not is_combo and rng.random() < .45:
            drink = int(rng.choice(DRINK_IDS, p=DRINK_P))
            lines[(drink, None)] = lines.get((drink, None), 0) + 1
    return lines


def pick_order_type(channel):
    if channel == "Storefront":
        return rng.choice(["Dine-in", "Takeout", "Delivery App"], p=[.38, .40, .22])
    return rng.choice(["Dine-in", "Takeout"], p=[.40, .60] if channel == "Vendor Event" else [.30, .70])


def pick_payment(channel, order_type):
    if order_type == "Delivery App":
        return "Online"
    if channel == "Storefront":
        if order_type == "Dine-in":
            return rng.choice(["Card", "Apple Pay", "Cash"], p=[.62, .22, .16])
        return rng.choice(["Online", "Card", "Apple Pay", "Cash"], p=[.25, .42, .20, .13])
    return rng.choice(["Card", "Cash", "Apple Pay"], p=[.42, .30, .28])


def pick_tip(payment, order_type, channel, subtotal):
    if payment == "Cash":
        return float(rng.choice([1, 2, 3, 5])) if rng.random() < .30 else 0.0
    if payment == "Online":
        prob = .80 if order_type == "Delivery App" else .30
        pct = rng.uniform(.10, .20)
    elif channel == "Storefront":
        prob, pct = (.75 if order_type == "Dine-in" else .45), rng.uniform(.08, .25)
    else:
        prob, pct = .55, rng.uniform(.10, .20)
    return round(subtotal * pct, 2) if rng.random() < prob else 0.0


def pick_discount(subtotal, is_member):
    if rng.random() >= (.09 if is_member else .04):  # overall ~5% of orders
        return 0.0
    kind = rng.choice(["p10", "p15", "f2", "f5"], p=[.4, .2, .25, .15])
    amt = {"p10": subtotal * .10, "p15": subtotal * .15, "f2": 2.0, "f5": 5.0}[kind]
    return round(min(amt, subtotal * .5), 2)


ID_RATE = {"Storefront": .38, "Night Market": .22, "Vendor Event": .08}  # share of non-delivery orders with a customer id

# --------------------------------------------------------------------------
# 4. Walk through every day of the year and create orders
# --------------------------------------------------------------------------
orders, lines_out = [], []

for day in pd.date_range(f"{YEAR}-01-01", f"{YEAR}-12-31"):
    dow, month = day.dayofweek, day.month
    trend = 1 + 0.004 * (month - 1)  # slow growth through the year
    plan = []  # (channel, n_orders, event_name)

    if day not in CLOSED_DATES and dow != 0:
        plan.append(("Storefront", rng.poisson(STORE_BASE * STORE_DOW[dow] * STORE_SEASON[month - 1] * trend), None))
    if dow == 4 and day not in EVENT_DAYS and day not in CLOSED_DATES:
        plan.append(("Night Market", rng.poisson(NM_BASE * NM_SEASON[month - 1] * trend), None))
    if day in EVENT_DAYS:
        name, per_day = EVENT_DAYS[day]
        plan.append(("Vendor Event", rng.poisson(per_day * EVENT_DOW.get(dow, 1.0)), name))

    day_idx = (day - pd.Timestamp(f"{YEAR}-01-01")).days
    eligible = (pool_arrival <= day_idx) & (day_idx <= pool_arrival + pool_life)

    for channel, n, event_name in plan:
        if n == 0:
            continue
        starts, probs = slot_table(channel, dow)
        minutes = starts[rng.choice(len(starts), size=n, p=probs)] + rng.integers(0, 30, n)
        batch = []
        for m in minutes:
            otype = pick_order_type(channel)
            hour = int(m // 60)
            lines = build_lines(channel, otype, hour)
            subtotal = sum(PRICE[i] * q for (i, _), q in lines.items())
            has_customer = otype == "Delivery App" or rng.random() < ID_RATE[channel]
            payment = pick_payment(channel, otype)
            batch.append(dict(
                order_datetime=day + pd.Timedelta(minutes=int(m), seconds=int(rng.integers(0, 60))),
                channel=channel, event_name=event_name, payment_method=payment, order_type=otype,
                has_customer=has_customer, tip_amount=pick_tip(payment, otype, channel, subtotal),
                lines=lines, subtotal=subtotal, n_items=sum(lines.values()),
                slot=int(m // 30),
            ))

        # Assign customers (heavier buyers and channel "fans" are picked more often)
        idx = [i for i, o in enumerate(batch) if o["has_customer"]]
        if idx:
            w = pool_activity * np.where(pool_pref == channel, 1.0, .25) * eligible
            chosen = rng.choice(N_CUSTOMER_POOL, size=len(idx), p=w / w.sum())
            for i, c in zip(idx, chosen):
                batch[i]["cust"] = int(c)
        for o in batch:
            cust = o.get("cust")
            o["customer_id"] = f"C{cust + 1:05d}" if cust is not None else None
            o["discount_amount"] = pick_discount(o["subtotal"], bool(pool_loyal[cust]) if cust is not None else False)
        orders.extend(batch)

# --------------------------------------------------------------------------
# 5. Assemble DataFrames
# --------------------------------------------------------------------------
orders_df = pd.DataFrame(orders).sort_values("order_datetime").reset_index(drop=True)
orders_df["order_id"] = [f"HC{i + 1:06d}" for i in range(len(orders_df))]

# Prep time: base + per-item time + a penalty that grows with orders in the same
# 30-minute window (the kitchen bottleneck). Storefront kitchen is the smallest.
LOAD_PENALTY = {"Storefront": .90, "Night Market": .45, "Vendor Event": .30}
orders_df["date"] = orders_df.order_datetime.dt.normalize()
slot_load = orders_df.groupby(["date", "channel", "slot"]).order_id.transform("count")
prep = (3.5 + .9 * orders_df.n_items + orders_df.channel.map(LOAD_PENALTY) * slot_load
        + np.where(orders_df.order_type == "Delivery App", 2, 0) + rng.normal(0, 1.2, len(orders_df)))
orders_df["prep_time_minutes"] = prep.clip(3, 45).round(1)

items_rows = []
for oid, lines in zip(orders_df.order_id, orders_df["lines"]):
    for (item, level), qty in lines.items():
        items_rows.append((oid, item, level, qty, PRICE[item]))
order_items_df = pd.DataFrame(items_rows, columns=["order_id", "item_id", "level_id", "quantity", "unit_price"])
order_items_df["level_id"] = order_items_df["level_id"].astype("Int64")  # keeps blanks for sides/drinks

# Customers = only pool members who actually ordered
first_order = orders_df.dropna(subset=["customer_id"]).groupby("customer_id").order_datetime.min().dt.normalize()
cust_idx = first_order.index.str[1:].astype(int) - 1
customers_df = pd.DataFrame({
    "customer_id": first_order.index,
    "first_order_date": first_order.values,
    "zip_code": pool_zip[cust_idx],
    "loyalty_member": pool_loyal[cust_idx],
}).reset_index(drop=True)

orders_out = orders_df[["order_id", "order_datetime", "channel", "event_name", "payment_method", "order_type",
                        "customer_id", "discount_amount", "tip_amount", "prep_time_minutes"]].copy()
orders_out["order_datetime"] = orders_out.order_datetime.dt.strftime("%Y-%m-%d %H:%M:%S")
customers_df["first_order_date"] = pd.to_datetime(customers_df.first_order_date).dt.strftime("%Y-%m-%d")
events_out = events.copy()
events_out["start_date"] = events_out.start_date.dt.strftime("%Y-%m-%d")
events_out["end_date"] = events_out.end_date.dt.strftime("%Y-%m-%d")

# --------------------------------------------------------------------------
# 6. Inject deliberate data-quality problems (so the cleaning step has work)
# --------------------------------------------------------------------------
def messy_case(series, frac):
    """Randomly UPPER / lower / pad a fraction of the values."""
    s = series.copy()
    pick = s.notna() & (rng.random(len(s)) < frac)
    styles = rng.integers(0, 3, len(s))
    s = s.astype(object)
    s[pick & (styles == 0)] = s[pick & (styles == 0)].str.upper()
    s[pick & (styles == 1)] = s[pick & (styles == 1)].str.lower()
    s[pick & (styles == 2)] = " " + s[pick & (styles == 2)] + " "
    return s


for col in ["channel", "payment_method", "order_type", "event_name"]:
    orders_out[col] = messy_case(orders_out[col], 0.04)

# 40 blank discounts and 8 impossible prep times
orders_out.loc[rng.choice(len(orders_out), 40, replace=False), "discount_amount"] = np.nan
orders_out.loc[rng.choice(len(orders_out), 4, replace=False), "prep_time_minutes"] = 0
orders_out.loc[rng.choice(len(orders_out), 4, replace=False), "prep_time_minutes"] = 240

# ~110 exact duplicate order rows (e.g. a POS double-sync)
dups = orders_out.sample(110, random_state=SEED)
orders_out = pd.concat([orders_out, dups], ignore_index=True).sample(frac=1, random_state=SEED).reset_index(drop=True)

# 30 negative quantities + 60 duplicate order-item lines
neg = rng.choice(len(order_items_df), 30, replace=False)
order_items_df.loc[neg, "quantity"] *= -1
order_items_df = pd.concat([order_items_df, order_items_df.sample(60, random_state=SEED)], ignore_index=True)

# ~6% missing zips + 1% literal "unknown" + 15 duplicated customer rows
customers_df["zip_code"] = customers_df.zip_code.astype(object)
miss = rng.random(len(customers_df))
customers_df.loc[miss < .06, "zip_code"] = np.nan
customers_df.loc[(miss >= .06) & (miss < .07), "zip_code"] = "unknown"
customers_df = pd.concat([customers_df, customers_df.sample(15, random_state=SEED)], ignore_index=True)

# --------------------------------------------------------------------------
# 7. Save
# --------------------------------------------------------------------------
ensure_dirs()
menu.to_csv(RAW_DIR / "menu.csv", index=False)
spice_levels.to_csv(RAW_DIR / "spice_levels.csv", index=False)
orders_out.to_csv(RAW_DIR / "orders.csv", index=False)
order_items_df.to_csv(RAW_DIR / "order_items.csv", index=False)
customers_df.to_csv(RAW_DIR / "customers.csv", index=False)
events_out.to_csv(RAW_DIR / "events.csv", index=False)

print(f"orders.csv       {len(orders_out):>7,} rows (incl. ~110 duplicates)")
print(f"order_items.csv  {len(order_items_df):>7,} rows")
print(f"customers.csv    {len(customers_df):>7,} rows")
print(orders_df.groupby("channel").size().rename("orders by channel").to_string())
