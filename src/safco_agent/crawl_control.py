from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class CrawlControlConfig(BaseModel):
    rate_limit_seconds: float = Field(default=1.0, ge=0)
    max_attempts: int = Field(default=2, ge=1)
    retry_backoff_seconds: float = Field(default=1.0, ge=0)


class PoliteCrawlController:
    """Apply request spacing and retry policy around crawl operations."""

    def __init__(self, config: CrawlControlConfig) -> None:
        self.config = config
        self._lock = asyncio.Lock()
        self._last_started_at: float | None = None

    async def run(self, operation: Callable[[], Awaitable[T]]) -> T:
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_attempts + 1):
            await self._wait_for_slot()
            try:
                return await operation()
            except Exception as exc:
                last_error = exc
                if attempt >= self.config.max_attempts:
                    break
                await asyncio.sleep(self.config.retry_backoff_seconds * attempt)
        if last_error:
            raise last_error
        raise RuntimeError("crawl operation did not run")

    async def _wait_for_slot(self) -> None:
        async with self._lock:
            now = monotonic()
            if self._last_started_at is not None:
                elapsed = now - self._last_started_at
                wait_seconds = self.config.rate_limit_seconds - elapsed
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
            self._last_started_at = monotonic()

