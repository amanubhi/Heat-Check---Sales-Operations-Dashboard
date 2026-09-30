-- ============================================================================
-- HEAT CHECK - SQL ANALYSIS (SQLite dialect)
-- Database: data/heatcheck.db   Tables: orders, order_items, customers,
--                                        events, menu, spice_levels
-- Run all queries with:  python scripts/run_sql_analysis.py
-- Each "-- @query" marker starts a new query; results go to outputs/sql_results/
--
-- Money definitions (same as the Excel and web dashboards):
--   revenue      = sum(unit_price * quantity) - order discount   (tips excluded)
--   gross_profit = revenue - food cost
--
-- COST ASSUMPTIONS (not in the raw data - edit the numbers in each `assumptions`
-- CTE to test scenarios):
--   loaded labor rate $22/hr | storefront 3 staff x 10 hrs per open day (+2.5 hrs on Fri/Sat late nights)
--   night market 3 staff x 6 hrs + $85 booth fee per night
--   vendor events: staff_count x event days x 10 hrs, plus the booth fee in events.csv
-- Rent, utilities and owner pay are NOT included, so "contribution" is not net income.
-- ============================================================================


-- @query Q01 revenue_profit_margin_by_channel_month
-- Business question: How do revenue, profit and margin move by channel each month?
-- Technique: GROUP BY + window SUM() to show each channel's share of the month.
SELECT
    channel,
    month,
    month_name,
    COUNT(*)                                             AS orders,
    ROUND(SUM(revenue), 2)                               AS revenue,
    ROUND(SUM(gross_profit), 2)                          AS gross_profit,
    ROUND(100.0 * SUM(gross_profit) / SUM(revenue), 2)   AS margin_pct,
    ROUND(AVG(revenue), 2)                               AS avg_order_value,
    ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (PARTITION BY month), 1) AS pct_of_month_revenue
FROM orders
GROUP BY channel, month, month_name
ORDER BY channel, month;


-- @query Q02 channel_scorecard_after_direct_costs
-- Business question: Which channel earns the most once staff and booth fees are paid?
-- Technique: several CTEs, UNION ALL of cost sources, JOIN, RANK().
WITH assumptions AS (
    SELECT 22.0 AS hourly_wage,
           3    AS storefront_staff,   10.0 AS storefront_hours, 2.5 AS storefront_late_hours,
           3    AS night_market_staff, 6.0  AS night_market_hours, 85.0 AS night_market_booth_fee,
           10.0 AS event_hours_per_day
),
channel_sales AS (
    SELECT channel,
           COUNT(*)                   AS orders,
           COUNT(DISTINCT order_date) AS operating_days,
           COUNT(DISTINCT CASE WHEN day_of_week_num IN (4, 5) THEN order_date END) AS fri_sat_days,
           SUM(revenue)               AS revenue,
           SUM(gross_profit)          AS gross_profit,
           AVG(revenue)               AS avg_order_value,
           AVG(prep_time_minutes)     AS avg_prep_min
    FROM orders
    GROUP BY channel
),
direct_costs AS (              -- one row per channel: labor hours + booth fees
    SELECT cs.channel,
           a.storefront_staff * (a.storefront_hours * cs.operating_days + a.storefront_late_hours * cs.fri_sat_days) AS labor_hours,
           0.0 AS booth_fees
    FROM channel_sales cs CROSS JOIN assumptions a WHERE cs.channel = 'Storefront'
    UNION ALL
    SELECT cs.channel,
           a.night_market_staff * a.night_market_hours * cs.operating_days,
           a.night_market_booth_fee * cs.operating_days
    FROM channel_sales cs CROSS JOIN assumptions a WHERE cs.channel = 'Night Market'
    UNION ALL
    SELECT 'Vendor Event',
           SUM(e.staff_count * e.event_days * a.event_hours_per_day),
           SUM(e.booth_fee)
    FROM events e CROSS JOIN assumptions a
),
scored AS (
    SELECT cs.channel, cs.orders, cs.operating_days,
           cs.revenue, cs.gross_profit, cs.avg_order_value, cs.avg_prep_min,
           dc.labor_hours, dc.booth_fees,
           dc.labor_hours * a.hourly_wage                                AS labor_cost,
           cs.gross_profit - dc.labor_hours * a.hourly_wage - dc.booth_fees AS contribution
    FROM channel_sales cs
    JOIN direct_costs dc ON dc.channel = cs.channel
    CROSS JOIN assumptions a
)
SELECT channel, orders, operating_days,
       ROUND(revenue, 2)                                AS revenue,
       ROUND(gross_profit, 2)                           AS gross_profit,
       ROUND(100.0 * gross_profit / revenue, 2)         AS margin_pct,
       ROUND(avg_order_value, 2)                        AS avg_order_value,
       ROUND(avg_prep_min, 1)                           AS avg_prep_min,
       ROUND(labor_cost, 2)                             AS labor_cost,
       ROUND(booth_fees, 2)                             AS booth_fees,
       ROUND(contribution, 2)                           AS contribution_after_direct_costs,
       ROUND(gross_profit / labor_hours, 2)             AS gross_profit_per_labor_hour,
       ROUND(contribution / operating_days, 2)          AS contribution_per_operating_day,
       RANK() OVER (ORDER BY contribution / labor_hours DESC) AS rank_by_contribution_per_labor_hour
