-- Mart: Sector performance — core portfolio KPI table.
-- Aggregates sales, profit, and order metrics by market, category, and quarter.

{{
  config(
    materialized='table',
    tags=['mart', 'sector', 'kpi'],
    indexes=[{'columns': ['market', 'order_year', 'order_quarter']}]
  )
}}

WITH base AS (
    SELECT *
    FROM {{ ref('int_orders_enriched') }}
),

aggregated AS (
    SELECT
        market,
        region,
        category,
        sub_category,
        order_year,
        order_quarter,
        order_size_tier,

        COUNT(DISTINCT order_id)                            AS order_count,
        COUNT(DISTINCT customer_id)                         AS unique_customers,
        SUM(quantity)                                       AS units_sold,

        ROUND(SUM(sales),         2)                        AS total_sales,
        ROUND(SUM(profit),        2)                        AS total_profit,
        ROUND(SUM(shipping_cost), 2)                        AS total_shipping_cost,

        ROUND(AVG(profit_margin) * 100, 2)                  AS avg_margin_pct,
        ROUND(AVG(discount)      * 100, 2)                  AS avg_discount_pct,
        ROUND(AVG(days_to_ship),        1)                  AS avg_days_to_ship,

        ROUND(SUM(sales) / NULLIF(COUNT(DISTINCT order_id), 0), 2)
                                                            AS avg_order_value,
        ROUND(SUM(profit) / NULLIF(SUM(sales), 0) * 100, 2)
                                                            AS realised_margin_pct

    FROM base
    GROUP BY
        market, region, category, sub_category,
        order_year, order_quarter, order_size_tier
),

with_growth AS (
    SELECT
        *,
        LAG(total_sales) OVER (
            PARTITION BY market, region, category
            ORDER BY order_year, order_quarter
        )                                                   AS prev_period_sales,

        LAG(total_profit) OVER (
            PARTITION BY market, region, category
            ORDER BY order_year, order_quarter
        )                                                   AS prev_period_profit
    FROM aggregated
)

SELECT
    *,
    ROUND(
        (total_sales - prev_period_sales) / NULLIF(prev_period_sales, 0) * 100, 2
    )                                                       AS qoq_sales_growth_pct,
    ROUND(
        (total_profit - prev_period_profit) / NULLIF(prev_period_profit, 0) * 100, 2
    )                                                       AS qoq_profit_growth_pct

FROM with_growth
ORDER BY market, order_year, order_quarter, total_sales DESC
