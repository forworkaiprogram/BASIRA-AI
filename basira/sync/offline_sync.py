"""Offline sync: local queue with retry and conflict-aware processing.

Nothing is uploaded automatically. Items are enqueued locally and only
processed when the user enables cloud sync AND a sync backend is
configured. The processor here is a deterministic state machine (pending ->
in_flight -> done/failed/conflict) with bounded retries; the actual
transport is injected, so tests run it without any network.
"""
from __future__ import annotations

from typing import Callable, Optional

from ..db.database import Database
from ..logging_setup import get_logger

log = get_logger("sync")

MAX_ATTEMPTS = 5


class OfflineSyncManager:
    def __init__(self, db: Database, transport: Optional[Callable[[str, dict], str]] = None):
        """transport(kind, payload) -> "done" | "conflict" | raises on failure."""
        self.db = db
        self.transport = transport

    def enqueue(self, kind: str, payload: dict) -> int:
        return self.db.enqueue_sync(kind, payload)

    def process_pending(self, limit: int = 20) -> dict[str, int]:
        stats = {"done": 0, "failed": 0, "conflict": 0, "skipped": 0}
        if self.transport is None:
            stats["skipped"] = len(self.db.pending_sync_items(limit))
            return stats
        for item in self.db.pending_sync_items(limit):
            if item["attempts"] >= MAX_ATTEMPTS:
                self.db.mark_sync(item["id"], "failed", "max attempts reached")
                stats["failed"] += 1
                continue
            self.db.mark_sync(item["id"], "in_flight")
            import json

            try:
                payload = json.loads(item["payload"])
                result = self.transport(item["kind"], payload)
            except Exception as e:
                self.db.mark_sync(item["id"], "failed", str(e)[:300])
                stats["failed"] += 1
                continue
            if result == "conflict":
                self.db.mark_sync(item["id"], "conflict", "server reported conflict")
                stats["conflict"] += 1
            else:
                self.db.mark_sync(item["id"], "done")
                stats["done"] += 1
        return stats

    def retry_failures(self) -> int:
        """Reset failed items (below max attempts) to pending."""
        rows = self.db.query(
            "SELECT id, attempts FROM sync_queue WHERE status = 'failed'")
        n = 0
        for r in rows:
            if r["attempts"] < MAX_ATTEMPTS:
                self.db.mark_sync(r["id"], "pending", "")
                n += 1
        return n
