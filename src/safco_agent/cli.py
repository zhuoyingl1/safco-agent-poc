from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer

from .browser import smoke_check
from .config import load_config
from .agents.navigator import NavigatorAgent
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


if __name__ == "__main__":
    app()
