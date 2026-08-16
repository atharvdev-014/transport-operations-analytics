# Power BI Guide — Transport Operations Performance Dashboard

This guide walks you through building the **Transport Operations Performance
Dashboard** in Power BI Desktop on top of the validated
`transport_operations.db` database. It's written for a Power BI beginner.

> **Why this is a guide, not a finished `.pbix` file:** Power BI Desktop is
> a licensed Windows application. It isn't available to run or validate in
> the environment that built this project, so rather than hand you an
> untested binary file, this guide gives you the exact connection steps,
> field list, chart-by-chart spec, and copy-pasteable DAX so you can build
> it yourself in ~1–2 hours and know exactly what each piece does (which
> also makes it much easier to explain in an interview than a file someone
> else built for you).

---

## 1. How the SQLite Connection Works

Power BI does not have a built-in SQLite connector, so it connects through
**ODBC** (Open Database Connectivity) — a driver that lets any application
talk to a SQLite file as if it were a normal database server.

1. Download and install the free **SQLite ODBC Driver**:
   `http://www.ch-werner.de/sqliteodbc/` (use the 64-bit `.exe` on Windows).
2. Open **ODBC Data Sources (64-bit)** (search for it in the Windows start
   menu) → **System DSN** tab → **Add** → choose the SQLite3 ODBC driver →
   give it a name (e.g. `TransportOpsDB`) → browse to your
   `transport_operations.db` file → OK.
3. In Power BI Desktop: **Home → Get Data → More → ODBC** → select the
   `TransportOpsDB` DSN → OK.
4. In the Navigator window, tick the 7 base tables **and** the 5 views
   (`vw_trip_profitability`, `vw_delivery_performance`, `vw_payment_status`,
   `vw_vehicle_performance`, `vw_customer_performance`) → **Load**.

If you don't want to install an ODBC driver, the alternative is: run the
Python scripts in this project to export each table/view to CSV
(`pandas.read_sql` + `to_csv`), then use **Get Data → Text/CSV** in Power BI.
The model and DAX below work identically either way.

## 2. How the Tables Are Related

Build these relationships in **Model view** (drag field to field):

| From | To | Cardinality | Cross-filter |
|---|---|---|---|
| `vehicles[vehicle_id]` | `trips[vehicle_id]` | 1 → many | Single |
| `drivers[driver_id]` | `trips[driver_id]` | 1 → many | Single |
| `customers[customer_id]` | `trips[customer_id]` | 1 → many | Single |
| `trips[trip_id]` | `trip_expenses[trip_id]` | 1 → many | Single |
| `trips[trip_id]` | `payments[trip_id]` | 1 → 1 | Single |
| `trips[trip_id]` | `documents[trip_id]` | 1 → 1 | Single |

This is a **star schema**: `trips` is the fact table at the center,
`vehicles`/`drivers`/`customers` are dimension tables, and
`trip_expenses`/`payments`/`documents` are child fact tables hanging off
`trips`. Keep filter direction **single** everywhere to avoid ambiguous
circular filtering.

**Tip:** for the KPI cards and charts that need revenue + expenses together
without double-counting, use the pre-aggregated `vw_trip_profitability` view
(one row per trip, expenses already summed) instead of relating
`trip_expenses` directly into visuals that also show `freight_revenue`.
Relating a one-to-many table (`trip_expenses`) into the same visual as
`trips.freight_revenue` is the #1 cause of inflated revenue numbers in
Power BI — the view avoids that trap entirely.

## 3. What Each Dashboard Page Shows

**Page 1 — Executive Overview**: the 30-second health check. 6 KPI cards
(Trips, Revenue, Expenses, Profit, Margin %, On-Time %), Monthly Revenue vs
Expenses, Trip Status breakdown, Monthly Profit Trend, Top 10 Destinations
by Revenue. Slicers: Date, Customer, Vehicle, Trip Status, Payment Status.

**Page 2 — Fleet & Delivery Performance**: which vehicles are working hard
and which are efficient. Trips/Revenue/Profit by Vehicle, Cost/KM ranked
from worst to best (spot the inefficient trucks), On-Time vs Delayed, Top
Routes by volume, and a vehicle performance table.

**Page 3 — Customers & Payments**: who generates revenue and who owes
money. Top 10 Customers by Revenue, Outstanding by Customer, Monthly
Collections, and a customer table with Trips/Revenue/Paid/
Outstanding/Overdue.

**Page 4 — Documentation & Operations**: compliance and exception tracking.
4 completion-% KPIs (POD, E-way Bill, Invoice, LR Copy), Missing POD by
Customer, Incomplete Documents by Trip Status, Delayed Trips by
Destination, and a detailed exception table (Trip ID → Payment status) for
ops teams to action.

