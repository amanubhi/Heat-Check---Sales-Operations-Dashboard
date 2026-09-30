"""STEP 4 - Build excel/HeatCheck_Dashboard.xlsx with xlsxwriter.

Run from the repo root:   python scripts/build_excel.py

Sheets: Dashboard, Analysis, Orders, Order_Items, Menu, Customers, Events.
The Analysis sheet uses real Excel formulas (SUMIFS / COUNTIFS) on the data
sheets, so the numbers stay live if you edit the data. The Dashboard charts
read from the Analysis sheet. We also pass each formula's pre-computed value
so the file displays correctly in viewers that do not recalculate.
"""
import numpy as np
import pandas as pd
import xlsxwriter
from xlsxwriter.utility import xl_col_to_name, xl_rowcol_to_cell

from paths import CLEAN_DIR, EXCEL_PATH, SQL_RESULTS_DIR, ensure_dirs

# Brand palette
CHARCOAL, RED, ORANGE, CREAM = "#1F1F1F", "#D7263D", "#F46036", "#FFF8E7"
HEAT_RAMP = ["#F7C59F", "#F9A26C", "#F46036", "#E4492F", "#D7263D", "#8E1B2B"]  # No Heat -> Reaper
CHANNEL_COLORS = [RED, ORANGE, CHARCOAL]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SPICE_ORDER = ["No Heat", "Mild", "Medium", "Hot", "Extra Hot", "Reaper"]
CHANNELS = ["Storefront", "Night Market", "Vendor Event"]

ensure_dirs()
orders = pd.read_csv(CLEAN_DIR / "orders.csv", parse_dates=["order_datetime", "order_date"])
items = pd.read_csv(CLEAN_DIR / "order_items.csv")
menu = pd.read_csv(CLEAN_DIR / "menu.csv")
customers = pd.read_csv(CLEAN_DIR / "customers.csv", parse_dates=["first_order_date"], dtype={"zip_code": str})
events = pd.read_csv(CLEAN_DIR / "events.csv", parse_dates=["start_date", "end_date"])

wb = xlsxwriter.Workbook(EXCEL_PATH, {"nan_inf_to_errors": True})
wb.set_properties({"title": "Heat Check - Sales & Operations Dashboard", "subject": "Synthetic data portfolio project",
                   "comments": "All data is synthetic."})

# Sheets are created in display order; Dashboard first.
ws_dash = wb.add_worksheet("Dashboard")
ws_an = wb.add_worksheet("Analysis")
data_sheets = {name: wb.add_worksheet(name) for name in ["Orders", "Order_Items", "Menu", "Customers", "Events"]}

# ---------------------------------------------------------------- formats
def fmt(**kw):
    base = {"font_name": "Calibri", "font_size": 11}
    base.update(kw)
    return wb.add_format(base)

