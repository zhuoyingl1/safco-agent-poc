from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from safco_agent.storage import summarize_sqlite


class SubmissionCheckResult(BaseModel):
    ok: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    missing_files: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def write_json(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )


SAMPLE_OUTPUT_FILES = [
    "discovery.json",
    "products.jsonl",
    "products.csv",
    "extraction-summary.json",
    "quality-report.json",
    "submission-check.json",
]


def export_sample_outputs(source_dir: Path, target_dir: Path) -> list[str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for filename in SAMPLE_OUTPUT_FILES:
        source_path = source_dir / filename
        if not source_path.exists():
            raise FileNotFoundError(f"Sample output source file not found: {source_path}")
        target_path = target_dir / filename
        shutil.copyfile(source_path, target_path)
        copied.append(str(target_path))
    return copied


def run_submission_check(
    discovery_path: Path,
    products_jsonl_path: Path,
    products_csv_path: Path,
    sqlite_path: Path,
    extraction_summary_path: Path,
    quality_report_path: Path,
) -> SubmissionCheckResult:
    required_paths = [
        discovery_path,
        products_jsonl_path,
        products_csv_path,
        sqlite_path,
        extraction_summary_path,
        quality_report_path,
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        return SubmissionCheckResult(
            ok=False,
            checks={"required_files_exist": False},
            missing_files=missing,
            warnings=["required output files are missing"],
        )

    jsonl_count = _count_jsonl(products_jsonl_path)
    csv_count = _count_csv_rows(products_csv_path)
    sqlite_summary = summarize_sqlite(sqlite_path, limit=0)
    extraction_summary = json.loads(extraction_summary_path.read_text(encoding="utf-8"))
    quality_report = json.loads(quality_report_path.read_text(encoding="utf-8"))
    sqlite_count = int(sqlite_summary["record_count"])
    quality_count = int(quality_report["record_count"])
    extraction_count = int(extraction_summary["record_count"])
    failed_urls = int(extraction_summary["failed_url_count"])
    quality_warnings = quality_report.get("warnings", [])

    checks = {
        "required_files_exist": True,
        "jsonl_has_records": jsonl_count > 0,
        "csv_count_matches_jsonl": csv_count == jsonl_count,
        "sqlite_count_matches_jsonl": sqlite_count == jsonl_count,
        "summary_count_matches_jsonl": extraction_count == jsonl_count,
        "quality_count_matches_jsonl": quality_count == jsonl_count,
        "no_failed_urls": failed_urls == 0,
        "quality_report_has_no_warnings": not quality_warnings,
    }
    warnings = []
    if not checks["jsonl_has_records"]:
        warnings.append("products JSONL has no records")
    if not checks["no_failed_urls"]:
        warnings.append("extraction summary has failed URLs")
    if quality_warnings:
        warnings.extend(f"quality warning: {warning}" for warning in quality_warnings)

    return SubmissionCheckResult(
        ok=all(checks.values()),
        checks=checks,
        metrics={
            "jsonl_record_count": jsonl_count,
            "csv_record_count": csv_count,
            "sqlite_record_count": sqlite_count,
            "extraction_summary_record_count": extraction_count,
            "quality_report_record_count": quality_count,
            "failed_url_count": failed_urls,
        },
        missing_files=[],
        warnings=warnings,
    )


def _count_jsonl(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))
