-- MART: fct_orders, the one table to use for orders and revenue. One row per order.
-- This is where the data team writes down what "revenue" means at this company.

select
    o.order_id,
    o.order_date,
    o.order_ts,
    r.city_name,
    o.restaurant_id,
    r.restaurant_name,
    o.customer_id,
    o.status,
    o.status = 'delivered'                                          as is_delivered,
    o.checkout_value_incl_gst,
    o.promo_discount,
    o.gst,
    o.refund_amount,

    -- THE BUSINESS RULE: revenue = delivered (not refunded) orders,
    -- checkout value minus promo discount minus GST. Anything else earns 0.
    case when o.status = 'delivered'
         then o.checkout_value_incl_gst - o.promo_discount - o.gst
         else 0 end                                                 as net_revenue,

    o.payment_method,
    o.cancel_reason

from {{ ref('stg_orders') }} o
join {{ ref('stg_restaurants') }} r using (restaurant_id)
