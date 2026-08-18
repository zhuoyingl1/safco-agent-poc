from pathlib import Path

from safco_agent.config import load_config


def test_load_default_config() -> None:
    config = load_config(Path("config/default.yaml"))

    assert config.project_name == "safco-agent-poc"
    assert [category.key for category in config.seed_categories] == [
        "gloves",
        "sutures_surgical",
    ]
    assert config.crawl.concurrency == 2
    assert config.crawl.max_attempts == 2
    assert config.crawl.retry_backoff_seconds == 1.0
