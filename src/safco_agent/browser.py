from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl


class LinkCandidate(BaseModel):
    text: str
    href: str


class PageSnapshot(BaseModel):
    requested_url: HttpUrl
    final_url: str
    title: str
    h1: str | None
    links: list[LinkCandidate] = Field(default_factory=list)
    json_ld: list[str] = Field(default_factory=list)
    body_sample: str
    body_text: str = Field(default="", exclude=True)


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
    snapshot = await fetch_page_snapshot(
        url=url,
        timeout_ms=timeout_ms,
        headless=headless,
    )
    result = BrowserSmokeResult(
        url=url,
        final_url=snapshot.final_url,
        title=snapshot.title,
        h1=snapshot.h1,
        product_link_count=sum(1 for link in snapshot.links if "/product/" in link.href),
        category_link_count=sum(1 for link in snapshot.links if "/catalog/" in link.href),
        body_sample=snapshot.body_sample,
    )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    return result


async def fetch_page_snapshot(
    url: str,
    timeout_ms: int = 30000,
    headless: bool = True,
    settle_ms: int = 2500,
) -> PageSnapshot:
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
        await page.wait_for_timeout(settle_ms)
        title = await page.title()
        h1 = await _first_text(page, "h1")
        links_payload = await page.eval_on_selector_all(
            "a",
            """
            els => els.map(a => ({
                text: (a.innerText || a.textContent || "").trim().replace(/\\s+/g, " "),
                href: a.href
            })).filter(x => x.href)
            """,
        )
        json_ld_payload = await page.eval_on_selector_all(
            "script",
            """
            els => els
                .filter(script => script.type === "application/ld+json")
                .map(script => script.textContent || "")
                .filter(Boolean)
            """,
        )
        body_text = await page.locator("body").inner_text(timeout=timeout_ms)
        snapshot = PageSnapshot(
            requested_url=url,
            final_url=page.url,
            title=title,
            h1=h1,
            links=[LinkCandidate.model_validate(link) for link in links_payload],
            json_ld=json_ld_payload,
            body_sample=" ".join(body_text.split())[:1000],
            body_text=body_text,
        )
        await browser.close()

    return snapshot


async def _first_text(page, selector: str) -> str | None:
    locator = page.locator(selector).first
    if await page.locator(selector).count() == 0:
        return None
    text = await locator.inner_text()
    return " ".join(text.split()) or None
