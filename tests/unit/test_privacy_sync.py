import json

from basira.privacy.privacy import PrivacyManager, PrivacyState
from basira.sync.offline_sync import OfflineSyncManager


def test_media_not_stored_by_default(tmp_home, db):
    pm = PrivacyManager(db)
    assert pm.can_store_media() is False


def test_purge_media(tmp_home, db):
    pm = PrivacyManager(db)
    d = pm.media_dir()
    f = d / "frame.jpg"
    f.write_bytes(b"\xff\xd8fake")
    assert pm.purge_media() == 1
    assert not f.exists()


def test_purge_all_user_data(tmp_home, db):
    db.add_translation("text", "text", "a", "b", "ar", 0.5)
    pm = PrivacyManager(db)
    counts = pm.purge_all_user_data()
    assert counts["translation_history"] == 1
    assert db.translation_history() == []
    assert any(e["event"] == "wipe_user_data" for e in db.audit_events())


def test_sync_no_transport_skips(db):
    mgr = OfflineSyncManager(db)
    mgr.enqueue("feedback", {"a": 1})
    stats = mgr.process_pending()
    assert stats["skipped"] == 1
    assert db.pending_sync_items()[0]["status"] in ("pending", "failed")


def test_sync_transport_success(db):
    sent = []

    def transport(kind, payload):
        sent.append((kind, payload))
        return "done"

    mgr = OfflineSyncManager(db, transport)
    mgr.enqueue("feedback", {"a": 1})
    stats = mgr.process_pending()
    assert stats["done"] == 1
    assert sent == [("feedback", {"a": 1})]
    assert db.pending_sync_items() == []


def test_sync_retry_and_conflict(db):
    calls = {"n": 0}

    def transport(kind, payload):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("offline")
        return "done"

    mgr = OfflineSyncManager(db, transport)
    item = mgr.enqueue("kb", {"b": 2})
    stats = mgr.process_pending()
    assert stats["failed"] == 1
    assert mgr.retry_failures() == 1
    stats2 = mgr.process_pending()
    assert stats2["done"] == 1

    mgr2 = OfflineSyncManager(db, lambda k, p: "conflict")
    item2 = mgr2.enqueue("kb", {"c": 3})
    stats3 = mgr2.process_pending()
    assert stats3["conflict"] == 1
    row = db.query_one("SELECT status FROM sync_queue WHERE id = ?", (item2,))
    assert row["status"] == "conflict"


def test_sync_max_attempts(db):
    mgr = OfflineSyncManager(db, transport=lambda k, p: (_ for _ in ()).throw(OSError("down")))
    item = mgr.enqueue("kb", {})
    for _ in range(6):
        mgr.process_pending()
    row = db.query_one("SELECT status, attempts FROM sync_queue WHERE id = ?", (item,))
    assert row["status"] == "failed"
    assert row["attempts"] >= 5
