-- Conformed customer dimension, deduplicated from the order stream.
-- In production this would also pull in Salesforce Account fields
-- (industry, account owner, tier) via a second source join.

with orders as (

    select * from {{ ref('stg_sales_orders') }}

),

customers as (

    select
        customer_id,
        customer_name,
        region,
        -- naive "first seen" / "last seen" so downstream marts can compute
        -- tenure without re-scanning the fact table
        min(order_date) as first_order_date,
        max(order_date) as last_order_date,
        count(distinct order_id) as lifetime_order_count

    from orders
    group by 1, 2, 3

)

select
    customer_id as customer_key,   -- swap for dbt_utils.generate_surrogate_key() once dbt_utils is added as a package
    customer_id,
    customer_name,
    region,
    first_order_date,
    last_order_date,
    lifetime_order_count
from customers