F = {
    "title": fmt(bold=True, font_size=22, font_color=CREAM, bg_color=CHARCOAL, valign="vcenter"),
    "subtitle": fmt(italic=True, font_color="#C9C2B0", bg_color=CHARCOAL),
    "bg": fmt(bg_color=CHARCOAL),
    "section": fmt(bold=True, font_size=13, font_color=CREAM, bg_color=RED),
    "hdr": fmt(bold=True, font_color=CREAM, bg_color=CHARCOAL, border=1, border_color="#555555", align="center"),
    "cell": fmt(bg_color=CREAM, border=1, border_color="#E2D9BF"),
    "int": fmt(bg_color=CREAM, border=1, border_color="#E2D9BF", num_format="#,##0"),
    "usd": fmt(bg_color=CREAM, border=1, border_color="#E2D9BF", num_format="$#,##0"),
    "usd2": fmt(bg_color=CREAM, border=1, border_color="#E2D9BF", num_format="$#,##0.00"),
    "pct": fmt(bg_color=CREAM, border=1, border_color="#E2D9BF", num_format="0.0%"),
    "note": fmt(italic=True, font_color="#666666"),
    "kpi_label": fmt(bold=True, font_size=10, font_color=CREAM, bg_color=RED, align="center", valign="vcenter"),
    "kpi_usd": fmt(bold=True, font_size=26, font_color=CHARCOAL, bg_color=CREAM, align="center", valign="vcenter", num_format="$#,##0"),
    "kpi_usd2": fmt(bold=True, font_size=26, font_color=CHARCOAL, bg_color=CREAM, align="center", valign="vcenter", num_format="$#,##0.00"),
    "kpi_int": fmt(bold=True, font_size=26, font_color=CHARCOAL, bg_color=CREAM, align="center", valign="vcenter", num_format="#,##0"),
    "kpi_pct": fmt(bold=True, font_size=26, font_color=CHARCOAL, bg_color=CREAM, align="center", valign="vcenter", num_format="0.0%"),
    "heat_lbl": fmt(bold=True, font_color=CREAM, bg_color=CHARCOAL, align="center"),
    "heat": fmt(bg_color=CREAM, align="center", num_format="#,##0", font_color=CHARCOAL),
    "date": wb.add_format({"num_format": "yyyy-mm-dd"}),
    "datetime": wb.add_format({"num_format": "yyyy-mm-dd hh:mm"}),
    "hdr_table": wb.add_format({"bold": True, "font_color": CREAM, "bg_color": CHARCOAL}),
}


def write_data_sheet(ws, df, table_name):
    """Write a dataframe as an Excel Table (good for pivots) with date formats and sensible widths."""
    cols = []
    for c in df.columns:
        spec = {"header": c, "header_format": F["hdr_table"]}
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            spec["format"] = F["datetime"] if c == "order_datetime" else F["date"]
        cols.append(spec)
    data = df.astype(object).where(df.notna(), None).values.tolist()
    ws.add_table(0, 0, len(df), len(df.columns) - 1,
                 {"data": data, "columns": cols, "name": table_name, "style": "Table Style Light 1"})
    for i, c in enumerate(df.columns):
        ws.set_column(i, i, max(12, min(len(c) + 4, 30)))
    ws.freeze_panes(1, 0)
    ws.set_tab_color(CHARCOAL)


tables = {"Orders": orders, "Order_Items": items, "Menu": menu, "Customers": customers, "Events": events}
for name, df in tables.items():
    write_data_sheet(data_sheets[name], df, f"Tbl_{name}")


def rng(sheet, col):
    """Absolute range for one data column, e.g. Orders!$O$2:$O$24252."""
    df = tables[sheet]
    letter = xl_col_to_name(list(df.columns).index(col))
    return f"{sheet}!${letter}$2:${letter}${len(df) + 1}"


# ------------------------------------------------------------ Analysis sheet
ws_an.hide_gridlines(2)
ws_an.set_tab_color(ORANGE)
ws_an.set_column("A:A", 2)
ws_an.set_column("B:B", 30)
ws_an.set_column("C:P", 14)
ws_an.write("B1", "Analysis - summary tables (live formulas on the data sheets)", fmt(bold=True, font_size=18, font_color=CHARCOAL))
ws_an.write("B2", "The Dashboard charts read from these tables. Revenue = line sales - discounts (tips excluded). "
                  "Gross profit = revenue - food cost.", F["note"])

row = 3          # running row pointer (0-based)
REF = {}         # remember where each table lives so charts/KPIs can point at it


def section(title, width=8):
    global row
    ws_an.merge_range(row, 1, row, width, title, F["section"])
    row += 1


def header(labels):
    global row
    for j, lab in enumerate(labels):
        ws_an.write(row, 1 + j, lab, F["hdr"])
    row += 1


def put(r, c, value, f):
    """Write a plain value, or a (formula, cached_value) tuple as a formula."""
    if isinstance(value, tuple):
        ws_an.write_formula(r, c, value[0], f, value[1])
    else:
        ws_an.write(r, c, value, f)


rev_all, gp_all, n_orders = orders.revenue.sum(), orders.gross_profit.sum(), len(orders)
repeat_rate = (customers.total_orders > 1).mean()

