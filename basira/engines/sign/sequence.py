"""Dynamic sign sequence recognition.

Maintains a rolling buffer of normalized landmark frames and matches it
against recorded templates using Dynamic Time Warping (DTW). Templates come
from the dataset tools (datasets/sign) recorded with user consent — the
engine ships with NO preloaded vocabulary and reports `unknown` until
templates are enrolled, instead of inventing translations.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from ...logging_setup import get_logger
from .recognizer import normalize_landmarks

log = get_logger("engines.sign.sequence")

FEATURE_DIM = 42  # 21 landmarks x (x, y)
NUM_LANDMARKS = 21


@dataclass
class SignTemplate:
    label: str
    frames: np.ndarray            # (T, 42) normalized
    source: str = ""              # dataset/session provenance


@dataclass
class SequenceResult:
    label: Optional[str]
    confidence: float
    distance: float
    buffer_len: int


class SequenceBuffer:
    def __init__(self, max_len: int = 60, min_frames: int = 8):
        self.max_len = max_len
        self.min_frames = min_frames
        self.frames: list[np.ndarray] = []

    def push(self, lm: np.ndarray) -> None:
        self.frames.append(normalize_landmarks(lm))
        if len(self.frames) > self.max_len:
            self.frames.pop(0)

    def clear(self) -> None:
        self.frames.clear()

    def window(self) -> np.ndarray | None:
        if len(self.frames) < self.min_frames:
            return None
        return np.stack(self.frames)

    def __len__(self) -> int:
        return len(self.frames)


def dtw_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Average-path DTW distance between two (T, D) sequences."""
    T1, T2 = len(a), len(b)
    if T1 == 0 or T2 == 0:
        return float("inf")
    cost = np.full((T1 + 1, T2 + 1), np.inf, dtype=np.float64)
    cost[0, 0] = 0.0
    for i in range(1, T1 + 1):
        ai = a[i - 1]
        for j in range(1, T2 + 1):
            d = np.linalg.norm(ai - b[j - 1])
            cost[i, j] = d + min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])
    path_len = T1 + T2
    return float(cost[T1, T2] / path_len)


class SequenceRecognizer:
    def __init__(self, threshold: float = 0.09, cooldown_frames: int = 15):
        self.templates: list[SignTemplate] = []
        self.threshold = threshold
        self.cooldown_frames = cooldown_frames
        self._cooldown_left = 0
        self._last_label: Optional[str] = None

    # -- template management ---------------------------------------------------
    def add_template(self, label: str, frames: np.ndarray, source: str = "") -> None:
        if frames.ndim != 2 or frames.shape[1] != FEATURE_DIM:
            raise ValueError(f"expected (T, {FEATURE_DIM}) frames, got {frames.shape}")
        if len(frames) < 4:
            raise ValueError("template too short (min 4 frames)")
        normalized = np.stack([
            normalize_landmarks(f.reshape(NUM_LANDMARKS, -1)) for f in frames
        ]).astype(np.float32)
        self.templates.append(SignTemplate(label, normalized, source))

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "threshold": self.threshold,
            "templates": [
                {"label": t.label, "source": t.source,
                 "frames": t.frames.tolist()}
                for t in self.templates
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "SequenceRecognizer":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        rec = cls(threshold=data.get("threshold", 0.09))
        for t in data.get("templates", []):
            rec.add_template(t["label"], np.array(t["frames"], dtype=np.float32),
                             t.get("source", ""))
        return rec

    # -- recognition -----------------------------------------------------------
    def recognize(self, buffer: SequenceBuffer) -> SequenceResult:
        if self._cooldown_left > 0:
            self._cooldown_left -= 1
        window = buffer.window()
        if window is None or not self.templates:
            return SequenceResult(None, 0.0, float("inf"), len(buffer))
        best_label, best_dist = None, float("inf")
        for t in self.templates:
            d = dtw_distance(window, t.frames)
            if d < best_dist:
                best_label, best_dist = t.label, d
        if best_label is None or best_dist > self.threshold:
            return SequenceResult(None, 0.0, best_dist, len(buffer))
        if best_label == self._last_label and self._cooldown_left > 0:
            return SequenceResult(None, 0.0, best_dist, len(buffer))
        self._last_label = best_label
        self._cooldown_left = self.cooldown_frames
        conf = max(0.0, min(1.0, 1.0 - best_dist / self.threshold * 0.5))
        return SequenceResult(best_label, conf, best_dist, len(buffer))
