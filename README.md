# Safco Agent POC

Agent-based product scraping proof of concept for the Frontier Dental AI team take-home assessment.

## Current Slice

This is the 0-2 hour foundation:

- Python project scaffold
- Config-driven seed categories
- Pydantic product schema
- Agent responsibility skeleton
- Typer CLI
- Playwright smoke check entrypoint
- Category discovery and product URL collection
- JSON-LD product detail extraction for product variants
- Basic tests for config, schema, page classification, and URL collection

The extraction crawl now supports a small product-detail extraction slice with JSONL, CSV, and SQLite outputs. The next slice should add richer product table fallbacks and data quality reporting.

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

## Commands

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
safco-agent extract-products --discovery output/discovery.json --output output/products.jsonl --summary-output output/extraction-summary.json --max-products-per-category 2
```

Inspect the SQLite product store:

```powershell
safco-agent inspect-store --sqlite output/safco.sqlite --limit 5
```

Run tests:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
pytest -q
```

## Architecture

The production-facing design separates responsibilities:

- `CategoryDiscoveryAgent`: starts from configured category URLs and discovers subcategories.
- `NavigatorAgent`: visits category/listing pages, handles pagination, and collects product URLs.
- `PageClassifierAgent`: classifies pages as category, listing, product, blocked, or unknown.
- `ProductExtractorAgent`: extracts product fields from product detail pages.
- `ValidatorDeduperAgent`: validates required fields, normalizes records, deduplicates variants, and emits quality metrics.

The first implementation should keep deterministic selectors as the default path. LLM usage should be reserved for irregular page classification, selector repair suggestions, or turning messy product bullets into structured attributes.

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

## Near-Term Roadmap

1. Add product table extraction fallback when JSON-LD is incomplete.
2. Add checkpointing for resumable category and product crawls.
3. Add field coverage reporting.
4. Add selector drift and quality monitoring.
5. Add optional LLM fallback for irregular pages.

## Known Limitations

- Playwright must be installed before browser smoke checks can run.
- Prices and stock availability may vary by account state, location, JavaScript loading, or site access controls.
- Product extraction currently relies on Safco JSON-LD and does not yet parse every visible product table control.