# 1. KPIs ---------------------------------------------------------------
section("1. Headline KPIs")
header(["KPI", "Value"])
kpis = [
    ("Total Revenue", f"=SUM({rng('Orders', 'revenue')})", rev_all, "usd"),
    ("Gross Profit", f"=SUM({rng('Orders', 'gross_profit')})", gp_all, "usd"),
    ("Gross Margin %", "=C{gp}/C{rev}", gp_all / rev_all, "pct"),
    ("Total Orders", f"=COUNTA({rng('Orders', 'order_id')})", n_orders, "int"),
    ("Average Order Value", "=C{rev}/C{orders}", rev_all / n_orders, "usd2"),
    ("Repeat Customer Rate", f'=COUNTIF({rng("Customers", "total_orders")},">1")/COUNTA({rng("Customers", "customer_id")})',
     repeat_rate, "pct"),
]
first = row + 1  # Excel 1-based row of first KPI
cells = {"rev": first, "gp": first + 1, "orders": first + 3}
for i, (label, formula, val, f) in enumerate(kpis):
    ws_an.write(row, 1, label, F["cell"])
    put(row, 2, (formula.format(**cells), val), F[f])
    REF[label] = f"Analysis!$C${row + 1}"
    row += 1
row += 1

# 2. Monthly -----------------------------------------------------------
section("2. Revenue by month")
header(["Month", "Orders", "Revenue", "Gross Profit", "Margin %", "Avg Order Value"])
m = orders.groupby("month").agg(o=("order_id", "count"), r=("revenue", "sum"), g=("gross_profit", "sum"))
REF["month_first"] = row
for i, mon in enumerate(MONTHS, 1):
    r1 = row + 1
    ws_an.write(row, 1, mon, F["cell"])
    put(row, 2, (f"=COUNTIFS({rng('Orders', 'month')},{i})", m.o[i]), F["int"])
    put(row, 3, (f"=SUMIFS({rng('Orders', 'revenue')},{rng('Orders', 'month')},{i})", m.r[i]), F["usd"])
    put(row, 4, (f"=SUMIFS({rng('Orders', 'gross_profit')},{rng('Orders', 'month')},{i})", m.g[i]), F["usd"])
    put(row, 5, (f"=E{r1}/D{r1}", m.g[i] / m.r[i]), F["pct"])
    put(row, 6, (f"=D{r1}/C{r1}", m.r[i] / m.o[i]), F["usd2"])
    row += 1
REF["month_last"] = row - 1
row += 1

# 3. Channel -----------------------------------------------------------
section("3. Performance by channel")
header(["Channel", "Orders", "Revenue", "Gross Profit", "Margin %", "Avg Order Value", "Share of Revenue"])
ch = orders.groupby("channel").agg(o=("order_id", "count"), r=("revenue", "sum"), g=("gross_profit", "sum"))
REF["channel_first"] = row
for c in CHANNELS:
    r1 = row + 1
    ws_an.write(row, 1, c, F["cell"])
    put(row, 2, (f"=COUNTIFS({rng('Orders', 'channel')},$B{r1})", ch.o[c]), F["int"])
    put(row, 3, (f"=SUMIFS({rng('Orders', 'revenue')},{rng('Orders', 'channel')},$B{r1})", ch.r[c]), F["usd"])
    put(row, 4, (f"=SUMIFS({rng('Orders', 'gross_profit')},{rng('Orders', 'channel')},$B{r1})", ch.g[c]), F["usd"])
    put(row, 5, (f"=E{r1}/D{r1}", ch.g[c] / ch.r[c]), F["pct"])
    put(row, 6, (f"=D{r1}/C{r1}", ch.r[c] / ch.o[c]), F["usd2"])
    put(row, 7, (f"=D{r1}/{REF['Total Revenue']}", ch.r[c] / rev_all), F["pct"])
    row += 1
REF["channel_last"] = row - 1
row += 1

