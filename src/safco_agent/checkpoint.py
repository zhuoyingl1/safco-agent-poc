from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class CheckpointStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class CheckpointEntry(BaseModel):
    url: str
    status: CheckpointStatus
    attempt_count: int
    record_count: int
    last_error: str | None
    run_id: str | None
    updated_at: str


class CheckpointStore:
    """SQLite-backed crawl checkpoint store."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def should_skip(self, url: str, resume: bool, force_refresh: bool) -> bool:
        if not resume or force_refresh:
            return False
        entry = self.get(url)
        return bool(entry and entry.status == CheckpointStatus.SUCCESS)

    def mark_success(self, url: str, record_count: int, run_id: str) -> None:
        self._upsert(
            url=url,
            status=CheckpointStatus.SUCCESS,
            record_count=record_count,
            last_error=None,
            run_id=run_id,
        )

    def mark_failed(self, url: str, error: str, run_id: str) -> None:
        self._upsert(
            url=url,
            status=CheckpointStatus.FAILED,
            record_count=0,
            last_error=error,
            run_id=run_id,
        )

    def get(self, url: str) -> CheckpointEntry | None:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT url, status, attempt_count, record_count, last_error, run_id, updated_at
                FROM crawl_checkpoints
                WHERE url = ?
                """,
                (url,),
            ).fetchone()
        if not row:
            return None
        return CheckpointEntry(
            url=row["url"],
            status=CheckpointStatus(row["status"]),
            attempt_count=row["attempt_count"],
            record_count=row["record_count"],
            last_error=row["last_error"],
            run_id=row["run_id"],
            updated_at=row["updated_at"],
        )

    def summary(self) -> dict[str, Any]:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            total = connection.execute("SELECT COUNT(*) FROM crawl_checkpoints").fetchone()[0]
            status_rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM crawl_checkpoints GROUP BY status"
            ).fetchall()
            attempts = connection.execute(
                "SELECT COALESCE(SUM(attempt_count), 0) FROM crawl_checkpoints"
            ).fetchone()[0]
        return {
            "path": str(self.path),
            "checkpoint_count": total,
            "status_counts": {row["status"]: row["count"] for row in status_rows},
            "total_attempts": attempts,
        }

    def _init_schema(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS crawl_checkpoints (
                    url TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    record_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    run_id TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _upsert(
        self,
        url: str,
        status: CheckpointStatus,
        record_count: int,
        last_error: str | None,
        run_id: str,
    ) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO crawl_checkpoints (
                    url,
                    status,
                    attempt_count,
                    record_count,
                    last_error,
                    run_id,
                    updated_at
                ) VALUES (
                    :url,
                    :status,
                    1,
                    :record_count,
                    :last_error,
                    :run_id,
                    :updated_at
                )
                ON CONFLICT(url) DO UPDATE SET
                    status = excluded.status,
                    attempt_count = crawl_checkpoints.attempt_count + 1,
                    record_count = excluded.record_count,
                    last_error = excluded.last_error,
                    run_id = excluded.run_id,
                    updated_at = excluded.updated_at
                """,
                {
                    "url": url,
                    "status": status.value,
                    "record_count": record_count,
                    "last_error": last_error,
                    "run_id": run_id,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )

