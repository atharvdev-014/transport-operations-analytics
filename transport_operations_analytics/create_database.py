"""
create_database.py
-------------------
Transport Operations Analytics System - Database Build Script

Creates transport_operations.db (SQLite) with a 7-table schema modelling a
medium-sized Indian road transportation company, and populates it with
realistic (but 100% fictional) synthetic operational data.

Safe to re-run: the script always DROPs and recreates the schema, then
regenerates the data using a FIXED random seed. That means every run
produces the exact same dataset (no duplicate/accumulating rows), while
still being driven entirely by code (nothing is hand-typed row by row).

Usage:
    python3 create_database.py
"""

import sqlite3
import random
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_NAME = "transport_operations.db"
RANDOM_SEED = 42
TODAY = date(2026, 8, 1)          # fixed "as of" date so the dataset is reproducible
DATA_WINDOW_DAYS = 540            # ~18 months of trip history

N_VEHICLES = 20
N_DRIVERS = 30
N_CUSTOMERS = 50
N_TRIPS = 500

random.seed(RANDOM_SEED)

# ---------------------------------------------------------------------------
# Reference / lookup data
# ---------------------------------------------------------------------------

VEHICLE_TYPES = {
    # type: (capacity_tons_range, base_freight_rate_per_km, diesel_rate_per_km)
    "10 Tyre":   ((9, 12),  (30, 36), (7.0, 8.0)),
    "12 Tyre":   ((14, 18), (36, 43), (7.8, 8.8)),
    "14 Tyre":   ((18, 22), (42, 50), (8.5, 9.5)),
    "16 Tyre":   ((22, 28), (48, 57), (9.2, 10.5)),
    "Container": ((25, 32), (52, 62), (9.5, 11.0)),
}

OWNERSHIP_TYPES = ["Owned", "Leased", "Market/Attached"]
VEHICLE_STATUS_WEIGHTS = [("Active", 0.80), ("Under Maintenance", 0.12), ("Inactive", 0.08)]

DRIVER_FIRST_NAMES = [
    "Ramesh", "Suresh", "Mahesh", "Ganesh", "Rajesh", "Vikram", "Sanjay", "Anil",
    "Sunil", "Ashok", "Pravin", "Dinesh", "Santosh", "Ravindra", "Vijay", "Manoj",
    "Deepak", "Prakash", "Ramchandra", "Balaji", "Vasant", "Shivaji", "Gopal",
    "Nitin", "Kailash", "Arjun", "Bhushan", "Yogesh", "Chetan", "Rahul",
]
DRIVER_LAST_NAMES = [
    "Patil", "Sharma", "Deshmukh", "Kulkarni", "Jadhav", "More", "Pawar",
    "Chavan", "Shinde", "Gaikwad", "Yadav", "Singh", "Kumar", "Rao", "Reddy",
    "Naik", "Mane", "Bhosale", "Salunkhe", "Waghmare",
]
LICENSE_TYPES = ["HMV", "LMV+HMV", "Heavy Goods Vehicle"]
DRIVER_STATUS_WEIGHTS = [("Active", 0.82), ("On Leave", 0.10), ("Inactive", 0.08)]

CUSTOMER_TYPES = ["Manufacturing", "FMCG", "E-commerce", "Pharma", "Textile", "Retail", "Automotive", "Agro"]
CUSTOMER_NAME_PREFIXES = [
    "Shree", "Om", "Jai", "National", "United", "Bharat", "Sai", "Krishna", "Vishal",
    "Metro", "Prime", "Apex", "Golden", "Sunrise", "Royal", "Reliable", "Kaveri",
    "Deccan", "Western", "Konkan", "Ganges", "Vindhya", "Sahyadri", "Malabar",
]
CUSTOMER_NAME_SUFFIXES = [
    "Industries", "Enterprises", "Traders", "Logistics Pvt Ltd", "Textiles",
    "Agro Foods", "Pharma Ltd", "Motors", "Retail Chain", "Distributors",
    "Manufacturing Co", "Exports", "Impex", "Corporation", "Merchandise",
]
PAYMENT_TERMS_OPTIONS = [0, 15, 30, 45, 60]
PAYMENT_TERMS_WEIGHTS = [0.05, 0.20, 0.45, 0.20, 0.10]

