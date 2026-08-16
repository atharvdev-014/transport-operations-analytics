-- =============================================================================
-- kpi_queries.sql
-- Transport Operations Analytics System
--
-- Ready-to-run KPI queries against transport_operations.db.
-- Grouped by business area. Each query is self-contained (run it on its own).
--
-- Notes on conventions used throughout:
--   * "Cancelled" trips are excluded from revenue/cost/on-time KPIs since they
--     never actually moved freight (their tiny cancellation charge would
--     distort revenue-per-trip and cost-per-km figures).
--   * NULLIF() is used anywhere we divide, so a query can never crash with a
--     divide-by-zero error even on an empty/filtered dataset.
--   * Money columns are plain REAL (rupees); format them as ₹#,##0 in Excel/Power BI.
-- =============================================================================


-- =========================
-- OVERALL KPIs
-- =========================

-- Total Trips (excluding cancelled)
SELECT COUNT(*) AS total_trips
FROM trips
WHERE trip_status <> 'Cancelled';

-- Total Revenue
SELECT ROUND(SUM(freight_revenue), 2) AS total_revenue
FROM trips
WHERE trip_status <> 'Cancelled';

-- Total Expenses
SELECT ROUND(SUM(e.amount), 2) AS total_expenses
FROM trip_expenses e
JOIN trips t ON e.trip_id = t.trip_id
WHERE t.trip_status <> 'Cancelled';

-- Total Profit (Revenue - Expenses)
SELECT
    ROUND(SUM(t.freight_revenue), 2)               AS total_revenue,
    ROUND(SUM(e.total_expense), 2)                  AS total_expenses,
    ROUND(SUM(t.freight_revenue) - SUM(e.total_expense), 2) AS total_profit
FROM trips t
JOIN (
    SELECT trip_id, SUM(amount) AS total_expense
    FROM trip_expenses
    GROUP BY trip_id
) e ON t.trip_id = e.trip_id
WHERE t.trip_status <> 'Cancelled';

-- Profit Margin %
SELECT
    ROUND(SUM(t.freight_revenue), 2) AS total_revenue,
    ROUND(SUM(t.freight_revenue) - SUM(e.total_expense), 2) AS total_profit,
    ROUND(
        (SUM(t.freight_revenue) - SUM(e.total_expense)) * 100.0
        / NULLIF(SUM(t.freight_revenue), 0), 2
    ) AS profit_margin_pct
FROM trips t
JOIN (
    SELECT trip_id, SUM(amount) AS total_expense
    FROM trip_expenses
    GROUP BY trip_id
) e ON t.trip_id = e.trip_id
WHERE t.trip_status <> 'Cancelled';

-- Average Revenue per Trip
SELECT ROUND(AVG(freight_revenue), 2) AS avg_revenue_per_trip
FROM trips
WHERE trip_status <> 'Cancelled';

-- Average Cost per Trip
SELECT ROUND(AVG(e.total_expense), 2) AS avg_cost_per_trip
FROM (
    SELECT trip_id, SUM(amount) AS total_expense
    FROM trip_expenses
    GROUP BY trip_id
) e
JOIN trips t ON t.trip_id = e.trip_id
WHERE t.trip_status <> 'Cancelled';

-- Average Cost per Kilometer
-- (expenses aggregated to one row per trip FIRST, so joining to trips can never
--  fan-out and double-count distance_km)
SELECT
    ROUND(SUM(e.total_expense) * 1.0 / NULLIF(SUM(t.distance_km), 0), 2) AS cost_per_km
FROM trips t
JOIN (SELECT trip_id, SUM(amount) AS total_expense FROM trip_expenses GROUP BY trip_id) e
    ON t.trip_id = e.trip_id
WHERE t.trip_status <> 'Cancelled';

-- Total Distance Covered
SELECT ROUND(SUM(distance_km), 1) AS total_distance_km
FROM trips
WHERE trip_status <> 'Cancelled';


-- =========================
-- DELIVERY KPIs
-- =========================

-- On-Time Delivery % (Delivered on/before expected date, among completed trips)
SELECT
    SUM(CASE WHEN trip_status = 'Delivered' THEN 1 ELSE 0 END) AS on_time_trips,
    SUM(CASE WHEN trip_status IN ('Delivered','Delayed') THEN 1 ELSE 0 END) AS completed_trips,
    ROUND(
        SUM(CASE WHEN trip_status = 'Delivered' THEN 1 ELSE 0 END) * 100.0
        / NULLIF(SUM(CASE WHEN trip_status IN ('Delivered','Delayed') THEN 1 ELSE 0 END), 0), 2
    ) AS on_time_delivery_pct
