-- Fact table, grain = 1 row per order line.
-- Joins to conformed dims so BI tools (Power BI) build a clean star schema
-- instead of querying the flat staging view directly.

with orders as (

    select * from {{ ref('stg_sales_orders') }}

)

select
    o.order_id,
    o.order_date,
    c.customer_key,
    p.product_key,
    o.region,
    o.channel,
    o.sales_rep,
    o.quantity,
    o.unit_price,
    o.unit_cost,
    o.extended_revenue,
    o.extended_cost,
    o.extended_margin,
    o.extended_margin / nullif(o.extended_revenue, 0) as margin_pct

from orders o
left join {{ ref('dim_customer') }} c on o.customer_id = c.customer_id
left join {{ ref('dim_product') }} p on o.sku = p.sku