# City -> approximate one-way road distance (km) pairs used to build realistic routes
CITY_DISTANCES = {
    ("Mumbai", "Pune"): 150,
    ("Mumbai", "Nashik"): 165,
    ("Mumbai", "Surat"): 285,
    ("Mumbai", "Ahmedabad"): 530,
    ("Mumbai", "Indore"): 585,
    ("Mumbai", "Nagpur"): 830,
    ("Mumbai", "Aurangabad"): 335,
    ("Mumbai", "Bengaluru"): 985,
    ("Mumbai", "Hyderabad"): 710,
    ("Mumbai", "Delhi"): 1400,
    ("Mumbai", "Jaipur"): 1155,
    ("Pune", "Nashik"): 210,
    ("Pune", "Aurangabad"): 235,
    ("Pune", "Surat"): 435,
    ("Pune", "Bengaluru"): 840,
    ("Pune", "Hyderabad"): 560,
    ("Pune", "Nagpur"): 700,
    ("Pune", "Indore"): 590,
    ("Nashik", "Aurangabad"): 210,
    ("Nashik", "Indore"): 400,
    ("Nashik", "Surat"): 270,
    ("Nagpur", "Hyderabad"): 500,
    ("Nagpur", "Indore"): 435,
    ("Nagpur", "Aurangabad"): 500,
    ("Surat", "Ahmedabad"): 265,
    ("Surat", "Indore"): 400,
    ("Ahmedabad", "Indore"): 405,
    ("Ahmedabad", "Jaipur"): 660,
    ("Ahmedabad", "Delhi"): 950,
    ("Indore", "Bengaluru"): 1200,
    ("Indore", "Hyderabad"): 700,
    ("Bengaluru", "Hyderabad"): 570,
    ("Bengaluru", "Chennai"): 345,
    ("Hyderabad", "Chennai"): 625,
    ("Delhi", "Jaipur"): 280,
    ("Aurangabad", "Hyderabad"): 500,
    ("Aurangabad", "Indore"): 460,
    ("Nashik", "Ahmedabad"): 460,
}
ALL_CITIES = sorted({c for pair in CITY_DISTANCES for c in pair})

EXPENSE_TYPES = ["Diesel", "Toll", "Driver Allowance", "Loading", "Unloading", "Maintenance", "Other"]

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def weighted_choice(options_with_weights):
    options = [o for o, _ in options_with_weights]
    weights = [w for _, w in options_with_weights]
    return random.choices(options, weights=weights, k=1)[0]


def random_date_in_window(start_days_ago, end_days_ago):
    """Return a random date between (today - start_days_ago) and (today - end_days_ago)."""
    lo = TODAY - timedelta(days=start_days_ago)
    hi = TODAY - timedelta(days=end_days_ago)
    delta = (hi - lo).days
    return lo + timedelta(days=random.randint(0, max(delta, 0)))


def route_distance(origin, destination):
    key = (origin, destination)
    if key in CITY_DISTANCES:
        return CITY_DISTANCES[key]
    key2 = (destination, origin)
    if key2 in CITY_DISTANCES:
        return CITY_DISTANCES[key2]
    return None


def random_route():
    pair = random.choice(list(CITY_DISTANCES.keys()))
    if random.random() < 0.5:
        origin, destination = pair
    else:
        destination, origin = pair
    return origin, destination, CITY_DISTANCES[pair]


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE vehicles (
    vehicle_id      TEXT PRIMARY KEY,
    vehicle_number  TEXT UNIQUE NOT NULL,
    vehicle_type    TEXT,
    capacity_tons   REAL,
    ownership_type  TEXT,
    status          TEXT
);

CREATE TABLE drivers (
    driver_id           TEXT PRIMARY KEY,
    driver_name         TEXT NOT NULL,
    phone               TEXT,
    license_type        TEXT,
    assigned_vehicle_id TEXT,
    status              TEXT,
    FOREIGN KEY (assigned_vehicle_id) REFERENCES vehicles(vehicle_id)
);

