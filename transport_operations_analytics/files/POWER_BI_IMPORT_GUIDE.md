# Power BI Import Guide — CSV Data (powerbi_data/)

This guide covers importing the 5 pre-exported CSV files in `powerbi_data/`
into Power BI Desktop. Use this instead of the ODBC route in
`POWER_BI_GUIDE.md` if you'd rather not install a SQLite ODBC driver — the
CSVs are exact, unaltered exports of the same 5 validated views, so
everything else in `POWER_BI_GUIDE.md` (relationships, DAX, page layouts)
still applies unchanged.

## What's in `powerbi_data/`

| CSV file | Source view | Rows | Grain |
|---|---|---|---|
| `trip_profitability.csv` | `vw_trip_profitability` | 500 | 1 row per trip |
| `delivery_performance.csv` | `vw_delivery_performance` | 500 | 1 row per trip |
| `payment_status.csv` | `vw_payment_status` | 500 | 1 row per trip (payment record) |
| `vehicle_performance.csv` | `vw_vehicle_performance` | 20 | 1 row per vehicle (pre-aggregated) |
| `customer_performance.csv` | `vw_customer_performance` | 50 | 1 row per customer (pre-aggregated) |

All 5 files were exported directly from the database with `SELECT * FROM <view>`
— no values were recalculated, reformatted, or altered. Column names and
row counts have been verified to match the live SQLite views exactly (see
`validate_powerbi_exports.py`).

## Which CSV feeds which dashboard page

| Dashboard page | Primary CSV(s) | Why |
|---|---|---|
| **Page 1 — Executive Overview** | `trip_profitability.csv` | Has revenue, expense, profit, and margin already computed per trip — powers the Monthly Revenue vs Expenses chart, Monthly Profit Trend, and the top KPI cards when aggregated with SUM/AVERAGE measures |
| **Page 2 — Fleet & Delivery Performance** | `vehicle_performance.csv` (summary cards/table) + `delivery_performance.csv` (on-time/delayed detail) | `vehicle_performance.csv` already has trip count, revenue, expense, profit and cost/km per vehicle; `delivery_performance.csv` provides `is_on_time` / `is_delayed` / `delay_days` at trip grain for the On-Time vs Delayed chart and route/destination breakdowns |
| **Page 3 — Customers & Payments** | `customer_performance.csv` (summary cards/table) + `payment_status.csv` (invoice-level detail) | `customer_performance.csv` already has revenue, paid, outstanding, overdue per customer; `payment_status.csv` gives per-invoice detail (due date, payment date, days overdue) for the Monthly Collections trend and overdue drill-through |
| **Page 4 — Documentation & Operations** | `delivery_performance.csv` (joined to `documents` if imported) | The documentation completion % measures need the `documents` table's flag columns; import the `documents` table itself (via ODBC or its own CSV export if you add one) alongside `delivery_performance.csv` for the exception table (Trip ID, dispatch/expected/actual dates, delivery status) |

> Note: `payment_status.csv` and `delivery_performance.csv` are both at
> trip grain, so if you load both plus the `trips` table itself into the
> same model, only relate them through `trip_id` — don't load `trips` and
> then also treat these CSVs as separate fact tables with their own
> relationships to `vehicles`/`customers`, or you'll get duplicate paths.
> For a CSV-only model (no database connection at all), each of these 5
> files can stand alone as its own table without further relationships,
> since they already carry every column a page needs pre-joined.

## How to Import into Power BI Desktop

1. Open Power BI Desktop → **Home → Get Data → Text/CSV**.
2. Browse to `powerbi_data/trip_profitability.csv` → **Open**.
3. In the preview window, confirm:
   - **File Origin** is set to `65001: Unicode (UTF-8)` (Power BI usually
     auto-detects this correctly for UTF-8 files, but check it if any
     special characters look wrong).
   - The Data Type Detection preview looks right — dates like
     `dispatch_date` should show as text or date icons; Power BI's
     auto-detection is generally reliable, but review it before loading.
4. Click **Load** (or **Transform Data** first if you want to explicitly
   set column types in Power Query before loading — recommended for date
   columns, see below).
5. Repeat steps 2–4 for the other 4 CSVs, or use **Get Data → Text/CSV**
   again and multi-select all 5 files in one go (they'll load as 5
   separate tables — Power BI does not merge same-shaped CSVs
   automatically, which is what you want here).

### Recommended type fixes in Power Query (Transform Data)
CSV has no native date/number types, so Power BI infers them — double-check
these columns are set correctly (select the column → **Transform** ribbon
→ **Data Type**):

- `dispatch_date`, `expected_delivery_date`, `actual_delivery_date`,
  `invoice_date`, `due_date`, `payment_date` → **Date**
- `freight_revenue`, `total_expense`, `profit`, `distance_km`,
  `cost_per_km`, `invoice_amount`, `total_revenue`, `total_outstanding`,
  etc. → **Decimal Number**
- `is_on_time`, `is_delayed`, `delay_days`, `trip_count` → **Whole Number**
- ID columns (`trip_id`, `vehicle_id`, `customer_id`, `payment_id`,
  `document_id`) → **Text** (even though some look numeric-ish, keep them
  as text so leading characters like `TRP`/`VEH` aren't stripped and so
  they match correctly as relationship keys)

### Building relationships after import
In **Model view**, relate the tables on their shared `trip_id`,
`vehicle_id`, or `customer_id` columns exactly as described in the "How
the Tables Are Related" section of `POWER_BI_GUIDE.md`. If you're working
purely from these 5 CSVs (no `vehicles`/`drivers`/`customers`/`trips`
tables loaded separately), most visuals can be built directly off a single
CSV table's columns without any relationships at all, since each view was
designed to be "already joined" for its dashboard page.

### Refreshing after new data
These CSVs are a **point-in-time snapshot**, not a live connection. If the
underlying database changes, re-run the export:
```bash
python3 export_powerbi_views.py
python3 validate_powerbi_exports.py
```
then in Power BI Desktop: **Home → Refresh** (it will re-read the same file
paths). If you want a live connection instead of re-exporting CSVs each
time, use the ODBC method in `POWER_BI_GUIDE.md`.