FROM scored
ORDER BY contribution DESC;


-- @query Q03 vendor_event_roi
-- Business question: After booth fees and staff cost, which events should we keep or drop?
-- Technique: CTEs, JOIN, derived ROI, RANK(), CASE verdict.
-- ROI = net profit / (booth fee + staff cost).
WITH assumptions AS (
    SELECT 22.0 AS hourly_wage, 10.0 AS hours_per_event_day
),
event_sales AS (
    SELECT event_name,
           COUNT(*)          AS orders,
           SUM(revenue)      AS revenue,
           SUM(gross_profit) AS gross_profit
    FROM orders
    WHERE channel = 'Vendor Event'
    GROUP BY event_name
),
event_costs AS (
    SELECT e.event_name, e.city, e.start_date, e.event_days, e.booth_fee, e.staff_count,
           e.staff_count * e.event_days * a.hours_per_event_day * a.hourly_wage AS staff_cost
    FROM events e CROSS JOIN assumptions a
),
scored AS (
    SELECT c.event_name, c.city, c.start_date, c.event_days, c.staff_count,
           s.orders, s.revenue, s.gross_profit, c.booth_fee, c.staff_cost,
           s.gross_profit - c.booth_fee - c.staff_cost                        AS net_profit,
           (s.gross_profit - c.booth_fee - c.staff_cost) / (c.booth_fee + c.staff_cost) AS roi
    FROM event_costs c
    JOIN event_sales s ON s.event_name = c.event_name
)
SELECT event_name, city, start_date, event_days, staff_count, orders,
       ROUND(revenue, 2)                     AS revenue,
       ROUND(gross_profit, 2)                AS gross_profit,
       booth_fee,
       ROUND(staff_cost, 2)                  AS staff_cost,
       ROUND(net_profit, 2)                  AS net_profit,
       ROUND(100.0 * roi, 1)                 AS roi_pct,
       ROUND(net_profit / event_days, 2)     AS net_profit_per_day,
       ROUND(1.0 * orders / (staff_count * event_days), 1) AS orders_per_staff_day,
       RANK() OVER (ORDER BY roi DESC)       AS roi_rank,
       CASE WHEN roi >= 3.0 THEN 'KEEP - priority'
            WHEN roi >= 1.0 THEN 'KEEP'
            ELSE 'REVIEW / DROP' END         AS verdict
FROM scored
ORDER BY roi_rank;


