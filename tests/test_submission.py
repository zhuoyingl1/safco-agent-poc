import json

from safco_agent.models import ExtractionStatus, Price, ProductRecord
from safco_agent.quality import build_quality_report
from safco_agent.storage import write_csv, write_jsonl, write_sqlite
from safco_agent.submission import SAMPLE_OUTPUT_FILES, export_sample_outputs, run_submission_check


def test_submission_check_passes_for_consistent_outputs(tmp_path) -> None:
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
        description="Powder-free nitrile exam gloves.",
        specifications={"source_id": "variant-4871105"},
        image_urls=["https://www.safcodental.com/media/catalog/product/d/r/drcbm.jpg"],
        extraction_status=ExtractionStatus.COMPLETE,
    )
    discovery = tmp_path / "discovery.json"
    jsonl = tmp_path / "products.jsonl"
    csv_path = tmp_path / "products.csv"
    sqlite_path = tmp_path / "safco.sqlite"
    extraction_summary = tmp_path / "extraction-summary.json"
    quality_report = tmp_path / "quality-report.json"
    discovery.write_text('{"categories": []}\n', encoding="utf-8")
    write_jsonl([record], jsonl)
    write_csv([record], csv_path)
    write_sqlite([record], sqlite_path)
    extraction_summary.write_text(
        json.dumps({"record_count": 1, "failed_url_count": 0}) + "\n",
        encoding="utf-8",
    )
    build_quality_report([record], source_path=str(jsonl)).write_json(quality_report)

    result = run_submission_check(
        discovery_path=discovery,
        products_jsonl_path=jsonl,
        products_csv_path=csv_path,
        sqlite_path=sqlite_path,
        extraction_summary_path=extraction_summary,
        quality_report_path=quality_report,
    )

    assert result.ok is True
    assert result.metrics["jsonl_record_count"] == 1
    assert result.checks["sqlite_count_matches_jsonl"] is True


def test_submission_check_fails_when_required_file_is_missing(tmp_path) -> None:
    result = run_submission_check(
        discovery_path=tmp_path / "missing-discovery.json",
        products_jsonl_path=tmp_path / "missing-products.jsonl",
        products_csv_path=tmp_path / "missing-products.csv",
        sqlite_path=tmp_path / "missing.sqlite",
        extraction_summary_path=tmp_path / "missing-summary.json",
        quality_report_path=tmp_path / "missing-quality.json",
    )

    assert result.ok is False
    assert result.checks == {"required_files_exist": False}
    assert len(result.missing_files) == 6


def test_export_sample_outputs_copies_expected_files(tmp_path) -> None:
    source_dir = tmp_path / "output"
    target_dir = tmp_path / "sample_output"
    source_dir.mkdir()
    for filename in SAMPLE_OUTPUT_FILES:
        (source_dir / filename).write_text(f"{filename}\n", encoding="utf-8")

    copied = export_sample_outputs(source_dir=source_dir, target_dir=target_dir)

    assert len(copied) == len(SAMPLE_OUTPUT_FILES)
    assert sorted(path.name for path in target_dir.iterdir()) == sorted(SAMPLE_OUTPUT_FILES)

