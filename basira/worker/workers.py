"""QThread workers so AI inference never blocks the UI thread."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from ..engines.vision.engine import VisionEngine, VisionResult
from ..engines.sign.engine import SignEngine, SignFrameResult
from ..hardware.camera import CameraManager


_LIVE_THREADS: list[QThread] = []


class CameraOpenerWorker(QObject):
    """Opens a camera in a QThread so the GUI never blocks on open()
    (camera open can take several seconds on Windows/MSMF)."""

    finished = Signal(object)   # CameraManager, on success
    failed = Signal(str)        # error message

    def __init__(self, camera: CameraManager):
        super().__init__()
        self.camera = camera

    def run(self) -> None:
        try:
            self.camera.start()
            self.finished.emit(self.camera)
        except Exception as e:
            self.failed.emit(str(e))


class VisionWorker(QObject):
    finished = Signal(object)   # VisionResult
    failed = Signal(str)

    def __init__(self, engine: VisionEngine, frame: np.ndarray,
                 question: str | None, lang: str):
        super().__init__()
        self.engine = engine
        self.frame = frame
        self.question = question
        self.lang = lang

    def run(self) -> None:
        try:
            result = self.engine.analyze_frame(self.frame, self.question, self.lang)
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class SignWorker(QObject):
    finished = Signal(object)   # SignFrameResult
    failed = Signal(str)

    def __init__(self, engine: SignEngine, frame: np.ndarray, lang: str):
        super().__init__()
        self.engine = engine
        self.frame = frame
        self.lang = lang

    def run(self) -> None:
        try:
            result = self.engine.process_frame(self.frame, self.lang)
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class FunctionWorker(QObject):
    """Runs an arbitrary callable inside a QThread and emits its return
    value. Use for short CPU-bound blocking calls (STT, TTS synth) that
    must not freeze the GUI."""

    finished = Signal(object)   # callable return value
    failed = Signal(str)        # exception message

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished.emit(self._fn())
        except Exception as e:
            self.failed.emit(str(e))


class ScanWorker(QObject):
    """Runs DeviceManager.scan() off the GUI thread (camera probing is
    slow, especially on Windows where opening unused indices blocks)."""

    finished = Signal(object)   # DeviceReport
    failed = Signal(str)

    def __init__(self, devices):
        super().__init__()
        self.devices = devices

    def run(self) -> None:
        try:
            self.finished.emit(self.devices.scan())
        except Exception as e:
            self.failed.emit(str(e))


def run_in_thread(worker: QObject, on_done, on_fail=None) -> QThread:
    """Standard QThread wiring: move worker to thread, start, cleanup.

    Live threads are tracked in _LIVE_THREADS so they are never destroyed
    by Python garbage collection while running (destroying a running
    QThread aborts the process). wait_for_workers() quits and joins them
    on application shutdown."""
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    if on_fail is not None:
        worker.failed.connect(on_fail)
    worker.finished.connect(on_done)
    _LIVE_THREADS.append(thread)
    thread.finished.connect(lambda: _LIVE_THREADS.remove(thread)
                            if thread in _LIVE_THREADS else None)
    thread.start()
    return thread


def wait_for_workers(timeout: float = 5.0) -> None:
    """Quit and join every live worker thread (call on app shutdown)."""
    for thread in list(_LIVE_THREADS):
        try:
            thread.quit()
            thread.wait(int(timeout * 1000))
        except Exception:
            pass
    _LIVE_THREADS.clear()