CREATE TABLE customers (
    customer_id         TEXT PRIMARY KEY,
    customer_name        TEXT NOT NULL,
    city                 TEXT,
    customer_type         TEXT,
    payment_terms_days    INTEGER
);

CREATE TABLE trips (
    trip_id                 TEXT PRIMARY KEY,
    vehicle_id               TEXT NOT NULL,
    driver_id                 TEXT NOT NULL,
    customer_id                TEXT NOT NULL,
    origin                      TEXT,
    destination                  TEXT,
    dispatch_date                 TEXT,
    expected_delivery_date         TEXT,
    actual_delivery_date            TEXT,
    distance_km                      REAL,
    freight_revenue                   REAL,
    trip_status                        TEXT,
    payment_status                      TEXT,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE trip_expenses (
    expense_id    TEXT PRIMARY KEY,
    trip_id        TEXT NOT NULL,
    expense_type    TEXT,
    amount            REAL,
    expense_date       TEXT,
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
);

CREATE TABLE payments (
    payment_id      TEXT PRIMARY KEY,
    trip_id          TEXT UNIQUE NOT NULL,
    invoice_date      TEXT,
    invoice_amount     REAL,
    due_date            TEXT,
    payment_date         TEXT,
    payment_status        TEXT,
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
);

CREATE TABLE documents (
    document_id           TEXT PRIMARY KEY,
    trip_id                 TEXT UNIQUE NOT NULL,
    invoice_available        INTEGER,
    eway_bill_available        INTEGER,
    pod_available                INTEGER,
    lr_copy_available             INTEGER,
    document_status                TEXT,
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
);
"""

# NOTE: the extra internal spacing above is purely cosmetic/harmless to SQLite.


def build_schema(conn):
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS documents;
        DROP TABLE IF EXISTS payments;
        DROP TABLE IF EXISTS trip_expenses;
        DROP TABLE IF EXISTS trips;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS drivers;
        DROP TABLE IF EXISTS vehicles;
        """
    )
    cur.executescript(SCHEMA_SQL)
    conn.commit()


# ---------------------------------------------------------------------------
# Data generators
# ---------------------------------------------------------------------------


def generate_vehicles():
    rows = []
    type_cycle = list(VEHICLE_TYPES.keys())
    for i in range(1, N_VEHICLES + 1):
        vehicle_id = f"VEH{i:03d}"
        vtype = type_cycle[(i - 1) % len(type_cycle)]
        cap_range, _, _ = VEHICLE_TYPES[vtype]
        capacity = round(random.uniform(*cap_range), 1)
        state_code = random.choice(["MH", "MH", "MH", "GJ", "KA", "TS", "MP"])
        vehicle_number = f"{state_code}{random.randint(1,49):02d}{random.choice('ABCDEFGH')}{random.choice('TXYZ')}{random.randint(1000,9999)}"
        ownership = weighted_choice([("Owned", 0.55), ("Leased", 0.25), ("Market/Attached", 0.20)])
        status = weighted_choice(VEHICLE_STATUS_WEIGHTS)
        rows.append((vehicle_id, vehicle_number, vtype, capacity, ownership, status))
    return rows


def generate_drivers(vehicle_rows):
    rows = []
    vehicle_ids = [v[0] for v in vehicle_rows]
    # Not every driver gets a permanently assigned vehicle (some are pool/spare drivers)
    assignable_vehicle_ids = vehicle_ids.copy()
    random.shuffle(assignable_vehicle_ids)

    used_names = set()
    for i in range(1, N_DRIVERS + 1):
        driver_id = f"DRV{i:03d}"
        while True:
            name = f"{random.choice(DRIVER_FIRST_NAMES)} {random.choice(DRIVER_LAST_NAMES)}"
            if name not in used_names:
                used_names.add(name)
                break
        phone = f"9{random.randint(100000000, 999999999)}"
        license_type = weighted_choice([(LICENSE_TYPES[0], 0.5), (LICENSE_TYPES[1], 0.3), (LICENSE_TYPES[2], 0.2)])
        # ~75% of drivers have a home/assigned vehicle; some overlap allowed (multiple drivers per vehicle, e.g. shifts)
        if i <= int(N_DRIVERS * 0.75):
            assigned_vehicle_id = assignable_vehicle_ids[(i - 1) % len(assignable_vehicle_ids)]
        else:
            assigned_vehicle_id = None
        status = weighted_choice(DRIVER_STATUS_WEIGHTS)
        rows.append((driver_id, name, phone, license_type, assigned_vehicle_id, status))
    return rows


