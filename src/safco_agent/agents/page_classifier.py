from __future__ import annotations

from enum import StrEnum


class PageType(StrEnum):
    CATEGORY = "category"
    LISTING = "listing"
    PRODUCT = "product"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class PageClassifierAgent:
    """Rule-first page classifier with room for LLM fallback later."""

    def classify(self, url: str, text: str) -> PageType:
        normalized_text = " ".join(text.lower().split())
        if "unable to accept or process orders" in normalized_text:
            return PageType.BLOCKED
        if "/product/" in url:
            return PageType.PRODUCT
        if "item #" in normalized_text and "stock availability" in normalized_text:
            return PageType.PRODUCT
        if "/catalog/" in url and ("showing" in normalized_text or "products" in normalized_text):
            return PageType.LISTING
        if "/catalog/" in url:
            return PageType.CATEGORY
        return PageType.UNKNOWN