-- @query Q04 top10_items_by_profit
-- Business question: Which items actually make the money (profit, not just revenue)?
-- Technique: CTE, two RANK() windows, SUM() OVER () for share of total.
WITH item_totals AS (
    SELECT item_id, item_name, category,
           SUM(quantity)                    AS units_sold,
           SUM(line_revenue - line_discount) AS revenue,
           SUM(line_profit)                 AS gross_profit
    FROM order_items
    GROUP BY item_id, item_name, category
),
ranked AS (
    SELECT *,
           RANK() OVER (ORDER BY gross_profit DESC) AS profit_rank,
           RANK() OVER (ORDER BY revenue DESC)      AS revenue_rank,
           100.0 * gross_profit / SUM(gross_profit) OVER () AS pct_of_total_profit
    FROM item_totals
)
SELECT profit_rank, item_name, category, units_sold,
       ROUND(revenue, 2)                        AS revenue,
       ROUND(gross_profit, 2)                   AS gross_profit,
       ROUND(100.0 * gross_profit / revenue, 1) AS margin_pct,
       revenue_rank,
       revenue_rank - profit_rank               AS rank_gain_vs_revenue,
       ROUND(pct_of_total_profit, 1)            AS pct_of_total_profit
FROM ranked
WHERE profit_rank <= 10
ORDER BY profit_rank;


-- @query Q05 category_profitability
-- Business question: Which menu categories carry the profit and which dilute margin?
-- Technique: GROUP BY, window share-of-total, RANK().
WITH cat AS (
    SELECT category,
           SUM(quantity)                     AS units_sold,
           SUM(line_revenue - line_discount) AS revenue,
           SUM(line_profit)                  AS gross_profit
    FROM order_items
    GROUP BY category
)
SELECT category, units_sold,
       ROUND(revenue, 2)                              AS revenue,
       ROUND(gross_profit, 2)                         AS gross_profit,
       ROUND(100.0 * gross_profit / revenue, 1)       AS margin_pct,
       ROUND(100.0 * revenue / SUM(revenue) OVER (), 1)          AS pct_of_revenue,
       ROUND(100.0 * gross_profit / SUM(gross_profit) OVER (), 1) AS pct_of_profit,
       RANK() OVER (ORDER BY gross_profit DESC)       AS profit_rank
FROM cat
ORDER BY profit_rank;


-- @query Q06 spice_level_by_channel
-- Business question: Which heat levels does each channel order (for inventory and prep)?
-- Technique: JOINs across three tables, PARTITION BY window for within-channel share.
-- Sides and drinks have no spice level so they are excluded.
WITH spice_units AS (
    SELECT o.channel, sl.level_name AS spice_level, sl.heat_rank,
           SUM(oi.quantity) AS units
    FROM order_items oi
    JOIN orders o        ON o.order_id = oi.order_id
    JOIN spice_levels sl ON sl.level_id = oi.level_id
    GROUP BY o.channel, sl.level_name, sl.heat_rank
)
SELECT channel, spice_level, heat_rank, units,
       ROUND(100.0 * units / SUM(units) OVER (PARTITION BY channel), 1) AS pct_of_channel_units,
       RANK() OVER (PARTITION BY channel ORDER BY units DESC)           AS popularity_rank
FROM spice_units
ORDER BY channel, heat_rank;


