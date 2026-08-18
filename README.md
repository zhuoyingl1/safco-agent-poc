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
- Basic tests for config, schema, and page classification

The extraction crawl is intentionally not implemented yet. The next slice should add category traversal and product URL discovery.

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

1. Add `CategoryDiscoveryAgent` implementation for the two configured categories.
2. Add listing traversal and product URL collection with checkpointing.
3. Add product detail extraction for name, brand, price, breadcrumbs, description, specs, and images.
4. Add CSV/JSONL/SQLite writers.
5. Add run report with field coverage and failure counts.

## Known Limitations

- Playwright must be installed before browser smoke checks can run.
- Prices and stock availability may vary by account state, location, JavaScript loading, or site access controls.
- The current slice does not persist crawl state or scrape product records yet.
