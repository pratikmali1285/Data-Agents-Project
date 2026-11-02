-- Ground truth for every demo question. "Today" is 2026-10-15, so
-- last month = September 2026 and last week = Mon 5 Oct to Sun 11 Oct 2026.
-- Run:  python check_answers.py   (or paste into the DuckDB CLI on warehouse.duckdb)

-- Q1. How many orders did we get from Mumbai last month?  (all orders placed)
SELECT COUNT(*) AS mumbai_orders_sept
FROM orders o JOIN restaurants r USING (restaurant_id) JOIN cities c USING (city_id)
WHERE c.city_name = 'Mumbai' AND o.order_ts >= '2026-09-01' AND o.order_ts < '2026-10-01';

-- Q2. What was our revenue last month?  The naive answers an agent can give on the raw tables:
SELECT
  SUM(o.amount)                                                                AS a_sum_amount_all_orders,
  SUM(o.amount) FILTER (WHERE o.status = 'delivered')                          AS b_delivered_only,
  SUM(o.amount - o.promo_value) FILTER (WHERE o.status = 'delivered')          AS c_delivered_minus_promo,
  SUM(o.amount - o.promo_value - t.gst) FILTER (WHERE o.status = 'delivered')  AS d_also_minus_gst_but_keeps_refunds,
  SUM(o.amount - o.promo_value - t.gst) FILTER (WHERE o.status = 'delivered' AND f.order_id IS NULL) AS e_correct_revenue
FROM orders o JOIN order_taxes t USING (order_id) LEFT JOIN refunds f USING (order_id)
WHERE o.order_ts >= '2026-09-01' AND o.order_ts < '2026-10-01';

-- Q3. Why did our orders drop in Mumbai last week?  (week 40 vs week 41)
SELECT date_trunc('week', o.order_ts)::DATE AS week_start,
       COUNT(*)                                                            AS placed,
       COUNT(*) FILTER (WHERE o.status = 'delivered' AND f.order_id IS NULL) AS delivered_not_refunded,
       COUNT(*) FILTER (WHERE o.status = 'cancelled')                      AS cancelled,
       COUNT(*) FILTER (WHERE o.cancel_reason = 'heavy_rain_no_rider')     AS cancelled_heavy_rain
FROM orders o JOIN restaurants r USING (restaurant_id) LEFT JOIN refunds f USING (order_id)
WHERE r.city_id = 1 AND o.order_ts >= '2026-09-28' AND o.order_ts < '2026-10-12'
GROUP BY 1 ORDER BY 1;

-- Q4. Which 5 Mumbai restaurants had the highest cancellation rate last month? (min 50 orders)
SELECT r.restaurant_name, r.restaurant_id, COUNT(*) AS orders,
       ROUND(100.0 * COUNT(*) FILTER (WHERE o.status = 'cancelled') / COUNT(*), 1) AS cancel_pct
FROM orders o JOIN restaurants r USING (restaurant_id)
WHERE r.city_id = 1 AND o.order_ts >= '2026-09-01' AND o.order_ts < '2026-10-01'
GROUP BY ALL HAVING COUNT(*) >= 50 ORDER BY cancel_pct DESC LIMIT 5;

-- Q5. What was the average order value in Bengaluru last month? (revenue per delivered order)
SELECT ROUND(SUM(o.amount) / COUNT(*), 2) AS naive_avg_amount_all_orders,
       ROUND(SUM(o.amount - o.promo_value - t.gst) FILTER (WHERE o.status = 'delivered' AND f.order_id IS NULL)
             / COUNT(*) FILTER (WHERE o.status = 'delivered' AND f.order_id IS NULL), 2) AS correct_aov
FROM orders o JOIN restaurants r USING (restaurant_id) JOIN order_taxes t USING (order_id) LEFT JOIN refunds f USING (order_id)
WHERE r.city_id = 2 AND o.order_ts >= '2026-09-01' AND o.order_ts < '2026-10-01';