def generate_customers():
    rows = []
    used_names = set()
    for i in range(1, N_CUSTOMERS + 1):
        customer_id = f"CUS{i:03d}"
        while True:
            name = f"{random.choice(CUSTOMER_NAME_PREFIXES)} {random.choice(CUSTOMER_NAME_SUFFIXES)}"
            if name not in used_names:
                used_names.add(name)
                break
        city = random.choice(ALL_CITIES)
        ctype = random.choice(CUSTOMER_TYPES)
        terms = weighted_choice(list(zip(PAYMENT_TERMS_OPTIONS, PAYMENT_TERMS_WEIGHTS)))
        rows.append((customer_id, name, city, ctype, terms))
    return rows


def generate_trips(vehicle_rows, driver_rows, customer_rows):
    rows = []
    vehicle_ids = [v[0] for v in vehicle_rows]
    vehicle_by_id = {v[0]: v for v in vehicle_rows}
    driver_ids = [d[0] for d in driver_rows]
    customer_ids = [c[0] for c in customer_rows]
    customer_by_id = {c[0]: c for c in customer_rows}

    for i in range(1, N_TRIPS + 1):
        trip_id = f"TRP{i:05d}"
        vehicle_id = random.choice(vehicle_ids)
        driver_id = random.choice(driver_ids)
        customer_id = random.choice(customer_ids)

        origin, destination, distance = random_route()
        distance = round(distance * random.uniform(0.97, 1.05), 1)  # small realistic variation

        # decide the status bucket first, since it drives dates/revenue logic
        status = weighted_choice(
            [("Delivered", 0.62), ("Delayed", 0.16), ("In Transit", 0.13), ("Cancelled", 0.09)]
        )

        if status == "In Transit":
            dispatch_date = random_date_in_window(9, 0)  # dispatched in the last ~9 days
        else:
            dispatch_date = random_date_in_window(DATA_WINDOW_DAYS, 10)

        avg_speed_kmpd = random.uniform(320, 420)  # km covered per day incl. loading/unloading/rest
        transit_days = max(1, round(distance / avg_speed_kmpd))
        expected_delivery_date = dispatch_date + timedelta(days=transit_days)

        actual_delivery_date = None
        if status == "Delivered":
            # on-time or early
            offset = random.randint(-1, 0)
            actual_delivery_date = expected_delivery_date + timedelta(days=offset)
            if actual_delivery_date < dispatch_date:
                actual_delivery_date = dispatch_date
        elif status == "Delayed":
            offset = random.randint(1, 6)
            actual_delivery_date = expected_delivery_date + timedelta(days=offset)
        elif status == "Cancelled":
            actual_delivery_date = None
        else:  # In Transit
            actual_delivery_date = None

        # don't let dates go beyond "today"
        if actual_delivery_date and actual_delivery_date > TODAY:
            actual_delivery_date = TODAY

        vtype = vehicle_by_id[vehicle_id][2]
        capacity = vehicle_by_id[vehicle_id][3]
        _, rate_range, _ = VEHICLE_TYPES[vtype]
        rate_per_km = random.uniform(*rate_range) * (0.9 + capacity / 60)  # capacity nudges rate up
        freight_revenue = round(distance * rate_per_km * random.uniform(0.95, 1.1), 0)

        if status == "Cancelled":
            # cancelled trips generate little to no revenue (nominal cancellation charge only)
            freight_revenue = round(freight_revenue * random.uniform(0.0, 0.15), 0)

        # payment_status placeholder here; the real source of truth is the payments table,
        # this column is kept in sync when payments are generated below.
        payment_status_placeholder = "Pending"

        rows.append(
            [
                trip_id, vehicle_id, driver_id, customer_id, origin, destination,
                dispatch_date.isoformat(), expected_delivery_date.isoformat(),
                actual_delivery_date.isoformat() if actual_delivery_date else None,
                distance, freight_revenue, status, payment_status_placeholder,
            ]
        )
    return rows


