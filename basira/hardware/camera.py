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
        self.state = "idle"  # idle | starting | running | error

    # -- discovery ------------------------------------------------------------
    @staticmethod
    def _backends() -> list[int]:
        """OpenCV capture backends appropriate for the current OS.
        Windows: DirectShow first (fast open, MSMF can take 10s+).
        macOS: AVFoundation. Linux: V4L2."""
        import sys as _sys
        if _sys.platform.startswith("win"):
            return [b for b in (cv2.CAP_DSHOW, cv2.CAP_MSMF) if b is not None]
        if _sys.platform == "darwin" and hasattr(cv2, "CAP_AVFOUNDATION"):
            return [cv2.CAP_AVFOUNDATION]
        return [cv2.CAP_V4L2 if hasattr(cv2, "CAP_V4L2") else 0]

    @staticmethod
    def _open_capture(index: int):
        """Open a VideoCapture with the first working platform backend."""
        for backend in CameraManager._backends():
            try:
                cap = cv2.VideoCapture(index, backend)
            except Exception:
                continue
            if cap is not None and cap.isOpened():
                return cap
            try:
                cap.release()
            except Exception:
                pass
        return None

    @staticmethod
    def list_cameras(max_probe: int = 5) -> list[CameraInfo]:
        if cv2 is None:
            return []
        found: list[CameraInfo] = []
        for idx in range(max_probe):
            cap = CameraManager._open_capture(idx)
            if cap is None:
                continue
            ok = False
            try:
                ok = cap.read()[0]
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
        """Open the camera and start the reader thread (blocking open).
        For UI code use start_async() so the open never blocks the GUI."""
        if self._running.is_set():
            return
        if cv2 is None:
            raise HardwareUnavailableError("OpenCV is not installed")
        self.state = "starting"
        cap = self._open_capture(self.camera_index)
        if cap is None:
            self.state = "error"
            self._last_error = f"No camera available at index {self.camera_index}"
            raise HardwareUnavailableError(self._last_error)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        with self._lock:
            self._cap = cap
        self._running.set()
        self.state = "running"
        self._thread = threading.Thread(target=self._read_loop, name="basira-camera", daemon=True)
        self._thread.start()

    def start_async(self, on_started=None, on_error=None) -> None:
        """Open the camera in a background thread (never blocks the caller).

        on_started/on_error run in the opener thread; Qt callers must marshal
        results to the GUI thread via signals (see desktop worker helpers)."""
        if self._running.is_set() or getattr(self, "_opening", False):
            return
        self._opening = True

        def _work() -> None:
            try:
                self.start()
                self._opening = False
                if on_started is not None:
                    on_started()
            except Exception as e:
                self._opening = False
                self._last_error = str(e)
                if on_error is not None:
                    on_error(e)

        threading.Thread(target=_work, name="basira-camera-open", daemon=True).start()

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
        self.state = "idle"

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
                    self.state = "error"
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
            "state": self.state,
            "index": self.camera_index,
            "error": self._last_error,
            "frames": self._frame_seq,
        }

    def __enter__(self) -> "CameraManager":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
