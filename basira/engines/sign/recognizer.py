"""Static gesture recognition from hand landmarks (geometry-based).

These recognizers use explicit hand geometry (which fingers are extended,
thumb direction, fingertip distances). They are real, deterministic and
unit-testable with synthetic landmarks. They cover a small starter
vocabulary useful for BASIRA CONNECT; full Arabic sign-language vocabulary
requires the dataset/training pipeline (training/sign) and is NOT claimed
here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .hand_tracker import (
    FINGER_PIPS, FINGER_TIPS, INDEX_TIP, MIDDLE_TIP, PINKY_TIP, RING_TIP,
    THUMB_TIP, WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP,
)

GESTURE_LABELS_AR = {
    "open_palm": "كف مفتوح",
    "fist": "قبضة",
    "pointing": "إشارة بالإصبع",
    "victory": "علامة النصر",
    "thumbs_up": "إبهام لأعلى",
    "thumbs_down": "إبهام لأسفل",
    "call_me": "إشارة الاتصال",
    "unknown": "غير معروفة",
}

GESTURE_LABELS_EN = {
    "open_palm": "open palm",
    "fist": "fist",
    "pointing": "pointing",
    "victory": "victory",
    "thumbs_up": "thumbs up",
    "thumbs_down": "thumbs down",
    "call_me": "call me",
    "unknown": "unknown",
}


@dataclass
class GesturePrediction:
    label: str
    confidence: float


def fingers_extended(lm: np.ndarray) -> list[bool]:
    """For each finger [thumb, index, middle, ring, pinky], is it extended?

    Four fingers: tip is farther from the wrist than the PIP joint.
    Thumb: tip distance from pinky MCP exceeds index MCP distance
    (works across left/right hands and rotation better than a fixed axis).
    """
    wrist = lm[WRIST, :2]
    out = []
    # thumb
    d_tip = np.linalg.norm(lm[THUMB_TIP, :2] - lm[PINKY_MCP, :2])
    d_mcp = np.linalg.norm(lm[INDEX_MCP, :2] - lm[PINKY_MCP, :2])
    out.append(bool(d_tip > d_mcp * 1.15))
    # four fingers
    for tip, pip in zip(FINGER_TIPS[1:], FINGER_PIPS[1:]):
        d_tip = np.linalg.norm(lm[tip, :2] - wrist)
        d_pip = np.linalg.norm(lm[pip, :2] - wrist)
        out.append(bool(d_tip > d_pip * 1.1))
    return out


def classify_static_gesture(lm: np.ndarray) -> GesturePrediction:
    """Classify one hand pose into the starter vocabulary."""
    ext = fingers_extended(lm)
    n_ext = sum(ext)
    thumb, index, middle, ring, pinky = ext

    if not thumb and not index and not middle and not ring and not pinky:
        return GesturePrediction("fist", 0.9)
    if index and middle and ring and pinky and not thumb:
        return GesturePrediction("open_palm", 0.85 if not thumb else 0.75)
    if thumb and index and middle and ring and pinky:
        return GesturePrediction("open_palm", 0.9)
    if index and not middle and not ring and not pinky:
        return GesturePrediction("pointing", 0.85)
    if index and middle and not ring and not pinky:
        return GesturePrediction("victory", 0.85)
    if thumb and not index and not middle and not ring and not pinky:
        # thumb up vs down from thumb direction relative to wrist
        dy = lm[WRIST, 1] - lm[THUMB_TIP, 1]  # image y grows downward
        if dy > 0.08:
            return GesturePrediction("thumbs_up", 0.85)
        if dy < -0.08:
            return GesturePrediction("thumbs_down", 0.85)
        return GesturePrediction("thumbs_up", 0.5)
    if thumb and pinky and not index and not middle and not ring:
        return GesturePrediction("call_me", 0.85)
    return GesturePrediction("unknown", 0.4)


def normalize_landmarks(lm: np.ndarray) -> np.ndarray:
    """Translation/scale-invariant normalization for recognition & storage."""
    out = lm[:, :2].copy()
    out -= out[WRIST]
    span = np.linalg.norm(out[INDEX_MCP] - out[PINKY_MCP])
    if span < 1e-6:
        span = np.linalg.norm(out) + 1e-6
    return (out / span).reshape(-1)
