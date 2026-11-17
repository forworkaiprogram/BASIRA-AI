"""SignEngine: hand tracking + static gestures + dynamic sequences.

Output is always accompanied by a confidence value. Unknown gestures and
unmatched sequences are reported as such — the engine never fabricates a
translation for a sign it does not know.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from ...config import models_dir
from ...logging_setup import get_logger, ModelNotAvailableError
from ..base import BaseEngine, EngineState
from .hand_tracker import HandFrame, HandTracker
from .recognizer import (
    GESTURE_LABELS_AR,
    GESTURE_LABELS_EN,
    GesturePrediction,
    classify_static_gesture,
)
from .sequence import SequenceBuffer, SequenceRecognizer, SequenceResult

log = get_logger("engines.sign")


@dataclass
class SignFrameResult:
    hands: list[HandFrame] = field(default_factory=list)
    gestures: list[GesturePrediction] = field(default_factory=list)
    sequence: SequenceResult | None = None
    text: str = ""
    confidence: float = 0.0
    lang: str = "ar"


class SignEngine(BaseEngine):
    name = "sign"

    def __init__(self, tracker_model: str | Path | None = None,
                 templates_path: str | Path | None = None,
                 gesture_text: bool = True):
        super().__init__()
        base = models_dir() / "sign"
        self.tracker = HandTracker(tracker_model or base / "hand_landmarker.task")
        self.sequence_rec = SequenceRecognizer()
        self.templates_path = Path(templates_path) if templates_path else \
            base / "sign_templates.json"
        self.gesture_text = gesture_text
        self.buffer = SequenceBuffer()
        self._templates_loaded = False
        self._vocabulary: dict[str, dict] = {}   # label -> meaning (dataset-defined)

    def _do_load(self) -> None:
        self.tracker.load()
        self._load_templates()
        self._load_vocabulary()

    def _do_unload(self) -> None:
        self.tracker.unload()

    def _load_templates(self) -> None:
        if self._templates_loaded:
            return
        if self.templates_path.exists():
            try:
                self.sequence_rec = SequenceRecognizer.load(self.templates_path)
                log.info("loaded %d sign templates",
                         len(self.sequence_rec.templates))
            except Exception as e:
                log.warning("failed to load templates: %s", e)
        self._templates_loaded = True

    def _load_vocabulary(self) -> None:
        vocab_path = self.templates_path.parent / "vocabulary.json"
        if vocab_path.exists():
            import json
            try:
                self._vocabulary = json.loads(
                    vocab_path.read_text(encoding="utf-8"))
            except Exception:
                self._vocabulary = {}

    @property
    def vocabulary_size(self) -> int:
        return len(self._vocabulary)

    # -- per-frame processing ---------------------------------------------------
    def process_frame(self, frame_bgr: np.ndarray, lang: str = "ar") -> SignFrameResult:
        if self.tracker.state.value != "ready":
            self.tracker.load()
        res = SignFrameResult(lang=lang)
        try:
            res.hands = self._timed(self.tracker.track, frame_bgr)
        except ModelNotAvailableError:
            raise
        except Exception as e:
            log.warning("hand tracking failed: %s", e)
            return res

        if not res.hands:
            return res

        primary = res.hands[0]
        res.gestures = [classify_static_gesture(primary.landmarks)]
        self.buffer.push(primary.landmarks)
        res.sequence = self._timed(self.sequence_rec.recognize, self.buffer)

        res.text, res.confidence = self._compose_text(res, lang)
        return res

    def _compose_text(self, res: SignFrameResult, lang: str) -> tuple[str, float]:
        if res.sequence and res.sequence.label:
            label = res.sequence.label
            meaning = self._vocabulary.get(label, {})
            text = (meaning.get("meaning_ar") if lang == "ar" else None) \
                or (meaning.get("meaning_en") if lang == "en" else None) \
                or meaning.get("meaning_en") or meaning.get("meaning_ar") or label
            return text, res.sequence.confidence
        if self.gesture_text and res.gestures:
            g = res.gestures[0]
            if g.label != "unknown":
                label = GESTURE_LABELS_AR.get(g.label, g.label) if lang == "ar" \
                    else GESTURE_LABELS_EN.get(g.label, g.label)
                return label, g.confidence
        return "", 0.0

    # -- user correction & dataset expansion -------------------------------------
    def add_correction(self, wrong_label: str, corrected_text: str) -> None:
        """Store a user correction for later retraining (no silent rewrite)."""
        import json
        from ...config import app_home
        corr = app_home() / "corrections.jsonl"
        with corr.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"wrong": wrong_label, "corrected": corrected_text},
                                ensure_ascii=False) + "\n")

    def enroll_sequence(self, label: str, frames: np.ndarray, consent_id: str,
                        dataset_path: str | Path | None = None) -> int:
        """Enroll a new dynamic sign: dataset record + live template."""
        from .dataset_tools import SignDatasetWriter
        path = Path(dataset_path) if dataset_path else \
            self.templates_path.parent / "recordings.jsonl"
        writer = SignDatasetWriter(path)
        n = writer.append(label, frames, consent_id)
        self.sequence_rec.add_template(label, frames, source=str(path))
        self.sequence_rec.save(self.templates_path)
        return n