# 4. Top 10 items by profit ---------------------------------------------
section("4. Top 10 items by gross profit")
header(["Item", "Units Sold", "Revenue", "Gross Profit", "Margin %"])
it = items.assign(net=items.line_revenue - items.line_discount).groupby("item_name").agg(
    u=("quantity", "sum"), r=("net", "sum"), g=("line_profit", "sum")).sort_values("g", ascending=False).head(10)
REF["item_first"] = row
for name, rec in it.iterrows():
    r1 = row + 1
    ws_an.write(row, 1, name, F["cell"])
    put(row, 2, (f"=SUMIFS({rng('Order_Items', 'quantity')},{rng('Order_Items', 'item_name')},$B{r1})", rec.u), F["int"])
    put(row, 3, (f"=SUMIFS({rng('Order_Items', 'line_revenue')},{rng('Order_Items', 'item_name')},$B{r1})"
                 f"-SUMIFS({rng('Order_Items', 'line_discount')},{rng('Order_Items', 'item_name')},$B{r1})", rec.r), F["usd"])
    put(row, 4, (f"=SUMIFS({rng('Order_Items', 'line_profit')},{rng('Order_Items', 'item_name')},$B{r1})", rec.g), F["usd"])
    put(row, 5, (f"=E{r1}/D{r1}", rec.g / rec.r), F["pct"])
    row += 1
REF["item_last"] = row - 1
row += 1

# 5. Spice mix ------------------------------------------------------------
section("5. Spice level mix (units of spiced items)")
header(["Spice Level", "Units", "Share"])
sp = items[items.spice_level != "Not Applicable"].groupby("spice_level").quantity.sum()
REF["spice_first"] = row
for lvl in SPICE_ORDER:
    r1 = row + 1
    ws_an.write(row, 1, lvl, F["cell"])
    put(row, 2, (f"=SUMIFS({rng('Order_Items', 'quantity')},{rng('Order_Items', 'spice_level')},$B{r1})", sp[lvl]), F["int"])
    put(row, 3, (f"=C{r1}/SUM($C${REF['spice_first'] + 1}:$C${REF['spice_first'] + 6})", sp[lvl] / sp.sum()), F["pct"])
    row += 1
REF["spice_last"] = row - 1
row += 1

# 6. Orders by hour ---------------------------------------------------------
section("6. Orders by hour of day")
header(["Hour", "Orders", "Revenue"])
hr = orders.groupby("hour").agg(o=("order_id", "count"), r=("revenue", "sum"))
hours = sorted(hr.index)
REF["hour_first"] = row
for h in hours:
    ws_an.write(row, 1, f"{h}:00", F["cell"])
    put(row, 2, (f"=COUNTIFS({rng('Orders', 'hour')},{h})", hr.o[h]), F["int"])
    put(row, 3, (f"=SUMIFS({rng('Orders', 'revenue')},{rng('Orders', 'hour')},{h})", hr.r[h]), F["usd"])
    row += 1
REF["hour_last"] = row - 1
row += 1

# 7. Day of week -------------------------------------------------------------
section("7. Day-of-week performance")
header(["Day", "Orders", "Revenue", "Gross Profit", "Avg Revenue per Order"])
dw = orders.groupby("day_of_week").agg(o=("order_id", "count"), r=("revenue", "sum"), g=("gross_profit", "sum")).reindex(DAYS, fill_value=0)  # closed Mondays -> 0
REF["dow_first"] = row
for d in DAYS:
    r1 = row + 1
    ws_an.write(row, 1, d, F["cell"])
    put(row, 2, (f"=COUNTIFS({rng('Orders', 'day_of_week')},$B{r1})", dw.o[d]), F["int"])
    put(row, 3, (f"=SUMIFS({rng('Orders', 'revenue')},{rng('Orders', 'day_of_week')},$B{r1})", dw.r[d]), F["usd"])
    put(row, 4, (f"=SUMIFS({rng('Orders', 'gross_profit')},{rng('Orders', 'day_of_week')},$B{r1})", dw.g[d]), F["usd"])
    put(row, 5, (f"=IFERROR(D{r1}/C{r1},0)", dw.r[d] / dw.o[d] if dw.o[d] else 0), F["usd2"])
    row += 1
