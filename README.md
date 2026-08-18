# Safco Agent POC

Agent-based product scraping proof of concept for the Frontier Dental AI team take-home assessment.

## Current Capability

This POC demonstrates a clean working slice of an agent-based product scraping system:

- Python project scaffold
- Config-driven seed categories
- Pydantic product schema
- Agent responsibility separation
- Typer CLI
- Playwright smoke check entrypoint
- Category discovery and product URL collection
- JSON-LD product detail extraction for product variants
- JSONL, CSV, and SQLite outputs
- SQLite checkpointing and resume mode
- Retry and request spacing controls
- Field coverage quality report
- Tests for config, schema, discovery, extraction, storage, quality, checkpoints, and crawl controls

The current implementation is intentionally scoped to a representative sample rather than a full-site crawl. It proves the crawl, extraction, storage, resume, and quality-monitoring path end to end.

## Target Categories

- Dental Exam Gloves: `https://www.safcodental.com/catalog/gloves`
- Sutures & surgical products: `https://www.safcodental.com/catalog/sutures-surgical-products`

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

If running from the repository without installing the package:

```powershell
$env:PYTHONPATH = "src"
python -m safco_agent validate-config --config config/default.yaml
```

## Workflow

Run the following workflow to reproduce the sample dataset.

Validate the default config:

```powershell
safco-agent validate-config --config config/default.yaml
```

Show the planned agent responsibilities:

```powershell
safco-agent plan
```

Export the product JSON schema:

```powershell
safco-agent schema --output docs/product_schema.json
```

Run a browser smoke check against one target page:

```powershell
safco-agent smoke --url https://www.safcodental.com/catalog/gloves --output output/smoke-gloves.json
```

Discover child categories and product detail URLs from configured seeds:

```powershell
safco-agent discover --config config/default.yaml --output output/discovery.json
```

Extract normalized product records from discovered product URLs:

```powershell
safco-agent extract-products --discovery output/discovery.json --output output/products.jsonl --summary-output output/extraction-summary.json --max-products-per-category 2 --checkpoint-db output/checkpoints.sqlite --rate-limit-seconds 1.5 --max-attempts 2
```

Inspect the SQLite product store:

```powershell
safco-agent inspect-store --sqlite output/safco.sqlite --limit 5
```

Inspect checkpoint state:

```powershell
safco-agent inspect-checkpoints --checkpoint-db output/checkpoints.sqlite
```

Resume a product extraction run and skip product URLs already marked successful:

```powershell
safco-agent extract-products --discovery output/discovery.json --resume --checkpoint-db output/checkpoints.sqlite
```

Build a data quality report:

```powershell
safco-agent quality-report --input output/products.jsonl --output output/quality-report.json
```

Validate sample output readiness:

```powershell
safco-agent submission-check --output output/submission-check.json
```

Run tests:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
pytest -q
```

## Approach

The implementation uses deterministic extraction first. Safco product pages expose `application/ld+json` product data, including `ProductGroup` and `hasVariant`, so the extractor uses that stable structured source before falling back to visible page text. This keeps the prototype practical and avoids unnecessary LLM calls.

LLMs are intentionally not required for the core path. They would be useful later for:

- classifying unexpected page layouts
- suggesting selector repairs after DOM drift
- normalizing messy description bullets into key-value attributes
- triaging failures that deterministic rules cannot explain

This keeps AI usage practical rather than decorative.

## Architecture

The production-facing design separates responsibilities:

- `CategoryDiscoveryAgent`: starts from configured category URLs and discovers subcategories.
- `NavigatorAgent`: visits category/listing pages, handles pagination, and collects product URLs.
- `PageClassifierAgent`: classifies pages as category, listing, product, blocked, or unknown.
- `ProductExtractorAgent`: extracts product fields from product detail pages.
- `ValidatorDeduperAgent`: validates required fields, normalizes records, deduplicates variants, and emits quality metrics.
- `CheckpointStore`: records product URL success/failure state for resume-safe extraction.
- `PoliteCrawlController`: applies rate limiting and retry behavior around crawl operations.

The first implementation should keep deterministic selectors as the default path. LLM usage should be reserved for irregular page classification, selector repair suggestions, or turning messy product bullets into structured attributes.

## Failure Handling

- Browser navigation uses `domcontentloaded` plus a short settle wait instead of `networkidle`, because Safco pages may keep background requests open.
- Crawl operations are wrapped by `PoliteCrawlController`, which applies request spacing and retry attempts.
- Product extraction records URL-level failures in `extraction-summary.json`.
- `CheckpointStore` records each product URL as success or failed, including attempt count and last error.
- `--resume` skips product URLs already marked successful.
- `--force-refresh` reprocesses URLs even if they already succeeded.
- Product records carry `extraction_status` and `errors` fields for row-level quality checks.

## Data Quality Monitoring

Run `quality-report` after extraction. The report includes:

- total record count
- complete / partial / failed record counts
- field coverage for key fields
- category distribution
- brand distribution
- duplicate product ID count
- error counts
- warnings for low coverage or failed records

For production, the same metrics should become dashboard and alert signals. Examples:

- alert if required-field coverage drops below 95%
- alert if failed URL rate rises above a configured threshold
- alert if duplicate product IDs appear
- compare category and brand distributions between runs to detect drift
- store run summaries over time for trend analysis

## Production Scaling Path

To scale this POC to a full-site crawler:

1. Move URL frontier state into a durable queue.
2. Split category discovery and product extraction into separate workers.
3. Add per-domain concurrency limits and adaptive rate limiting.
4. Persist raw HTML or snapshots for failed pages.
5. Version extraction rules and track selector drift.
6. Store normalized records in a production database with history tables.
7. Add scheduled incremental crawls based on changed categories or product URLs.
8. Add observability for crawl latency, retry rate, field coverage, and failed URLs.
9. Add secrets management for future authenticated workflows.
10. Run in a containerized environment with CI checks and a repeatable deployment process.

## Output Schema

Each row represents a sellable product or product variant. The stable identity is derived from `product_url` plus `sku` or `mfr_number` when available.

Core fields include:

- product name and variant name
- brand / manufacturer
- SKU / item number / manufacturer number
- category hierarchy
- product URL
- price
- pack size / unit
- availability
- description
- specifications
- image URLs
- alternative products
- extraction status and errors

Run `safco-agent schema --output docs/product_schema.json` for the machine-readable schema.

## Sample Outputs

The sample workflow writes:

- `output/discovery.json`: discovered child categories, visited pages, and product URLs
- `output/products.jsonl`: normalized variant-level product records
- `output/products.csv`: reviewer-friendly tabular export
- `output/safco.sqlite`: queryable SQLite product store
- `output/extraction-summary.json`: extraction run summary
- `output/checkpoints.sqlite`: product URL checkpoint state
- `output/quality-report.json`: data quality and field coverage report
- `output/submission-check.json`: final output consistency check

## Near-Term Roadmap

1. Add product table extraction fallback when JSON-LD is incomplete.
2. Add selector drift and quality monitoring.
3. Add optional LLM fallback for irregular pages.
4. Add production deployment notes and a fuller runbook.
5. Add CI workflow documentation.

## Known Limitations

- Playwright must be installed before browser smoke checks can run.
- Prices and stock availability may vary by account state, location, JavaScript loading, or site access controls.
- Product extraction currently relies on Safco JSON-LD and does not yet parse every visible product table control.
- Resume mode skips already successful product URLs and therefore writes outputs for newly processed records only.
- Product extraction applies request spacing and retry controls, but it still runs sequentially in this POC.
