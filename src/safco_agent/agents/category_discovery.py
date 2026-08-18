from __future__ import annotations

from pydantic import BaseModel, Field

from safco_agent.url_utils import canonicalize_url


class DiscoveredCategory(BaseModel):
    name: str = Field(min_length=1)
    url: str
    parent_url: str | None = None


class CategoryDiscoveryAgent:
    """Find subcategory URLs from configured category seed pages."""

    def discover_from_links(
        self,
        seed_url: str,
        links: list[tuple[str, str]],
    ) -> list[DiscoveredCategory]:
        discovered: list[DiscoveredCategory] = []
        seen: set[str] = set()
        for label, href in links:
            normalized = canonicalize_url(href)
            if not self._looks_like_child_category(seed_url, normalized):
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            discovered.append(
                DiscoveredCategory(
                    name=" ".join(label.split()),
                    url=normalized,
                    parent_url=seed_url,
                )
            )
        return discovered

    @staticmethod
    def _looks_like_child_category(seed_url: str, href: str) -> bool:
        seed = canonicalize_url(seed_url)
        target = canonicalize_url(href)
        return target.startswith(seed + "/") and "/product/" not in target
