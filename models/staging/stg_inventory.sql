with source as (

    select * from {{ ref('raw_inventory') }}

),

renamed as (

    select
        sku,
        product_family,
        warehouse,
        cast(on_hand_qty as integer)        as on_hand_qty,
        cast(unit_cost as decimal(12,2))    as unit_cost,
        cast(reorder_point as integer)      as reorder_point,
        cast(lead_time_days as integer)     as lead_time_days,
        cast(last_received_date as date)    as last_received_date,
        on_hand_qty * unit_cost              as inventory_value,
        case when on_hand_qty <= reorder_point then true else false end as is_below_reorder_point

    from source

)

select * from renamed
