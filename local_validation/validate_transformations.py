"""
Local validation harness for the dbt pilot.

This does NOT replace dbt -- it exists so you can prove the transformation
LOGIC is correct (using the same seed CSVs) without needing a live Snowflake
account or the dbt CLI installed. Load the CSVs into SQLite, run SQL that
mirrors the dbt models statement-for-statement, and print the results.

Run it with: python3 validate_transformations.py
"""

import sqlite3
import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEDS_DIR = os.path.join(BASE_DIR, "..", "seeds")

conn = sqlite3.connect(":memory:")
cur = conn.cursor()


def load_csv_to_table(csv_path, table_name):
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        cols = reader.fieldnames

    col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
    cur.execute(f'CREATE TABLE "{table_name}" ({col_defs})')

    placeholders = ", ".join("?" for _ in cols)
    cur.executemany(
        f'INSERT INTO "{table_name}" VALUES ({placeholders})',
        [[r[c] for c in cols] for r in rows],
    )
    conn.commit()


load_csv_to_table(os.path.join(SEEDS_DIR, "raw_sales_orders.csv"), "raw_sales_orders")
load_csv_to_table(os.path.join(SEEDS_DIR, "raw_inventory.csv"), "raw_inventory")

# ---- stg_sales_orders (mirrors models/staging/stg_sales_orders.sql) ----
cur.execute("""
    CREATE VIEW stg_sales_orders AS
    SELECT
        order_id,
        order_date,
        customer_id,
        TRIM(customer_name) AS customer_name,
        region,
        product_sku AS sku,
        product_family,
        channel,
        sales_rep,
        CAST(quantity AS INTEGER) AS quantity,
        CAST(unit_price AS REAL) AS unit_price,
        CAST(unit_cost AS REAL) AS unit_cost,
        CAST(quantity AS INTEGER) * CAST(unit_price AS REAL) AS extended_revenue,
        CAST(quantity AS INTEGER) * CAST(unit_cost AS REAL) AS extended_cost,
        (CAST(quantity AS INTEGER) * CAST(unit_price AS REAL))
            - (CAST(quantity AS INTEGER) * CAST(unit_cost AS REAL)) AS extended_margin
    FROM raw_sales_orders
""")

# ---- stg_inventory (mirrors models/staging/stg_inventory.sql) ----
cur.execute("""
    CREATE VIEW stg_inventory AS
    SELECT
        sku,
        product_family,
        warehouse,
        CAST(on_hand_qty AS INTEGER) AS on_hand_qty,
        CAST(unit_cost AS REAL) AS unit_cost,
        CAST(reorder_point AS INTEGER) AS reorder_point,
        CAST(lead_time_days AS INTEGER) AS lead_time_days,
        last_received_date,
        CAST(on_hand_qty AS INTEGER) * CAST(unit_cost AS REAL) AS inventory_value,
        CASE WHEN CAST(on_hand_qty AS INTEGER) <= CAST(reorder_point AS INTEGER)
             THEN 1 ELSE 0 END AS is_below_reorder_point
    FROM raw_inventory
""")

# ---- dim_customer (mirrors models/marts/dim_customer.sql) ----
cur.execute("""
    CREATE VIEW dim_customer AS
    SELECT
        customer_id AS customer_key,
        customer_id,
        customer_name,
        region,
        MIN(order_date) AS first_order_date,
        MAX(order_date) AS last_order_date,
        COUNT(DISTINCT order_id) AS lifetime_order_count
    FROM stg_sales_orders
    GROUP BY customer_id, customer_name, region
""")

# ---- dim_product (mirrors models/marts/dim_product.sql) ----
cur.execute("""
    CREATE VIEW dim_product AS
    SELECT sku AS product_key, sku, product_family FROM stg_sales_orders
    UNION
    SELECT sku AS product_key, sku, product_family FROM stg_inventory
""")

