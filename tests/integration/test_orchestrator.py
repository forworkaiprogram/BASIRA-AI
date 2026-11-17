"""End-to-end orchestrator tests with the real vision stack."""
from pathlib import Path

import cv2
import numpy as np
import pytest

from basira.config import AppSettings
from basira.db.database import Database
from basira.intelligence.orchestrator import BASIRACore

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture()
def core(tmp_home):
    settings = AppSettings()
    db = Database(tmp_home / "core.db")
    c = BASIRACore(db, settings)
    yield c
    c.shutdown()
    db.close()


def test_handle_request_without_camera(core):
    resp = core.handle_request("أين الهاتف؟", frame=None)
    assert resp.mode in ("vision", "hear")
    assert resp.text


def test_orchestrator_records_history(core):
    core.settings.save_history = True
    core.handle_request("صف المشهد", frame=None)
    rows = core.db.translation_history()
    assert len(rows) == 1


def test_full_vision_request_real_model(core):
    model = __import__("basira.config", fromlist=["models_dir"]).models_dir() / "vision" / "yolov8n.onnx"
    if not model.exists():
        pytest.skip("yolov8n.onnx not downloaded")
    frame = cv2.imread(str(DATA / "bus.jpg"))
    resp = core.handle_request("ماذا يوجد أمامي؟", frame)
    assert resp.mode == "vision"
    assert resp.confidence > 0
    assert "شخص" in resp.data["fused_summary"] or "أشياء" in resp.data["fused_summary"]
    assert resp.data["detections"]

    resp2 = core.handle_request("أين الشخص؟", frame)
    assert "شخص" in resp2.text
    assert resp2.confidence > 0.3


def test_context_updates(core):
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    core.handle_request("صف المشهد", frame)
    snap = core.context.snapshot()
    assert snap["mode"] == "vision"
    # empty frame: no detections -> description says it cannot confirm
    assert "لا أستطيع" in core.context.last_answer or "أرى" in core.context.last_answer
