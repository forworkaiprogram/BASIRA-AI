"""Local backend service tests: loopback binding, token auth, endpoints."""
import base64

import numpy as np
import pytest

fastapi = pytest.importorskip("fastapi")

from basira.config import AppSettings
from basira.db.database import Database
from basira.intelligence.orchestrator import BASIRACore
from basira.server.app import create_app, get_or_create_token


@pytest.fixture()
def client(tmp_home, monkeypatch):
    from fastapi.testclient import TestClient

    settings = AppSettings()
    db = Database(tmp_home / "srv.db")
    core = BASIRACore(db, settings)
    app = create_app(core, db, settings)
    token = get_or_create_token(db)
    with TestClient(app) as c:
        yield c, token
    core.shutdown()
    db.close()


def test_health_no_auth(client):
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_status_requires_token(client):
    c, token = client
    assert c.get("/status").status_code == 401
    assert c.get("/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
    r = c.get("/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "engines" in r.json()


def test_query_endpoint(client):
    c, token = client
    headers = {"Authorization": f"Bearer {token}"}
    r = c.post("/query", json={"request": "أين الهاتف؟"}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "vision"
    assert body["text"]
    r2 = c.post("/query", json={}, headers=headers)
    assert r2.status_code == 400


def test_query_with_frame(client):
    c, token = client
    headers = {"Authorization": f"Bearer {token}"}
    import cv2

    frame = cv2.imread(str(__import__("pathlib").Path(__file__).parents[1] / "data" / "bus.jpg"))
    ok, buf = cv2.imencode(".jpg", frame)
    payload = {
        "request": "صف المشهد",
        "frame_b64": base64.b64encode(buf.tobytes()).decode("ascii"),
    }
    model = __import__("basira.config", fromlist=["models_dir"]).models_dir() / "vision" / "yolov8n.onnx"
    if not model.exists():
        pytest.skip("yolov8n.onnx not downloaded")
    r = c.post("/query", json=payload, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["detections"]


def test_tts_endpoint(client):
    c, token = client
    headers = {"Authorization": f"Bearer {token}"}
    voice = __import__("basira.config", fromlist=["models_dir"]).models_dir() / "language" / "ar_JO-kareem-medium.onnx"
    if not voice.exists():
        pytest.skip("piper voice not downloaded")
    r = c.post("/tts", json={"text": "مرحبا"}, headers=headers)
    assert r.status_code == 200
    wav = base64.b64decode(r.json()["wav_b64"])
    assert len(wav) > 1000


def test_websocket_auth(client):
    from starlette.websockets import WebSocketDisconnect

    c, token = client
    with c.websocket_connect("/ws?token=wrong") as ws:
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    with c.websocket_connect(f"/ws?token={token}") as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_token_persisted(tmp_home):
    db = Database(tmp_home / "tok.db")
    t1 = get_or_create_token(db)
    t2 = get_or_create_token(db)
    assert t1 == t2
    assert len(t1) >= 32
    db.close()