## 4. What Each KPI Means

| KPI | Meaning |
|---|---|
| Total Trips | Count of trips excluding cancellations |
| Total Revenue | Sum of `freight_revenue` billed to customers |
| Total Expenses | Sum of all `trip_expenses` (diesel, toll, allowance, loading, unloading, maintenance, other) |
| Total Profit | Revenue − Expenses |
| Profit Margin % | Profit ÷ Revenue |
| On-Time Delivery % | Delivered-on-time trips ÷ all completed trips (Delivered + Delayed) |
| Cost per KM | Total expenses ÷ total distance — the core unit-economics metric in trucking |
| Total Invoiced / Paid / Outstanding / Overdue | Payment lifecycle — invoiced is everything billed, outstanding is unpaid, overdue is unpaid *past* the due date |
| POD Completion % | % of trips where the Proof of Delivery document exists — missing POD is a common reason customers delay payment |

## 5. DAX Measures

Create these as a new **measure table** (right-click the model → "New
table" → name it `_Measures`, or add them directly under the `trips` table).
Comments explain what each one calculates.

```DAX
-- Core volume & money measures --------------------------------------------

Total Trips =
CALCULATE(
    COUNTROWS(trips),
    trips[trip_status] <> "Cancelled"
)
-- Counts trips that actually moved freight (excludes cancellations).

Total Revenue =
CALCULATE(
    SUM(trips[freight_revenue]),
    trips[trip_status] <> "Cancelled"
)
-- Sum of freight billed to customers.

Total Expenses =
CALCULATE(
    SUM(vw_trip_profitability[total_expense]),
    vw_trip_profitability[trip_status] <> "Cancelled"
)
-- Uses the pre-aggregated view (1 row per trip) so summing here can never
-- double-count expenses, even if trip_expenses is also in the model.

Total Profit = [Total Revenue] - [Total Expenses]

Profit Margin % = DIVIDE([Total Profit], [Total Revenue], 0)
-- DIVIDE() returns 0 instead of an error when Revenue is 0 (e.g. empty filter).

Average Revenue per Trip = DIVIDE([Total Revenue], [Total Trips], 0)

Average Cost per Trip = DIVIDE([Total Expenses], [Total Trips], 0)

Total Distance (KM) =
CALCULATE(
    SUM(trips[distance_km]),
    trips[trip_status] <> "Cancelled"
)

Cost per KM = DIVIDE([Total Expenses], [Total Distance (KM)], 0)

-- Delivery measures ---------------------------------------------------------

On-Time Trips = CALCULATE(COUNTROWS(trips), trips[trip_status] = "Delivered")

Completed Trips =
CALCULATE(COUNTROWS(trips), trips[trip_status] IN {"Delivered", "Delayed"})

On-Time Delivery % = DIVIDE([On-Time Trips], [Completed Trips], 0)

Delayed Trips = CALCULATE(COUNTROWS(trips), trips[trip_status] = "Delayed")

-- Payment measures -----------------------------------------------------------

Total Invoiced =
CALCULATE(SUM(payments[invoice_amount]), payments[payment_status] <> "Not Applicable")

Total Paid =
CALCULATE(SUM(payments[invoice_amount]), payments[payment_status] = "Paid")

Total Outstanding =
CALCULATE(
    SUM(payments[invoice_amount]),
    payments[payment_status] IN {"Pending", "Overdue"}
)

Total Overdue =
CALCULATE(SUM(payments[invoice_amount]), payments[payment_status] = "Overdue")

Payment Collection Rate % = DIVIDE([Total Paid], [Total Invoiced], 0)

-- Documentation measures ------------------------------------------------------

POD Completion % = DIVIDE(SUM(documents[pod_available]), COUNTROWS(documents), 0)

E-Way Bill Completion % =
DIVIDE(SUM(documents[eway_bill_available]), COUNTROWS(documents), 0)

Invoice Doc Completion % =
DIVIDE(SUM(documents[invoice_available]), COUNTROWS(documents), 0)

LR Copy Completion % =
DIVIDE(SUM(documents[lr_copy_available]), COUNTROWS(documents), 0)
```

That's **14 core measures** (plus 4 documentation ones = 18 total if you
count each completion % separately) — enough to power every KPI card on
all 4 pages without any duplicate logic scattered across visuals.

### Number formatting (apply in the measure's Formatting pane)
- Revenue / Expenses / Profit / Invoiced / Paid / Outstanding / Overdue → `₹#,##0`
- Percentages (Margin, On-Time %, Completion %, Collection Rate) → `0.0%`
- Distance → `#,##0 "km"`
- Cost per KM → `₹0.00`

