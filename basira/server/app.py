"""Local BASIRA backend service.

Security rules enforced here:
- binds to 127.0.0.1 only (never 0.0.0.0);
- every request requires a bearer token (generated at first run and stored
  in the local database, not in the repo);
- no media is persisted server-side; frames are processed in memory.
"""
from __future__ import annotations

import secrets
import threading
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from ..config import AppSettings, database_path, load_settings
from ..db.database import Database
from ..intelligence.orchestrator import BASIRACore
from ..logging_setup import get_logger

log = get_logger("server")


def get_or_create_token(db: Database) -> str:
    token = db.get_setting("backend_token")
    if not token:
        token = secrets.token_urlsafe(32)
        db.set_setting("backend_token", token)
        db.add_audit_event("backend_token_created")
    return token


def create_app(core: BASIRACore, db: Database, settings: AppSettings) -> FastAPI:
    token = get_or_create_token(db)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        core.load_lightweight()
        yield
        core.shutdown()

    app = FastAPI(title="BASIRA AI Local Service", lifespan=lifespan)

    def require_token(authorization: str = Header(default="")) -> None:
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "missing bearer token")
        if not secrets.compare_digest(authorization[7:], token):
            raise HTTPException(401, "invalid token")

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/status", dependencies=[Depends(require_token)])
    def status():
        return {
            "engines": [s.__dict__ for s in core.registry.all_status()],
            "context": core.context.snapshot(),
        }

    @app.post("/query", dependencies=[Depends(require_token)])
    async def query(body: dict, authorization: str = Header(default="")):
        request = str(body.get("request", "")).strip()
        if not request:
            raise HTTPException(400, "request text is required")
        frame = None
        if body.get("frame_b64"):
            import base64, cv2

            arr = np.frombuffer(base64.b64decode(body["frame_b64"]), np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                raise HTTPException(400, "invalid frame data")
        resp = core.handle_request(request, frame, body.get("language"))
        return JSONResponse({
            "mode": resp.mode, "intent": resp.intent, "text": resp.text,
            "confidence": resp.confidence, "data": resp.data,
            "latency_ms": round(resp.latency_ms, 1),
        })

    @app.post("/tts", dependencies=[Depends(require_token)])
    async def tts(body: dict):
        text = str(body.get("text", "")).strip()
        if not text:
            raise HTTPException(400, "text is required")
        try:
            wav = core.tts.synthesize_to_wav(text)
        except Exception as e:
            raise HTTPException(503, f"TTS unavailable: {e}")
        import base64

        return {"wav_b64": base64.b64encode(wav).decode("ascii"),
                "sample_rate": core.tts.sample_rate}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        auth = ws.query_params.get("token", "")
        if not secrets.compare_digest(auth, token):
            await ws.close(code=4401)
            return
        try:
            while True:
                msg = await ws.receive_json()
                if msg.get("type") == "query":
                    resp = core.handle_request(str(msg.get("request", "")),
                                               None, msg.get("language"))
                    await ws.send_json({"type": "answer", "text": resp.text,
                                        "mode": resp.mode})
                elif msg.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
        except WebSocketDisconnect:
            return

    return app


class LocalServer:
    """Runs the FastAPI app on a loopback port in a daemon thread."""

    def __init__(self, core: BASIRACore, db: Database, settings: AppSettings,
                 port: int | None = None):
        self.app = create_app(core, db, settings)
        self.port = port or settings.backend_port
        self._thread: threading.Thread | None = None
        self._server = None

    def start(self) -> None:
        import uvicorn

        config = uvicorn.Config(self.app, host="127.0.0.1", port=self.port,
                                log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run,
                                        name="basira-server", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"
