from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, HttpUrl


class BrowserSmokeResult(BaseModel):
    url: HttpUrl
    final_url: str
    title: str
    h1: str | None
    product_link_count: int
    category_link_count: int
    body_sample: str


async def smoke_check(
    url: str,
    output_path: Path | None = None,
    timeout_ms: int = 30000,
    headless: bool = True,
) -> BrowserSmokeResult:
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: python -m pip install -e . "
            "and then: python -m playwright install chromium"
        ) from exc

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        page = await browser.new_page()
        page.set_default_timeout(timeout_ms)
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        title = await page.title()
        h1 = await _first_text(page, "h1")
        product_link_count = await page.locator('a[href*="/product/"]').count()
        category_link_count = await page.locator('a[href*="/catalog/"]').count()
        body_text = await page.locator("body").inner_text(timeout=timeout_ms)
        result = BrowserSmokeResult(
            url=url,
            final_url=page.url,
            title=title,
            h1=h1,
            product_link_count=product_link_count,
            category_link_count=category_link_count,
            body_sample=" ".join(body_text.split())[:1000],
        )
        await browser.close()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    return result


async def _first_text(page, selector: str) -> str | None:
    locator = page.locator(selector).first
    if await page.locator(selector).count() == 0:
        return None
    text = await locator.inner_text()
    return " ".join(text.split()) or None