REF["dow_last"] = row - 1
row += 1

# 8. Heatmap grid -------------------------------------------------------------
section("8. Orders heatmap: day of week x hour", width=1 + len(hours))
ws_an.write(row, 1, "Day \\ Hour", F["hdr"])
for j, h in enumerate(hours):
    ws_an.write(row, 2 + j, h, F["hdr"])
row += 1
cross = pd.crosstab(orders.day_of_week, orders.hour).reindex(index=DAYS, columns=hours, fill_value=0)
REF["heat_first"] = row
for i, d in enumerate(DAYS):
    ws_an.write(row, 1, d, F["cell"])
    for j, h in enumerate(hours):
        hdr_cell = xl_rowcol_to_cell(REF["heat_first"] - 1, 2 + j, row_abs=True)
        put(row, 2 + j, (f"=COUNTIFS({rng('Orders', 'day_of_week')},$B{row + 1},{rng('Orders', 'hour')},{hdr_cell})",
                         int(cross.loc[d, h])), F["heat"])
    row += 1
ws_an.conditional_format(REF["heat_first"], 2, row - 1, 1 + len(hours),
                         {"type": "2_color_scale", "min_color": CREAM, "max_color": RED})
row += 1

# 9. Static tables from the SQL analysis -------------------------------------------
section("9. Channel scorecard after direct costs (from SQL Q02 - includes labor assumptions)", width=9)
q2 = pd.read_csv(next(SQL_RESULTS_DIR.glob("Q02_*.csv")))
cols2 = ["channel", "orders", "revenue", "gross_profit", "labor_cost", "booth_fees", "contribution_after_direct_costs",
         "gross_profit_per_labor_hour"]
header(["Channel", "Orders", "Revenue", "Gross Profit", "Labor Cost", "Booth Fees", "Contribution", "GP / Labor Hr"])
for rec in q2[cols2].itertuples(index=False):
    for j, v in enumerate(rec):
        ws_an.write(row, 1 + j, v, F["cell"] if j == 0 else (F["int"] if j == 1 else F["usd"] if j < 7 else F["usd2"]))
    row += 1
row += 1

section("10. Vendor event ROI (from SQL Q03 - after booth fee and staff cost)", width=9)
q3 = pd.read_csv(next(SQL_RESULTS_DIR.glob("Q03_*.csv")))
header(["Event", "Days", "Orders", "Revenue", "Booth Fee", "Staff Cost", "Net Profit", "ROI %"])
for rec in q3.itertuples(index=False):
    vals = [rec.event_name, rec.event_days, rec.orders, rec.revenue, rec.booth_fee, rec.staff_cost, rec.net_profit, rec.roi_pct / 100]
    fm = [F["cell"], F["int"], F["int"], F["usd"], F["usd"], F["usd"], F["usd"], fmt(bg_color=CREAM, border=1, border_color="#E2D9BF", num_format="0%")]
    for j, (v, f) in enumerate(zip(vals, fm)):
        ws_an.write(row, 1 + j, v, f)
    row += 1

# ------------------------------------------------------------- Dashboard sheet
ws_dash.hide_gridlines(2)
ws_dash.set_tab_color(RED)
ws_dash.set_column("A:AD", 10, F["bg"])   # charcoal background everywhere
ws_dash.set_column("A:A", 2, F["bg"])
ws_dash.set_row(0, 42)
ws_dash.merge_range("B1:S1", "HEAT CHECK  |  Hot Chicken Sales & Operations Dashboard - 2025", F["title"])
ws_dash.merge_range("B2:S2", "Storefront + Friday Night Market + Vendor Events  |  Synthetic data modeled on real small-business operations",
                    F["subtitle"])

