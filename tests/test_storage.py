import csv
import json
import sqlite3

from safco_agent.models import ExtractionStatus, Price, ProductRecord
from safco_agent.storage import summarize_sqlite, write_csv, write_jsonl, write_sqlite


def test_storage_writes_jsonl_csv_and_sqlite(tmp_path) -> None:
    record = ProductRecord(
        parent_product_name="Aurelia Amazing",
        variant_name="Aurelia Amazing gloves small 300/box",
        brand="Supermax",
        sku="4871105",
        item_number="4871105",
        category_path=["Dental Supplies", "Dental Exam Gloves", "Nitrile gloves"],
        product_url="https://www.safcodental.com/product/aurelia-reg-amazing-reg",
        price=Price(raw="USD 20.99", amount="20.99", currency="USD"),
        availability="InStock",
        unit_pack_size="300/box",
        description="Powder-free nitrile exam gloves.",
        extraction_status=ExtractionStatus.COMPLETE,
    )
    jsonl_path = tmp_path / "products.jsonl"
    csv_path = tmp_path / "products.csv"
    sqlite_path = tmp_path / "safco.sqlite"

    write_jsonl([record], jsonl_path)
    write_csv([record], csv_path)
    write_sqlite([record], sqlite_path)
    write_sqlite([record], sqlite_path)

    jsonl_record = json.loads(jsonl_path.read_text(encoding="utf-8").splitlines()[0])
    assert jsonl_record["parent_product_name"] == "Aurelia Amazing"

    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["sku"] == "4871105"
    assert json.loads(rows[0]["category_path"]) == [
        "Dental Supplies",
        "Dental Exam Gloves",
        "Nitrile gloves",
    ]

    with sqlite3.connect(sqlite_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    assert count == 1

    summary = summarize_sqlite(sqlite_path)
    assert summary["record_count"] == 1
    assert summary["status_counts"] == {"complete": 1}


def test_sqlite_can_preserve_existing_records_for_resume(tmp_path) -> None:
    first = ProductRecord(
        parent_product_name="Aurelia Amazing",
        variant_name="Aurelia Amazing gloves small 300/box",
        brand="Supermax",
        sku="4871105",
        item_number="4871105",
        category_path=["Dental Supplies", "Dental Exam Gloves", "Nitrile gloves"],
        product_url="https://www.safcodental.com/product/aurelia-reg-amazing-reg",
        price=Price(raw="USD 20.99", amount="20.99", currency="USD"),
        extraction_status=ExtractionStatus.COMPLETE,
    )
    second = ProductRecord(
        parent_product_name="OraSoothe Sockit!",
        variant_name="OraSoothe Oral Coating Rinse",
        brand="Septodont",
        sku="5106359",
        item_number="5106359",
        category_path=[
            "Dental Supplies",
            "Sutures & surgical products",
            "Surgical medicaments and packing",
        ],
        product_url="https://www.safcodental.com/product/orasoothe-reg-sockit-gel",
        price=Price(raw="USD 9.99", amount="9.99", currency="USD"),
        extraction_status=ExtractionStatus.COMPLETE,
    )
    sqlite_path = tmp_path / "safco.sqlite"

    write_sqlite([first], sqlite_path)
    write_sqlite([second], sqlite_path, replace=False)

    assert summarize_sqlite(sqlite_path)["record_count"] == 2
