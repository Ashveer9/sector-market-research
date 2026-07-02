"""Central configuration loader with environment variable overrides."""

import os
from pathlib import Path
from typing import Any

import yaml


class Config:
    """Loads config.yaml and applies .env overrides."""

    _instance: "Config | None" = None
    _data: dict = {}

    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        with open(config_path) as f:
            self._data = yaml.safe_load(f)

        # Apply environment variable overrides
        env_overrides = {
            "DUCKDB_PATH": ("paths", "db"),
            "LOG_LEVEL": ("logging", "level"),
            "DATA_ROOT": ("paths", "data_root"),
        }
        for env_key, (section, key) in env_overrides.items():
            if val := os.getenv(env_key):
                self._data.setdefault(section, {})[key] = val

    def get(self, *keys: str, default: Any = None) -> Any:
        """Dot-path accessor: config.get('paths', 'db')."""
        node = self._data
        for key in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(key, default)
        return node

    @property
    def data_root(self) -> Path:
        return Path(self.get("paths", "data_root", default="data"))

    @property
    def raw_path(self) -> Path:
        return Path(self.get("paths", "raw", default="data/raw"))

    @property
    def processed_path(self) -> Path:
        return Path(self.get("paths", "processed", default="data/processed"))

    @property
    def analytics_path(self) -> Path:
        return Path(self.get("paths", "analytics", default="data/analytics"))

    @property
    def db_path(self) -> str:
        return self.get("paths", "db", default="data/warehouse.duckdb")

    @property
    def sample_path(self) -> Path:
        return Path(self.get("paths", "sample", default="data/sample"))


# Singleton instance
config = Config()
