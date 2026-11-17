"""Camera management built on OpenCV.

Runs frame capture in a background thread so the UI never blocks. All
methods are safe to call when no camera exists: they raise
HardwareUnavailableError (never crash) and the device manager reports the
camera as missing.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from ..logging_setup import get_logger, HardwareUnavailableError

log = get_logger("hardware.camera")

try:  # pragma: no cover - trivial import guard
    import cv2
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore


@dataclass
class CameraInfo:
    index: int
    name: str
    width: int
    height: int


class CameraManager:
    """Background-thread camera reader with graceful unavailability."""

    def __init__(self, camera_index: int = 0, width: int = 1280, height: int = 720,
                 fps: int = 30):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self._cap = None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._latest: Optional[np.ndarray] = None
        self._last_error: str = ""
        self._frame_seq = 0

    # -- discovery ------------------------------------------------------------
    @staticmethod
    def list_cameras(max_probe: int = 5) -> list[CameraInfo]:
        if cv2 is None:
            return []
        found: list[CameraInfo] = []
        for idx in range(max_probe):
            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2 if hasattr(cv2, "CAP_V4L2") else 0)
            ok = False
            try:
                ok = cap.isOpened() and cap.read()[0]
            except Exception:
                ok = False
            if ok:
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                found.append(CameraInfo(index=idx, name=f"Camera {idx}", width=w, height=h))
            cap.release()
        return found

    # -- lifecycle ------------------------------------------------------------
    def is_available(self) -> bool:
        return self.list_cameras_probe(self.camera_index)

    @staticmethod
    def list_cameras_probe(index: int) -> bool:
        cams = CameraManager.list_cameras(max_probe=index + 1)
        return any(c.index == index for c in cams)

    def start(self) -> None:
        if self._running.is_set():
            return
        if cv2 is None:
            raise HardwareUnavailableError("OpenCV is not installed")
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            raise HardwareUnavailableError(
                f"No camera available at index {self.camera_index}"
            )
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        with self._lock:
            self._cap = cap
        self._running.set()
        self._thread = threading.Thread(target=self._read_loop, name="basira-camera", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
        with self._lock:
            self._latest = None

    def _read_loop(self) -> None:
        interval = 1.0 / max(self.fps, 1)
        consecutive_failures = 0
        while self._running.is_set():
            with self._lock:
                cap = self._cap
            if cap is None:
                break
            ok, frame = cap.read()
            if not ok:
                consecutive_failures += 1
                if consecutive_failures >= 30:
                    self._last_error = "camera stream lost"
                    log.warning("camera stream lost; stopping capture")
                    self._running.clear()
                    break
                time.sleep(0.05)
                continue
            consecutive_failures = 0
            with self._lock:
                self._latest = frame
                self._frame_seq += 1
            time.sleep(interval)

    # -- frame access ---------------------------------------------------------
    def latest_frame(self, max_age: float = 1.0) -> Optional[np.ndarray]:
        with self._lock:
            frame = self._latest
        return frame

    def capture_still(self, timeout: float = 2.0) -> np.ndarray:
        deadline = time.time() + timeout
        start_seq = self._frame_seq
        while time.time() < deadline:
            with self._lock:
                if self._latest is not None and self._frame_seq > start_seq:
                    return self._latest.copy()
            time.sleep(0.02)
        frame = self.latest_frame()
        if frame is None:
            raise HardwareUnavailableError("No frame available from camera")
        return frame.copy()

    @property
    def status(self) -> dict:
        return {
            "running": self._running.is_set(),
            "index": self.camera_index,
            "error": self._last_error,
            "frames": self._frame_seq,
        }

    def __enter__(self) -> "CameraManager":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
