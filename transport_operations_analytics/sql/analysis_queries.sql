-- =============================================================================
-- analysis_queries.sql
-- Transport Operations Analytics System
--
-- Deeper "business analysis" queries (trends, top-N, exception lists) that sit
-- on top of the raw tables. All expense aggregation is pre-grouped by trip_id
-- before joining to trips, so revenue/expense figures are never inflated by
-- join fan-out.
-- =============================================================================


-- =========================
-- TRENDS OVER TIME
-- =========================

-- Monthly revenue
SELECT
    strftime('%Y-%m', dispatch_date) AS month,
    ROUND(SUM(freight_revenue), 2) AS monthly_revenue
FROM trips
WHERE trip_status <> 'Cancelled'
GROUP BY month
ORDER BY month;

-- Monthly expenses
SELECT
    strftime('%Y-%m', t.dispatch_date) AS month,
    ROUND(SUM(e.amount), 2) AS monthly_expenses
FROM trip_expenses e
JOIN trips t ON e.trip_id = t.trip_id
WHERE t.trip_status <> 'Cancelled'
GROUP BY month
ORDER BY month;

-- Monthly profit (revenue vs expenses, joined at trip level to avoid fan-out)
SELECT
    strftime('%Y-%m', t.dispatch_date) AS month,
    ROUND(SUM(t.freight_revenue), 2) AS monthly_revenue,
    ROUND(SUM(e.total_expense), 2) AS monthly_expenses,
    ROUND(SUM(t.freight_revenue) - SUM(e.total_expense), 2) AS monthly_profit
FROM trips t
JOIN (SELECT trip_id, SUM(amount) AS total_expense FROM trip_expenses GROUP BY trip_id) e
    ON t.trip_id = e.trip_id
WHERE t.trip_status <> 'Cancelled'
GROUP BY month
ORDER BY month;

-- Monthly trip volume
SELECT
    strftime('%Y-%m', dispatch_date) AS month,
    COUNT(*) AS trip_count
FROM trips
WHERE trip_status <> 'Cancelled'
GROUP BY month
ORDER BY month;


-- =========================
-- TOP-N RANKINGS
-- =========================

-- Top 10 customers by revenue
SELECT c.customer_name, ROUND(SUM(t.freight_revenue), 2) AS revenue
FROM customers c
JOIN trips t ON c.customer_id = t.customer_id
WHERE t.trip_status <> 'Cancelled'
GROUP BY c.customer_id
ORDER BY revenue DESC
LIMIT 10;

-- Top 10 routes by revenue
SELECT
    origin || ' -> ' || destination AS route,
    COUNT(*) AS trip_count,
    ROUND(SUM(freight_revenue), 2) AS revenue
FROM trips
WHERE trip_status <> 'Cancelled'
GROUP BY origin, destination
ORDER BY revenue DESC
LIMIT 10;

-- Top 10 routes by profit
SELECT
    t.origin || ' -> ' || t.destination AS route,
    COUNT(*) AS trip_count,
    ROUND(SUM(t.freight_revenue), 2) AS revenue,
    ROUND(SUM(e.total_expense), 2) AS expenses,
    ROUND(SUM(t.freight_revenue) - SUM(e.total_expense), 2) AS profit
FROM trips t
JOIN (SELECT trip_id, SUM(amount) AS total_expense FROM trip_expenses GROUP BY trip_id) e
    ON t.trip_id = e.trip_id
WHERE t.trip_status <> 'Cancelled'
GROUP BY t.origin, t.destination
ORDER BY profit DESC
LIMIT 10;

-- Vehicles with highest trip count
SELECT v.vehicle_number, v.vehicle_type, COUNT(t.trip_id) AS trip_count
FROM vehicles v
JOIN trips t ON v.vehicle_id = t.vehicle_id
WHERE t.trip_status <> 'Cancelled'
GROUP BY v.vehicle_id
ORDER BY trip_count DESC
LIMIT 10;

-- Vehicles with highest profit
SELECT
    v.vehicle_number,
    ROUND(SUM(t.freight_revenue), 2) AS revenue,
    ROUND(SUM(e.total_expense), 2) AS expenses,
    ROUND(SUM(t.freight_revenue) - SUM(e.total_expense), 2) AS profit
FROM vehicles v
JOIN trips t ON v.vehicle_id = t.vehicle_id
JOIN (SELECT trip_id, SUM(amount) AS total_expense FROM trip_expenses GROUP BY trip_id) e
    ON t.trip_id = e.trip_id
