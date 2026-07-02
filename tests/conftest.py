"""Shared pytest fixtures for the sector-market-research test suite."""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Ensure src/ is importable from tests
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Minimal valid DataFrame mimicking Silver-layer output."""
    return pd.DataFrame({
        "order_id":      ["CA-2013-100001", "CA-2013-100001", "CA-2013-100002", "CA-2013-100003"],
        "order_date":    ["2013-01-15",      "2013-01-15",      "2013-03-22",      "2013-06-10"],
        "ship_date":     ["2013-01-18",      "2013-01-18",      "2013-03-26",      "2013-06-14"],
        "ship_mode":     ["Standard Class",  "Standard Class",  "First Class",     "Second Class"],
        "customer_id":   ["CG-12520",        "CG-12520",        "DV-13045",        "SO-20335"],
        "customer_name": ["Claire Gute",     "Claire Gute",     "Darrin Van Huff", "Sean O'Donnell"],
        "segment":       ["Consumer",        "Consumer",        "Corporate",       "Consumer"],
        "city":          ["Henderson",       "Henderson",       "Los Angeles",     "Fort Lauderdale"],
        "state":         ["Kentucky",        "Kentucky",        "California",      "Florida"],
        "country":       ["United States",   "United States",   "United States",   "United States"],
        "postal_code":   ["42420",           "42420",           "90036",           "33311"],
        "market":        ["US",              "US",              "US",              "US"],
        "region":        ["South",           "South",           "West",            "South"],
        "product_id":    ["FUR-BO-10001798", "FUR-CH-10000454", "OFF-LA-10000240", "FUR-TA-10000198"],
        "category":      ["Furniture",       "Furniture",       "Office Supplies", "Furniture"],
        "sub_category":  ["Bookcases",       "Chairs",          "Labels",          "Tables"],
        "product_name":  ["Bush Somerset",   "Hon Deluxe Fabric", "Self-Adhesive",  "Bretford Table"],
        "sales":         [261.96,            731.94,             14.62,             957.58],
        "quantity":      [2,                 3,                  2,                 5],
        "discount":      [0.0,               0.0,                0.0,               0.45],
        "profit":        [41.91,             219.58,             6.87,              -383.03],
        "shipping_cost": [35.0,              65.0,               5.0,               80.0],
        "order_priority":["Medium",          "Medium",           "High",            "Medium"],
    })


@pytest.fixture
def raw_df() -> pd.DataFrame:
    """Raw ingestor-format DataFrame (original column names)."""
    return pd.DataFrame({
        "Row ID":        [1, 2, 3],
        "Order ID":      ["CA-2013-100001", "CA-2013-100002", "CA-2013-100003"],
        "Order Date":    ["15/01/2013",     "22/03/2013",     "10/06/2013"],
        "Ship Date":     ["18/01/2013",     "26/03/2013",     "14/06/2013"],
        "Ship Mode":     ["Standard Class", "First Class",    "Second Class"],
        "Customer ID":   ["CG-12520",       "DV-13045",       "SO-20335"],
        "Customer Name": ["Claire Gute",    "Darrin Van Huff","Sean O'Donnell"],
        "Segment":       ["Consumer",       "Corporate",      "Consumer"],
        "City":          ["Henderson",      "Los Angeles",    "Fort Lauderdale"],
        "State":         ["Kentucky",       "California",     "Florida"],
        "Country":       ["United States",  "United States",  "United States"],
        "Postal Code":   ["42420",          "90036",          "33311"],
        "Market":        ["US",             "US",             "US"],
        "Region":        ["South",          "West",           "South"],
        "Product ID":    ["FUR-BO-10001798","OFF-LA-10000240","FUR-TA-10000198"],
        "Category":      ["Furniture",      "Office Supplies","Furniture"],
        "Sub-Category":  ["Bookcases",      "Labels",         "Tables"],
        "Product Name":  ["Bush Somerset",  "Self-Adhesive",  "Bretford Table"],
        "Sales":         [261.96,           14.62,            957.58],
        "Quantity":      [2,                2,                5],
        "Discount":      [0.0,              0.0,              0.45],
        "Profit":        [41.91,            6.87,             -383.03],
        "Shipping Cost": [35.0,             5.0,              80.0],
        "Order Priority":["Medium",         "High",           "Medium"],
    })


@pytest.fixture
def tmp_duckdb(tmp_path: Path) -> str:
    """Return a temp DuckDB path."""
    return str(tmp_path / "test_warehouse.duckdb")