-- @query Q07 spice_level_by_daypart
-- Business question: Do guests order hotter later in the day?
-- Technique: same pattern as Q06, partitioned by daypart; CASE for a sortable daypart order.
WITH spice_units AS (
    SELECT o.daypart, sl.level_name AS spice_level, sl.heat_rank,
           SUM(oi.quantity) AS units
    FROM order_items oi
    JOIN orders o        ON o.order_id = oi.order_id
    JOIN spice_levels sl ON sl.level_id = oi.level_id
    GROUP BY o.daypart, sl.level_name, sl.heat_rank
)
SELECT daypart,
       CASE daypart WHEN 'Lunch' THEN 1 WHEN 'Afternoon' THEN 2 WHEN 'Dinner' THEN 3 ELSE 4 END AS daypart_order,
       spice_level, heat_rank, units,
       ROUND(100.0 * units / SUM(units) OVER (PARTITION BY daypart), 1) AS pct_of_daypart_units,
       -- share of the two hottest levels, repeated on each row for easy reading
       ROUND(100.0 * SUM(CASE WHEN heat_rank >= 4 THEN units ELSE 0 END) OVER (PARTITION BY daypart)
             / SUM(units) OVER (PARTITION BY daypart), 1)                AS extra_hot_plus_share_pct
FROM spice_units
ORDER BY daypart_order, heat_rank;


-- @query Q08 customer_retention_repeat_rate
-- Business question: What share of identified customers come back, and how fast?
-- Technique: UNION ALL of segments, conditional aggregation with CASE.
-- Note: only orders with a customer_id (app/online/loyalty/known guests) can be tracked.
SELECT 'All customers' AS segment,
       COUNT(*)                                                   AS customers,
       SUM(CASE WHEN total_orders > 1 THEN 1 ELSE 0 END)          AS repeat_customers,
       ROUND(100.0 * SUM(CASE WHEN total_orders > 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS repeat_rate_pct,
       ROUND(AVG(total_orders), 2)                                AS avg_orders_per_customer,
       ROUND(AVG(days_to_second_order), 1)                        AS avg_days_to_second_order
FROM customers
UNION ALL
SELECT CASE WHEN loyalty_member = 1 THEN 'Loyalty members' ELSE 'Non-members' END,
       COUNT(*),
       SUM(CASE WHEN total_orders > 1 THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN total_orders > 1 THEN 1 ELSE 0 END) / COUNT(*), 1),
       ROUND(AVG(total_orders), 2),
       ROUND(AVG(days_to_second_order), 1)
FROM customers
GROUP BY loyalty_member
UNION ALL
SELECT county || ' County',
       COUNT(*),
       SUM(CASE WHEN total_orders > 1 THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN total_orders > 1 THEN 1 ELSE 0 END) / COUNT(*), 1),
       ROUND(AVG(total_orders), 2),
       ROUND(AVG(days_to_second_order), 1)
FROM customers
GROUP BY county;


-- @query Q09 cohort_retention_by_first_order_month
-- Business question: Of customers first seen in month X, what % ordered again N months later?
-- Technique: CTEs, month-index arithmetic, self-referencing cohort join.
-- Caution: customers who already existed in Jan 2025 all land in the Jan cohort.
WITH cohort AS (
    SELECT customer_id, first_order_month,
           CAST(substr(first_order_month, 1, 4) AS INTEGER) * 12 + CAST(substr(first_order_month, 6, 2) AS INTEGER) AS first_idx
    FROM customers
),
activity AS (                    -- one row per customer per month they ordered
    SELECT DISTINCT customer_id,
           CAST(substr(order_date, 1, 4) AS INTEGER) * 12 + CAST(substr(order_date, 6, 2) AS INTEGER) AS active_idx
    FROM orders
    WHERE customer_id IS NOT NULL
),
cohort_activity AS (
    SELECT c.first_order_month AS cohort_month,
           a.active_idx - c.first_idx AS months_since_first,
           COUNT(DISTINCT c.customer_id) AS active_customers
    FROM cohort c
    JOIN activity a ON a.customer_id = c.customer_id
    GROUP BY c.first_order_month, a.active_idx - c.first_idx
),
sizes AS (
    SELECT first_order_month AS cohort_month, COUNT(*) AS cohort_size FROM cohort GROUP BY first_order_month
)
SELECT ca.cohort_month, s.cohort_size, ca.months_since_first, ca.active_customers,
       ROUND(100.0 * ca.active_customers / s.cohort_size, 1) AS retention_pct
