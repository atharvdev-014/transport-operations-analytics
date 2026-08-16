"""
validate_database.py
---------------------
Validation checks for transport_operations.db.
Run after create_database.py. Exits non-zero if any check fails.
"""

import sqlite3
import sys

DB_NAME = "transport_operations.db"


def run():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    errors = []

    def check(label, condition, detail=""):
        status = "PASS" if condition else "FAIL"
        print(f"[{status}] {label}" + (f" -- {detail}" if detail and not condition else ""))
        if not condition:
            errors.append(label)

    # 1. All tables exist
    expected_tables = {"vehicles", "drivers", "customers", "trips", "trip_expenses", "payments", "documents"}
    actual_tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    check("All 7 tables exist", expected_tables.issubset(actual_tables), actual_tables)

    # 2. foreign_keys pragma
    fk_status = cur.execute("PRAGMA foreign_keys").fetchone()[0]
    check("Foreign key enforcement is ON", fk_status == 1, f"pragma returned {fk_status}")

    # 3. foreign_key_check - should return zero rows (no violations)
    violations = cur.execute("PRAGMA foreign_key_check").fetchall()
    check("No foreign key violations", len(violations) == 0, violations)

    # 4. Record counts roughly match spec
    counts = {}
    for t in expected_tables:
        counts[t] = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    check("vehicles ~20", counts["vehicles"] == 20, counts["vehicles"])
    check("drivers ~30", counts["drivers"] == 30, counts["drivers"])
    check("customers ~50", counts["customers"] == 50, counts["customers"])
    check("trips ~500", counts["trips"] == 500, counts["trips"])
    check("trip_expenses 1500-2500", 1500 <= counts["trip_expenses"] <= 2500, counts["trip_expenses"])
    check("payments = trips (1:1)", counts["payments"] == counts["trips"], counts["payments"])
    check("documents = trips (1:1)", counts["documents"] == counts["trips"], counts["documents"])

    # 5. Orphan checks (redundant with foreign_key_check but explicit/readable)
    orphan_trips_vehicle = cur.execute(
        "SELECT COUNT(*) FROM trips t LEFT JOIN vehicles v ON t.vehicle_id = v.vehicle_id WHERE v.vehicle_id IS NULL"
    ).fetchone()[0]
    check("No trips with missing vehicle", orphan_trips_vehicle == 0, orphan_trips_vehicle)

    orphan_trips_driver = cur.execute(
        "SELECT COUNT(*) FROM trips t LEFT JOIN drivers d ON t.driver_id = d.driver_id WHERE d.driver_id IS NULL"
    ).fetchone()[0]
    check("No trips with missing driver", orphan_trips_driver == 0, orphan_trips_driver)

    orphan_trips_customer = cur.execute(
        "SELECT COUNT(*) FROM trips t LEFT JOIN customers c ON t.customer_id = c.customer_id WHERE c.customer_id IS NULL"
    ).fetchone()[0]
    check("No trips with missing customer", orphan_trips_customer == 0, orphan_trips_customer)

    orphan_expenses = cur.execute(
        "SELECT COUNT(*) FROM trip_expenses e LEFT JOIN trips t ON e.trip_id = t.trip_id WHERE t.trip_id IS NULL"
    ).fetchone()[0]
    check("No orphan trip_expenses", orphan_expenses == 0, orphan_expenses)

    trips_without_payment = cur.execute(
        "SELECT COUNT(*) FROM trips t LEFT JOIN payments p ON t.trip_id = p.trip_id WHERE p.trip_id IS NULL"
    ).fetchone()[0]
    check("Every trip has a payment record", trips_without_payment == 0, trips_without_payment)

    trips_without_document = cur.execute(
        "SELECT COUNT(*) FROM trips t LEFT JOIN documents doc ON t.trip_id = doc.trip_id WHERE doc.trip_id IS NULL"
    ).fetchone()[0]
    check("Every trip has a document record", trips_without_document == 0, trips_without_document)

    # 6. No duplicate primary keys / unique constraint sanity
    for table, pk in [
        ("vehicles", "vehicle_id"), ("drivers", "driver_id"), ("customers", "customer_id"),
        ("trips", "trip_id"), ("trip_expenses", "expense_id"), ("payments", "payment_id"),
        ("documents", "document_id"),
    ]:
        total = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        distinct = cur.execute(f"SELECT COUNT(DISTINCT {pk}) FROM {table}").fetchone()[0]
        check(f"{table}.{pk} has no duplicates", total == distinct, f"{total} rows vs {distinct} distinct")

    dup_vehicle_numbers = cur.execute(
        "SELECT COUNT(*) FROM (SELECT vehicle_number FROM vehicles GROUP BY vehicle_number HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    check("vehicle_number is unique", dup_vehicle_numbers == 0, dup_vehicle_numbers)

    dup_payment_trip = cur.execute(
        "SELECT COUNT(*) FROM (SELECT trip_id FROM payments GROUP BY trip_id HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    check("payments.trip_id is unique (1 payment per trip)", dup_payment_trip == 0, dup_payment_trip)

    dup_doc_trip = cur.execute(
        "SELECT COUNT(*) FROM (SELECT trip_id FROM documents GROUP BY trip_id HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    check("documents.trip_id is unique (1 document set per trip)", dup_doc_trip == 0, dup_doc_trip)

    # 7. Date consistency: actual_delivery_date >= dispatch_date when present
    bad_dates = cur.execute(
        "SELECT COUNT(*) FROM trips WHERE actual_delivery_date IS NOT NULL AND actual_delivery_date < dispatch_date"
    ).fetchone()[0]
    check("actual_delivery_date >= dispatch_date (when present)", bad_dates == 0, bad_dates)

    bad_expected = cur.execute(
        "SELECT COUNT(*) FROM trips WHERE expected_delivery_date < dispatch_date"
    ).fetchone()[0]
    check("expected_delivery_date >= dispatch_date", bad_expected == 0, bad_expected)

    # 8. In Transit / Cancelled trips should not have an actual delivery date
    bad_status_dates = cur.execute(
        "SELECT COUNT(*) FROM trips WHERE trip_status IN ('In Transit','Cancelled') AND actual_delivery_date IS NOT NULL"
    ).fetchone()[0]
    check("In Transit / Cancelled trips have no actual_delivery_date", bad_status_dates == 0, bad_status_dates)

    delivered_missing_date = cur.execute(
        "SELECT COUNT(*) FROM trips WHERE trip_status IN ('Delivered','Delayed') AND actual_delivery_date IS NULL"
    ).fetchone()[0]
    check("Delivered / Delayed trips have an actual_delivery_date", delivered_missing_date == 0, delivered_missing_date)

    # 9. payments.due_date = invoice_date + customer payment_terms_days (spot check via SQL)
    mismatched_due_dates = cur.execute(
        """
        SELECT COUNT(*) FROM payments p
        JOIN trips t ON p.trip_id = t.trip_id
        JOIN customers c ON t.customer_id = c.customer_id
        WHERE p.invoice_date IS NOT NULL
          AND julianday(p.due_date) - julianday(p.invoice_date) <> c.payment_terms_days
        """
    ).fetchone()[0]
    check("payments.due_date matches invoice_date + customer terms", mismatched_due_dates == 0, mismatched_due_dates)

    # 10. Overdue/Paid payment_date sanity: paid trips must have a payment_date, pending/overdue must not
    bad_paid = cur.execute("SELECT COUNT(*) FROM payments WHERE payment_status = 'Paid' AND payment_date IS NULL").fetchone()[0]
    check("Paid payments have a payment_date", bad_paid == 0, bad_paid)

    bad_pending = cur.execute(
        "SELECT COUNT(*) FROM payments WHERE payment_status IN ('Pending','Overdue') AND payment_date IS NOT NULL"
    ).fetchone()[0]
    check("Pending/Overdue payments have no payment_date", bad_pending == 0, bad_pending)

    # 11. No negative amounts
    neg_revenue = cur.execute("SELECT COUNT(*) FROM trips WHERE freight_revenue < 0").fetchone()[0]
    check("No negative freight_revenue", neg_revenue == 0, neg_revenue)

    neg_expense = cur.execute("SELECT COUNT(*) FROM trip_expenses WHERE amount < 0").fetchone()[0]
    check("No negative expense amounts", neg_expense == 0, neg_expense)

    # 12. document_status is consistent with the 4 flags
    bad_doc_status = cur.execute(
        """
        SELECT COUNT(*) FROM documents
        WHERE (invoice_available + eway_bill_available + pod_available + lr_copy_available = 4 AND document_status <> 'Complete')
           OR (invoice_available + eway_bill_available + pod_available + lr_copy_available = 0 AND document_status <> 'Missing')
           OR (invoice_available + eway_bill_available + pod_available + lr_copy_available BETWEEN 1 AND 3 AND document_status <> 'Incomplete')
        """
    ).fetchone()[0]
    check("document_status matches the 4 availability flags", bad_doc_status == 0, bad_doc_status)

    # 13. There IS variation - not everything is perfect (business requirement)
    delayed_count = cur.execute("SELECT COUNT(*) FROM trips WHERE trip_status = 'Delayed'").fetchone()[0]
    check("Dataset contains delayed trips", delayed_count > 0, delayed_count)

    missing_pod = cur.execute("SELECT COUNT(*) FROM documents WHERE pod_available = 0").fetchone()[0]
    check("Dataset contains trips with missing POD", missing_pod > 0, missing_pod)

    overdue_count = cur.execute("SELECT COUNT(*) FROM payments WHERE payment_status = 'Overdue'").fetchone()[0]
    check("Dataset contains overdue payments", overdue_count > 0, overdue_count)

    pending_count = cur.execute("SELECT COUNT(*) FROM payments WHERE payment_status = 'Pending'").fetchone()[0]
    check("Dataset contains pending payments", pending_count > 0, pending_count)

    paid_count = cur.execute("SELECT COUNT(*) FROM payments WHERE payment_status = 'Paid'").fetchone()[0]
    check("Dataset contains fully paid payments", paid_count > 0, paid_count)

    # 14. Profit sanity: total revenue > total expenses (company should be broadly profitable but not by an absurd margin)
    total_revenue = cur.execute("SELECT SUM(freight_revenue) FROM trips").fetchone()[0]
    total_expenses = cur.execute("SELECT SUM(amount) FROM trip_expenses").fetchone()[0]
    margin_pct = (total_revenue - total_expenses) / total_revenue * 100
    check(
        "Overall profit margin is realistic (between 5% and 40%)",
        5 <= margin_pct <= 40,
        f"{margin_pct:.1f}%",
    )

    # 15. Revenue broadly increases with distance (correlation should be positive)
    rows = cur.execute("SELECT distance_km, freight_revenue FROM trips WHERE trip_status <> 'Cancelled'").fetchall()
    n = len(rows)
    mean_x = sum(r[0] for r in rows) / n
    mean_y = sum(r[1] for r in rows) / n
    cov = sum((r[0] - mean_x) * (r[1] - mean_y) for r in rows) / n
    std_x = (sum((r[0] - mean_x) ** 2 for r in rows) / n) ** 0.5
    std_y = (sum((r[1] - mean_y) ** 2 for r in rows) / n) ** 0.5
    corr = cov / (std_x * std_y)
    check("Revenue correlates positively with distance", corr > 0.5, f"correlation={corr:.2f}")

    print()
    if errors:
        print(f"VALIDATION FAILED - {len(errors)} check(s) failed:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("ALL VALIDATION CHECKS PASSED.")

    conn.close()


if __name__ == "__main__":
    run()
