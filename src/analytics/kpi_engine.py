"""
Analytics / KPI engine: generates business reports from the Gold layer.
Outputs CSV and Parquet reports to data/analytics/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from src.gold.warehouse import GoldWarehouse
from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class KPIEngine:
    """Computes and exports sector market research KPI reports."""

    def __init__(
        self,
        warehouse: Optional[GoldWarehouse] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        self.wh = warehouse or GoldWarehouse()
        self.output_dir = output_dir or config.analytics_path
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_all(self) -> dict[str, str]:
        """Generate all KPI reports. Returns dict of report_name → file_path."""
        logger.info("Generating KPI reports...")
        reports: dict[str, str] = {}

        reports.update(self._sector_performance())
        reports.update(self._segment_analysis())
        reports.update(self._top_products())
        reports.update(self._regional_trends())
        reports.update(self._discount_impact())
        reports.update(self._shipping_efficiency())
        reports.update(self._executive_summary())

        logger.info("Generated %d reports → %s", len(reports), self.output_dir)
        return reports

    # ── Report methods ────────────────────────────────────────────────────

    def _sector_performance(self) -> dict[str, str]:
        """Sales, profit, and margin by market sector and product category."""
        sql = """
        SELECT
            g.market,
            g.region,
            p.category,
            f.order_year,
            f.order_quarter,
            COUNT(DISTINCT f.order_id)                          AS order_count,
            ROUND(SUM(f.sales), 2)                              AS total_sales,
            ROUND(SUM(f.profit), 2)                             AS total_profit,
            ROUND(AVG(f.profit_margin) * 100, 2)                AS avg_margin_pct,
            ROUND(SUM(f.sales) / NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS avg_order_value
        FROM gold.fact_orders f
        JOIN gold.dim_geography g   ON f.geo_key      = g.geo_key
        JOIN gold.dim_product   p   ON f.product_key  = p.product_key
        WHERE f.sales IS NOT NULL
        GROUP BY g.market, g.region, p.category, f.order_year, f.order_quarter
        ORDER BY g.market, f.order_year, f.order_quarter, total_sales DESC
        """
        return self._save_report(sql, "sector_performance")

    def _segment_analysis(self) -> dict[str, str]:
        """Revenue, profit, and order volume by customer segment."""
        sql = """
        SELECT
            c.segment,
            g.market,
            f.order_year,
            COUNT(DISTINCT c.customer_id)                      AS unique_customers,
            COUNT(DISTINCT f.order_id)                          AS order_count,
            ROUND(SUM(f.sales), 2)                              AS total_revenue,
            ROUND(SUM(f.profit), 2)                             AS total_profit,
            ROUND(AVG(f.discount) * 100, 2)                     AS avg_discount_pct,
            ROUND(SUM(f.sales) / NULLIF(COUNT(DISTINCT c.customer_id), 0), 2)
                                                                AS revenue_per_customer
        FROM gold.fact_orders f
        JOIN gold.dim_customer  c ON f.customer_key = c.customer_key
        JOIN gold.dim_geography g ON f.geo_key      = g.geo_key
        GROUP BY c.segment, g.market, f.order_year
        ORDER BY f.order_year, total_revenue DESC
        """
        return self._save_report(sql, "segment_analysis")

    def _top_products(self) -> dict[str, str]:
        """Top 20 products by profit margin with sales context."""
        sql = """
        SELECT
            p.product_name,
            p.category,
            p.sub_category,
            COUNT(*)                                            AS order_lines,
            ROUND(SUM(f.quantity), 0)                           AS units_sold,
            ROUND(SUM(f.sales), 2)                              AS total_sales,
            ROUND(SUM(f.profit), 2)                             AS total_profit,
            ROUND(AVG(f.profit_margin) * 100, 2)                AS avg_margin_pct,
            ROUND(AVG(f.discount) * 100, 2)                     AS avg_discount_pct
        FROM gold.fact_orders f
        JOIN gold.dim_product p ON f.product_key = p.product_key
        GROUP BY p.product_name, p.category, p.sub_category
        HAVING SUM(f.sales) > 100
        ORDER BY avg_margin_pct DESC
        LIMIT 20
        """
        return self._save_report(sql, "top_products")

    def _regional_trends(self) -> dict[str, str]:
        """Quarter-over-quarter growth in sales and profit per region."""
        sql = """
        WITH quarterly AS (
            SELECT
                g.market,
                g.region,
                f.order_year,
                f.order_quarter,
                ROUND(SUM(f.sales), 2)  AS sales,
                ROUND(SUM(f.profit), 2) AS profit
            FROM gold.fact_orders f
            JOIN gold.dim_geography g ON f.geo_key = g.geo_key
            GROUP BY g.market, g.region, f.order_year, f.order_quarter
        ),
        lagged AS (
            SELECT *,
                LAG(sales)  OVER (PARTITION BY market, region ORDER BY order_year, order_quarter)
                    AS prev_sales,
                LAG(profit) OVER (PARTITION BY market, region ORDER BY order_year, order_quarter)
                    AS prev_profit
            FROM quarterly
        )
        SELECT
            market,
            region,
            order_year,
            order_quarter,
            sales,
            profit,
            ROUND((sales - prev_sales) / NULLIF(prev_sales, 0) * 100, 2)   AS qoq_sales_growth_pct,
            ROUND((profit - prev_profit) / NULLIF(prev_profit, 0) * 100, 2) AS qoq_profit_growth_pct
        FROM lagged
        ORDER BY market, region, order_year, order_quarter
        """
        return self._save_report(sql, "regional_trends")

    def _discount_impact(self) -> dict[str, str]:
        """Correlation between discount bands and profit outcomes."""
        sql = """
        SELECT
            p.category,
            CASE
                WHEN f.discount = 0            THEN '0% (No Discount)'
                WHEN f.discount <= 0.1         THEN '1–10%'
                WHEN f.discount <= 0.2         THEN '11–20%'
                WHEN f.discount <= 0.3         THEN '21–30%'
                WHEN f.discount <= 0.5         THEN '31–50%'
                ELSE                                '>50%'
            END                                                 AS discount_band,
            COUNT(*)                                            AS order_count,
            ROUND(SUM(f.sales), 2)                              AS total_sales,
            ROUND(SUM(f.profit), 2)                             AS total_profit,
            ROUND(AVG(f.profit_margin) * 100, 2)                AS avg_margin_pct,
            ROUND(AVG(f.discount) * 100, 2)                     AS avg_discount_pct
        FROM gold.fact_orders f
        JOIN gold.dim_product p ON f.product_key = p.product_key
        GROUP BY p.category, discount_band
        ORDER BY p.category, avg_discount_pct
        """
        return self._save_report(sql, "discount_impact")

    def _shipping_efficiency(self) -> dict[str, str]:
        """Average shipping time and cost by ship mode and region."""
        sql = """
        SELECT
            s.ship_mode,
            s.delivery_class,
            g.market,
            COUNT(*)                                            AS shipments,
            ROUND(AVG(f.days_to_ship), 1)                       AS avg_days_to_ship,
            ROUND(AVG(f.shipping_cost), 2)                      AS avg_shipping_cost,
            ROUND(SUM(f.shipping_cost), 2)                      AS total_shipping_cost,
            ROUND(SUM(f.sales), 2)                              AS total_sales
        FROM gold.fact_orders f
        JOIN gold.dim_ship_mode  s ON f.ship_key = s.ship_key
        JOIN gold.dim_geography  g ON f.geo_key  = g.geo_key
        WHERE f.days_to_ship IS NOT NULL
        GROUP BY s.ship_mode, s.delivery_class, g.market
        ORDER BY g.market, avg_days_to_ship
        """
        return self._save_report(sql, "shipping_efficiency")

    def _executive_summary(self) -> dict[str, str]:
        """Single-row executive summary of overall pipeline KPIs."""
        sql = """
        SELECT
            COUNT(DISTINCT f.order_id)           AS total_orders,
            COUNT(DISTINCT c.customer_id)        AS total_customers,
            COUNT(DISTINCT p.product_id)         AS total_products,
            COUNT(DISTINCT g.country)            AS total_countries,
            COUNT(DISTINCT g.market)             AS total_markets,
            MIN(d.full_date)                     AS earliest_order,
            MAX(d.full_date)                     AS latest_order,
            ROUND(SUM(f.sales), 2)               AS total_revenue,
            ROUND(SUM(f.profit), 2)              AS total_profit,
            ROUND(AVG(f.profit_margin) * 100, 2) AS overall_margin_pct,
            ROUND(AVG(f.discount) * 100, 2)      AS avg_discount_pct,
            ROUND(SUM(f.shipping_cost), 2)       AS total_shipping_cost
        FROM gold.fact_orders   f
        JOIN gold.dim_customer  c ON f.customer_key = c.customer_key
        JOIN gold.dim_product   p ON f.product_key  = p.product_key
        JOIN gold.dim_geography g ON f.geo_key      = g.geo_key
        JOIN gold.dim_date      d ON f.date_key     = d.date_key
        """
        return self._save_report(sql, "executive_summary")

    # ── Helper ────────────────────────────────────────────────────────────

    def _save_report(self, sql: str, name: str) -> dict[str, str]:
        try:
            df = self.wh.query(sql)
            if df.empty:
                logger.warning("Report '%s' returned no data", name)
                return {}

            csv_path = self.output_dir / f"{name}.csv"
            parquet_path = self.output_dir / f"{name}.parquet"
            df.to_csv(csv_path, index=False)
            df.to_parquet(parquet_path, index=False)
            logger.info("Report '%s': %d rows → %s", name, len(df), csv_path)
            return {name: str(csv_path)}
        except Exception as exc:
            logger.error("Failed to generate report '%s': %s", name, exc)
            return {}
