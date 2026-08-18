from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, HttpUrl, PositiveInt, field_validator


class SeedCategory(BaseModel):
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    url: HttpUrl


class CrawlConfig(BaseModel):
    user_agent: str = Field(min_length=1)
    request_timeout_ms: PositiveInt = 30000
    browser_timeout_ms: PositiveInt = 45000
    rate_limit_seconds: float = Field(default=1.0, ge=0)
    concurrency: PositiveInt = 2
    max_pages_per_category: PositiveInt = 3
    max_products_per_category: PositiveInt = 25
    output_dir: Path = Path("output")
    checkpoint_db: Path = Path("output/safco.sqlite")


class AppConfig(BaseModel):
    project_name: str = Field(min_length=1)
    seed_categories: list[SeedCategory] = Field(min_length=1)
    crawl: CrawlConfig

    @field_validator("seed_categories")
    @classmethod
    def category_keys_are_unique(cls, value: list[SeedCategory]) -> list[SeedCategory]:
        keys = [category.key for category in value]
        if len(keys) != len(set(keys)):
            raise ValueError("seed category keys must be unique")
        return value


def load_config(path: Path) -> AppConfig:
    data = _read_yaml(path)
    return AppConfig.model_validate(data)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must contain a YAML object: {path}")
    return data

