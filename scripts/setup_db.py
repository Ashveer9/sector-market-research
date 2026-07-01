"""
Initialise the DuckDB warehouse schema.
Run this once before loading data if you want to inspect the empty schema.

Usage:
    python scripts/setup_db.py [--db path/to/warehouse.duckdb]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import duckdb

from src.gold.warehouse import SCHEMA_DDL, GoldWarehouse
from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def setup(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    logger.info("Initialising DuckDB schema at: %s", db_path)

    with duckdb.connect(db_path) as con:
        con.execute(SCHEMA_DDL)

    wh = GoldWarehouse(db_path=db_path)
    counts = wh.table_counts()
    logger.info("Schema ready. Tables: %s", list(counts.keys()))

    print("\nGold layer tables:")
    for table, count in counts.items():
        print(f"  {table:<35} {count:>8} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialise DuckDB warehouse schema")
    parser.add_argument(
        "--db",
        default=config.db_path,
        help=f"Path to DuckDB file (default: {config.db_path})",
    )
    args = parser.parse_args()
    setup(args.db)


if __name__ == "__main__":
    main()
