from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from safco_agent.models import ProductRecord


QUALITY_FIELDS = [
    "parent_product_name",
    "variant_name",
    "brand",
    "sku",
    "item_number",
    "category_path",
    "product_url",
    "price",
    "unit_pack_size",
    "availability",
    "description",
    "specifications",
    "image_urls",
]


class FieldCoverage(BaseModel):
    field: str
    present_count: int
    total_count: int
    coverage: float


class QualityReport(BaseModel):
    source_path: str
    record_count: int
    complete_record_count: int
    partial_record_count: int
    failed_record_count: int
    field_coverage: list[FieldCoverage] = Field(default_factory=list)
    category_counts: dict[str, int] = Field(default_factory=dict)
    brand_counts: dict[str, int] = Field(default_factory=dict)
    error_counts: dict[str, int] = Field(default_factory=dict)
    duplicate_product_id_count: int
    warnings: list[str] = Field(default_factory=list)

    def write_json(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )


def load_records_jsonl(input_path: Path) -> list[ProductRecord]:
    if not input_path.exists():
        raise FileNotFoundError(f"Product JSONL file not found: {input_path}")
    records: list[ProductRecord] = []
    with input_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(ProductRecord.model_validate_json(line))
            except Exception as exc:
                raise ValueError(f"Invalid product JSONL at line {line_number}: {exc}") from exc
    return records


def build_quality_report(records: list[ProductRecord], source_path: str) -> QualityReport:
    total = len(records)
    product_ids = [record.product_id for record in records]
    duplicate_count = len(product_ids) - len(set(product_ids))
    status_counts = Counter(record.extraction_status.value for record in records)
    error_counts = Counter(error for record in records for error in record.errors)
    report = QualityReport(
        source_path=source_path,
        record_count=total,
        complete_record_count=status_counts.get("complete", 0),
        partial_record_count=status_counts.get("partial", 0),
        failed_record_count=status_counts.get("failed", 0),
        field_coverage=[
            FieldCoverage(
                field=field,
                present_count=sum(1 for record in records if _has_value(record, field)),
                total_count=total,
                coverage=_coverage(sum(1 for record in records if _has_value(record, field)), total),
            )
            for field in QUALITY_FIELDS
        ],
        category_counts=_top_counts(_category_label(record) for record in records),
        brand_counts=_top_counts(record.brand for record in records),
        error_counts=dict(error_counts),
        duplicate_product_id_count=duplicate_count,
        warnings=[],
    )
    report.warnings.extend(_quality_warnings(report))
    return report


def build_quality_report_from_jsonl(input_path: Path) -> QualityReport:
    records = load_records_jsonl(input_path)
    return build_quality_report(records, source_path=str(input_path))


def _has_value(record: ProductRecord, field: str) -> bool:
    value: Any = getattr(record, field)
    if field == "price":
        return value is not None and value.amount is not None
    if isinstance(value, list | dict | str):
        return bool(value)
    return value is not None


def _coverage(present_count: int, total_count: int) -> float:
    if total_count == 0:
        return 0.0
    return round(present_count / total_count, 4)


def _category_label(record: ProductRecord) -> str | None:
    if not record.category_path:
        return None
    return " > ".join(record.category_path)


def _top_counts(values, limit: int = 10) -> dict[str, int]:
    counter = Counter(value for value in values if value)
    return dict(counter.most_common(limit))


def _quality_warnings(report: QualityReport) -> list[str]:
    warnings: list[str] = []
    if report.record_count == 0:
        warnings.append("no product records found")
    if report.duplicate_product_id_count:
        warnings.append("duplicate product ids found")
    for coverage in report.field_coverage:
        if coverage.field in {"parent_product_name", "sku", "category_path", "product_url", "price"}:
            if report.record_count and coverage.coverage < 0.95:
                warnings.append(f"low coverage for required field: {coverage.field}")
    if report.failed_record_count:
        warnings.append("failed product records found")
    return warnings

