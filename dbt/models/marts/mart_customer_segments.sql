-- Mart: Customer segment analysis — revenue distribution and behaviour by segment.

{{
  config(
    materialized='table',
    tags=['mart', 'customers', 'segments']
  )
}}

WITH orders AS (
    SELECT * FROM {{ ref('int_orders_enriched') }}
),

segment_metrics AS (
    SELECT
        segment,
        market,
        order_year,

        COUNT(DISTINCT customer_id)                         AS unique_customers,
        COUNT(DISTINCT order_id)                            AS total_orders,
        SUM(quantity)                                       AS units_sold,

        ROUND(SUM(sales),   2)                              AS total_revenue,
        ROUND(SUM(profit),  2)                              AS total_profit,

        ROUND(AVG(sales),   2)                              AS avg_order_value,
        ROUND(AVG(profit_margin) * 100, 2)                  AS avg_margin_pct,
        ROUND(AVG(discount)      * 100, 2)                  AS avg_discount_pct,
        ROUND(AVG(days_to_ship),        1)                  AS avg_days_to_ship,

        ROUND(SUM(sales) / NULLIF(COUNT(DISTINCT customer_id), 0), 2)
                                                            AS revenue_per_customer,
        ROUND(COUNT(DISTINCT order_id)::FLOAT / NULLIF(COUNT(DISTINCT customer_id), 0), 2)
                                                            AS orders_per_customer,

        -- Discount usage
        ROUND(
            COUNT(CASE WHEN discount > 0 THEN 1 END)::FLOAT
            / NULLIF(COUNT(*), 0) * 100, 2
        )                                                   AS pct_orders_discounted,

        -- Loss-making order rate
        ROUND(
            COUNT(CASE WHEN profit < 0 THEN 1 END)::FLOAT
            / NULLIF(COUNT(*), 0) * 100, 2
        )                                                   AS pct_loss_making_orders

    FROM orders
    GROUP BY segment, market, order_year
)

SELECT
    *,
    RANK() OVER (PARTITION BY market, order_year ORDER BY total_revenue DESC)
                                                            AS revenue_rank_in_market
FROM segment_metrics
ORDER BY order_year, total_revenue DESC
