from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer

from .agents.navigator import NavigatorAgent, ProductUrlCandidate
from .agents.product_extractor import ProductExtractorAgent
from .browser import smoke_check
from .config import load_config
from .models import ProductRecord

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
    summary_output: Path = typer.Option(
        Path("output/extraction-summary.json"),
        "--summary-output",
    ),
    max_products: Optional[int] = typer.Option(None, "--max-products"),
    max_products_per_category: int = typer.Option(3, "--max-products-per-category"),
    timeout_ms: int = typer.Option(45000, "--timeout-ms"),
    headed: bool = typer.Option(False, "--headed"),
) -> None:
    """Extract normalized product records from discovered product URLs."""
    try:
        result = asyncio.run(
            _extract_products_from_discovery(
                discovery=discovery,
                output=output,
                summary_output=summary_output,
                max_products=max_products,
                max_products_per_category=max_products_per_category,
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


async def _extract_products_from_discovery(
    discovery: Path,
    output: Path,
    summary_output: Path,
    max_products: int | None,
    max_products_per_category: int,
    timeout_ms: int,
    headless: bool,
) -> dict[str, int]:
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
    records: list[ProductRecord] = []
    errors: list[dict[str, str]] = []
    for candidate in candidates:
        try:
            snapshot = await fetch_page_snapshot(
                candidate.url,
                timeout_ms=timeout_ms,
                headless=headless,
            )
            records.extend(
                extractor.extract(
                    snapshot,
                    source_category_url=candidate.source_page_url,
                )
            )
        except Exception as exc:
            errors.append({"url": candidate.url, "error": str(exc)})

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.model_dump(mode="json")) + "\n")

    summary = {
        "visited_product_url_count": len(candidates),
        "record_count": len(records),
        "complete_record_count": sum(
            1 for record in records if record.extraction_status.value == "complete"
        ),
        "partial_record_count": sum(
            1 for record in records if record.extraction_status.value == "partial"
        ),
        "failed_url_count": len(errors),
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
