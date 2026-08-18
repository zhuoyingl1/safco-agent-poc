from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, computed_field, field_validator


class ExtractionStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class Price(BaseModel):
    raw: str | None = None
    amount: Decimal | None = None
    currency: str | None = "USD"


class ProductRecord(BaseModel):
    parent_product_name: str = Field(min_length=1)
    variant_name: str | None = None
    brand: str | None = None
    manufacturer: str | None = None
    sku: str | None = None
    item_number: str | None = None
    mfr_number: str | None = None
    category_path: list[str] = Field(default_factory=list)
    product_url: HttpUrl
    source_category_url: HttpUrl | None = None
    price: Price | None = None
    unit_pack_size: str | None = None
    availability: str | None = None
    description: str | None = None
    specifications: dict[str, Any] = Field(default_factory=dict)
    image_urls: list[HttpUrl] = Field(default_factory=list)
    alternative_products: list[HttpUrl] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    extraction_status: ExtractionStatus = ExtractionStatus.PARTIAL
    errors: list[str] = Field(default_factory=list)

    @field_validator("category_path")
    @classmethod
    def strip_category_parts(cls, value: list[str]) -> list[str]:
        return [part.strip() for part in value if part and part.strip()]

    @computed_field
    @property
    def product_id(self) -> str:
        identity = "|".join(
            [
                str(self.product_url).rstrip("/"),
                self.sku or "",
                self.item_number or "",
                self.mfr_number or "",
                self.variant_name or "",
            ]
        )
        return sha256(identity.encode("utf-8")).hexdigest()