kpi_cards = [("TOTAL REVENUE", "Total Revenue", "kpi_usd"), ("GROSS PROFIT", "Gross Profit", "kpi_usd"),
             ("GROSS MARGIN", "Gross Margin %", "kpi_pct"), ("TOTAL ORDERS", "Total Orders", "kpi_int"),
             ("AVG ORDER VALUE", "Average Order Value", "kpi_usd2"), ("REPEAT CUSTOMER RATE", "Repeat Customer Rate", "kpi_pct")]
cached = {"Total Revenue": rev_all, "Gross Profit": gp_all, "Gross Margin %": gp_all / rev_all, "Total Orders": n_orders,
          "Average Order Value": rev_all / n_orders, "Repeat Customer Rate": repeat_rate}
ws_dash.set_row(3, 6, F["bg"])
ws_dash.set_row(4, 22)
ws_dash.set_row(5, 30)
ws_dash.set_row(6, 30)
for i, (label, key, f) in enumerate(kpi_cards):
    c0 = 1 + 3 * i
    ws_dash.merge_range(4, c0, 4, c0 + 2, label, F["kpi_label"])
    ws_dash.merge_range(5, c0, 6, c0 + 2, "", F[f])
    ws_dash.write_formula(5, c0, f"={REF[key]}", F[f], cached[key])
ws_dash.set_row(7, 12, F["bg"])


def chart_base(chart, title):
    chart.set_title({"name": title, "name_font": {"size": 13, "bold": True, "color": CHARCOAL}})
    chart.set_chartarea({"fill": {"color": CREAM}, "border": {"none": True}})
    chart.set_plotarea({"fill": {"none": True}})


def sheet_range(first_key, last_key, col):
    """Analysis range for a chart series: [sheet, r1, c1, r2, c2] (0-based)."""
    return ["Analysis", REF[first_key], col, REF[last_key], col]


# Line: revenue & profit by month
ch1 = wb.add_chart({"type": "line"})
chart_base(ch1, "Revenue & Gross Profit by Month")
ch1.add_series({"name": "Revenue", "categories": sheet_range("month_first", "month_last", 1),
                "values": sheet_range("month_first", "month_last", 3), "line": {"color": RED, "width": 3},
                "marker": {"type": "circle", "size": 7, "fill": {"color": RED}, "border": {"color": RED}}})
ch1.add_series({"name": "Gross Profit", "categories": sheet_range("month_first", "month_last", 1),
                "values": sheet_range("month_first", "month_last", 4), "line": {"color": ORANGE, "width": 3},
                "marker": {"type": "diamond", "size": 7, "fill": {"color": ORANGE}, "border": {"color": ORANGE}}})
ch1.set_y_axis({"num_format": "$#,##0", "major_gridlines": {"visible": True, "line": {"color": "#E2D9BF"}}})
ch1.set_legend({"position": "bottom"})
ch1.set_size({"width": 900, "height": 340})
ws_dash.insert_chart("B9", ch1)

# Donut: revenue by channel
ch2 = wb.add_chart({"type": "doughnut"})
chart_base(ch2, "Revenue by Channel")
ch2.add_series({"categories": sheet_range("channel_first", "channel_last", 1),
                "values": sheet_range("channel_first", "channel_last", 3),
                "points": [{"fill": {"color": c}} for c in CHANNEL_COLORS],
                "data_labels": {"percentage": True, "font": {"color": CREAM, "bold": True, "size": 11}}})
ch2.set_hole_size(55)
ch2.set_legend({"position": "bottom"})
ch2.set_size({"width": 450, "height": 340})
ws_dash.insert_chart("N9", ch2)

# Bar: top 10 items by profit
ch3 = wb.add_chart({"type": "bar"})
chart_base(ch3, "Top 10 Items by Gross Profit")
ch3.add_series({"categories": sheet_range("item_first", "item_last", 1), "values": sheet_range("item_first", "item_last", 4),
                "fill": {"color": RED}, "gap": 40,
                "data_labels": {"value": True, "num_format": "$#,##0", "font": {"size": 9}}})
