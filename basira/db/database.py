"""SQLite database access layer.

Thread-safety: SQLite connections are opened per-thread via
``Database.connection()`` using thread-local storage, which matches how the
desktop app and the local backend access the database (UI thread + worker
threads).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterator

from .schema import SCHEMA_SQL, SCHEMA_VERSION
from ..logging_setup import get_logger

log = get_logger("db")


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self.migrate()

    # -- connection management ------------------------------------------------
    def connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.path), timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # -- schema ---------------------------------------------------------------
    def migrate(self) -> None:
        conn = self.connection()
        conn.executescript(SCHEMA_SQL)
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        elif row["version"] < SCHEMA_VERSION:
            # Future migrations go here, gated on the stored version.
            conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
        conn.commit()

    # -- generic helpers ------------------------------------------------------
    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        conn = self.connection()
        cur = conn.execute(sql, params)
        conn.commit()
        return cur

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.connection().execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.connection().execute(sql, params).fetchone()

    # -- domain operations ----------------------------------------------------
    def add_audit_event(self, event: str, details: str = "") -> None:
        self.execute("INSERT INTO audit_events (event, details) VALUES (?, ?)", (event, details))

    def audit_events(self, limit: int = 100) -> list[sqlite3.Row]:
        return self.query(
            "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)
        )

    def set_setting(self, key: str, value: Any) -> None:
        self.execute(
            "INSERT INTO application_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = datetime('now')",
            (key, json.dumps(value, ensure_ascii=False)),
        )

    def get_setting(self, key: str, default: Any = None) -> Any:
        row = self.query_one("SELECT value FROM application_settings WHERE key = ?", (key,))
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]

    def add_translation(
        self,
        source_kind: str,
        target_kind: str,
        source_text: str = "",
        target_text: str = "",
        language: str = "ar",
        confidence: float | None = None,
        session_id: int | None = None,
    ) -> int:
        cur = self.execute(
            "INSERT INTO translation_history (session_id, source_kind, source_text, "
            "target_kind, target_text, language, confidence) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, source_kind, source_text, target_kind, target_text, language, confidence),
        )
        return int(cur.lastrowid)

    def translation_history(self, limit: int = 50) -> list[sqlite3.Row]:
        return self.query(
            "SELECT * FROM translation_history ORDER BY id DESC LIMIT ?", (limit,)
        )

    def upsert_model(
        self,
        key: str,
        display_name: str,
        task: str,
        file_path: str,
        sha256: str | None = None,
        size_bytes: int | None = None,
        source_url: str = "",
        license: str = "",
    ) -> None:
        self.execute(
            "INSERT INTO model_registry (key, display_name, task, file_path, sha256, "
            "size_bytes, source_url, license) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET display_name = excluded.display_name, "
            "task = excluded.task, file_path = excluded.file_path, "
            "sha256 = excluded.sha256, size_bytes = excluded.size_bytes, "
            "source_url = excluded.source_url, license = excluded.license",
            (key, display_name, task, file_path, sha256, size_bytes, source_url, license),
        )

    def set_model_loaded(self, key: str, loaded: bool) -> None:
        self.execute("UPDATE model_registry SET loaded = ? WHERE key = ?", (int(loaded), key))

    def models(self) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM model_registry ORDER BY key")

    def enqueue_sync(self, kind: str, payload: dict) -> int:
        cur = self.execute(
            "INSERT INTO sync_queue (kind, payload) VALUES (?, ?)",
            (kind, json.dumps(payload, ensure_ascii=False)),
        )
        return int(cur.lastrowid)

    def pending_sync_items(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.query(
            "SELECT * FROM sync_queue WHERE status IN ('pending','failed') "
            "ORDER BY id LIMIT ?",
            (limit,),
        )

    def mark_sync(self, item_id: int, status: str, error: str = "") -> None:
        self.execute(
            "UPDATE sync_queue SET status = ?, last_error = ?, attempts = attempts + 1, "
            "updated_at = datetime('now') WHERE id = ?",
            (status, error, item_id),
        )

    def wipe_user_data(self) -> dict[str, int]:
        """Delete all user-generated data (privacy 'delete my data')."""
        counts: dict[str, int] = {}
        for table in [
            "translation_history",
            "conversation_contexts",
            "sessions",
            "user_feedback",
            "audit_events",
            "sync_queue",
        ]:
            cur = self.execute(f"DELETE FROM {table}")
            counts[table] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        self.add_audit_event("wipe_user_data", json.dumps(counts))
        return counts
