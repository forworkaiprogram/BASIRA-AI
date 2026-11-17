from basira.db.database import Database
from basira.db.schema import SCHEMA_VERSION


def test_migrate_creates_all_tables(db):
    tables = {r["name"] for r in db.query(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    expected = {
        "users", "user_preferences", "accessibility_profiles", "devices",
        "sessions", "conversation_contexts", "translation_history",
        "model_registry", "model_versions", "user_feedback", "sync_queue",
        "application_settings", "audit_events", "schema_version",
    }
    assert expected.issubset(tables)
    assert db.query_one("SELECT version FROM schema_version")["version"] == SCHEMA_VERSION


def test_settings_roundtrip(db):
    db.set_setting("foo", {"a": 1, "b": [1, 2]})
    assert db.get_setting("foo") == {"a": 1, "b": [1, 2]}
    assert db.get_setting("missing", 42) == 42


def test_translation_history(db):
    db.add_translation("sign", "text", "hello", "مرحبا", "ar", 0.9)
    db.add_translation("speech", "text", "hi", "أهلا", "ar", 0.8)
    rows = db.translation_history()
    assert len(rows) == 2
    assert rows[0]["source_kind"] == "speech"  # newest first


def test_model_registry_upsert(db):
    db.upsert_model("vision.detector.yolov8n", "YOLOv8n", "object-detection",
                    "/tmp/yolov8n.onnx", sha256="abc", size_bytes=12,
                    source_url="https://example.com", license="AGPL-3.0")
    db.upsert_model("vision.detector.yolov8n", "YOLOv8n", "object-detection",
                    "/tmp/yolov8n.onnx")
    rows = db.models()
    assert len(rows) == 1
    assert rows[0]["sha256"] is None or rows[0]["key"] == "vision.detector.yolov8n"
    db.set_model_loaded("vision.detector.yolov8n", True)
    assert db.models()[0]["loaded"] == 1


def test_sync_queue_lifecycle(db):
    item_id = db.enqueue_sync("feedback", {"x": 1})
    items = db.pending_sync_items()
    assert len(items) == 1 and items[0]["kind"] == "feedback"
    db.mark_sync(item_id, "failed", "net down")
    assert db.pending_sync_items()[0]["attempts"] == 1
    db.mark_sync(item_id, "done")
    assert db.pending_sync_items() == []


def test_wipe_user_data(db):
    db.add_translation("text", "text", "a", "b", "ar", 0.5)
    db.add_audit_event("test")
    db.enqueue_sync("x", {})
    counts = db.wipe_user_data()
    assert counts["translation_history"] == 1
    assert db.translation_history() == []
    assert db.pending_sync_items() == []
    # wipe itself is audited
    assert any(e["event"] == "wipe_user_data" for e in db.audit_events())


def test_audit_events(db):
    db.add_audit_event("camera_started", "camera index=0")
    rows = db.audit_events(limit=5)
    assert rows[0]["event"] == "camera_started"
    assert "camera" in rows[0]["details"]