ch3.set_y_axis({"reverse": True})
ch3.set_x_axis({"num_format": "$#,##0", "major_gridlines": {"visible": True, "line": {"color": "#E2D9BF"}}})
ch3.set_legend({"none": True})
ch3.set_size({"width": 675, "height": 380})
ws_dash.insert_chart("B27", ch3)

# Column: spice mix
ch4 = wb.add_chart({"type": "column"})
chart_base(ch4, "Spice Level Mix (share of spiced items)")
ch4.add_series({"categories": sheet_range("spice_first", "spice_last", 1), "values": sheet_range("spice_first", "spice_last", 3),
                "points": [{"fill": {"color": c}} for c in HEAT_RAMP], "gap": 40,
                "data_labels": {"value": True, "num_format": "0%", "font": {"size": 10}}})
ch4.set_y_axis({"num_format": "0%", "major_gridlines": {"visible": True, "line": {"color": "#E2D9BF"}}})
ch4.set_legend({"none": True})
ch4.set_size({"width": 675, "height": 380})
ws_dash.insert_chart("K27", ch4)

# Column: orders by hour
ch5 = wb.add_chart({"type": "column"})
chart_base(ch5, "Orders by Hour of Day")
ch5.add_series({"categories": sheet_range("hour_first", "hour_last", 1), "values": sheet_range("hour_first", "hour_last", 2),
                "fill": {"color": ORANGE}, "gap": 30})
ch5.set_y_axis({"num_format": "#,##0", "major_gridlines": {"visible": True, "line": {"color": "#E2D9BF"}}})
ch5.set_legend({"none": True})
ch5.set_size({"width": 675, "height": 340})
ws_dash.insert_chart("B47", ch5)

# Column: day-of-week revenue + profit
ch6 = wb.add_chart({"type": "column"})
chart_base(ch6, "Day-of-Week Performance")
ch6.add_series({"name": "Revenue", "categories": sheet_range("dow_first", "dow_last", 1),
                "values": sheet_range("dow_first", "dow_last", 3), "fill": {"color": RED}, "gap": 60})
ch6.add_series({"name": "Gross Profit", "categories": sheet_range("dow_first", "dow_last", 1),
                "values": sheet_range("dow_first", "dow_last", 4), "fill": {"color": CHARCOAL}})
ch6.set_y_axis({"num_format": "$#,##0", "major_gridlines": {"visible": True, "line": {"color": "#E2D9BF"}}})
ch6.set_legend({"position": "bottom"})
ch6.set_size({"width": 675, "height": 340})
ws_dash.insert_chart("K47", ch6)

# Heatmap grid on the dashboard (cells link to the Analysis heatmap)
hm_row = 65
ws_dash.merge_range(hm_row, 1, hm_row, 14, "Orders Heatmap: Day of Week x Hour (darker = busier)", F["section"])
ws_dash.write(hm_row + 1, 1, "Day \\ Hour", F["heat_lbl"])
for j, h in enumerate(hours):
    ws_dash.write(hm_row + 1, 2 + j, f"{h}:00", F["heat_lbl"])
for i, d in enumerate(DAYS):
    ws_dash.write(hm_row + 2 + i, 1, d, F["heat_lbl"])
    for j, h in enumerate(hours):
        src = xl_rowcol_to_cell(REF["heat_first"] + i, 2 + j)
        ws_dash.write_formula(hm_row + 2 + i, 2 + j, f"=Analysis!{src}", F["heat"], int(cross.loc[d, h]))
ws_dash.conditional_format(hm_row + 2, 2, hm_row + 8, 1 + len(hours),
                           {"type": "2_color_scale", "min_color": CREAM, "max_color": RED})
ws_dash.write(hm_row + 10, 1, "Tip: add slicers (Channel, Month, Category, Spice Level) via pivot tables - see excel/README_excel.md",
              fmt(italic=True, font_color="#C9C2B0", bg_color=CHARCOAL))

ws_dash.set_landscape()
ws_dash.fit_to_pages(1, 0)
ws_dash.activate()
wb.close()
print(f"Workbook written to {EXCEL_PATH}")
