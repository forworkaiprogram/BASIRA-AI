"""Hand tracking with MediaPipe Tasks (HandLandmarker).

Lazy-loads the .task model. If MediaPipe or the model file is missing the
engine reports `unavailable` instead of crashing, and callers must degrade
gracefully (e.g. show a message in the UI).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ...logging_setup import get_logger, ModelNotAvailableError
from ..base import BaseEngine, EngineState

log = get_logger("engines.sign.tracker")

# MediaPipe hand landmark indices
WRIST = 0
THUMB_TIP = 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_MCP, RING_PIP, RING_TIP = 13, 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20
FINGER_TIPS = [4, 8, 12, 16, 20]
FINGER_PIPS = [2, 6, 10, 14, 18]
FINGER_MCPS = [1, 5, 9, 13, 17]

NUM_LANDMARKS = 21


@dataclass
class HandFrame:
    """One hand's landmarks, normalized to image coordinates (0..1)."""
    landmarks: np.ndarray          # (21, 3) x, y, z in image-normalized coords
    handedness: str                # "Left" | "Right"
    score: float

    @property
    def wrist(self) -> np.ndarray:
        return self.landmarks[WRIST]

    def to_flat(self) -> np.ndarray:
        return self.landmarks.reshape(-1)


class HandTracker(BaseEngine):
    name = "sign.tracker"

    def __init__(self, model_path: str | Path, num_hands: int = 2):
        super().__init__()
        self.model_path = Path(model_path)
        self.num_hands = num_hands
        self._landmarker = None

    def _do_load(self) -> None:
        if not self.model_path.exists():
            self._state = EngineState.UNAVAILABLE
            raise ModelNotAvailableError(
                f"Hand landmarker model not found: {self.model_path}. "
                "Run scripts/download_models.py"
            )
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import vision
        except Exception as e:
            self._state = EngineState.UNAVAILABLE
            raise ModelNotAvailableError(f"MediaPipe unavailable: {e}") from e

        base = mp.tasks.BaseOptions
        opts = vision.HandLandmarkerOptions(
            base_options=base(model_asset_path=str(self.model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=self.num_hands,
            min_hand_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(opts)
        self._mp_image_cls = mp.Image
        self._fmt = mp.ImageFormat.SRGB
        self._ts_ms = 0

    def _do_unload(self) -> None:
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:
                pass
        self._landmarker = None

    def track(self, frame_bgr: np.ndarray, advance_time: bool = True) -> list[HandFrame]:
        """Detect hands in one BGR frame. Returns [] when no hand is visible."""
        if self._landmarker is None:
            self.load()
        import cv2

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = self._mp_image_cls(image_format=self._fmt, data=rgb)
        ts = self._ts_ms
        if advance_time:
            self._ts_ms += 33
        result = self._timed(self._landmarker.detect_for_video, mp_image, ts)
        hands: list[HandFrame] = []
        if result.hand_landmarks:
            for i, lm in enumerate(result.hand_landmarks):
                arr = np.array([[p.x, p.y, p.z] for p in lm], dtype=np.float32)
                label = "Right"
                score = 1.0
                if result.handedness and i < len(result.handedness) \
                        and result.handedness[i]:
                    label = result.handedness[i][0].category_name
                    score = result.handedness[i][0].score
                hands.append(HandFrame(landmarks=arr, handedness=label, score=float(score)))
        return hands
