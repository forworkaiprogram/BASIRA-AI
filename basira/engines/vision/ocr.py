"""OCR engine (Arabic + English) with pluggable backends.

Primary backend: EasyOCR (torch, CPU) with lazy loading. The backend is
isolated behind `read_text`, so a lighter backend (e.g. PaddleOCR ONNX or
tesseract) can be dropped in without touching callers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ...logging_setup import get_logger, ModelNotAvailableError
from ..base import BaseEngine, EngineState

log = get_logger("engines.vision.ocr")


@dataclass
class OcrResult:
    text: str
    lines: list[str] = field(default_factory=list)
    boxes: list[tuple[float, float, float, float]] = field(default_factory=list)
    confidences: list[float] = field(default_factory=list)
    language: str = "ar+en"

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class OcrEngine(BaseEngine):
    name = "vision.ocr"

    def __init__(self, languages: tuple[str, ...] = ("ar", "en"),
                 model_dir: str | Path | None = None, gpu: bool = False):
        super().__init__()
        self.languages = list(languages)
        self.model_dir = str(model_dir) if model_dir else None
        self.gpu = gpu
        self._reader = None

    def _do_load(self) -> None:
        try:
            import easyocr  # noqa: F401
        except Exception as e:
            self._state = EngineState.UNAVAILABLE
            raise ModelNotAvailableError(f"EasyOCR is not installed: {e}") from e
        try:
            self._reader = easyocr.Reader(
                self.languages, gpu=self.gpu, model_storage_directory=self.model_dir,
                verbose=False,
            )
        except Exception as e:
            self._state = EngineState.UNAVAILABLE
            raise ModelNotAvailableError(f"OCR models unavailable: {e}") from e

    def _do_unload(self) -> None:
        self._reader = None

    def read(self, frame: np.ndarray, detail: bool = True) -> OcrResult:
        if self._reader is None:
            self.load()
        results = self._timed(self._reader.readtext, frame, detail=detail)
        lines, boxes, confs = [], [], []
        for item in results:
            box, text, conf = item[0], item[1], float(item[2])
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            lines.append(str(text))
            boxes.append((float(min(xs)), float(min(ys)),
                          float(max(xs)), float(max(ys))))
            confs.append(conf)
        text = " ".join(lines).strip()
        return OcrResult(text=text, lines=lines, boxes=boxes, confidences=confs,
                         language="+".join(self.languages))
