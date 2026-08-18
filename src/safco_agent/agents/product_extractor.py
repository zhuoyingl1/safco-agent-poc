from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Any

from .page_classifier import PageType
from safco_agent.browser import PageSnapshot
from safco_agent.models import ExtractionStatus, Price, ProductRecord
from safco_agent.url_utils import canonicalize_url


class ProductExtractorAgent:
    """Extract normalized product records from Safco product detail pages."""

    supported_page_type = PageType.PRODUCT

    def extract(
        self,
        snapshot: PageSnapshot,
        source_category_url: str | None = None,
    ) -> list[ProductRecord]:
        graphs = self._load_json_ld(snapshot.json_ld)
        product_group = self._find_graph(graphs, "ProductGroup")
        product = product_group or self._find_graph(graphs, "Product")
        breadcrumbs = self._extract_breadcrumbs(graphs)
        if not product:
            return [self._fallback_record(snapshot, source_category_url)]

        parent_name = self._clean_text(product.get("name")) or snapshot.h1 or snapshot.title
        brand = self._extract_brand(product)
        category_path = self._category_path(product, breadcrumbs, parent_name)
        description = self._clean_text(product.get("description"))
        images = self._image_urls(product)
        group_sku = self._clean_text(product.get("sku") or product.get("productGroupID"))
        variants = product.get("hasVariant") or []
        if not isinstance(variants, list):
            variants = [variants]

        if not variants:
            return [
                self._record_from_payload(
                    payload=product,
                    snapshot=snapshot,
                    parent_name=parent_name,
                    brand=brand,
                    category_path=category_path,
                    description=description,
                    images=images,
                    source_category_url=source_category_url,
                    fallback_sku=group_sku,
                )
            ]

        records: list[ProductRecord] = []
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            records.append(
                self._record_from_payload(
                    payload=variant,
                    snapshot=snapshot,
                    parent_name=parent_name,
                    brand=brand,
                    category_path=category_path,
                    description=description,
                    images=images,
                    source_category_url=source_category_url,
                    fallback_sku=None,
                )
            )
        return records or [self._fallback_record(snapshot, source_category_url)]

    def _record_from_payload(
        self,
        payload: dict[str, Any],
        snapshot: PageSnapshot,
        parent_name: str,
        brand: str | None,
        category_path: list[str],
        description: str | None,
        images: list[str],
        source_category_url: str | None,
        fallback_sku: str | None,
    ) -> ProductRecord:
        variant_name = self._clean_text(payload.get("name"))
        sku = self._clean_text(payload.get("sku")) or fallback_sku
        offers = payload.get("offers") if isinstance(payload.get("offers"), dict) else {}
        price = self._price_from_offer(offers)
        errors = self._record_errors(parent_name, category_path, sku, price)
        status = ExtractionStatus.PARTIAL if errors else ExtractionStatus.COMPLETE
        return ProductRecord(
            parent_product_name=parent_name,
            variant_name=variant_name if variant_name != parent_name else None,
            brand=brand,
            manufacturer=brand,
            sku=sku,
            item_number=sku,
            mfr_number=None,
            category_path=category_path,
            product_url=canonicalize_url(snapshot.final_url),
            source_category_url=source_category_url,
            price=price,
            unit_pack_size=self._extract_pack_size(variant_name or description or ""),
            availability=self._availability_from_offer(offers),
            description=description,
            specifications=self._specifications(description, payload),
            image_urls=images,
            alternative_products=[],
            extraction_status=status,
            errors=errors,
        )

    def _fallback_record(
        self,
        snapshot: PageSnapshot,
        source_category_url: str | None,
    ) -> ProductRecord:
        parent_name = snapshot.h1 or snapshot.title or "Unknown product"
        price = self._price_from_text(snapshot.body_text)
        return ProductRecord(
            parent_product_name=parent_name,
            category_path=[],
            product_url=canonicalize_url(snapshot.final_url),
            source_category_url=source_category_url,
            price=price,
            description=snapshot.body_sample,
            extraction_status=ExtractionStatus.PARTIAL,
            errors=["product JSON-LD not found"],
        )

    def _load_json_ld(self, scripts: list[str]) -> list[dict[str, Any]]:
        graphs: list[dict[str, Any]] = []
        for script in scripts:
            try:
                payload = json.loads(script)
            except json.JSONDecodeError:
                continue
            graphs.extend(self._flatten_json_ld(payload))
        return graphs

    def _flatten_json_ld(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [
                graph
                for item in payload
                for graph in self._flatten_json_ld(item)
            ]
        if not isinstance(payload, dict):
            return []
        graphs = [payload]
        nested = payload.get("@graph")
        if isinstance(nested, list):
            graphs.extend(item for item in nested if isinstance(item, dict))
        return graphs

    def _find_graph(
        self,
        graphs: list[dict[str, Any]],
        graph_type: str,
    ) -> dict[str, Any] | None:
        for graph in graphs:
            value = graph.get("@type")
            if value == graph_type or (isinstance(value, list) and graph_type in value):
                return graph
        return None

    def _extract_breadcrumbs(self, graphs: list[dict[str, Any]]) -> list[str]:
        graph = self._find_graph(graphs, "BreadcrumbList")
        if not graph:
            return []
        items = graph.get("itemListElement") or []
        if not isinstance(items, list):
            return []
        names: list[str] = []
        for item in sorted(items, key=lambda value: value.get("position", 0)):
            if isinstance(item, dict):
                name = self._clean_text(item.get("name"))
                if name:
                    names.append(name)
        return names

    def _category_path(
        self,
        product: dict[str, Any],
        breadcrumbs: list[str],
        parent_name: str,
    ) -> list[str]:
        category = self._clean_text(product.get("category"))
        if category:
            return [part.strip() for part in category.split(">") if part.strip()]
        filtered = [part for part in breadcrumbs if part.lower() != "home"]
        if filtered and filtered[-1].lower() == parent_name.lower():
            filtered = filtered[:-1]
        return filtered

    def _extract_brand(self, product: dict[str, Any]) -> str | None:
        brand = product.get("brand")
        if isinstance(brand, dict):
            return self._clean_text(brand.get("name"))
        return self._clean_text(brand)

    def _image_urls(self, product: dict[str, Any]) -> list[str]:
        images = product.get("image") or []
        if isinstance(images, str):
            images = [images]
        if not isinstance(images, list):
            return []
        unique: list[str] = []
        seen: set[str] = set()
        for image in images:
            if not isinstance(image, str) or not image.startswith("http"):
                continue
            if image in seen:
                continue
            seen.add(image)
            unique.append(image)
        return unique

    def _price_from_offer(self, offers: dict[str, Any]) -> Price | None:
        value = offers.get("price")
        amount = self._decimal(value)
        currency = self._clean_text(offers.get("priceCurrency")) or "USD"
        if amount is None and value is None:
            return None
        return Price(
            raw=f"{currency} {value}" if value is not None else None,
            amount=amount,
            currency=currency,
        )

    def _price_from_text(self, text: str) -> Price | None:
        match = re.search(r"(?:From|As low as)?\s*\$([0-9]+(?:\.[0-9]{2})?)", text)
        if not match:
            return None
        return Price(raw=match.group(0).strip(), amount=Decimal(match.group(1)), currency="USD")

    def _availability_from_offer(self, offers: dict[str, Any]) -> str | None:
        availability = self._clean_text(offers.get("availability"))
        if not availability:
            return None
        return availability.rstrip("/").split("/")[-1]

    def _specifications(
        self,
        description: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        specs: dict[str, Any] = {}
        if payload.get("@id"):
            specs["source_id"] = payload["@id"]
        if description:
            for key, value in re.findall(r"([A-Z][A-Za-z /-]{2,30}):\s*([^;]+)", description):
                specs[key.strip().lower().replace(" ", "_")] = value.strip()
        return specs

    def _extract_pack_size(self, text: str) -> str | None:
        patterns = [
            r"\b\d+\s*/\s*(?:box|pack|case|pkg)\b",
            r"\b\d+(?:\.\d+)?\s*(?:oz|g|ml)\s+(?:bottle|syringe|tube|jar)\b",
            r"\b\d+\s+(?:gloves|syringes|bottles|packs)\s+per\s+\w+\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(0)
        return None

    def _record_errors(
        self,
        parent_name: str,
        category_path: list[str],
        sku: str | None,
        price: Price | None,
    ) -> list[str]:
        errors: list[str] = []
        if not parent_name:
            errors.append("missing product name")
        if not category_path:
            errors.append("missing category path")
        if not sku:
            errors.append("missing sku")
        if not price or price.amount is None:
            errors.append("missing price")
        return errors

    def _decimal(self, value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value).replace("$", "").replace(",", "").strip())
        except (InvalidOperation, ValueError):
            return None

    def _clean_text(self, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"<[^>]+>", " ", unescape(str(value)))
        cleaned = " ".join(cleaned.split())
        return cleaned or None