WHERE t.trip_status <> 'Cancelled'
GROUP BY v.vehicle_id
ORDER BY profit DESC
LIMIT 10;

-- Vehicles with highest cost per KM
SELECT
    v.vehicle_number,
    ROUND(SUM(e.total_expense) * 1.0 / NULLIF(SUM(t.distance_km), 0), 2) AS cost_per_km
FROM vehicles v
JOIN trips t ON v.vehicle_id = t.vehicle_id
JOIN (SELECT trip_id, SUM(amount) AS total_expense FROM trip_expenses GROUP BY trip_id) e
    ON t.trip_id = e.trip_id
WHERE t.trip_status <> 'Cancelled'
GROUP BY v.vehicle_id
ORDER BY cost_per_km DESC
LIMIT 10;

-- Customers with highest outstanding amount
SELECT
    c.customer_name,
    ROUND(SUM(p.invoice_amount), 2) AS outstanding_amount
FROM customers c
JOIN trips t ON c.customer_id = t.customer_id
JOIN payments p ON t.trip_id = p.trip_id
WHERE p.payment_status IN ('Pending', 'Overdue')
GROUP BY c.customer_id
ORDER BY outstanding_amount DESC
LIMIT 10;


-- =========================
-- EXCEPTION / PROBLEM LISTS  (operational drill-down tables)
-- =========================

-- Delayed trips (full detail)
SELECT
    t.trip_id, c.customer_name, v.vehicle_number, t.origin, t.destination,
    t.dispatch_date, t.expected_delivery_date, t.actual_delivery_date,
    CAST(julianday(t.actual_delivery_date) - julianday(t.expected_delivery_date) AS INTEGER) AS delay_days
FROM trips t
JOIN customers c ON t.customer_id = c.customer_id
JOIN vehicles v ON t.vehicle_id = v.vehicle_id
WHERE t.trip_status = 'Delayed'
ORDER BY delay_days DESC;

-- Trips with missing POD
SELECT
    t.trip_id, c.customer_name, v.vehicle_number, t.destination, t.trip_status, d.document_status
FROM documents d
JOIN trips t ON d.trip_id = t.trip_id
JOIN customers c ON t.customer_id = c.customer_id
JOIN vehicles v ON t.vehicle_id = v.vehicle_id
WHERE d.pod_available = 0
ORDER BY t.dispatch_date DESC;

-- Trips with incomplete documentation (any missing document)
SELECT
    t.trip_id, c.customer_name, d.invoice_available, d.eway_bill_available,
    d.pod_available, d.lr_copy_available, d.document_status
FROM documents d
JOIN trips t ON d.trip_id = t.trip_id
JOIN customers c ON t.customer_id = c.customer_id
WHERE d.document_status IN ('Incomplete', 'Missing')
ORDER BY d.document_status, t.dispatch_date DESC;

-- Overdue payments (full detail)
SELECT
    p.trip_id, c.customer_name, p.invoice_date, p.invoice_amount, p.due_date,
    CAST(julianday('now') - julianday(p.due_date) AS INTEGER) AS days_overdue
FROM payments p
JOIN trips t ON p.trip_id = t.trip_id
JOIN customers c ON t.customer_id = c.customer_id
WHERE p.payment_status = 'Overdue'
ORDER BY days_overdue DESC;


-- =========================
-- POWER BI PREPARATION — VIEWS
-- =========================
-- These views are safe to import directly into Power BI / Excel Power Query.
-- Each view is trip-grain (one row per trip) or a simple aggregate, so
-- Power BI relationships built on top of them won't double-count.

DROP VIEW IF EXISTS vw_trip_profitability;
CREATE VIEW vw_trip_profitability AS
SELECT
    t.trip_id,
    t.dispatch_date,
    strftime('%Y-%m', t.dispatch_date) AS dispatch_month,
    t.vehicle_id,
    t.driver_id,
    t.customer_id,
    t.origin,
    t.destination,
    t.distance_km,
    t.trip_status,
    t.freight_revenue,
    COALESCE(e.total_expense, 0) AS total_expense,
    ROUND(t.freight_revenue - COALESCE(e.total_expense, 0), 2) AS profit,
    ROUND(
        (t.freight_revenue - COALESCE(e.total_expense, 0)) * 100.0 / NULLIF(t.freight_revenue, 0), 2
    ) AS profit_margin_pct,
    ROUND(COALESCE(e.total_expense, 0) * 1.0 / NULLIF(t.distance_km, 0), 2) AS cost_per_km
