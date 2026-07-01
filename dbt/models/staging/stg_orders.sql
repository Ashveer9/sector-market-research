-- Staging model: casts and renames columns from raw Silver Parquet data.
-- Acts as the single source of truth for downstream models.

{{
  config(
    materialized='view',
    tags=['staging', 'orders']
  )
}}

SELECT
    order_id,
    CAST(order_date AS DATE)                            AS order_date,
    CAST(ship_date  AS DATE)                            AS ship_date,
    ship_mode,
    customer_id,
    customer_name,
    segment,
    city,
    state,
    country,
    COALESCE(postal_code, 'UNKNOWN')                    AS postal_code,
    market,
    region,
    product_id,
    category,
    sub_category,
    product_name,
    CAST(sales          AS DECIMAL(12, 4))              AS sales,
    CAST(quantity       AS INTEGER)                     AS quantity,
    CAST(discount       AS DECIMAL(6, 4))               AS discount,
    CAST(profit         AS DECIMAL(12, 4))              AS profit,
    CAST(shipping_cost  AS DECIMAL(12, 4))              AS shipping_cost,
    order_priority,

    -- Derived financial metrics
    ROUND(profit / NULLIF(sales, 0), 4)                 AS profit_margin,
    ROUND((1 - discount) * sales, 4)                    AS net_sales,

    -- Date parts (pre-computed for performance)
    EXTRACT(YEAR    FROM CAST(order_date AS DATE))      AS order_year,
    EXTRACT(QUARTER FROM CAST(order_date AS DATE))      AS order_quarter,
    EXTRACT(MONTH   FROM CAST(order_date AS DATE))      AS order_month,

    -- Shipping lead time
    DATEDIFF('day', CAST(order_date AS DATE), CAST(ship_date AS DATE)) AS days_to_ship

FROM silver.orders

WHERE order_id IS NOT NULL
  AND sales     IS NOT NULL
  AND sales     > 0
