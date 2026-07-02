"""
Gold layer: builds a Star Schema in DuckDB from Silver Parquet data.
Produces: dim_date, dim_customer, dim_product, dim_geography,
          dim_ship_mode, fact_orders
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

SCHEMA_DDL = """
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS analytics;

-- ── Dimension Tables ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS gold.dim_date (
    date_key        INTEGER PRIMARY KEY,
    full_date       DATE,
    year            INTEGER,
    quarter         INTEGER,
    month           INTEGER,
    month_name      VARCHAR,
    week            INTEGER,
    day_of_month    INTEGER,
    day_of_week     INTEGER,
    day_name        VARCHAR,
    is_weekend      BOOLEAN,
    fiscal_year     INTEGER,
    fiscal_quarter  INTEGER
);

CREATE TABLE IF NOT EXISTS gold.dim_customer (
    customer_key    INTEGER PRIMARY KEY,
    customer_id     VARCHAR NOT NULL,
    customer_name   VARCHAR,
    segment         VARCHAR
);

CREATE TABLE IF NOT EXISTS gold.dim_product (
    product_key     INTEGER PRIMARY KEY,
    product_id      VARCHAR NOT NULL,
    product_name    VARCHAR,
    category        VARCHAR,
    sub_category    VARCHAR
);

CREATE TABLE IF NOT EXISTS gold.dim_geography (
    geo_key         INTEGER PRIMARY KEY,
    country         VARCHAR,
    city            VARCHAR,
    state           VARCHAR,
    postal_code     VARCHAR,
    region          VARCHAR,
    market          VARCHAR
);

CREATE TABLE IF NOT EXISTS gold.dim_ship_mode (
    ship_key        INTEGER PRIMARY KEY,
    ship_mode       VARCHAR NOT NULL,
    delivery_class  VARCHAR
);

