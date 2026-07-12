-- Staging model: 1 row per source order line, light cleaning/renaming only.
-- No business logic here -- that belongs in marts. This mirrors the
-- "staging -> marts" convention so anyone opening the project recognizes
-- the pattern immediately.

with source as (

    select * from {{ ref('raw_sales_orders') }}

),

renamed as (

    select
        order_id,
        cast(order_date as date)           as order_date,
        customer_id,
        trim(customer_name)                as customer_name,
        region,
        product_sku                        as sku,
        product_family,
        channel,
        sales_rep,
        cast(quantity as integer)           as quantity,
        cast(unit_price as decimal(12,2))   as unit_price,
        cast(unit_cost as decimal(12,2))    as unit_cost,
        quantity * unit_price                as extended_revenue,
        quantity * unit_cost                 as extended_cost,
        (quantity * unit_price) - (quantity * unit_cost) as extended_margin

    from source

)

select * from renamed
