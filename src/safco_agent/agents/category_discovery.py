from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveredCategory:
    name: str
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
            if not self._looks_like_child_category(seed_url, href):
                continue
            normalized = href.rstrip("/")
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
        seed = seed_url.rstrip("/")
        target = href.rstrip("/")
        return target.startswith(seed + "/") and "/product/" not in target

