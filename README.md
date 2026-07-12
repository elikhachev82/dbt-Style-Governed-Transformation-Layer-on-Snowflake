# Project 1: dbt-Style Governed Transformation Layer on Snowflake

## What was actually built
A working dbt project (`dbt_project.yml`, seeds, staging models, mart models,
`schema.yml` tests) that replaces one existing Power Query pipeline — the
sales + inventory reporting domain — with tested, documented, version-controlled
SQL models. `local_validation/validate_transformations.py` re-implements the
same SQL logic in SQLite (stdlib, no install needed) against the same seed
data, so the transformation logic is proven correct without requiring a live
Snowflake account or the dbt CLI. Run it: `python3 local_validation/validate_transformations.py`.
It prints every test result and sample rollups (see output below).

## Architecture
```
raw_sales_orders.csv  ─┐
                        ├─► stg_sales_orders (view) ─┐
raw_inventory.csv     ─┘                              ├─► dim_customer
                        ├─► stg_inventory (view)  ────┤─► dim_product
                                                       ├─► fct_sales   (table)
                                                       └─► fct_inventory (table)
```
- **Staging layer**: 1:1 with source, only casts/renames — no business logic.
- **Mart layer**: star schema (`dim_customer`, `dim_product`, `fct_sales`,
  `fct_inventory`) at the grain Power BI actually needs — one row per order
  line, one row per SKU/warehouse.
- **Tests**: `unique`, `not_null`, `accepted_values`, and `relationships`
  (referential integrity between facts and dims) — the same checks a
  production dbt project runs on every `dbt build`.

## Verified output (from `validate_transformations.py`)
```
[PASS] unique order_id in fct_sales
[PASS] not_null customer_key in fct_sales
[PASS] not_null product_key in fct_sales
[PASS] relationships: every fct_sales.customer_key exists in dim_customer
[PASS] relationships: every fct_inventory.product_key exists in dim_product

Total inventory value (seed sample): $2,764,600.00
Total sales revenue (seed sample):    $2,495,200.00
Average margin % (seed sample):        39.6%
```

## How to actually run this against real Snowflake
1. `pip install dbt-snowflake`
2. Copy `profiles.yml.example` to `~/.dbt/profiles.yml`, fill in real
   Snowflake account/user/role (use a service account with least-privilege
   `TRANSFORMER` role, not your personal login).
3. `dbt seed` (loads the CSVs as tables — in production you'd point
   `stg_*` models at real Salesforce/ERP extract tables instead of seeds).
4. `dbt run` then `dbt test`.
5. `dbt docs generate && dbt docs serve` — gives you a browsable data
   dictionary and lineage graph for free, which is itself a governance win
   worth mentioning.

## What replaced what
| Before (current state) | After (this pilot) |
|---|---|
| Power Query steps embedded inside each .pbix, invisible outside Power BI Desktop | SQL models in Git, readable/reviewable by anyone |
| No automated tests on transformations — errors caught by eyeballing dashboards | `not_null`/`unique`/`relationships` tests run on every build, before anything reaches a dashboard |
| Logic duplicated across dashboards that need the same numbers | Single `fct_sales` / `fct_inventory` models referenced by every downstream report |
| No lineage documentation | `dbt docs` auto-generates lineage + column-level docs |

