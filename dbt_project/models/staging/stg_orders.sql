-- STAGING: clean up the raw orders, one row per order.
-- Rename confusing columns, and bring in GST and refunds from their own tables.

select
    o.order_id,
    o.customer_id,
    o.restaurant_id,
    o.order_ts,
    cast(o.order_ts as date)                         as order_date,

    -- In the raw table a refunded order still says 'delivered'. Fix that here.
    case when f.order_id is not null then 'refunded'
         else o.status end                           as status,

    o.amount                                         as checkout_value_incl_gst,   -- item value + GST, before promo
    o.promo_value                                    as promo_discount,
    t.gst,                                                                          -- from order_taxes
    f.refund_amount,                                                                -- from refunds
    o.payment_method,
    o.cancel_reason

from {{ source('raw', 'orders') }} o
left join {{ source('raw', 'order_taxes') }} t using (order_id)
left join {{ source('raw', 'refunds') }} f using (order_id)