# ---- fct_sales (mirrors models/marts/fct_sales.sql) ----
cur.execute("""
    CREATE VIEW fct_sales AS
    SELECT
        o.order_id, o.order_date, c.customer_key, p.product_key,
        o.region, o.channel, o.sales_rep, o.quantity, o.unit_price, o.unit_cost,
        o.extended_revenue, o.extended_cost, o.extended_margin,
        o.extended_margin / NULLIF(o.extended_revenue, 0) AS margin_pct
    FROM stg_sales_orders o
    LEFT JOIN dim_customer c ON o.customer_id = c.customer_id
    LEFT JOIN dim_product p ON o.sku = p.sku
""")

# ---- fct_inventory (mirrors models/marts/fct_inventory.sql) ----
cur.execute("""
    CREATE VIEW fct_inventory AS
    SELECT
        i.sku, p.product_key, i.warehouse, i.on_hand_qty, i.unit_cost,
        i.inventory_value, i.reorder_point, i.lead_time_days,
        i.last_received_date, i.is_below_reorder_point
    FROM stg_inventory i
    LEFT JOIN dim_product p ON i.sku = p.sku
""")

print("=" * 70)
print("dbt-equivalent TESTS (unique / not_null / relationships)")
print("=" * 70)

tests = [
    ("unique order_id in fct_sales",
     "SELECT order_id, COUNT(*) c FROM fct_sales GROUP BY order_id HAVING c > 1"),
    ("not_null customer_key in fct_sales",
     "SELECT * FROM fct_sales WHERE customer_key IS NULL"),
    ("not_null product_key in fct_sales",
     "SELECT * FROM fct_sales WHERE product_key IS NULL"),
    ("relationships: every fct_sales.customer_key exists in dim_customer",
     """SELECT f.customer_key FROM fct_sales f
        LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
        WHERE c.customer_key IS NULL"""),
    ("relationships: every fct_inventory.product_key exists in dim_product",
     """SELECT f.product_key FROM fct_inventory f
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        WHERE p.product_key IS NULL"""),
]

all_passed = True
for name, sql in tests:
    cur.execute(sql)
    failures = cur.fetchall()
    status = "PASS" if len(failures) == 0 else f"FAIL ({len(failures)} rows)"
    if failures:
        all_passed = False
    print(f"  [{status}] {name}")

print()
print("=" * 70)
print("SAMPLE OUTPUT: fct_sales (top 5 by extended_revenue)")
print("=" * 70)
cur.execute("""
    SELECT order_id, region, channel, sales_rep, extended_revenue,
           ROUND(margin_pct * 100, 1) AS margin_pct
    FROM fct_sales
    ORDER BY extended_revenue DESC
    LIMIT 5
""")
for row in cur.fetchall():
    print(f"  {row[0]:10} {row[1]:10} {row[2]:12} {row[3]:12} "
          f"rev=${row[4]:>10,.0f}  margin={row[5]}%")

print()
print("=" * 70)
print("SAMPLE OUTPUT: fct_inventory flagged below reorder point")
print("=" * 70)
cur.execute("""
    SELECT sku, warehouse, on_hand_qty, reorder_point, inventory_value
    FROM fct_inventory
    WHERE is_below_reorder_point = 1
    ORDER BY inventory_value DESC
""")
for row in cur.fetchall():
    print(f"  {row[0]:10} {row[1]:15} on_hand={row[2]:>3} reorder_pt={row[3]:>3} "
          f"value=${row[4]:>10,.0f}")

print()
print("=" * 70)
print("BUSINESS SUMMARY: total inventory value & revenue (proof the model rolls up)")
print("=" * 70)
cur.execute("SELECT ROUND(SUM(inventory_value), 2) FROM fct_inventory")
print(f"  Total inventory value (seed sample): ${cur.fetchone()[0]:,.2f}")
cur.execute("SELECT ROUND(SUM(extended_revenue), 2) FROM fct_sales")
print(f"  Total sales revenue (seed sample):    ${cur.fetchone()[0]:,.2f}")
cur.execute("SELECT ROUND(AVG(margin_pct) * 100, 1) FROM fct_sales")
print(f"  Average margin % (seed sample):        {cur.fetchone()[0]}%")

print()
print("Overall result:", "ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED")
