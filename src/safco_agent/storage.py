from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

from safco_agent.models import ProductRecord


CSV_FIELDS = [
    "product_id",
    "parent_product_name",
    "variant_name",
    "brand",
    "manufacturer",
    "sku",
    "item_number",
    "mfr_number",
    "category_path",
    "product_url",
    "source_category_url",
    "price_raw",
    "price_amount",
    "price_currency",
    "unit_pack_size",
    "availability",
    "description",
    "specifications",
    "image_urls",
    "alternative_products",
    "scraped_at",
    "extraction_status",
    "errors",
]


def write_product_outputs(
    records: list[ProductRecord],
    jsonl_path: Path,
    csv_path: Path | None = None,
    sqlite_path: Path | None = None,
) -> None:
    write_jsonl(records, jsonl_path)
    if csv_path:
        write_csv(records, csv_path)
    if sqlite_path:
        write_sqlite(records, sqlite_path)


def write_jsonl(records: list[ProductRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.model_dump(mode="json")) + "\n")


def write_csv(records: list[ProductRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(_flatten_record(record))


def write_sqlite(records: list[ProductRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                parent_product_name TEXT NOT NULL,
                variant_name TEXT,
                brand TEXT,
                manufacturer TEXT,
                sku TEXT,
                item_number TEXT,
                mfr_number TEXT,
                category_path TEXT NOT NULL,
                product_url TEXT NOT NULL,
                source_category_url TEXT,
                price_raw TEXT,
                price_amount TEXT,
                price_currency TEXT,
                unit_pack_size TEXT,
                availability TEXT,
                description TEXT,
                specifications TEXT NOT NULL,
                image_urls TEXT NOT NULL,
                alternative_products TEXT NOT NULL,
                scraped_at TEXT NOT NULL,
                extraction_status TEXT NOT NULL,
                errors TEXT NOT NULL
            )
            """
        )
        connection.execute("DELETE FROM products")
        rows = [_flatten_record(record) for record in records]
        connection.executemany(
            """
            INSERT INTO products (
                product_id,
                parent_product_name,
                variant_name,
                brand,
                manufacturer,
                sku,
                item_number,
                mfr_number,
                category_path,
                product_url,
                source_category_url,
                price_raw,
                price_amount,
                price_currency,
                unit_pack_size,
                availability,
                description,
                specifications,
                image_urls,
                alternative_products,
                scraped_at,
                extraction_status,
                errors
            ) VALUES (
                :product_id,
                :parent_product_name,
                :variant_name,
                :brand,
                :manufacturer,
                :sku,
                :item_number,
                :mfr_number,
                :category_path,
                :product_url,
                :source_category_url,
                :price_raw,
                :price_amount,
                :price_currency,
                :unit_pack_size,
                :availability,
                :description,
                :specifications,
                :image_urls,
                :alternative_products,
                :scraped_at,
                :extraction_status,
                :errors
            )
            ON CONFLICT(product_id) DO UPDATE SET
                parent_product_name = excluded.parent_product_name,
                variant_name = excluded.variant_name,
                brand = excluded.brand,
                manufacturer = excluded.manufacturer,
                sku = excluded.sku,
                item_number = excluded.item_number,
                mfr_number = excluded.mfr_number,
                category_path = excluded.category_path,
                product_url = excluded.product_url,
                source_category_url = excluded.source_category_url,
                price_raw = excluded.price_raw,
                price_amount = excluded.price_amount,
                price_currency = excluded.price_currency,
                unit_pack_size = excluded.unit_pack_size,
                availability = excluded.availability,
                description = excluded.description,
                specifications = excluded.specifications,
                image_urls = excluded.image_urls,
                alternative_products = excluded.alternative_products,
                scraped_at = excluded.scraped_at,
                extraction_status = excluded.extraction_status,
                errors = excluded.errors
            """,
            rows,
        )


def summarize_sqlite(sqlite_path: Path, limit: int = 5) -> dict[str, Any]:
    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        total = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        status_rows = connection.execute(
            "SELECT extraction_status, COUNT(*) AS count FROM products GROUP BY extraction_status"
        ).fetchall()
        samples = connection.execute(
            """
            SELECT parent_product_name, variant_name, brand, sku, price_amount, availability
            FROM products
            ORDER BY parent_product_name, variant_name
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return {
        "record_count": total,
        "status_counts": {row["extraction_status"]: row["count"] for row in status_rows},
        "samples": [dict(row) for row in samples],
    }


def _flatten_record(record: ProductRecord) -> dict[str, Any]:
    price = record.price
    return {
        "product_id": record.product_id,
        "parent_product_name": record.parent_product_name,
        "variant_name": record.variant_name,
        "brand": record.brand,
        "manufacturer": record.manufacturer,
        "sku": record.sku,
        "item_number": record.item_number,
        "mfr_number": record.mfr_number,
        "category_path": json.dumps(record.category_path),
        "product_url": str(record.product_url),
        "source_category_url": str(record.source_category_url)
        if record.source_category_url
        else None,
        "price_raw": price.raw if price else None,
        "price_amount": str(price.amount) if price and price.amount is not None else None,
        "price_currency": price.currency if price else None,
        "unit_pack_size": record.unit_pack_size,
        "availability": record.availability,
        "description": record.description,
        "specifications": json.dumps(record.specifications),
        "image_urls": json.dumps([str(url) for url in record.image_urls]),
        "alternative_products": json.dumps(
            [str(url) for url in record.alternative_products]
        ),
        "scraped_at": record.scraped_at.isoformat(),
        "extraction_status": record.extraction_status.value,
        "errors": json.dumps(record.errors),
    }
