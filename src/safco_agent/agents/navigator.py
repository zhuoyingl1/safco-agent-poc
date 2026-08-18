from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from safco_agent.agents.category_discovery import CategoryDiscoveryAgent, DiscoveredCategory
from safco_agent.agents.page_classifier import PageClassifierAgent, PageType
from safco_agent.browser import PageSnapshot, fetch_page_snapshot
from safco_agent.config import AppConfig, SeedCategory
from safco_agent.crawl_control import CrawlControlConfig, PoliteCrawlController
from safco_agent.url_utils import canonicalize_url, is_safco_product_url


class ProductUrlCandidate(BaseModel):
    url: str
    text: str
    source_page_url: str
    source_category_key: str
    source_category_name: str


class VisitedPage(BaseModel):
    requested_url: str
    final_url: str
    title: str
    h1: str | None
    page_type: PageType
    product_link_count: int
    category_link_count: int


class CategoryDiscoverySummary(BaseModel):
    seed_key: str
    seed_name: str
    seed_url: str
    discovered_categories: list[DiscoveredCategory] = Field(default_factory=list)
    visited_pages: list[VisitedPage] = Field(default_factory=list)
    product_urls: list[ProductUrlCandidate] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DiscoveryRunResult(BaseModel):
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    seed_category_count: int
    categories: list[CategoryDiscoverySummary]

    @property
    def total_product_urls(self) -> int:
        return sum(len(category.product_urls) for category in self.categories)

    def write_json(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )


class NavigatorAgent:
    """Traverse category pages and collect product detail URLs."""

    def __init__(
        self,
        category_agent: CategoryDiscoveryAgent | None = None,
        classifier: PageClassifierAgent | None = None,
    ) -> None:
        self.category_agent = category_agent or CategoryDiscoveryAgent()
        self.classifier = classifier or PageClassifierAgent()

    async def discover(
        self,
        config: AppConfig,
        max_pages_per_category: int | None = None,
        timeout_ms: int | None = None,
        headless: bool = True,
    ) -> DiscoveryRunResult:
        limit = max_pages_per_category or config.crawl.max_pages_per_category
        browser_timeout = timeout_ms or config.crawl.browser_timeout_ms
        crawl_controller = PoliteCrawlController(
            CrawlControlConfig(
                rate_limit_seconds=config.crawl.rate_limit_seconds,
                max_attempts=config.crawl.max_attempts,
                retry_backoff_seconds=config.crawl.retry_backoff_seconds,
            )
        )
        categories: list[CategoryDiscoverySummary] = []
        for seed in config.seed_categories:
            categories.append(
                await self._discover_seed(
                    seed=seed,
                    max_pages=limit,
                    timeout_ms=browser_timeout,
                    headless=headless,
                    crawl_controller=crawl_controller,
                )
            )
        return DiscoveryRunResult(
            seed_category_count=len(config.seed_categories),
            categories=categories,
        )

    async def _discover_seed(
        self,
        seed: SeedCategory,
        max_pages: int,
        timeout_ms: int,
        headless: bool,
        crawl_controller: PoliteCrawlController,
    ) -> CategoryDiscoverySummary:
        summary = CategoryDiscoverySummary(
            seed_key=seed.key,
            seed_name=seed.name,
            seed_url=canonicalize_url(str(seed.url)),
        )
        snapshots: list[PageSnapshot] = []
        try:
            seed_snapshot = await crawl_controller.run(
                lambda: fetch_page_snapshot(
                    str(seed.url),
                    timeout_ms=timeout_ms,
                    headless=headless,
                )
            )
            snapshots.append(seed_snapshot)
            summary.discovered_categories = self.category_agent.discover_from_links(
                str(seed.url),
                [(link.text, link.href) for link in seed_snapshot.links],
            )
        except Exception as exc:
            summary.errors.append(f"seed fetch failed: {exc}")
            return summary

        for category in summary.discovered_categories[: max(0, max_pages - 1)]:
            try:
                snapshots.append(
                    await crawl_controller.run(
                        lambda category_url=category.url: fetch_page_snapshot(
                            category_url,
                            timeout_ms=timeout_ms,
                            headless=headless,
                        )
                    )
                )
            except Exception as exc:
                summary.errors.append(f"category fetch failed: {category.url}: {exc}")

        product_urls: dict[str, ProductUrlCandidate] = {}
        for snapshot in snapshots:
            page_type = self.classifier.classify(snapshot.final_url, snapshot.body_text)
            summary.visited_pages.append(self._visited_page(snapshot, page_type))
            for candidate in self.collect_product_links(snapshot, seed):
                product_urls.setdefault(candidate.url, candidate)
        summary.product_urls = list(product_urls.values())
        return summary

    def collect_product_links(
        self,
        snapshot: PageSnapshot,
        seed: SeedCategory,
    ) -> list[ProductUrlCandidate]:
        candidates: list[ProductUrlCandidate] = []
        seen: set[str] = set()
        for link in snapshot.links:
            href = canonicalize_url(link.href)
            text = " ".join(link.text.split())
            if not self._looks_like_product_candidate(href, text):
                continue
            if href in seen:
                continue
            seen.add(href)
            candidates.append(
                ProductUrlCandidate(
                    url=href,
                    text=text,
                    source_page_url=canonicalize_url(snapshot.final_url),
                    source_category_key=seed.key,
                    source_category_name=seed.name,
                )
            )
        return candidates

    def _visited_page(self, snapshot: PageSnapshot, page_type: PageType) -> VisitedPage:
        return VisitedPage(
            requested_url=canonicalize_url(str(snapshot.requested_url)),
            final_url=canonicalize_url(snapshot.final_url),
            title=snapshot.title,
            h1=snapshot.h1,
            page_type=page_type,
            product_link_count=sum(
                1
                for link in snapshot.links
                if self._looks_like_product_candidate(canonicalize_url(link.href), link.text)
            ),
            category_link_count=sum(1 for link in snapshot.links if "/catalog/" in link.href),
        )

    @staticmethod
    def _looks_like_product_candidate(url: str, text: str) -> bool:
        normalized_text = " ".join(text.lower().split())
        if not is_safco_product_url(url):
            return False
        if url.endswith("/clearance-item") or normalized_text in {"clearance", "shop now"}:
            return False
        return bool(normalized_text)
