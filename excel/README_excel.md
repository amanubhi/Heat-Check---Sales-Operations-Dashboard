# Excel Dashboard Guide

`HeatCheck_Dashboard.xlsx` contains:

| Sheet | What it is |
|---|---|
| **Dashboard** | KPI cards, 6 native charts and a day x hour heatmap (all linked to the Analysis sheet) |
| **Explorer** | Pick a **Channel** and **Month** from the orange dropdown cells and the KPIs, tables and 4 charts recalculate instantly (live `SUMIFS`). This works without pivot tables. |
| **Analysis** | 10 summary tables. Sections 1-8 are live `SUMIFS` / `COUNTIFS` formulas on the data sheets; 9-10 are values from SQL queries Q02 and Q03 |
| **Orders, Order_Items, Menu, Customers, Events** | Clean data, each formatted as an Excel Table (`Tbl_Orders`, `Tbl_Order_Items`, `Tbl_Menu`, `Tbl_Customers`, `Tbl_Events`) so pivot tables can use them by name |

Colors: charcoal `#1F1F1F`, flame red `#D7263D`, orange `#F46036`, cream `#FFF8E7`.

> Python cannot create real pivot tables or slicers, so the steps below are the part you add by hand. (The **Explorer** sheet already gives you dropdown filtering without them.) It takes about 15 minutes and is a good portfolio talking point.

---

## Pivot tables to add (new sheet called `Pivots`)

For each one: click any cell in the source table, then **Insert > PivotTable > From Table/Range**, and choose *Existing Worksheet* -> `Pivots`.

| # | Pivot name | Source table | Rows | Columns | Values | Notes |
|---|---|---|---|---|---|---|
| 1 | `pvt_ChannelMonth` | `Tbl_Orders` | `month_name` | `channel` | Sum of `revenue` | Sort months by `month` (use *More Sort Options > Custom list* or a helper column) |
| 2 | `pvt_ProfitByChannel` | `Tbl_Orders` | `channel` | (none) | Sum of `revenue`, Sum of `gross_profit`, Average of `gross_margin_pct` | Show values as currency |
| 3 | `pvt_CategoryProfit` | `Tbl_Order_Items` | `category`, `item_name` | (none) | Sum of `quantity`, Sum of `line_revenue`, Sum of `line_profit` | Sort by profit descending; add a **Top 10** value filter on `item_name` |
| 4 | `pvt_SpiceMix` | `Tbl_Order_Items` | `spice_level` | (none) | Sum of `quantity`; then *Show Values As > % of Column Total* | Filter out `Not Applicable` |
| 5 | `pvt_DaypartHeat` | `Tbl_Orders` | `day_of_week` | `daypart` | Count of `order_id` | Add *Conditional Formatting > Color Scales* for a heatmap |
| 6 | `pvt_EventPerformance` | `Tbl_Orders` | `event_name` | (none) | Sum of `revenue`, Sum of `gross_profit`, Count of `order_id` | Filter `channel` = Vendor Event |
| 7 | `pvt_Loyalty` | `Tbl_Orders` | `loyalty_member` | (none) | Count of `order_id`, Average of `revenue` | Filter out blank (walk-ups) |

**Tip:** `Tbl_Order_Items` already includes `channel`, `month` and `month_name`, so pivots 3 and 4 can be sliced by channel and month with no lookup column.

---

## Slicers to add

Select a pivot table, then **PivotTable Analyze > Insert Slicer**. Place them along the top or right of the `Dashboard` sheet.

| Slicer | Field | Connect to pivots | Where the field lives |
|---|---|---|---|
| **Channel** | `channel` | 1, 2, 5, 6 (use the `Tbl_Order_Items` `channel` field for 3 and 4) | `Tbl_Orders` / `Tbl_Order_Items` |
| **Month** | `month_name` | 1, 2, 5, 6 (use the `Tbl_Order_Items` `month_name` field for 3 and 4) | `Tbl_Orders` / `Tbl_Order_Items` |
| **Category** | `category` | 3, 4 | `Tbl_Order_Items` |
| **Spice Level** | `spice_level` | 3, 4 | `Tbl_Order_Items` |

To link one slicer to several pivots: right-click the slicer > **Report Connections** > tick every pivot that uses the same source table.

Optional extras: a **Timeline** slicer on `order_date` (Insert > Timeline) and a slicer on `daypart`.

---

## Finishing touches

1. Right-click each slicer > **Slicer Settings** and set the style to a custom orange/red style (*Slicer Styles > New Slicer Style*).
2. Take a screenshot of the finished dashboard with slicers for the README (`assets/excel_dashboard.png`).
3. The formulas on `Analysis` work on all rows, so they are **not** affected by slicers. Build extra charts from pivot tables (*PivotChart*) if you want them to respond to slicers.

## Regenerating the workbook

```bash
python scripts/build_excel.py
```

This overwrites the file, so save your pivot/slicer version under another name (e.g. `HeatCheck_Dashboard_with_slicers.xlsx`).
