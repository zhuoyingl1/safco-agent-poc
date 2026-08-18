import asyncio

import pytest

from safco_agent.crawl_control import CrawlControlConfig, PoliteCrawlController


def test_crawl_controller_retries_until_success() -> None:
    attempts = 0
    controller = PoliteCrawlController(
        CrawlControlConfig(
            rate_limit_seconds=0,
            max_attempts=3,
            retry_backoff_seconds=0,
        )
    )

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("temporary failure")
        return "ok"

    result = asyncio.run(controller.run(operation))

    assert result == "ok"
    assert attempts == 2


def test_crawl_controller_raises_after_max_attempts() -> None:
    attempts = 0
    controller = PoliteCrawlController(
        CrawlControlConfig(
            rate_limit_seconds=0,
            max_attempts=2,
            retry_backoff_seconds=0,
        )
    )

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("permanent failure")

    with pytest.raises(RuntimeError, match="permanent failure"):
        asyncio.run(controller.run(operation))

    assert attempts == 2

