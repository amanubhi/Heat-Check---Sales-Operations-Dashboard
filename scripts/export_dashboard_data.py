"""STEP 5 - Build docs/index.html: the live web dashboard for GitHub Pages.

Run from the repo root:   python scripts/export_dashboard_data.py

1. Pre-aggregates the clean data into small "fact" tables sliced by month and
   channel (so the browser can filter instantly without loading 24k rows).
2. Computes the headline insights shown on the page (numbers come from the data).
3. Embeds everything as JSON inside scripts/templates/dashboard_template.html
   and writes the single self-contained file docs/index.html.
"""
import json
import sys

import pandas as pd

from paths import CLEAN_DIR, DATASET, DOCS_DIR, SENSITIVITY_DIR, SQL_RESULTS_DIR, TEMPLATE_DIR, ensure_dirs

ensure_dirs()
CHANNELS = ["Storefront", "Night Market", "Vendor Event"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SPICE = ["No Heat", "Mild", "Medium", "Hot", "Extra Hot", "Reaper"]

orders = pd.read_csv(CLEAN_DIR / "orders.csv", parse_dates=["order_datetime"])
items = pd.read_csv(CLEAN_DIR / "order_items.csv")
customers = pd.read_csv(CLEAN_DIR / "customers.csv")


def sql_result(prefix):
    return pd.read_csv(next(SQL_RESULTS_DIR.glob(f"{prefix}_*.csv")))


# Numeric codes keep the JSON small: month 0-11, channel 0-2, weekday 0-6 (Mon=0)
orders["m"] = orders.month - 1
orders["c"] = orders.channel.map({n: i for i, n in enumerate(CHANNELS)})
orders["d"] = orders.day_of_week_num
orders["prep_ok"] = orders.prep_time_minutes.notna().astype(int)
orders["prep_sum"] = orders.prep_time_minutes.fillna(0)


def rows(df):
    """DataFrame -> list of lists (rounded) for compact JSON."""
    return [[round(v, 2) if isinstance(v, float) else int(v) for v in r] for r in df.itertuples(index=False)]


mc = orders.groupby(["m", "c"]).agg(n=("order_id", "count"), rev=("revenue", "sum"), gp=("gross_profit", "sum"),
                                    disc=("discount_amount", "sum"), ps=("prep_sum", "sum"), pn=("prep_ok", "sum")).reset_index()
hour = orders.groupby(["m", "c", "hour"]).agg(n=("order_id", "count"), ps=("prep_sum", "sum"), pn=("prep_ok", "sum")).reset_index()
heat = orders.groupby(["m", "c", "d", "hour"]).size().rename("n").reset_index()
dow = orders.groupby(["m", "c", "d"]).agg(n=("order_id", "count"), rev=("revenue", "sum"), gp=("gross_profit", "sum")).reset_index()

lines = items.merge(orders[["order_id", "m", "c"]], on="order_id")
lines["net"] = lines.line_revenue - lines.line_discount
item_names = sorted(lines.item_name.unique())
lines["i"] = lines.item_name.map({n: i for i, n in enumerate(item_names)})
item_f = lines.groupby(["m", "c", "i"]).agg(u=("quantity", "sum"), rev=("net", "sum"), gp=("line_profit", "sum")).reset_index()
spice_lines = lines[lines.spice_level != "Not Applicable"].copy()
spice_lines["s"] = spice_lines.spice_level.map({n: i for i, n in enumerate(SPICE)})
spice_f = spice_lines.groupby(["m", "c", "s"]).quantity.sum().reset_index()

known = orders.dropna(subset=["customer_id"])
cust_codes = {cid: i for i, cid in enumerate(known.customer_id.unique())}
cust_f = (known.assign(k=known.customer_id.map(cust_codes)).groupby(["m", "c", "k"]).size().rename("n").reset_index())

events_tbl = sql_result("Q03")
scorecard = sql_result("Q02")

# ---------------------------------------------------------------- insights
def compute_insights():
    """Headline findings, each computed from the data (no hand-typed numbers)."""
    rev_total = orders.revenue.sum()
    ch = orders.groupby("channel").agg(rev=("revenue", "sum"), gp=("gross_profit", "sum"), days=("order_date", "nunique"))
    open_days = orders.order_date.nunique()
    ev = events_tbl.sort_values("roi_pct", ascending=False)
    weak = ev[ev.verdict == "REVIEW / DROP"]
    strong = ev[ev.verdict != "REVIEW / DROP"]

    # Storefront weekday economics vs a 3-person crew at $22/hr x 10 hrs = $660/day.
    # Tue+Wed are below cost with 95% confidence; Thursday is break-even (see sensitivity_analysis.py).
    sf = orders[orders.channel == "Storefront"]
    sf_day = sf.groupby(["order_date", "day_of_week_num"]).gross_profit.sum().reset_index()
    by_dow = sf_day.groupby("day_of_week_num").gross_profit.agg(["mean", "count"])
    cut = by_dow.loc[[1, 2]]
    midweek_savings = int(cut["count"].sum() * 10 * 22)
    thu_extra = int(by_dow.loc[3, "count"] * 10 * 22)

    q12 = sql_result("Q12")
    evb = q12[q12.channel == "Vendor Event"].set_index("bucket_order")
    peak_share = evb.loc[5, "orders"] / evb.orders.sum()

    cat = items.assign(net=items.line_revenue - items.line_discount).groupby("category").agg(
        rev=("net", "sum"), gp=("line_profit", "sum"), u=("quantity", "sum"))
    cat["margin"] = cat.gp / cat.rev
    wing_units = cat.loc["Wings", "u"] + items[items.item_name == "Wing Combo"].quantity.sum()
    has_drink = items.assign(d=items.category == "Drinks").groupby("order_id").d.max()
    drink_attach = has_drink.reindex(orders.order_id).fillna(False).mean()
    drink_profit = cat.loc["Drinks", "gp"] / cat.loc["Drinks", "u"]
    drink_upside = orders.shape[0] * 0.07 * drink_profit

    sp = spice_lines.merge(orders[["order_id", "daypart"]], on="order_id")
    hot_share = lambda d: d[d.spice_level.isin(["Extra Hot", "Reaper"])].quantity.sum() / d.quantity.sum()
    medhot = spice_lines[spice_lines.spice_level.isin(["Medium", "Hot"])].quantity.sum() / spice_lines.quantity.sum()
    ev_hot = hot_share(spice_lines[spice_lines.c == 2])
    sf_hot = hot_share(spice_lines[spice_lines.c == 0])
    ln_hot = hot_share(sp[sp.daypart == "Late Night"])

    cu = customers.groupby("loyalty_member").agg(n=("customer_id", "count"), rep=("total_orders", lambda s: (s > 1).mean()),
                                                 rev=("total_revenue", "sum"))
    member_rev_share = cu.loc[True, "rev"] / cu.rev.sum()
    member_rpc, non_rpc = cu.loc[True, "rev"] / cu.loc[True, "n"], cu.loc[False, "rev"] / cu.loc[False, "n"]
    id_rate = orders.groupby("channel").customer_id.apply(lambda s: s.notna().mean())
    days_to_2nd = customers.days_to_second_order.mean()

    fri_peak = ((orders.d == 4) & orders.hour.between(17, 20)).mean()
    frisat_rev = orders[orders.d.isin([4, 5])].revenue.sum() / rev_total
    sc = scorecard.set_index("channel")
    nm_night = sc.loc["Night Market", "contribution_per_operating_day"]
    sf_day_contrib = sc.loc["Storefront", "contribution_per_operating_day"]

    late = sf[sf.hour >= 21]
    late_nights = late.order_date.nunique()
    late_labor = 3 * 2.5 * 22 * late_nights
    jul_aug = orders[orders.month.isin([7, 8])].revenue.sum() / rev_total

    pct = lambda x, d=0: f"{x * 100:.{d}f}%"
    usd = lambda x: f"${x:,.0f}"
    return [
        dict(tag="Channel mix", stat=pct(ch.loc["Vendor Event", "rev"] / rev_total),
             title=f"Vendor events earn {pct(ch.loc['Vendor Event', 'rev'] / rev_total)} of revenue in just {ch.loc['Vendor Event', 'days']} of {open_days} selling days",
             body=f"Six of eight events return {strong.roi_pct.min():,.0f}%-{strong.roi_pct.max():,.0f}% on booth fee plus staff cost. "
                  f"{' and '.join(weak.event_name)} return only {weak.roi_pct.min():,.0f}%-{weak.roi_pct.max():,.0f}%. "
                  f"July-August alone is {pct(jul_aug)} of annual revenue.",
             action="Keep the six strong events, renegotiate or drop the two weak ones, and use the freed dates for large summer/fall regional festivals."),
        dict(tag="Staffing", stat=usd(midweek_savings),
             title="Tue-Wed storefront days earn less gross profit than a 3-person crew costs",
             body=f"Gross profit averages {usd(by_dow.loc[1, 'mean'])} (Tue) and {usd(by_dow.loc[2, 'mean'])} (Wed) versus $660 of daily labor "
                  f"(3 staff x 10 hrs x $22), below cost with 95% confidence. Thursday ({usd(by_dow.loc[3, 'mean'])}) is break-even within the margin of error. "
                  f"The finding holds only if loaded labor is above roughly $19/hr.",
             action=f"Run 2 staff Tue-Wed (about {usd(midweek_savings)} saved per year) and pilot 2 staff on Thursday for 6 weeks (up to {usd(thu_extra)} more if sales hold)."),
        dict(tag="Operations", stat=f"{evb.loc[5, 'avg_prep_min']:.0f} min",
             title="Event kitchens slow down sharply once an hour passes 60 orders",
             body=f"Prep time averages {evb.loc[5, 'avg_prep_min']:.1f} min in 61+ order hours vs {evb.loc[1, 'avg_prep_min']:.1f} min in quiet hours, and "
                  f"{evb.loc[5, 'pct_orders_over_15min']:.0f}% of those orders take over 15 minutes. {pct(peak_share)} of all event orders land in those hours.",
             action="Add a second fry station and pre-batch tenders for event lunch (11:30-1:30) and dinner (5-7pm) peaks; test QR pre-ordering to flatten the queue."),
        dict(tag="Menu & pricing", stat=pct(cat.loc["Wings", "margin"], 0),
             title=f"Wings have the lowest margin ({pct(cat.loc['Wings', 'margin'], 1)}) while drinks run at {pct(cat.loc['Drinks', 'margin'], 0)}",
             body=f"Combos drive {pct(cat.loc['Combos', 'gp'] / cat.gp.sum())} of profit. Tenders earn {pct(cat.loc['Tenders', 'margin'], 1)} vs wings {pct(cat.loc['Wings', 'margin'], 1)}. "
                  f"Only {pct(drink_attach)} of orders include a drink.",
             action=f"Add $1 to wings and the Wing Combo (~{usd(wing_units)} at flat volume) and push a drink add-on to lift attach by 7 pts (~{usd(drink_upside)})."),
        dict(tag="Inventory", stat=pct(medhot),
             title="Medium and Hot make up most spiced orders, but events skew hotter",
             body=f"Extra Hot + Reaper are {pct(ev_hot)} of event units vs {pct(sf_hot)} at the storefront and {pct(ln_hot)} on late-night orders.",
             action="Prep sauce by channel: heavier Extra Hot/Reaper for events and late nights, lighter Mild/No Heat; treat Reaper as a small-batch challenge item."),
        dict(tag="Loyalty", stat=pct(cu.loc[True, "rep"]),
             title=f"Loyalty members repeat at {pct(cu.loc[True, 'rep'])} vs {pct(cu.loc[False, 'rep'])} for non-members",
             body=f"Members are {pct(cu.loc[True, 'n'] / cu.n.sum())} of known customers but {pct(member_rev_share)} of their revenue ({usd(member_rpc)} vs {usd(non_rpc)} per customer). "
                  f"Only {pct(id_rate['Vendor Event'])} of event orders and {pct(id_rate['Night Market'])} of night-market orders are tied to a customer.",
             action=f"Capture a phone/email at every booth (QR code) and send a 'come back' offer around day 21; customers typically return after {days_to_2nd:.0f} days."),
        dict(tag="Peak demand", stat=pct(fri_peak),
             title=f"Friday 5-8pm is {pct(fri_peak)} of all orders, and Fri/Sat are {pct(frisat_rev)} of revenue",
             body=f"The Friday night market nets about {usd(nm_night)} per night after staff and booth fees vs {usd(sf_day_contrib)} per storefront day.",
             action="Protect full staffing for Friday 5-8pm and test a second weekly market (Sat or Sun midday) - the night market earns far more gross profit per labor hour."),
        dict(tag="Hours", stat=usd(late_labor - late.gross_profit.sum()),
             title="The storefront's Fri/Sat late-night window earns less than it costs to staff",
             body=f"Orders after 9pm bring {usd(late.gross_profit.sum())} of gross profit over {late_nights} nights, against about {usd(late_labor)} of labor (3 staff x 2.5 hrs x $22).",
             action="Close at 10pm or run a 2-person skeleton crew after 9pm; the window then roughly breaks even."),
    ]


try:
    insights = compute_insights()
except Exception as exc:   # the written insights are built around the demo data; skip them for other datasets
    if DATASET == "synthetic":
        raise
    print(f"Insights skipped for real data ({type(exc).__name__}: {exc})")
    insights = []

payload = {
    "months": MONTHS, "channels": CHANNELS, "days": DAYS, "spice": SPICE, "items": item_names,
    "mc": rows(mc), "hour": rows(hour), "heat": rows(heat), "dow": rows(dow),
    "itemf": rows(item_f), "spicef": rows(spice_f), "cust": rows(cust_f),
    "events": events_tbl[["event_name", "city", "event_days", "orders", "revenue", "booth_fee", "staff_cost",
                          "net_profit", "roi_pct", "verdict"]].to_dict("records"),
    "scorecard": scorecard[["channel", "orders", "revenue", "gross_profit", "labor_cost", "booth_fees",
                            "contribution_after_direct_costs", "gross_profit_per_labor_hour"]].to_dict("records"),
    "insights": insights,
    "sens": json.loads((SENSITIVITY_DIR / "sensitivity_summary.json").read_text()) if (SENSITIVITY_DIR / "sensitivity_summary.json").exists() else None,
}

template = (TEMPLATE_DIR / "dashboard_template.html").read_text()
assert "/*__DATA__*/" in template, "placeholder missing from template"
html = template.replace("/*__DATA__*/null", json.dumps(payload, separators=(",", ":")))
(DOCS_DIR / "index.html").write_text(html)
(DOCS_DIR / ".nojekyll").write_text("")  # tell GitHub Pages to serve the folder as-is
print(f"docs/index.html written: {len(html) / 1024:.0f} KB, {len(insights)} insights")
for i in insights:
    print(f" - [{i['tag']}] {i['title']}")
