"""
Exploratory Data Analysis — Sector Market Research
===================================================
Standalone script (also runs as a Jupyter notebook via Jupytext).
Produces HTML charts to data/analytics/charts/.

Run:
    python notebooks/eda_sector_analysis.py
"""

# %% [markdown]
# # Sector Market Research — Exploratory Data Analysis
#
# Analyses the Global Superstore Gold layer to surface:
# - Revenue and profit distribution by market
# - Segment profitability across regions
# - Discount impact on margin
# - Top/bottom performing sub-categories
# - Shipping cost efficiency

# %%
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.gold.warehouse import GoldWarehouse
from src.utils.logger import get_logger

logger = get_logger(__name__)
OUTPUT_DIR = Path("data/analytics/charts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

wh = GoldWarehouse()


# %% [markdown]
# ## 1. Revenue & Profit by Market Sector

# %%
sector_df = wh.query("""
    SELECT
        g.market,
        ROUND(SUM(f.sales), 0)              AS total_sales,
        ROUND(SUM(f.profit), 0)             AS total_profit,
        COUNT(DISTINCT f.order_id)          AS orders,
        ROUND(AVG(f.profit_margin)*100, 1)  AS avg_margin_pct
    FROM gold.fact_orders f
    JOIN gold.dim_geography g ON f.geo_key = g.geo_key
    GROUP BY g.market
    ORDER BY total_sales DESC
""")

fig1 = make_subplots(
    rows=1, cols=2,
    subplot_titles=["Revenue by Market ($)", "Avg Profit Margin (%)"],
)
fig1.add_trace(
    go.Bar(x=sector_df["market"], y=sector_df["total_sales"],
           name="Revenue", marker_color="#2563EB"),
    row=1, col=1,
)
fig1.add_trace(
    go.Bar(x=sector_df["market"], y=sector_df["avg_margin_pct"],
           name="Margin %", marker_color="#16A34A"),
    row=1, col=2,
)
fig1.update_layout(title="Market Sector Performance Overview", height=450, showlegend=False)
fig1.write_html(OUTPUT_DIR / "01_sector_performance.html")
print(f"Chart 1 saved: {OUTPUT_DIR / '01_sector_performance.html'}")
print(sector_df.to_string(index=False))


# %% [markdown]
# ## 2. Customer Segment Analysis

# %%
segment_df = wh.query("""
    SELECT
        c.segment,
        g.market,
        ROUND(SUM(f.sales), 0)              AS revenue,
        ROUND(SUM(f.profit), 0)             AS profit,
        COUNT(DISTINCT c.customer_id)       AS customers,
        ROUND(AVG(f.discount)*100, 1)       AS avg_discount_pct
    FROM gold.fact_orders f
    JOIN gold.dim_customer  c ON f.customer_key = c.customer_key
    JOIN gold.dim_geography g ON f.geo_key      = g.geo_key
    GROUP BY c.segment, g.market
    ORDER BY revenue DESC
""")

fig2 = px.sunburst(
    segment_df,
    path=["segment", "market"],
    values="revenue",
    color="profit",
    color_continuous_scale="RdYlGn",
    title="Revenue by Customer Segment × Market (colour = profit)",
)
fig2.write_html(OUTPUT_DIR / "02_segment_sunburst.html")
print(f"\nChart 2 saved: {OUTPUT_DIR / '02_segment_sunburst.html'}")


# %% [markdown]
# ## 3. Category Profitability Treemap

# %%
cat_df = wh.query("""
    SELECT
        p.category,
        p.sub_category,
        ROUND(SUM(f.sales), 0)              AS revenue,
        ROUND(SUM(f.profit), 0)             AS profit,
        ROUND(AVG(f.profit_margin)*100, 1)  AS margin_pct
    FROM gold.fact_orders f
    JOIN gold.dim_product p ON f.product_key = p.product_key
    GROUP BY p.category, p.sub_category
""")

fig3 = px.treemap(
    cat_df,
    path=["category", "sub_category"],
    values="revenue",
    color="margin_pct",
    color_continuous_scale="RdYlGn",
    color_continuous_midpoint=0,
    title="Revenue Treemap by Category/Sub-Category (colour = margin %)",
)
fig3.write_html(OUTPUT_DIR / "03_category_treemap.html")
print(f"\nChart 3 saved: {OUTPUT_DIR / '03_category_treemap.html'}")


# %% [markdown]
# ## 4. Discount Impact on Profitability

# %%
disc_df = wh.query("""
    SELECT
        CASE
            WHEN discount = 0         THEN '0% — No Discount'
            WHEN discount <= 0.1      THEN '1–10%'
            WHEN discount <= 0.2      THEN '11–20%'
            WHEN discount <= 0.3      THEN '21–30%'
            WHEN discount <= 0.5      THEN '31–50%'
            ELSE                           '>50%'
        END                                 AS discount_band,
        ROUND(AVG(profit_margin)*100, 2)    AS avg_margin_pct,
        COUNT(*)                            AS order_count,
        ROUND(SUM(profit), 0)               AS total_profit
    FROM gold.fact_orders
    GROUP BY discount_band
    ORDER BY avg_margin_pct DESC
""")

fig4 = px.bar(
    disc_df,
    x="discount_band",
    y="avg_margin_pct",
    color="avg_margin_pct",
    color_continuous_scale="RdYlGn",
    text="avg_margin_pct",
    title="Average Profit Margin by Discount Band",
    labels={"avg_margin_pct": "Avg Margin (%)", "discount_band": "Discount Band"},
)
fig4.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
fig4.write_html(OUTPUT_DIR / "04_discount_impact.html")
print(f"\nChart 4 saved: {OUTPUT_DIR / '04_discount_impact.html'}")
print(disc_df.to_string(index=False))


# %% [markdown]
# ## 5. Revenue Trend by Quarter

# %%
trend_df = wh.query("""
    SELECT
        order_year,
        order_quarter,
        g.market,
        ROUND(SUM(f.sales), 0)  AS revenue,
        ROUND(SUM(f.profit), 0) AS profit
    FROM gold.fact_orders f
    JOIN gold.dim_geography g ON f.geo_key = g.geo_key
    GROUP BY order_year, order_quarter, g.market
    ORDER BY order_year, order_quarter
""")
trend_df["period"] = (
    trend_df["order_year"].astype(str) + " Q" + trend_df["order_quarter"].astype(str)
)

fig5 = px.line(
    trend_df,
    x="period",
    y="revenue",
    color="market",
    markers=True,
    title="Quarterly Revenue Trend by Market Sector",
    labels={"revenue": "Revenue ($)", "period": "Quarter"},
)
fig5.write_html(OUTPUT_DIR / "05_quarterly_trend.html")
print(f"\nChart 5 saved: {OUTPUT_DIR / '05_quarterly_trend.html'}")


# %% [markdown]
# ## 6. Shipping Efficiency

# %%
ship_df = wh.query("""
    SELECT
        s.ship_mode,
        s.delivery_class,
        ROUND(AVG(f.days_to_ship), 1)   AS avg_days,
        ROUND(AVG(f.shipping_cost), 2)  AS avg_cost,
        COUNT(*)                        AS shipments
    FROM gold.fact_orders f
    JOIN gold.dim_ship_mode s ON f.ship_key = s.ship_key
    WHERE f.days_to_ship IS NOT NULL
    GROUP BY s.ship_mode, s.delivery_class
    ORDER BY avg_days
""")

fig6 = px.scatter(
    ship_df,
    x="avg_days",
    y="avg_cost",
    size="shipments",
    color="ship_mode",
    text="ship_mode",
    title="Shipping Mode — Days vs Cost (bubble = volume)",
    labels={"avg_days": "Avg Days to Ship", "avg_cost": "Avg Shipping Cost ($)"},
)
fig6.update_traces(textposition="top center")
fig6.write_html(OUTPUT_DIR / "06_shipping_efficiency.html")
print(f"\nChart 6 saved: {OUTPUT_DIR / '06_shipping_efficiency.html'}")

print("\n✓ EDA complete — all charts saved to", OUTPUT_DIR)
