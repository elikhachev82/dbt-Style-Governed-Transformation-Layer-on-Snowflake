-- Fact table, grain = 1 row per SKU/warehouse snapshot.
-- This is the model the $90M inventory-value dashboard would sit on top of.

with inv as (

    select * from {{ ref('stg_inventory') }}

)

select
    i.sku,
    p.product_key,
    i.warehouse,
    i.on_hand_qty,
    i.unit_cost,
    i.inventory_value,
    i.reorder_point,
    i.lead_time_days,
    i.last_received_date,
    i.is_below_reorder_point

from inv i
left join {{ ref('dim_product') }} p on i.sku = p.sku