def generate_trip_expenses(trip_rows):
    rows = []
    expense_counter = 1
    for trip in trip_rows:
        trip_id, vehicle_id, driver_id, customer_id, origin, destination, dispatch_date, \
            expected_dd, actual_dd, distance, revenue, status, _ = trip

        dispatch_dt = date.fromisoformat(dispatch_date)

        if status == "Cancelled":
            # cancelled trips still incur a small loading/admin cost, nothing else
            n_diesel_days = 0
            possible_types = [("Loading", 0.6, (300, 800))]
        else:
            possible_types = [
                ("Diesel", 1.0, None),               # handled specially below (distance based)
                ("Toll", 0.85, (distance * 2.8, distance * 4.2)),
                ("Driver Allowance", 0.95, (1200, 3600)),
                ("Loading", 0.9, (900, 3800)),
                ("Unloading", 0.85, (800, 3400)),
                ("Maintenance", 0.28, (2200, 18000)),
                ("Other", 0.30, (400, 3200)),
            ]

        for etype, prob, amt_range in possible_types:
            if random.random() > prob:
                continue
            expense_id = f"EXP{expense_counter:06d}"
            expense_counter += 1

            if etype == "Diesel":
                amount = round(distance * random.uniform(22.0, 29.0), 2)
            else:
                amount = round(random.uniform(*amt_range), 2)

            exp_date = dispatch_dt + timedelta(days=random.randint(0, max(1, (date.fromisoformat(actual_dd) - dispatch_dt).days if actual_dd else 1)))
            if exp_date > TODAY:
                exp_date = TODAY

            rows.append((expense_id, trip_id, etype, amount, exp_date.isoformat()))
    return rows


def generate_payments(trip_rows, customer_rows):
    customer_terms = {c[0]: c[4] for c in customer_rows}
    rows = []
    trip_status_updates = {}  # trip_id -> final payment_status (synced back into trips)

    for idx, trip in enumerate(trip_rows, start=1):
        trip_id, vehicle_id, driver_id, customer_id, origin, destination, dispatch_date, \
            expected_dd, actual_dd, distance, revenue, status, _ = trip

        payment_id = f"PAY{idx:05d}"

        if status == "Cancelled":
            invoice_amount = 0.0
            invoice_date_val = None
            due_date_val = None
            payment_date_val = None
            pay_status = "Not Applicable"
        else:
            # invoice raised a couple of days after delivery (or after dispatch if still moving)
            ref_date = date.fromisoformat(actual_dd) if actual_dd else date.fromisoformat(expected_dd)
            invoice_dt = ref_date + timedelta(days=random.randint(0, 3))
            if invoice_dt > TODAY:
                invoice_dt = TODAY
            invoice_amount = revenue

            terms = customer_terms.get(customer_id, 30)
            due_dt = invoice_dt + timedelta(days=terms)

            if status == "In Transit":
                # not yet invoiced/paid in most cases
                pay_status = "Pending"
                payment_date_val = None
            else:
                roll = random.random()
                if due_dt >= TODAY:
                    # not yet due
                    if roll < 0.55:
                        pay_status = "Paid"
                        payment_date_val = invoice_dt + timedelta(days=random.randint(1, max(1, terms)))
                        if payment_date_val > TODAY:
                            payment_date_val = TODAY
                    else:
                        pay_status = "Pending"
                        payment_date_val = None
                else:
                    # due date already passed
                    if roll < 0.62:
                        pay_status = "Paid"
                        payment_date_val = invoice_dt + timedelta(
                            days=random.randint(1, max(1, (due_dt - invoice_dt).days + 10))
                        )
                        if payment_date_val > TODAY:
                            payment_date_val = TODAY
                    else:
                        pay_status = "Overdue"
                        payment_date_val = None

            invoice_date_val = invoice_dt.isoformat()
            due_date_val = due_dt.isoformat()
            payment_date_val = payment_date_val.isoformat() if payment_date_val else None

        trip_status_updates[trip_id] = pay_status
        rows.append(
            (payment_id, trip_id, invoice_date_val, invoice_amount, due_date_val, payment_date_val, pay_status)
        )
    return rows, trip_status_updates