FROM trips t
LEFT JOIN (SELECT trip_id, SUM(amount) AS total_expense FROM trip_expenses GROUP BY trip_id) e
    ON t.trip_id = e.trip_id;

DROP VIEW IF EXISTS vw_delivery_performance;
CREATE VIEW vw_delivery_performance AS
SELECT
    t.trip_id,
    t.customer_id,
    t.vehicle_id,
    t.driver_id,
    t.origin,
    t.destination,
    t.dispatch_date,
    t.expected_delivery_date,
    t.actual_delivery_date,
    t.trip_status,
    CASE WHEN t.trip_status = 'Delivered' THEN 1 ELSE 0 END AS is_on_time,
    CASE WHEN t.trip_status = 'Delayed' THEN 1 ELSE 0 END AS is_delayed,
    CASE
        WHEN t.actual_delivery_date IS NOT NULL
        THEN CAST(julianday(t.actual_delivery_date) - julianday(t.expected_delivery_date) AS INTEGER)
        ELSE NULL
    END AS delay_days
FROM trips t;

DROP VIEW IF EXISTS vw_payment_status;
CREATE VIEW vw_payment_status AS
SELECT
    p.payment_id,
    p.trip_id,
    t.customer_id,
    c.customer_name,
    p.invoice_date,
    p.invoice_amount,
    p.due_date,
    p.payment_date,
    p.payment_status,
    CASE WHEN p.payment_status = 'Overdue'
         THEN CAST(julianday('now') - julianday(p.due_date) AS INTEGER)
         ELSE NULL END AS days_overdue
FROM payments p
JOIN trips t ON p.trip_id = t.trip_id
JOIN customers c ON t.customer_id = c.customer_id;

DROP VIEW IF EXISTS vw_vehicle_performance;
CREATE VIEW vw_vehicle_performance AS
SELECT
    v.vehicle_id,
    v.vehicle_number,
    v.vehicle_type,
    v.ownership_type,
    v.status,
    COUNT(t.trip_id) AS trip_count,
    ROUND(COALESCE(SUM(t.freight_revenue), 0), 2) AS total_revenue,
    ROUND(COALESCE(SUM(e.total_expense), 0), 2) AS total_expense,
    ROUND(COALESCE(SUM(t.freight_revenue), 0) - COALESCE(SUM(e.total_expense), 0), 2) AS total_profit,
    ROUND(COALESCE(SUM(t.distance_km), 0), 1) AS total_distance_km,
    ROUND(COALESCE(SUM(e.total_expense), 0) * 1.0 / NULLIF(SUM(t.distance_km), 0), 2) AS cost_per_km
FROM vehicles v
LEFT JOIN trips t ON v.vehicle_id = t.vehicle_id AND t.trip_status <> 'Cancelled'
LEFT JOIN (SELECT trip_id, SUM(amount) AS total_expense FROM trip_expenses GROUP BY trip_id) e
    ON t.trip_id = e.trip_id
GROUP BY v.vehicle_id;

DROP VIEW IF EXISTS vw_customer_performance;
CREATE VIEW vw_customer_performance AS
SELECT
    c.customer_id,
    c.customer_name,
    c.city,
    c.customer_type,
    c.payment_terms_days,
    COUNT(t.trip_id) AS trip_count,
    ROUND(COALESCE(SUM(t.freight_revenue), 0), 2) AS total_revenue,
    ROUND(COALESCE(SUM(CASE WHEN p.payment_status = 'Paid' THEN p.invoice_amount ELSE 0 END), 0), 2) AS total_paid,
    ROUND(COALESCE(SUM(CASE WHEN p.payment_status IN ('Pending','Overdue') THEN p.invoice_amount ELSE 0 END), 0), 2) AS total_outstanding,
    ROUND(COALESCE(SUM(CASE WHEN p.payment_status = 'Overdue' THEN p.invoice_amount ELSE 0 END), 0), 2) AS total_overdue
FROM customers c
LEFT JOIN trips t ON c.customer_id = t.customer_id AND t.trip_status <> 'Cancelled'
LEFT JOIN payments p ON t.trip_id = p.trip_id
GROUP BY c.customer_id;