-- ── Fact Table ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gold.fact_orders (
    order_key       BIGINT PRIMARY KEY,
    order_id        VARCHAR NOT NULL,
    date_key        INTEGER REFERENCES gold.dim_date(date_key),
    ship_date_key   INTEGER REFERENCES gold.dim_date(date_key),
    customer_key    INTEGER REFERENCES gold.dim_customer(customer_key),
    product_key     INTEGER REFERENCES gold.dim_product(product_key),
    geo_key         INTEGER REFERENCES gold.dim_geography(geo_key),
    ship_key        INTEGER REFERENCES gold.dim_ship_mode(ship_key),
    sales           DECIMAL(12,4),
    quantity        INTEGER,
    discount        DECIMAL(6,4),
    profit          DECIMAL(12,4),
    shipping_cost   DECIMAL(12,4),
    profit_margin   DECIMAL(8,4),
    days_to_ship    INTEGER,
    order_priority  VARCHAR,
    order_year      INTEGER,
    order_quarter   INTEGER,
    order_month     INTEGER
);
"""


class GoldWarehouse:
    """Manages the DuckDB Star Schema (Gold layer)."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or config.db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(self.db_path)

    def initialise_schema(self) -> None:
        """Create all schemas and tables if not present."""
        logger.info("Initialising DuckDB Gold schema at %s", self.db_path)
        with self._connect() as con:
            con.execute(SCHEMA_DDL)
        logger.info("Schema initialisation complete")

    def load(self, df: pd.DataFrame) -> dict[str, int]:
        """
        Build all dimension tables and the fact table from a Silver DataFrame.
        Returns row counts per table.
        """
        logger.info("Loading %d rows into Gold Star Schema", len(df))
        self.initialise_schema()

        with self._connect() as con:
            counts: dict[str, int] = {}
            counts["dim_date"] = self._load_dim_date(con, df)
            counts["dim_customer"] = self._load_dim_customer(con, df)
            counts["dim_product"] = self._load_dim_product(con, df)
            counts["dim_geography"] = self._load_dim_geography(con, df)
            counts["dim_ship_mode"] = self._load_dim_ship_mode(con, df)
            counts["fact_orders"] = self._load_fact_orders(con, df)

        logger.info("Gold load complete: %s", counts)
        return counts

    # ── Dimension loaders ─────────────────────────────────────────────────

    def _load_dim_date(self, con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
        dates = pd.to_datetime(
            pd.concat([df["order_date"], df.get("ship_date", pd.Series())]).dropna()
        ).drop_duplicates()

        dim = pd.DataFrame({
            "full_date": dates,
            "year": dates.dt.year,
            "quarter": dates.dt.quarter,
            "month": dates.dt.month,
            "month_name": dates.dt.strftime("%B"),
            "week": dates.dt.isocalendar().week.astype(int),
            "day_of_month": dates.dt.day,
            "day_of_week": dates.dt.dayofweek + 1,
            "day_name": dates.dt.strftime("%A"),
            "is_weekend": dates.dt.dayofweek >= 5,
            "fiscal_year": dates.dt.year,
            "fiscal_quarter": dates.dt.quarter,
        })
        dim["date_key"] = dim["full_date"].dt.strftime("%Y%m%d").astype(int)
        # Store full_date as Python date objects so DuckDB gets DATE, not TIMESTAMP
        dim["full_date"] = dim["full_date"].dt.date
        dim = dim.drop_duplicates(subset=["date_key"])

        # Explicit column order to match DDL
        col_order = [
            "date_key", "full_date", "year", "quarter", "month", "month_name",
            "week", "day_of_month", "day_of_week", "day_name", "is_weekend",
            "fiscal_year", "fiscal_quarter",
        ]
        dim = dim[col_order]

        con.execute("DELETE FROM gold.dim_date")
        con.register("dim_date_tmp", dim)
        con.execute("INSERT INTO gold.dim_date SELECT * FROM dim_date_tmp")
        con.unregister("dim_date_tmp")
        return len(dim)

    def _load_dim_customer(self, con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
        dim = (
            df[["customer_id", "customer_name", "segment"]]
            .drop_duplicates(subset=["customer_id"])
            .reset_index(drop=True)
        )
        dim["customer_key"] = range(1, len(dim) + 1)

        con.execute("DELETE FROM gold.dim_customer")
        con.execute("INSERT INTO gold.dim_customer SELECT customer_key, customer_id, customer_name, segment FROM dim")
        return len(dim)

    def _load_dim_product(self, con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
        dim = (
            df[["product_id", "product_name", "category", "sub_category"]]
            .drop_duplicates(subset=["product_id"])
            .reset_index(drop=True)
        )
        dim["product_key"] = range(1, len(dim) + 1)

        con.execute("DELETE FROM gold.dim_product")
        con.execute("INSERT INTO gold.dim_product SELECT product_key, product_id, product_name, category, sub_category FROM dim")
        return len(dim)

    def _load_dim_geography(self, con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
        geo_cols = [c for c in ["country", "city", "state", "postal_code", "region", "market"] if c in df.columns]
        dim = df[geo_cols].copy().drop_duplicates().reset_index(drop=True)
        # Ensure all geo columns are strings to avoid DuckDB type coercion issues
        for col in geo_cols:
            dim[col] = dim[col].astype(str)
        dim["geo_key"] = range(1, len(dim) + 1)
        for col in ["country", "city", "state", "postal_code", "region", "market"]:
            if col not in dim.columns:
                dim[col] = None

        con.execute("DELETE FROM gold.dim_geography")
        con.register("dim_geo_tmp", dim)
        con.execute("INSERT INTO gold.dim_geography SELECT geo_key, country, city, state, postal_code, region, market FROM dim_geo_tmp")
        con.unregister("dim_geo_tmp")
        return len(dim)

    def _load_dim_ship_mode(self, con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
        delivery_map = {
            "First Class": "Premium",
            "Second Class": "Standard",
            "Standard Class": "Economy",
            "Same Day": "Express",
        }
        dim = (
            df[["ship_mode"]]
            .drop_duplicates()
            .reset_index(drop=True)
        )
        dim["ship_key"] = range(1, len(dim) + 1)
        dim["delivery_class"] = dim["ship_mode"].map(delivery_map).fillna("Standard")

        con.execute("DELETE FROM gold.dim_ship_mode")
        con.execute("INSERT INTO gold.dim_ship_mode SELECT ship_key, ship_mode, delivery_class FROM dim")
        return len(dim)

    def _load_fact_orders(self, con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
        # Fetch surrogate keys
        cust_map = con.execute(
            "SELECT customer_id, customer_key FROM gold.dim_customer"
        ).df().set_index("customer_id")["customer_key"]

        prod_map = con.execute(
            "SELECT product_id, product_key FROM gold.dim_product"
        ).df().set_index("product_id")["product_key"]

        geo_cols = [c for c in ["country", "city", "state", "postal_code", "region", "market"] if c in df.columns]
        geo_dim = con.execute("SELECT * FROM gold.dim_geography").df()

        ship_map = con.execute(
            "SELECT ship_mode, ship_key FROM gold.dim_ship_mode"
        ).df().set_index("ship_mode")["ship_key"]

        fact = df.copy()

        # Coerce all geo join columns to str to avoid type mismatches (e.g. postal_code int vs str)
        for col in geo_cols:
            fact[col] = fact[col].astype(str)
            geo_dim[col] = geo_dim[col].astype(str)

        fact["customer_key"] = fact["customer_id"].map(cust_map)
        fact["product_key"] = fact["product_id"].map(prod_map)
        fact["ship_key"] = fact["ship_mode"].map(ship_map)

        # Geo join
        geo_merged = fact[geo_cols].merge(geo_dim[geo_cols + ["geo_key"]], on=geo_cols, how="left")
        fact["geo_key"] = geo_merged["geo_key"].values

        # Date keys
        fact["date_key"] = pd.to_datetime(fact["order_date"]).dt.strftime("%Y%m%d").astype("Int64")
        if "ship_date" in fact.columns:
            fact["ship_date_key"] = pd.to_datetime(fact["ship_date"], errors="coerce").dt.strftime("%Y%m%d")
            fact["ship_date_key"] = pd.to_numeric(fact["ship_date_key"], errors="coerce").astype("Int64")
        else:
            fact["ship_date_key"] = None

        fact_cols = [
            "order_id", "date_key", "ship_date_key", "customer_key",
            "product_key", "geo_key", "ship_key",
            "sales", "quantity", "discount", "profit", "shipping_cost",
            "profit_margin", "days_to_ship", "order_priority",
            "order_year", "order_quarter", "order_month",
        ]
        fact_final = fact[[c for c in fact_cols if c in fact.columns]].copy()
        fact_final["order_key"] = range(1, len(fact_final) + 1)
        fact_final = fact_final.dropna(subset=["customer_key", "product_key", "geo_key"])

        con.execute("DELETE FROM gold.fact_orders")
        con.register("fact_final", fact_final)
        con.execute(
            "INSERT INTO gold.fact_orders SELECT order_key, order_id, date_key, ship_date_key, "
            "customer_key, product_key, geo_key, ship_key, sales, quantity, discount, profit, "
            "shipping_cost, profit_margin, days_to_ship, order_priority, "
            "order_year, order_quarter, order_month FROM fact_final"
        )
        return len(fact_final)

    def query(self, sql: str) -> pd.DataFrame:
        """Execute a SQL query against the DuckDB warehouse."""
        with self._connect() as con:
            return con.execute(sql).df()

    def table_counts(self) -> dict[str, int]:
        """Return row counts for all Gold tables."""
        tables = [
            "gold.dim_date", "gold.dim_customer", "gold.dim_product",
            "gold.dim_geography", "gold.dim_ship_mode", "gold.fact_orders",
        ]
        counts = {}
        with self._connect() as con:
            for t in tables:
                try:
                    counts[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                except Exception:
                    counts[t] = 0
        return counts
