# Transport Operations Analytics

> End-to-end logistics analytics project using **Python, SQLite, SQL and Power BI**.

A portfolio project that models the operations of a medium-sized Indian road
transportation (trucking) company and builds a complete analytics layer on
top of it: a relational database, synthetic operational data, validated SQL
analysis, Python validation scripts, and a multi-page Power BI dashboard.

> **Important:** The dataset is 100% synthetic and fictional. All vehicle
> numbers, driver names, customer names, financial figures and transactions
> are randomly generated for learning and portfolio purposes. They do not
> represent any real company, person or transaction.

---

## 1. Project Purpose

The goal of this project is to demonstrate an end-to-end data analytics
workflow using a realistic transportation and logistics business scenario.

The project covers:

- Database design
- Synthetic data generation
- Data validation using Python
- SQL KPI and business analysis
- Operational performance analysis
- Power BI dashboard development
- Business insight generation

The project focuses on road freight operations because the domain contains
interconnected operational data across vehicles, drivers, customers, trips,
expenses, payments and compliance documentation.

---

## 2. Business Problem

A logistics company runs hundreds of trips across its fleet and needs to
answer questions such as:

- Are we actually making money on freight after fuel, tolls and driver costs?
- Which vehicles and vehicle types are the most profitable?
- Which customers generate the most revenue?
- Are deliveries happening on time?
- Where are delivery delays concentrated?
- How much money is stuck in unpaid invoices?
- Which customers have the highest outstanding and overdue amounts?
- Are trips missing required paperwork such as POD, E-way bill, invoice or
  LR copy?
- How can documentation gaps affect operational control and payment
  collection?

This project creates the data foundation and analytics layer required to
answer these questions.

---

## 3. Technology Stack

| Technology | Purpose |
|---|---|
| **Python** | Synthetic data generation and database validation |
| **SQLite** | Relational operational database |
| **SQL** | KPI calculations and business analysis |
| **Power BI** | Interactive dashboard and visualization |
| **DAX** | Power BI business measures and KPIs |
| **CSV** | Data exchange and Power BI-ready datasets |

---

## 4. Database Structure

**Database:** `transport_operations.db`  
**Database type:** SQLite  
**Build script:** `create_database.py`

The database contains operational entities covering vehicles, drivers,
customers, trips, expenses, payments and documentation.

### Core Tables

| Table | Grain | Row Count |
|---|---|---:|
| `vehicles` | 1 row per truck | 20 |
| `drivers` | 1 row per driver | 30 |
| `customers` | 1 row per client company | 50 |
| `trips` | 1 row per trip | 500 |
| `trip_expenses` | 1 row per trip expense line | ~2,400 |
| `payments` | 1 row per trip invoice | 500 |
| `documents` | 1 row per trip document checklist | 500 |

### Relationships

```text
vehicles ──┐
           ├──< trips >──┬──< trip_expenses
drivers ───┤             ├──< payments
           │             └──< documents
customers ─┘