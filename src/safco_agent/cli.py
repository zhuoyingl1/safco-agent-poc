from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional
from uuid import uuid4

import typer

from .agents.navigator import NavigatorAgent, ProductUrlCandidate
from .agents.product_extractor import ProductExtractorAgent
from .browser import smoke_check
from .checkpoint import CheckpointStore
from .config import load_config
from .crawl_control import CrawlControlConfig, PoliteCrawlController
from .models import ProductRecord
from .quality import build_quality_report_from_jsonl
from .storage import summarize_sqlite, write_product_outputs

app = typer.Typer(help="Safco Dental agent-based scraping POC.")


@app.command("validate-config")
def validate_config(
    config: Path = typer.Option(Path("config/default.yaml"), "--config", "-c"),
) -> None:
    """Validate the crawl configuration."""
    parsed = load_config(config)
    typer.echo(
        f"OK: {parsed.project_name} with {len(parsed.seed_categories)} seed categories"
    )
    for category in parsed.seed_categories:
        typer.echo(f"- {category.key}: {category.name} ({category.url})")


@app.command("schema")
def schema(
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
) -> None:
    """Print or write the normalized product JSON schema."""
    schema_data = ProductRecord.model_json_schema()
    payload = json.dumps(schema_data, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
        typer.echo(f"Wrote schema to {output}")
    else:
        typer.echo(payload)


@app.command("plan")
def plan() -> None:
    """Show the planned agent responsibilities."""
    typer.echo("Agent responsibilities:")
    typer.echo("- CategoryDiscoveryAgent: discover subcategories from seed URLs")
    typer.echo("- NavigatorAgent: traverse listing pages and collect product URLs")
    typer.echo("- PageClassifierAgent: classify category, listing, product, blocked, unknown")
    typer.echo("- ProductExtractorAgent: extract product detail and variant fields")
    typer.echo("- ValidatorDeduperAgent: validate, normalize, deduplicate, and report quality")


@app.command("smoke")
def smoke(
    url: str = typer.Option(..., "--url", "-u"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    timeout_ms: int = typer.Option(30000, "--timeout-ms"),
    headed: bool = typer.Option(False, "--headed"),
) -> None:
    """Open a page with Playwright and record basic page signals."""
    try:
        result = asyncio.run(
            smoke_check(
                url=url,
                output_path=output,
                timeout_ms=timeout_ms,
                headless=not headed,
            )
        )
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))


@app.command("discover")
def discover(
    config: Path = typer.Option(Path("config/default.yaml"), "--config", "-c"),
    output: Path = typer.Option(Path("output/discovery.json"), "--output", "-o"),
    max_pages_per_category: Optional[int] = typer.Option(None, "--max-pages-per-category"),
    timeout_ms: Optional[int] = typer.Option(None, "--timeout-ms"),
    headed: bool = typer.Option(False, "--headed"),
) -> None:
    """Discover subcategories and product detail URLs from configured seeds."""
    parsed = load_config(config)
    try:
        result = asyncio.run(
            NavigatorAgent().discover(
                config=parsed,
                max_pages_per_category=max_pages_per_category,
                timeout_ms=timeout_ms,
                headless=not headed,
            )
        )
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc

    result.write_json(output)
    typer.echo(
        f"Wrote discovery result to {output} "
        f"with {result.seed_category_count} seeds and {result.total_product_urls} product URLs"
    )


@app.command("extract-products")
def extract_products(
    discovery: Path = typer.Option(Path("output/discovery.json"), "--discovery", "-d"),
    output: Path = typer.Option(Path("output/products.jsonl"), "--output", "-o"),
    csv_output: Optional[Path] = typer.Option(Path("output/products.csv"), "--csv-output"),
    sqlite_output: Optional[Path] = typer.Option(
        Path("output/safco.sqlite"),
        "--sqlite-output",
    ),
    summary_output: Path = typer.Option(
        Path("output/extraction-summary.json"),
        "--summary-output",
    ),
    max_products: Optional[int] = typer.Option(None, "--max-products"),
    max_products_per_category: int = typer.Option(3, "--max-products-per-category"),
    checkpoint_db: Optional[Path] = typer.Option(
        Path("output/checkpoints.sqlite"),
        "--checkpoint-db",
    ),
    resume: bool = typer.Option(False, "--resume"),
    force_refresh: bool = typer.Option(False, "--force-refresh"),
    rate_limit_seconds: float = typer.Option(1.5, "--rate-limit-seconds"),
    max_attempts: int = typer.Option(2, "--max-attempts"),
    retry_backoff_seconds: float = typer.Option(1.0, "--retry-backoff-seconds"),
    timeout_ms: int = typer.Option(45000, "--timeout-ms"),
    headed: bool = typer.Option(False, "--headed"),
) -> None:
    """Extract normalized product records from discovered product URLs."""
    try:
        result = asyncio.run(
            _extract_products_from_discovery(
                discovery=discovery,
                output=output,
                csv_output=csv_output,
                sqlite_output=sqlite_output,
                summary_output=summary_output,
                max_products=max_products,
                max_products_per_category=max_products_per_category,
                checkpoint_db=checkpoint_db,
                resume=resume,
                force_refresh=force_refresh,
                rate_limit_seconds=rate_limit_seconds,
                max_attempts=max_attempts,
                retry_backoff_seconds=retry_backoff_seconds,
                timeout_ms=timeout_ms,
                headless=not headed,
            )
        )
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        f"Wrote {result['record_count']} product records from "
        f"{result['visited_product_url_count']} product URLs to {output}"
    )
    if csv_output:
        typer.echo(f"Wrote CSV export to {csv_output}")
    if sqlite_output:
        typer.echo(f"Wrote SQLite store to {sqlite_output}")
    if checkpoint_db:
        typer.echo(f"Updated checkpoint store at {checkpoint_db}")


