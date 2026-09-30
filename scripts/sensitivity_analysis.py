"""STEP 3c - How sure are we? Sensitivity analysis, confidence intervals and a 2026 scenario plan.

Run from the repo root:   python scripts/sensitivity_analysis.py

The main recommendations depend on assumptions (labor rate, event attendance) and on
noisy daily sales. This script stress-tests them and writes CSVs to outputs/sensitivity/
plus sensitivity_summary.json (used by the web dashboard).

  1. labor_rate_sensitivity.csv  - recommendations if labor is $16-$28/hr
  2. attendance_scenarios.csv    - event net profit if attendance is -30% ... +20%
  3. weekday_breakeven.csv       - storefront gross profit per day with 95% bootstrap CIs
  4. claim_tests.csv             - significance tests for the loyalty and kitchen claims
  5. scenario_2026.csv           - worst / typical / best outcome for each recommended change

The cost assumptions below MUST match the `assumptions` CTEs in sql/analysis.sql.
"""
import json
import math
import sys

import numpy as np
import pandas as pd

from paths import CLEAN_DIR, DATASET, SENSITIVITY_DIR, ensure_dirs

# --- assumptions (same as sql/analysis.sql) ---
WAGE = 22.0
SF_STAFF, SF_HOURS, SF_LATE_HOURS = 3, 10.0, 2.5
EVENT_HOURS = 10.0
N_BOOT = 5000
rng = np.random.default_rng(42)


def bootstrap_ci(values, stat=np.mean, n=N_BOOT):
    """95% percentile bootstrap confidence interval for a statistic."""
    values = np.asarray(values, dtype=float)
    draws = [stat(rng.choice(values, size=len(values), replace=True)) for _ in range(n)]
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def two_prop_ztest(x1, n1, x2, n2):
    """Two-proportion z-test. Returns (difference, 95% CI low, high, two-sided p-value)."""
    p1, p2 = x1 / n1, x2 / n2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    pooled = (x1 + x2) / (n1 + n2)
    se0 = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se0
    p = math.erfc(abs(z) / math.sqrt(2))
    return p1 - p2, p1 - p2 - 1.96 * se, p1 - p2 + 1.96 * se, p