FROM cohort_activity ca
JOIN sizes s ON s.cohort_month = ca.cohort_month
ORDER BY ca.cohort_month, ca.months_since_first;


-- @query Q10 peak_hour_heatmap_day_by_hour
-- Business question: Which day/hour slots are busiest (for scheduling)?
-- Technique: JOIN to a per-weekday day count so we compare AVERAGE orders per day,
--            RANK() over the aggregate.
WITH day_counts AS (
    SELECT day_of_week_num, COUNT(DISTINCT order_date) AS days_with_sales
    FROM orders
    GROUP BY day_of_week_num
)
SELECT o.day_of_week_num, o.day_of_week, o.hour,
       COUNT(*)                                         AS orders,
       ROUND(SUM(o.revenue), 2)                         AS revenue,
       ROUND(1.0 * COUNT(*) / d.days_with_sales, 2)     AS avg_orders_per_day,
       RANK() OVER (ORDER BY 1.0 * COUNT(*) / d.days_with_sales DESC) AS peak_rank
FROM orders o
JOIN day_counts d ON d.day_of_week_num = o.day_of_week_num
GROUP BY o.day_of_week_num, o.day_of_week, o.hour, d.days_with_sales
ORDER BY o.day_of_week_num, o.hour;


-- @query Q11 month_over_month_growth
-- Business question: How fast is the business growing, and what does the running total look like?
-- Technique: LAG(), running total (SUM OVER), 3-month moving average, named WINDOW.
WITH monthly AS (
    SELECT month, month_name,
           COUNT(*)          AS orders,
           SUM(revenue)      AS revenue,
           SUM(gross_profit) AS gross_profit
    FROM orders
    GROUP BY month, month_name
)
SELECT month, month_name, orders,
       ROUND(revenue, 2)                                           AS revenue,
       ROUND(gross_profit, 2)                                      AS gross_profit,
       ROUND(LAG(revenue) OVER w, 2)                               AS prev_month_revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER w) / LAG(revenue) OVER w, 1) AS mom_growth_pct,
       ROUND(SUM(revenue) OVER (ORDER BY month ROWS UNBOUNDED PRECEDING), 2)  AS ytd_revenue,
       ROUND(AVG(revenue) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS rolling_3mo_avg_revenue
FROM monthly
WINDOW w AS (ORDER BY month)
ORDER BY month;


-- @query Q12 prep_time_vs_order_volume
-- Business question: At what order volume does the kitchen slow down (bottleneck)?
-- Technique: COUNT() OVER (PARTITION BY date, channel, hour) gives each order the volume of its
--            hour; then bucket with CASE and compare average prep time and "slow order" share.
WITH hourly AS (
    SELECT order_id, channel, prep_time_minutes,
           COUNT(*) OVER (PARTITION BY order_date, channel, hour) AS orders_in_that_hour
    FROM orders
    WHERE prep_time_minutes IS NOT NULL
),
bucketed AS (
    SELECT *,
           CASE WHEN orders_in_that_hour <= 10 THEN 1
                WHEN orders_in_that_hour <= 20 THEN 2
                WHEN orders_in_that_hour <= 40 THEN 3
                WHEN orders_in_that_hour <= 60 THEN 4
                ELSE 5 END AS bucket_order
    FROM hourly
)
SELECT channel,
       CASE bucket_order WHEN 1 THEN '1-10 orders/hr' WHEN 2 THEN '11-20' WHEN 3 THEN '21-40'
                         WHEN 4 THEN '41-60' ELSE '61+' END AS volume_bucket,
       bucket_order,
       COUNT(*)                                                   AS orders,
       ROUND(AVG(prep_time_minutes), 1)                           AS avg_prep_min,
       ROUND(100.0 * SUM(CASE WHEN prep_time_minutes > 15 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_orders_over_15min
FROM bucketed
GROUP BY channel, bucket_order
ORDER BY channel, bucket_order;


-- @query Q13 daypart_performance_by_channel
-- Business question: Which dayparts earn the most in each channel?
-- Technique: GROUP BY two keys, window share-of-channel, RANK() within channel.
SELECT channel, daypart,
       COUNT(*)                                                AS orders,
       ROUND(SUM(revenue), 2)                                  AS revenue,
       ROUND(SUM(gross_profit), 2)                             AS gross_profit,
       ROUND(100.0 * SUM(gross_profit) / SUM(revenue), 1)      AS margin_pct,
       ROUND(AVG(prep_time_minutes), 1)                        AS avg_prep_min,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (PARTITION BY channel), 1) AS pct_of_channel_revenue,
       RANK() OVER (PARTITION BY channel ORDER BY SUM(revenue) DESC)                  AS revenue_rank_in_channel
FROM orders
GROUP BY channel, daypart
ORDER BY channel, revenue_rank_in_channel;


-- @query Q14 loyalty_member_value
-- Business question: Are loyalty members worth more, even with their discounts?
-- Technique: CASE segmentation, COUNT(DISTINCT), UNION ALL to add walk-ups for comparison.
SELECT CASE WHEN loyalty_member = 1 THEN 'Loyalty member' ELSE 'Known non-member' END AS segment,
       COUNT(DISTINCT customer_id)                                   AS customers,
       COUNT(*)                                                      AS orders,
       ROUND(1.0 * COUNT(*) / COUNT(DISTINCT customer_id), 2)        AS orders_per_customer,
       ROUND(AVG(revenue), 2)                                        AS avg_order_value,
       ROUND(100.0 * AVG(CASE WHEN discount_amount > 0 THEN 1.0 ELSE 0 END), 1) AS pct_orders_discounted,
       ROUND(SUM(revenue) / COUNT(DISTINCT customer_id), 2)          AS revenue_per_customer,
       ROUND(SUM(gross_profit) / COUNT(DISTINCT customer_id), 2)     AS gross_profit_per_customer
FROM orders
WHERE customer_id IS NOT NULL
GROUP BY loyalty_member
UNION ALL
SELECT 'Walk-up (no customer id)', NULL, COUNT(*), NULL,
       ROUND(AVG(revenue), 2),
       ROUND(100.0 * AVG(CASE WHEN discount_amount > 0 THEN 1.0 ELSE 0 END), 1),
       NULL, NULL
FROM orders
WHERE customer_id IS NULL;


-- @query Q15 day_of_week_performance_by_channel
-- Business question: Which weekdays should get the most staff in each channel?
-- Technique: daily rollup CTE, then average per weekday, RANK() and an index vs channel average.
WITH daily AS (
    SELECT order_date, day_of_week_num, day_of_week, channel,
           COUNT(*) AS orders, SUM(revenue) AS revenue, SUM(gross_profit) AS gross_profit
    FROM orders
    GROUP BY order_date, day_of_week_num, day_of_week, channel
),
by_dow AS (
    SELECT channel, day_of_week_num, day_of_week,
           COUNT(*)                        AS days_operated,
           ROUND(AVG(orders), 1)           AS avg_orders_per_day,
           ROUND(AVG(revenue), 2)          AS avg_revenue_per_day,
           ROUND(AVG(gross_profit), 2)     AS avg_gross_profit_per_day
    FROM daily
    GROUP BY channel, day_of_week_num, day_of_week
)
SELECT channel, day_of_week_num, day_of_week, days_operated,
       avg_orders_per_day, avg_revenue_per_day, avg_gross_profit_per_day,
       RANK() OVER (PARTITION BY channel ORDER BY avg_revenue_per_day DESC)                AS rank_within_channel,
       ROUND(avg_revenue_per_day / AVG(avg_revenue_per_day) OVER (PARTITION BY channel), 2) AS index_vs_channel_avg
FROM by_dow
ORDER BY channel, day_of_week_num;