## 6. How to Refresh the Data

1. Re-run `python3 create_database.py` if you want a fresh synthetic dataset
   (note: with the fixed random seed it will regenerate the *same* data —
   change `RANDOM_SEED` in the script if you want different numbers).
2. In Power BI Desktop: **Home → Refresh**. Power BI re-runs the ODBC query
   against the `.db` file and pulls the latest rows.
3. If you're on the Power BI Service (published/online), you'd need the
   **On-premises Data Gateway** to refresh against a local SQLite file on a
   schedule — for a portfolio project, manual refresh in Desktop is enough.

## 7. How to Add a New Trip

1. The cleanest way: extend `create_database.py` and re-run it (keeps the
   dataset consistent and reproducible) — but for a one-off manual add:
2. Open the database in DB Browser for SQLite → `trips` table → **New
   Record** → fill in `trip_id` (unique), `vehicle_id`/`driver_id`/
   `customer_id` (must already exist in those tables), dates, distance,
   `freight_revenue`, `trip_status`, `payment_status`.
3. Add a matching row in `trip_expenses` (at least one), `payments`, and
   `documents` — every trip needs all three, or the "every trip has a
   payment/document record" business rule is broken.
4. **Write Changes** in DB Browser, then hit **Refresh** in Power BI.

## 8. How the Dashboard Updates After New Data Is Added

Because every visual is built on **measures** (not hardcoded numbers) and
the model relationships flow from `vehicles`/`drivers`/`customers` →
`trips` → `trip_expenses`/`payments`/`documents`, a new trip automatically:
- increases `Total Trips`, and shifts `Total Revenue`/`Total Expenses`/`Total Profit`
- shows up in whichever month's line/bar chart matches its `dispatch_date`
- appears in the relevant vehicle/customer/route breakdowns
- appears in the Page 4 exception table if its documents are incomplete

No manual chart edits are needed — that's the entire point of measures +
relationships over pasting static numbers.

## 9. Troubleshooting Common Refresh/Relationship Errors

| Symptom | Likely cause | Fix |
|---|---|---|
| Revenue looks 2–5× too high | `trip_expenses` (many rows per trip) related directly alongside `trips[freight_revenue]` in the same visual, causing fan-out | Use `vw_trip_profitability` (already 1 row per trip) instead of raw `trip_expenses` in revenue visuals |
| "Relationships in this model may be ambiguous" | Two active relationship paths between the same tables (e.g. both `Both`-direction filters) | Set cross-filter direction to **Single** on every relationship in Model view |
| ODBC connection fails | Driver not installed, or DSN points to the wrong file path | Reinstall the 64-bit SQLite ODBC driver; recheck the DSN's database file path in ODBC Data Sources |
| Refresh does nothing / stale data | You edited the `.db` file but didn't hit Refresh, or Power BI cached the query | Home → Refresh; if still stale, close and reopen the file |
| Blank KPI cards | A filter/slicer combination has zero matching rows, or a measure divides by zero | Confirm slicer selections aren't overly narrow; check every DAX ratio uses `DIVIDE()` (returns 0/blank safely instead of erroring) |
| Percentages show as decimals (0.22 instead of 22.0%) | Formatting not applied to the measure | Select the measure → Formatting pane → Format → Percentage |

## 10. How to Explain This Project in an Interview

A good 60-second walkthrough:

> "I built a synthetic logistics dataset — vehicles, drivers, customers,
> trips, expenses, payments, and delivery documents — as a SQLite database
> with proper foreign keys. On top of that I wrote and *tested* SQL for the
> KPIs a transport company actually cares about: profit margin, cost per
> km, on-time delivery rate, outstanding payments, and document
> completion. I was careful about a classic mistake — joining a one-to-many
> expenses table directly into a revenue visual causes double-counting — so
> I pre-aggregated expenses into a view before joining, and validated that
> the view totals match the raw query totals exactly. Then I modeled it as
> a star schema in Power BI, wrote DAX measures using `DIVIDE()` everywhere
> to avoid divide-by-zero errors, and built a 4-page dashboard: an
> executive overview, fleet efficiency, customer/payment health, and a
> documentation/exception tracker that ops teams could actually use day to
> day."

Be ready to explain: **why a star schema** (avoids ambiguous relationship
paths, keeps DAX simple), **why `DIVIDE()` over `/`** (safe division), and
**one specific insight** the data surfaced (e.g. "~26% of revenue is
outstanding, concentrated in a handful of customers — that's the kind of
finding that would trigger a credit-control conversation in a real
company").