def main():
    ensure_dirs()
    orders = pd.read_csv(CLEAN_DIR / "orders.csv", parse_dates=["order_datetime", "order_date"])
    items = pd.read_csv(CLEAN_DIR / "order_items.csv")
    customers = pd.read_csv(CLEAN_DIR / "customers.csv")
    events = pd.read_csv(CLEAN_DIR / "events.csv")

    # ---------------- building blocks ----------------
    sf = orders[orders.channel == "Storefront"]
    sf_days = sf.groupby(["order_date", "day_of_week_num", "day_of_week"]).gross_profit.sum().reset_index()
    # Tue+Wed are the days we recommend cutting; Thursday is a break-even "pilot" day (see weekday test below)
    cut_days = int(sf_days.day_of_week_num.isin([1, 2]).sum())
    cut_gp = float(sf_days[sf_days.day_of_week_num.isin([1, 2])].gross_profit.sum())
    thu_days = int((sf_days.day_of_week_num == 3).sum())
    tue_wed_mean = float(sf_days[sf_days.day_of_week_num.isin([1, 2])].gross_profit.mean())
    frisat_nights = int(sf_days.day_of_week_num.isin([4, 5]).sum())
    late = sf[sf.hour >= 21]
    late_gp, late_nights = float(late.gross_profit.sum()), int(late.order_date.nunique())

    ev_sales = orders[orders.channel == "Vendor Event"].groupby("event_name").agg(
        orders=("order_id", "count"), revenue=("revenue", "sum"), gp=("gross_profit", "sum")).reset_index()
    ev = events.merge(ev_sales, on="event_name")
    ev["staff_cost"] = ev.staff_count * ev.event_days * EVENT_HOURS * WAGE
    ev["net"] = ev.gp - ev.booth_fee - ev.staff_cost
    ev["roi"] = ev.net / (ev.booth_fee + ev.staff_cost)

    def verdict(roi):
        return "KEEP - priority" if roi >= 3 else "KEEP" if roi >= 1 else "REVIEW / DROP"

    # ---------------- 1. labor-rate sensitivity ----------------
    rows = []
    for w in [16, 18, 20, 22, 24, 26, 28]:
        staff_cost = ev.staff_count * ev.event_days * EVENT_HOURS * w
        roi = (ev.gp - ev.booth_fee - staff_cost) / (ev.booth_fee + staff_cost)
        sf_labor = SF_STAFF * (SF_HOURS * sf_days.shape[0] + SF_LATE_HOURS * frisat_nights) * w
        rows.append(dict(
            hourly_wage=w,
            tue_wed_savings_one_fewer_staff=round(cut_days * SF_HOURS * w),
            thursday_extra_savings_if_pilot_works=round(thu_days * SF_HOURS * w),
            tue_wed_below_crew_cost=bool(tue_wed_mean < SF_STAFF * SF_HOURS * w),
            late_night_shortfall=round(SF_STAFF * SF_LATE_HOURS * w * late_nights - late_gp),
            storefront_contribution=round(float(sf.gross_profit.sum()) - sf_labor),
            events_needing_review=int((roi.map(verdict) == "REVIEW / DROP").sum()),
            lowest_event_roi_pct=round(float(roi.min()) * 100),
            highest_event_roi_pct=round(float(roi.max()) * 100)))
    labor = pd.DataFrame(rows)
    labor.to_csv(SENSITIVITY_DIR / "labor_rate_sensitivity.csv", index=False)

    # ---------------- 2. attendance scenarios ----------------
    rows = []
    for f in [-0.30, -0.20, -0.10, 0.0, 0.10, 0.20]:
        for _, e in ev.iterrows():
            net = e.gp * (1 + f) - e.booth_fee - e.staff_cost   # food cost scales with sales; staff and fee are fixed
            roi = net / (e.booth_fee + e.staff_cost)
            rows.append(dict(attendance_change_pct=int(f * 100), event_name=e.event_name, net_profit=round(net),
                             roi_pct=round(roi * 100), verdict=verdict(roi)))
    att = pd.DataFrame(rows)
    att.to_csv(SENSITIVITY_DIR / "attendance_scenarios.csv", index=False)
    att_summary = att.groupby("attendance_change_pct").agg(
        events_losing_money=("net_profit", lambda s: int((s < 0).sum())),
        events_needing_review=("verdict", lambda s: int((s == "REVIEW / DROP").sum()))).reset_index()

    # ---------------- 3. weekday break-even with bootstrap CIs ----------------
    daily_cost = SF_STAFF * SF_HOURS * WAGE
    rows = []
    for num, name in [(1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")]:
        g = sf_days[sf_days.day_of_week_num == num].gross_profit.values
        lo, hi = bootstrap_ci(g)
        cost = daily_cost + (SF_STAFF * SF_LATE_HOURS * WAGE if num in (4, 5) else 0)
        hours = SF_STAFF * (SF_HOURS + (SF_LATE_HOURS if num in (4, 5) else 0))
        rows.append(dict(day=name, days_operated=len(g), avg_gross_profit_per_day=round(g.mean()),
                         ci95_low=round(lo), ci95_high=round(hi), crew_cost_per_day=round(cost),
                         breakeven_hourly_wage=round(g.mean() / hours, 2),
                         pct_days_below_crew_cost=round(100 * float((g < cost).mean()), 1),
                         mean_below_cost_with_95pct_confidence=bool(hi < cost)))
    wk = pd.DataFrame(rows)
    wk.to_csv(SENSITIVITY_DIR / "weekday_breakeven.csv", index=False)

    # ---------------- 4. significance tests on key claims ----------------
    tests = []
    known = customers.dropna(subset=["loyalty_member"])
    m, n = known[known.loyalty_member == True], known[known.loyalty_member == False]  # noqa: E712
    d, lo, hi, p = two_prop_ztest((m.total_orders > 1).sum(), len(m), (n.total_orders > 1).sum(), len(n))
    tests.append(dict(claim="Loyalty members repeat more often than non-members",
                      measure="repeat-rate difference (percentage points)", estimate=round(d * 100, 1),
                      ci95_low=round(lo * 100, 1), ci95_high=round(hi * 100, 1), p_value=float(f"{p:.2g}"),
                      conclusion="Significant at 95%" if p < 0.05 else "Not significant"))

    hourly = orders.assign(n=orders.groupby(["order_date", "channel", "hour"]).order_id.transform("count"))
    ev_o = hourly[(hourly.channel == "Vendor Event") & hourly.prep_time_minutes.notna()]
    busy, quiet = ev_o[ev_o.n > 60].prep_time_minutes.values, ev_o[ev_o.n <= 10].prep_time_minutes.values
    diffs = [rng.choice(busy, len(busy)).mean() - rng.choice(quiet, len(quiet)).mean() for _ in range(2000)]
    tests.append(dict(claim="Event kitchens are slower in 61+ order hours",
                      measure="difference in mean prep minutes", estimate=round(busy.mean() - quiet.mean(), 1),
                      ci95_low=round(float(np.percentile(diffs, 2.5)), 1), ci95_high=round(float(np.percentile(diffs, 97.5)), 1),
                      p_value=None, conclusion="Significant at 95% (CI excludes 0)" if np.percentile(diffs, 2.5) > 0 else "Not significant"))

    for label, nums in [("Tue-Wed", [1, 2]), ("Thursday", [3])]:
        g = sf_days[sf_days.day_of_week_num.isin(nums)].gross_profit.values
        lo, hi = bootstrap_ci(g)
        tests.append(dict(claim=f"{label} storefront gross profit per day is below a 3-person crew cost",
                          measure=f"mean gross profit per day vs ${daily_cost:,.0f} crew cost", estimate=round(g.mean()),
                          ci95_low=round(lo), ci95_high=round(hi), p_value=None,
                          conclusion="Below cost with 95% confidence" if hi < daily_cost else "Not proven: break-even within the margin of error"))
    claims = pd.DataFrame(tests)
    claims.to_csv(SENSITIVITY_DIR / "claim_tests.csv", index=False)

    # ---------------- 5. 2026 scenario plan ----------------
    strong = ev[ev.roi >= 3].sort_values("net", ascending=False)
    weak = ev[ev.roi < 3]
    weak_net = float(weak.net.sum())
    repl = {"worst": 0.0, "typical": float(strong.net.median()), "best": float(strong.net.head(3).median())}
    lever_events = {k: 2 * v - weak_net if len(weak) else 0 for k, v in repl.items()}
    lever_events["worst"] = -weak_net   # replacements earn nothing (and the weak events' small profit is lost)

    full = cut_days * SF_HOURS * WAGE
    lever_staff = {"worst": full - 0.10 * cut_gp, "typical": full - 0.03 * cut_gp, "best": full}

    drink = items[items.category == "Drinks"]
    drink_profit = float(drink.line_profit.sum() / drink.quantity.sum())
    drink_uplift = {"worst": 0.0, "typical": len(orders) * 0.04 * drink_profit, "best": len(orders) * 0.07 * drink_profit}

    wing = items[(items.category == "Wings") | (items.item_name == "Wing Combo")]
    w_units, w_unit_profit = float(wing.quantity.sum()), float(wing.line_profit.sum() / wing.quantity.sum())
    def wing_gain(volume_loss):   # +$1 price, some units lost at the old unit profit
        return w_units * (1 - volume_loss) * (w_unit_profit + 1) - w_units * w_unit_profit
    lever_wings = {"worst": wing_gain(0.15), "typical": wing_gain(0.05), "best": wing_gain(0.0)}

    full_late = SF_STAFF * SF_LATE_HOURS * WAGE * late_nights - 2 * SF_LATE_HOURS * WAGE * late_nights
    lever_late = {"worst": full_late - 0.10 * late_gp, "typical": full_late - 0.03 * late_gp, "best": full_late}

    levers = [("Replace the 2 weakest events", lever_events), ("2 staff Tue-Wed (not 3)", lever_staff),
              ("Drink add-on program", drink_uplift), ("+$1 on wings and Wing Combo", lever_wings),
              ("Late-night skeleton crew", lever_late)]
    baseline = float(orders.gross_profit.sum()) - (
        SF_STAFF * (SF_HOURS * sf_days.shape[0] + SF_LATE_HOURS * frisat_nights) * WAGE
        + float((ev.staff_cost + ev.booth_fee).sum())
        + 3 * 6 * WAGE * orders[orders.channel == "Night Market"].order_date.nunique()
        + 85 * orders[orders.channel == "Night Market"].order_date.nunique())
    rows = [dict(lever=name, worst_case=round(v["worst"]), typical_case=round(v["typical"]), best_case=round(v["best"]))
            for name, v in levers]
    total = {c: round(sum(v[k] for _, v in levers)) for c, k in [("worst_case", "worst"), ("typical_case", "typical"), ("best_case", "best")]}
    rows.append(dict(lever="TOTAL annual improvement", **total))
    rows.append(dict(lever="Improvement as % of 2025 contribution", **{c: round(100 * t / baseline, 1) for c, t in total.items()}))
    scen = pd.DataFrame(rows)
    scen.to_csv(SENSITIVITY_DIR / "scenario_2026.csv", index=False)

    def records(df):   # NaN is not valid JSON; use null instead
        return df.astype(object).where(df.notna(), None).to_dict("records")

    summary = dict(wage=WAGE, baseline_contribution=round(baseline), cut_days=cut_days, cut_gp=round(cut_gp),
                   thu_days=thu_days, tue_wed_mean_gp=round(tue_wed_mean),
                   thu_mean_gp=round(float(sf_days[sf_days.day_of_week_num == 3].gross_profit.mean())),
                   sf_gp=round(float(sf.gross_profit.sum())),
                   sf_labor_hours=SF_STAFF * (SF_HOURS * sf_days.shape[0] + SF_LATE_HOURS * frisat_nights),
                   late_nights=late_nights, late_gp=round(late_gp),
                   labor=records(labor), attendance=records(att_summary), weekday=records(wk),
                   tests=records(claims), scenarios=records(scen),
                   events=[dict(event_name=e.event_name, gp=round(e.gp), booth_fee=int(e.booth_fee), staff_count=int(e.staff_count),
                                event_days=int(e.event_days)) for e in ev.itertuples()])
    (SENSITIVITY_DIR / "sensitivity_summary.json").write_text(json.dumps(summary, separators=(",", ":")))
    for name, df in [("Labor-rate sensitivity", labor), ("Attendance scenarios (summary)", att_summary),
                     ("Weekday break-even", wk), ("Claim tests", claims), ("2026 scenarios", scen)]:
        print(f"\n== {name}\n{df.to_string(index=False)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:   # the demo data must always work; real data may lack the demo's structure
        if DATASET == "synthetic":
            raise
        print(f"Sensitivity analysis skipped for real data ({type(exc).__name__}: {exc})")
        sys.exit(0)
