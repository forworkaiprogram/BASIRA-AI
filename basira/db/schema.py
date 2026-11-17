"""SQLite schema for BASIRA AI local database (schema version 1)."""
from __future__ import annotations

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    language TEXT NOT NULL DEFAULT 'ar',
    theme TEXT NOT NULL DEFAULT 'dark',
    text_scale REAL NOT NULL DEFAULT 1.0,
    prefer_voice_output INTEGER NOT NULL DEFAULT 1,
    speech_rate REAL NOT NULL DEFAULT 1.0,
    high_contrast INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS accessibility_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profile_type TEXT NOT NULL,             -- blind | deaf | low_vision | hard_of_hearing | combined
    vision_mode INTEGER NOT NULL DEFAULT 1, -- enable vision assistance
    sign_mode INTEGER NOT NULL DEFAULT 0,
    hear_mode INTEGER NOT NULL DEFAULT 1,
    connect_mode INTEGER NOT NULL DEFAULT 0,
    haptic_alerts INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,                     -- camera | microphone | speaker
    index_or_id TEXT NOT NULL,
    name TEXT NOT NULL,
    last_seen_at TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    UNIQUE(kind, index_or_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    mode TEXT NOT NULL,                     -- vision | sign | hear | connect
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS conversation_contexts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    summary TEXT DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}'      -- serialized context snapshot
);

CREATE TABLE IF NOT EXISTS translation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id),
    source_kind TEXT NOT NULL,              -- sign | speech | text | image
    source_text TEXT DEFAULT '',
    target_kind TEXT NOT NULL,              -- text | speech
    target_text TEXT DEFAULT '',
    language TEXT DEFAULT 'ar',
    confidence REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS model_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,               -- e.g. vision.detector.yolov8n
    display_name TEXT NOT NULL,
    task TEXT NOT NULL,
    file_path TEXT NOT NULL,
    sha256 TEXT,
    size_bytes INTEGER,
    source_url TEXT,
    license TEXT DEFAULT '',
    loaded INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_key TEXT NOT NULL REFERENCES model_registry(key) ON DELETE CASCADE,
    version TEXT NOT NULL,
    metrics TEXT DEFAULT '{}',
    installed_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(model_key, version)
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id),
    item_type TEXT NOT NULL,                -- sign_translation | ocr | description
    item_ref TEXT DEFAULT '',
    corrected_text TEXT DEFAULT '',
    rating INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sync_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- pending | in_flight | done | failed | conflict
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS application_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT NOT NULL,
    details TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_translation_history_created
    ON translation_history(created_at);
CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue(status);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at);
"""
