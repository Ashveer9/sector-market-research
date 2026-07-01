-- Intermediate model: enriches staged orders with business categorisations
-- used by multiple downstream mart models.

{{
  config(
    materialized='ephemeral',
    tags=['intermediate']
  )
}}

SELECT
    o.*,

    -- Discount band for segmentation analysis
    CASE
        WHEN o.discount = 0            THEN 'No Discount'
        WHEN o.discount <= 0.10        THEN 'Low (1–10%)'
        WHEN o.discount <= 0.20        THEN 'Medium (11–20%)'
        WHEN o.discount <= 0.30        THEN 'High (21–30%)'
        ELSE                                'Very High (>30%)'
    END                                                     AS discount_band,

    -- Profitability classification
    CASE
        WHEN o.profit_margin >= 0.30   THEN 'High Margin'
        WHEN o.profit_margin >= 0.10   THEN 'Healthy Margin'
        WHEN o.profit_margin >= 0      THEN 'Low Margin'
        ELSE                                'Loss Making'
    END                                                     AS margin_class,

    -- Shipping speed classification
    CASE
        WHEN o.days_to_ship <= 1       THEN 'Same Day / Next Day'
        WHEN o.days_to_ship <= 3       THEN 'Express'
        WHEN o.days_to_ship <= 5       THEN 'Standard'
        ELSE                                'Economy'
    END                                                     AS shipping_speed,

    -- Order size tier
    CASE
        WHEN o.sales >= 1000           THEN 'Large'
        WHEN o.sales >= 200            THEN 'Medium'
        ELSE                                'Small'
    END                                                     AS order_size_tier

FROM {{ ref('stg_orders') }} o
