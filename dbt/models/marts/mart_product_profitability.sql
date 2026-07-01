-- Mart: Product profitability — ranks products by margin and flags loss-makers.

{{
  config(
    materialized='table',
    tags=['mart', 'products', 'profitability']
  )
}}

WITH orders AS (
    SELECT * FROM {{ ref('int_orders_enriched') }}
),

product_agg AS (
    SELECT
        product_id,
        product_name,
        category,
        sub_category,
        margin_class,

        COUNT(*)                                            AS order_lines,
        COUNT(DISTINCT order_id)                            AS distinct_orders,
        COUNT(DISTINCT customer_id)                         AS distinct_customers,
        SUM(quantity)                                       AS units_sold,

        ROUND(SUM(sales),   2)                              AS total_sales,
        ROUND(SUM(profit),  2)                              AS total_profit,
        ROUND(AVG(profit_margin)  * 100, 2)                 AS avg_margin_pct,
        ROUND(AVG(discount)       * 100, 2)                 AS avg_discount_pct,
        ROUND(AVG(shipping_cost),       2)                  AS avg_shipping_cost,

        -- Consistency: stdev of margin across orders
        ROUND(STDDEV(profit_margin) * 100, 2)               AS margin_stdev_pct,

        MIN(order_year)                                     AS first_sold_year,
        MAX(order_year)                                     AS last_sold_year

    FROM orders
    GROUP BY product_id, product_name, category, sub_category, margin_class
),

ranked AS (
    SELECT
        *,
        RANK() OVER (PARTITION BY category ORDER BY avg_margin_pct DESC)
                                                            AS margin_rank_in_category,
        RANK() OVER (PARTITION BY category ORDER BY total_sales DESC)
                                                            AS sales_rank_in_category,
        NTILE(4) OVER (ORDER BY avg_margin_pct)             AS margin_quartile
    FROM product_agg
)

SELECT
    *,
    CASE
        WHEN margin_quartile = 4                THEN 'Star Product'
        WHEN margin_quartile = 3                THEN 'Growth Product'
        WHEN margin_quartile = 2                THEN 'Watch Product'
        ELSE                                         'Review Product'
    END                                                     AS product_flag

FROM ranked
ORDER BY avg_margin_pct DESC
