# Running Heat Check on Real Data

The repo ships with synthetic data. The same pipeline can run on a real sales export from a point-of-sale (POS) system. **Real data never leaves your computer:** everything is written to a `private/` folder that is listed in `.gitignore`.

## 1. Export from your POS
Export item-level sales, **one row per item sold**. Most POS systems (Square, Toast, Clover, Shopify) have a "transactions" or "item sales" export.

Required columns:

| Column | Example |
|---|---|
| `order_id` | `10452` |
| `order_datetime` | `2025-03-14 18:42:00` |
| `channel` | `Storefront`, `Night Market` or `Vendor Event` (see "Mapping" below) |
| `item_name` | `Tender Combo` |
| `quantity` | `2` |
| `unit_price` | `18.00` |

Optional columns (more columns = richer analysis): `event_name`, `category`, `unit_food_cost`, `spice_level`, `payment_method`, `order_type`, `customer_id`, `discount_amount` (per order), `tip_amount` (per order), `prep_time_minutes`, `zip_code`, `loyalty_member`.

If you sell at events, also make an events file: `event_name, start_date, end_date, booth_fee, staff_count, city` (see `data/templates/events_template.csv`). Event names in the sales file must match exactly.

Examples are in `data/templates/` (`pos_export_example.csv` is 250 demo orders).

## 2. Protect privacy first
- **Never include names, phone numbers or emails.** Use an anonymous `customer_id` (for example a hash or a POS internal ID).
- Keep the files in `private/` or outside the repo. The folder is ignored by git, but double-check with `git status` before every commit.
- Do not publish `private/docs/index.html` or the private Excel file; they contain your real numbers.

## 3. Import and run
```bash
python scripts/import_real_data.py --sales path/to/pos_export.csv --events path/to/events.csv
python run_all.py --real
```
Optional: `--costs path/to/item_costs.csv` (`item_name,unit_food_cost`) to use real recipe costs. **Without it, food cost is assumed to be 30% of price** and profit numbers are only as good as that guess.

Outputs appear in `private/`: `private/docs/index.html` (dashboard), `private/excel/HeatCheck_Dashboard.xlsx`, `private/outputs/sql_results/`, `private/data/cleaning_log.md`.

## Mapping
POS labels are mapped onto the official ones in the dictionaries at the top of `scripts/import_real_data.py` (`CHANNELS`, `PAYMENTS`, `ORDER_TYPES`). Unrecognized labels are reported as warnings and set to a default, so add your own spellings there.

## What works on real data and what does not
- Works: cleaning, SQL queries, the Excel workbook, the web dashboard (filters, charts, heatmap, event table).
- Skipped automatically when the data does not fit: the **written insights** and the **sensitivity analysis**, which are tailored to the demo data. The pipeline tells you when it skips them. Adapt `compute_insights()` in `scripts/export_dashboard_data.py` and `scripts/sensitivity_analysis.py` to your business.
- Partial years, a missing channel or no customer IDs are handled.

## 4. Clean up
Delete the `private/` folder when you are done if you do not want a local copy. Nothing in it is ever tracked by git.