FROM trips;

-- Delayed Trip Count
SELECT COUNT(*) AS delayed_trip_count
FROM trips
WHERE trip_status = 'Delayed';

-- Average Delay (days), for delayed trips only
SELECT
    ROUND(AVG(julianday(actual_delivery_date) - julianday(expected_delivery_date)), 1) AS avg_delay_days
FROM trips
WHERE trip_status = 'Delayed';

-- Delivery performance by destination
SELECT
    destination,
    COUNT(*) AS completed_trips,
    SUM(CASE WHEN trip_status = 'Delivered' THEN 1 ELSE 0 END) AS on_time_trips,
    ROUND(SUM(CASE WHEN trip_status = 'Delivered' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS on_time_pct
FROM trips
WHERE trip_status IN ('Delivered', 'Delayed')
GROUP BY destination
ORDER BY completed_trips DESC;

-- Delivery performance by route (origin -> destination)
SELECT
    origin || ' -> ' || destination AS route,
    COUNT(*) AS completed_trips,
    SUM(CASE WHEN trip_status = 'Delivered' THEN 1 ELSE 0 END) AS on_time_trips,
    ROUND(SUM(CASE WHEN trip_status = 'Delivered' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS on_time_pct
FROM trips
WHERE trip_status IN ('Delivered', 'Delayed')
GROUP BY origin, destination
ORDER BY completed_trips DESC;


-- =========================
-- FLEET KPIs
-- =========================

-- Trips by vehicle
SELECT v.vehicle_number, v.vehicle_type, COUNT(t.trip_id) AS trip_count
FROM vehicles v
LEFT JOIN trips t ON v.vehicle_id = t.vehicle_id AND t.trip_status <> 'Cancelled'
GROUP BY v.vehicle_id
ORDER BY trip_count DESC;

-- Revenue by vehicle
SELECT v.vehicle_number, v.vehicle_type, ROUND(SUM(t.freight_revenue), 2) AS revenue
FROM vehicles v
LEFT JOIN trips t ON v.vehicle_id = t.vehicle_id AND t.trip_status <> 'Cancelled'
GROUP BY v.vehicle_id
ORDER BY revenue DESC;

-- Profit by vehicle
SELECT
    v.vehicle_number,
    v.vehicle_type,
    ROUND(SUM(t.freight_revenue), 2) AS revenue,
    ROUND(SUM(e.total_expense), 2) AS expenses,
    ROUND(SUM(t.freight_revenue) - SUM(e.total_expense), 2) AS profit
FROM vehicles v
JOIN trips t ON v.vehicle_id = t.vehicle_id AND t.trip_status <> 'Cancelled'
JOIN (SELECT trip_id, SUM(amount) AS total_expense FROM trip_expenses GROUP BY trip_id) e
    ON t.trip_id = e.trip_id
GROUP BY v.vehicle_id
ORDER BY profit DESC;

-- Distance by vehicle
SELECT v.vehicle_number, ROUND(SUM(t.distance_km), 1) AS total_distance_km
FROM vehicles v
LEFT JOIN trips t ON v.vehicle_id = t.vehicle_id AND t.trip_status <> 'Cancelled'
GROUP BY v.vehicle_id
ORDER BY total_distance_km DESC;

-- Cost per KM by vehicle
SELECT
    v.vehicle_number,
    ROUND(SUM(e.total_expense) * 1.0 / NULLIF(SUM(t.distance_km), 0), 2) AS cost_per_km
FROM vehicles v
JOIN trips t ON v.vehicle_id = t.vehicle_id AND t.trip_status <> 'Cancelled'
JOIN (SELECT trip_id, SUM(amount) AS total_expense FROM trip_expenses GROUP BY trip_id) e
    ON t.trip_id = e.trip_id
GROUP BY v.vehicle_id
ORDER BY cost_per_km DESC;

-- Vehicle utilization indicator (trips per vehicle vs. fleet average)
SELECT
    v.vehicle_number,
    COUNT(t.trip_id) AS trip_count,
    ROUND(
        COUNT(t.trip_id) * 1.0 / NULLIF((SELECT COUNT(*) * 1.0 / COUNT(DISTINCT vehicle_id) FROM trips WHERE trip_status <> 'Cancelled'), 0),
        2
    ) AS utilization_index   -- 1.0 = average utilization, >1 = above average
FROM vehicles v
LEFT JOIN trips t ON v.vehicle_id = t.vehicle_id AND t.trip_status <> 'Cancelled'
GROUP BY v.vehicle_id
ORDER BY utilization_index DESC;


-- =========================
-- CUSTOMER KPIs
-- =========================

-- Revenue by customer
SELECT c.customer_name, ROUND(SUM(t.freight_revenue), 2) AS revenue
FROM customers c
LEFT JOIN trips t ON c.customer_id = t.customer_id AND t.trip_status <> 'Cancelled'
GROUP BY c.customer_id
ORDER BY revenue DESC;

-- Number of trips by customer
SELECT c.customer_name, COUNT(t.trip_id) AS trip_count
FROM customers c
LEFT JOIN trips t ON c.customer_id = t.customer_id AND t.trip_status <> 'Cancelled'
GROUP BY c.customer_id
ORDER BY trip_count DESC;

-- Outstanding payment by customer (Pending + Overdue)
SELECT
    c.customer_name,
    ROUND(SUM(p.invoice_amount), 2) AS outstanding_amount
FROM customers c
JOIN trips t ON c.customer_id = t.customer_id
JOIN payments p ON t.trip_id = p.trip_id
WHERE p.payment_status IN ('Pending', 'Overdue')
GROUP BY c.customer_id
ORDER BY outstanding_amount DESC;

-- Overdue payment by customer
SELECT
    c.customer_name,
    ROUND(SUM(p.invoice_amount), 2) AS overdue_amount,
    COUNT(*) AS overdue_invoices
FROM customers c
JOIN trips t ON c.customer_id = t.customer_id
JOIN payments p ON t.trip_id = p.trip_id
WHERE p.payment_status = 'Overdue'
GROUP BY c.customer_id
ORDER BY overdue_amount DESC;


-- =========================
-- PAYMENT KPIs
-- =========================

-- Total invoiced amount
SELECT ROUND(SUM(invoice_amount), 2) AS total_invoiced
FROM payments
WHERE payment_status <> 'Not Applicable';

-- Total paid amount
SELECT ROUND(SUM(invoice_amount), 2) AS total_paid
FROM payments
WHERE payment_status = 'Paid';

-- Total outstanding amount (not yet paid)
SELECT ROUND(SUM(invoice_amount), 2) AS total_outstanding
FROM payments
WHERE payment_status IN ('Pending', 'Overdue');

-- Total overdue amount
SELECT ROUND(SUM(invoice_amount), 2) AS total_overdue
FROM payments
WHERE payment_status = 'Overdue';

-- Payment collection rate (Paid / Invoiced)
SELECT
    ROUND(SUM(CASE WHEN payment_status = 'Paid' THEN invoice_amount ELSE 0 END) * 100.0
        / NULLIF(SUM(invoice_amount), 0), 2) AS payment_collection_rate_pct
FROM payments
WHERE payment_status <> 'Not Applicable';

-- Average payment delay (days late, for paid invoices that were paid after the due date)
SELECT
    ROUND(AVG(julianday(payment_date) - julianday(due_date)), 1) AS avg_payment_delay_days
FROM payments
WHERE payment_status = 'Paid' AND payment_date > due_date;


-- =========================
-- DOCUMENTATION KPIs
-- =========================

-- POD completion percentage
SELECT ROUND(SUM(pod_available) * 100.0 / COUNT(*), 2) AS pod_completion_pct
FROM documents;

-- E-way bill completion percentage
SELECT ROUND(SUM(eway_bill_available) * 100.0 / COUNT(*), 2) AS eway_bill_completion_pct
FROM documents;

-- Invoice completion percentage
SELECT ROUND(SUM(invoice_available) * 100.0 / COUNT(*), 2) AS invoice_completion_pct
FROM documents;

-- LR copy completion percentage
SELECT ROUND(SUM(lr_copy_available) * 100.0 / COUNT(*), 2) AS lr_copy_completion_pct
FROM documents;

-- Incomplete document count
SELECT COUNT(*) AS incomplete_document_count
FROM documents
WHERE document_status IN ('Incomplete', 'Missing');