@app.command("inspect-store")
def inspect_store(
    sqlite_path: Path = typer.Option(Path("output/safco.sqlite"), "--sqlite", "-s"),
    limit: int = typer.Option(5, "--limit"),
) -> None:
    """Inspect the SQLite product store."""
    if not sqlite_path.exists():
        raise typer.BadParameter(f"SQLite file not found: {sqlite_path}")
    typer.echo(json.dumps(summarize_sqlite(sqlite_path, limit=limit), indent=2))


@app.command("inspect-checkpoints")
def inspect_checkpoints(
    checkpoint_db: Path = typer.Option(
        Path("output/checkpoints.sqlite"),
        "--checkpoint-db",
    ),
) -> None:
    """Inspect crawl checkpoint state."""
    if not checkpoint_db.exists():
        raise typer.BadParameter(f"Checkpoint file not found: {checkpoint_db}")
    typer.echo(json.dumps(CheckpointStore(checkpoint_db).summary(), indent=2))


@app.command("quality-report")
def quality_report(
    input_path: Path = typer.Option(Path("output/products.jsonl"), "--input", "-i"),
    output: Path = typer.Option(Path("output/quality-report.json"), "--output", "-o"),
) -> None:
    """Build a field coverage and quality report from product JSONL."""
    try:
        report = build_quality_report_from_jsonl(input_path)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    report.write_json(output)
    typer.echo(
        f"Wrote quality report to {output} with "
        f"{report.record_count} records and {len(report.warnings)} warnings"
    )


async def _extract_products_from_discovery(
    discovery: Path,
    output: Path,
    csv_output: Path | None,
    sqlite_output: Path | None,
    summary_output: Path,
    max_products: int | None,
    max_products_per_category: int,
    checkpoint_db: Path | None,
    resume: bool,
    force_refresh: bool,
    rate_limit_seconds: float,
    max_attempts: int,
    retry_backoff_seconds: float,
    timeout_ms: int,
    headless: bool,
) -> dict[str, object]:
    from .browser import fetch_page_snapshot

    if not discovery.exists():
        raise RuntimeError(f"Discovery file not found: {discovery}")
    payload = json.loads(discovery.read_text(encoding="utf-8"))
    candidates = _product_candidates_from_discovery(
        payload,
        max_products=max_products,
        max_products_per_category=max_products_per_category,
    )
    extractor = ProductExtractorAgent()
    checkpoint_store = CheckpointStore(checkpoint_db) if checkpoint_db else None
    crawl_controller = PoliteCrawlController(
        CrawlControlConfig(
            rate_limit_seconds=rate_limit_seconds,
            max_attempts=max_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
        )
    )
    run_id = str(uuid4())
    records: list[ProductRecord] = []
    errors: list[dict[str, str]] = []
    skipped_urls: list[str] = []
    for candidate in candidates:
        if checkpoint_store and checkpoint_store.should_skip(
            candidate.url,
            resume=resume,
            force_refresh=force_refresh,
        ):
            skipped_urls.append(candidate.url)
            continue
        try:
            snapshot = await crawl_controller.run(
                lambda product_url=candidate.url: fetch_page_snapshot(
                    product_url,
                    timeout_ms=timeout_ms,
                    headless=headless,
                )
            )
            extracted_records = extractor.extract(
                snapshot,
                source_category_url=candidate.source_page_url,
            )
            records.extend(extracted_records)
            if checkpoint_store:
                checkpoint_store.mark_success(
                    candidate.url,
                    record_count=len(extracted_records),
                    run_id=run_id,
                )
        except Exception as exc:
            errors.append({"url": candidate.url, "error": str(exc)})
            if checkpoint_store:
                checkpoint_store.mark_failed(candidate.url, str(exc), run_id=run_id)

    write_product_outputs(
        records,
        jsonl_path=output,
        csv_path=csv_output,
        sqlite_path=sqlite_output,
        replace_sqlite=not resume,
    )

    summary = {
        "run_id": run_id,
        "candidate_product_url_count": len(candidates),
        "visited_product_url_count": len(candidates) - len(skipped_urls),
        "skipped_product_url_count": len(skipped_urls),
        "record_count": len(records),
        "complete_record_count": sum(
            1 for record in records if record.extraction_status.value == "complete"
        ),
        "partial_record_count": sum(
            1 for record in records if record.extraction_status.value == "partial"
        ),
        "failed_url_count": len(errors),
        "jsonl_output": str(output),
        "csv_output": str(csv_output) if csv_output else None,
        "sqlite_output": str(sqlite_output) if sqlite_output else None,
        "checkpoint_db": str(checkpoint_db) if checkpoint_db else None,
        "resume": resume,
        "force_refresh": force_refresh,
        "rate_limit_seconds": rate_limit_seconds,
        "max_attempts": max_attempts,
        "retry_backoff_seconds": retry_backoff_seconds,
        "skipped_urls": skipped_urls,
        "errors": errors,
    }
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _product_candidates_from_discovery(
    payload: dict,
    max_products: int | None,
    max_products_per_category: int,
) -> list[ProductUrlCandidate]:
    candidates: list[ProductUrlCandidate] = []
    seen: set[str] = set()
    for category in payload.get("categories", []):
        category_count = 0
        for item in category.get("product_urls", []):
            candidate = ProductUrlCandidate.model_validate(item)
            if candidate.url in seen:
                continue
            seen.add(candidate.url)
            candidates.append(candidate)
            category_count += 1
            if category_count >= max_products_per_category:
                break
    if max_products is not None:
        return candidates[:max_products]
    return candidates


if __name__ == "__main__":
    app()
