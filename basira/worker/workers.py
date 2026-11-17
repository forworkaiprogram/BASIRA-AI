"""QThread workers so AI inference never blocks the UI thread."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from ..engines.vision.engine import VisionEngine, VisionResult
from ..engines.sign.engine import SignEngine, SignFrameResult


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


def run_in_thread(worker: QObject, on_done, on_fail=None) -> QThread:
    """Standard QThread wiring: move worker to thread, start, cleanup."""
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    if on_fail is not None:
        worker.failed.connect(on_fail)
    worker.finished.connect(on_done)
    thread.start()
    return thread
