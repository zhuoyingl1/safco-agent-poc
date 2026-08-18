from safco_agent.checkpoint import CheckpointStatus, CheckpointStore


def test_checkpoint_store_tracks_success_and_resume_skip(tmp_path) -> None:
    store = CheckpointStore(tmp_path / "checkpoints.sqlite")
    url = "https://www.safcodental.com/product/aurelia-reg-amazing-reg"

    assert store.should_skip(url, resume=True, force_refresh=False) is False

    store.mark_success(url, record_count=5, run_id="run-1")
    entry = store.get(url)

    assert entry is not None
    assert entry.status == CheckpointStatus.SUCCESS
    assert entry.attempt_count == 1
    assert entry.record_count == 5
    assert store.should_skip(url, resume=True, force_refresh=False) is True
    assert store.should_skip(url, resume=False, force_refresh=False) is False
    assert store.should_skip(url, resume=True, force_refresh=True) is False

    store.mark_success(url, record_count=4, run_id="run-2")
    refreshed = store.get(url)

    assert refreshed is not None
    assert refreshed.attempt_count == 2
    assert refreshed.record_count == 4
    assert store.summary()["status_counts"] == {"success": 1}


def test_checkpoint_store_does_not_skip_failed_urls(tmp_path) -> None:
    store = CheckpointStore(tmp_path / "checkpoints.sqlite")
    url = "https://www.safcodental.com/product/orasoothe-reg-sockit-gel"

    store.mark_failed(url, error="timeout", run_id="run-1")
    entry = store.get(url)

    assert entry is not None
    assert entry.status == CheckpointStatus.FAILED
    assert entry.last_error == "timeout"
    assert store.should_skip(url, resume=True, force_refresh=False) is False

