"""VisionEngine facade: one call -> detections + OCR + description + VQA."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ...config import models_dir
from ...logging_setup import get_logger
from ..base import BaseEngine, EngineRegistry
from .detector import Detection, ObjectDetector
from .ocr import OcrEngine, OcrResult
from .scene import SceneDescriptor
from .spatial import SpatialAnalyzer, SpatialRelation

log = get_logger("engines.vision")


@dataclass
class VisionResult:
    detections: list[Detection] = field(default_factory=list)
    ocr: OcrResult | None = None
    description: str = ""
    spatial: list[SpatialRelation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    answer: str = ""
    answer_confidence: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


class VisionEngine(BaseEngine):
    name = "vision"

    def __init__(self, detector_path: str | Path | None = None,
                 ocr_languages: tuple[str, ...] = ("ar", "en"),
                 enable_ocr: bool = True):
        super().__init__()
        base = models_dir() / "vision"
        self.detector = ObjectDetector(detector_path or base / "yolov8n.onnx")
        self.ocr: OcrEngine | None = (
            OcrEngine(ocr_languages) if enable_ocr else None
        )
        self.scene = SceneDescriptor()
        self._registry = EngineRegistry()
        for e in (self.detector, self.scene):
            self._registry.register(e)
        if self.ocr:
            self._registry.register(self.ocr)

    def _do_load(self) -> None:
        self.detector.load()
        if self.ocr:
            try:
                self.ocr.load()
            except Exception as e:
                log.warning("OCR unavailable, continuing without it: %s", e)
                self.ocr = None

    def _do_unload(self) -> None:
        self._registry.shutdown()

    def analyze_frame(self, frame: np.ndarray, question: str | None = None,
                      lang: str = "ar", run_ocr: bool | None = None) -> VisionResult:
        if self.detector.state.value != "ready":
            self.detector.load()
        result = VisionResult()
        result.detections = self._timed(self.detector.detect, frame)
        h, w = frame.shape[:2]
        analyzer = SpatialAnalyzer(w, h)
        result.spatial = analyzer.analyze(result.detections)
        result.warnings = analyzer.obstacle_warnings(result.detections, lang)

        want_ocr = run_ocr if run_ocr is not None else (
            question is not None and any(k in question.lower() for k in
                                         ["اقرأ", "مكتوب", "read", "text", "نص"])
        )
        if want_ocr and self.ocr is not None:
            try:
                result.ocr = self._timed(self.ocr.read, frame)
            except Exception as e:
                log.warning("OCR failed: %s", e)

        result.description = self.scene.describe(
            result.detections, result.ocr, frame.shape, lang
        )
        if question:
            result.answer, result.answer_confidence = self.scene.answer_question(
                question, result.detections, result.ocr, frame.shape, lang
            )
        result.meta["latency_ms"] = self._last_latency
        return result

    def find_object(self, frame: np.ndarray, query: str) -> Detection | None:
        if self.detector.state.value != "ready":
            self.detector.load()
        return self.detector.find_object(frame, query)
