import json

from safco_agent.models import ExtractionStatus, Price, ProductRecord
from safco_agent.quality import build_quality_report, build_quality_report_from_jsonl


def test_quality_report_calculates_field_coverage_and_counts(tmp_path) -> None:
    complete = ProductRecord(
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
        specifications={"source_id": "variant-4871105"},
        image_urls=["https://www.safcodental.com/media/catalog/product/d/r/drcbm.jpg"],
        extraction_status=ExtractionStatus.COMPLETE,
    )
    partial = ProductRecord(
        parent_product_name="Fallback Product",
        category_path=[],
        product_url="https://www.safcodental.com/product/fallback",
        extraction_status=ExtractionStatus.PARTIAL,
        errors=["missing sku"],
    )

    report = build_quality_report([complete, partial], source_path="products.jsonl")

    coverage = {item.field: item.coverage for item in report.field_coverage}
    assert report.record_count == 2
    assert report.complete_record_count == 1
    assert report.partial_record_count == 1
    assert report.error_counts == {"missing sku": 1}
    assert coverage["parent_product_name"] == 1.0
    assert coverage["sku"] == 0.5
    assert report.category_counts == {
        "Dental Supplies > Dental Exam Gloves > Nitrile gloves": 1
    }
    assert "low coverage for required field: sku" in report.warnings

    output_path = tmp_path / "quality-report.json"
    report.write_json(output_path)
    assert json.loads(output_path.read_text(encoding="utf-8"))["record_count"] == 2


def test_quality_report_loads_jsonl(tmp_path) -> None:
    record = ProductRecord(
        parent_product_name="OraSoothe Sockit!",
        variant_name="OraSoothe Oral Coating Rinse",
        brand="Septodont",
        sku="5106359",
        category_path=[
            "Dental Supplies",
            "Sutures & surgical products",
            "Surgical medicaments and packing",
        ],
        product_url="https://www.safcodental.com/product/orasoothe-reg-sockit-gel",
        price=Price(raw="USD 9.99", amount="9.99", currency="USD"),
        extraction_status=ExtractionStatus.COMPLETE,
    )
    input_path = tmp_path / "products.jsonl"
    input_path.write_text(record.model_dump_json() + "\n", encoding="utf-8")

    report = build_quality_report_from_jsonl(input_path)

    assert report.source_path == str(input_path)
    assert report.record_count == 1
    assert report.brand_counts == {"Septodont": 1}


def test_quality_report_warns_when_empty() -> None:
    report = build_quality_report([], source_path="products.jsonl")

    assert report.record_count == 0
    assert report.warnings == ["no product records found"]