def generate_documents(trip_rows):
    rows = []
    for idx, trip in enumerate(trip_rows, start=1):
        trip_id, vehicle_id, driver_id, customer_id, origin, destination, dispatch_date, \
            expected_dd, actual_dd, distance, revenue, status, _ = trip

        document_id = f"DOC{idx:05d}"

        invoice_avail = 1 if random.random() < 0.93 else 0
        eway_avail = 1 if random.random() < 0.90 else 0

        if status == "Delivered":
            pod_avail = 1 if random.random() < 0.94 else 0
        elif status == "Delayed":
            pod_avail = 1 if random.random() < 0.80 else 0
        elif status == "Cancelled":
            pod_avail = 0
        else:  # In Transit - POD can't exist yet
            pod_avail = 0

        lr_avail = 1 if random.random() < 0.91 else 0

        if status == "Cancelled":
            invoice_avail, eway_avail, lr_avail = 0, 0, 0

        completeness = invoice_avail + eway_avail + pod_avail + lr_avail
        if completeness == 4:
            doc_status = "Complete"
        elif completeness == 0:
            doc_status = "Missing"
        else:
            doc_status = "Incomplete"

        rows.append((document_id, trip_id, invoice_avail, eway_avail, pod_avail, lr_avail, doc_status))
    return rows


# ---------------------------------------------------------------------------
# Main build routine
# ---------------------------------------------------------------------------


def main():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")

    build_schema(conn)
    cur = conn.cursor()

    vehicle_rows = generate_vehicles()
    cur.executemany(
        "INSERT INTO vehicles (vehicle_id, vehicle_number, vehicle_type, capacity_tons, ownership_type, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        vehicle_rows,
    )

    driver_rows = generate_drivers(vehicle_rows)
    cur.executemany(
        "INSERT INTO drivers (driver_id, driver_name, phone, license_type, assigned_vehicle_id, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        driver_rows,
    )

    customer_rows = generate_customers()
    cur.executemany(
        "INSERT INTO customers (customer_id, customer_name, city, customer_type, payment_terms_days) "
        "VALUES (?, ?, ?, ?, ?)",
        customer_rows,
    )

    trip_rows = generate_trips(vehicle_rows, driver_rows, customer_rows)

    # payments are generated first (in memory only) so we can sync the trip-level
    # payment_status column, but they are only INSERTed after the trips row exists
    payment_rows, trip_payment_status = generate_payments(trip_rows, customer_rows)
    for trip in trip_rows:
        trip[-1] = trip_payment_status[trip[0]]

    cur.executemany(
        "INSERT INTO trips (trip_id, vehicle_id, driver_id, customer_id, origin, destination, "
        "dispatch_date, expected_delivery_date, actual_delivery_date, distance_km, freight_revenue, "
        "trip_status, payment_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [tuple(t) for t in trip_rows],
    )

    expense_rows = generate_trip_expenses(trip_rows)
    cur.executemany(
        "INSERT INTO trip_expenses (expense_id, trip_id, expense_type, amount, expense_date) "
        "VALUES (?, ?, ?, ?, ?)",
        expense_rows,
    )

    cur.executemany(
        "INSERT INTO payments (payment_id, trip_id, invoice_date, invoice_amount, due_date, payment_date, payment_status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        payment_rows,
    )

    document_rows = generate_documents(trip_rows)
    cur.executemany(
        "INSERT INTO documents (document_id, trip_id, invoice_available, eway_bill_available, "
        "pod_available, lr_copy_available, document_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        document_rows,
    )

    conn.commit()

    # -----------------------------------------------------------------
    # Basic build-time sanity output
    # -----------------------------------------------------------------
    print("Database build complete.")
    for table in ["vehicles", "drivers", "customers", "trips", "trip_expenses", "payments", "documents"]:
        count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:15s}: {count} rows")

    conn.close()


if __name__ == "__main__":
    main()
