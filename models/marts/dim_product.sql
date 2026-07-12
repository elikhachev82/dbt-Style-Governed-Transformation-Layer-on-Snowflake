-- Conformed product dimension, deduplicated across the sales and
-- inventory streams so both fact tables can join to the same keys.

with sales_products as (
    select distinct sku, product_family from {{ ref('stg_sales_orders') }}
),

inventory_products as (
    select distinct sku, product_family from {{ ref('stg_inventory') }}
),

combined as (
    select * from sales_products
    union
    select * from inventory_products
)

select
    sku as product_key,
    sku,
    product_family
from combined
