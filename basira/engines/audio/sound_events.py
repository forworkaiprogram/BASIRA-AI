"""Environmental sound detection.

Two layers:
1. Energy gate (RMS) — cheap, runs on every frame.
2. Event classifier — a small CNN trained with training/audio (ESC-50),
   loaded from ONNX when the model file exists. Until that model is
   installed, only the energy gate + spectral heuristic for alarm-like
   tones runs, and results are clearly labeled with low confidence and an
   "heuristic" flag. The engine never presents heuristic output as a
   trained classification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from ...config import models_dir
from ...logging_setup import get_logger
from ..base import BaseEngine, EngineState

log = get_logger("engines.audio.sounds")

ALARM_AR = "صوت إنذار محتمل"
ALARM_EN = "possible alarm sound"

try:
    import scipy.signal as sps
    _SCIPY = True
except Exception:  # pragma: no cover
    _SCIPY = False


@dataclass
class SoundEvent:
    label: str
    label_ar: str
    confidence: float
    timestamp: float
    level: float
    heuristic: bool = False


def compute_mel_spectrogram(pcm: np.ndarray, sample_rate: int = 16000,
                            n_mels: int = 64) -> np.ndarray:
    """Log-mel spectrogram (used both by the classifier and its training)."""
    if not _SCIPY:
        raise RuntimeError("scipy is required for audio features")
    frame_len = int(0.025 * sample_rate)
    frame_step = int(0.010 * sample_rate)
    f, t, Z = sps.stft(pcm.astype(np.float32), fs=sample_rate,
                       nperseg=frame_len, noverlap=frame_len - frame_step)
    power = (np.abs(Z) ** 2) + 1e-10
    # simple mel filterbank over the stft frequency bins (nperseg//2 + 1)
    def hz_to_mel(hz):
        return 2595 * np.log10(1 + hz / 700)

    def mel_to_hz(m):
        return 700 * (10 ** (m / 2595) - 1)

    n_freq = power.shape[0]
    mel_pts = np.linspace(hz_to_mel(50), hz_to_mel(sample_rate / 2), n_mels + 2)
    hz_pts = mel_to_hz(mel_pts)
    bins = np.floor(n_freq * hz_pts / (sample_rate / 2)).astype(int)
    bins = np.clip(bins, 0, n_freq - 1)
    fbank = np.zeros((n_mels, n_freq), dtype=np.float32)
    for i in range(n_mels):
        l, c, r = bins[i], bins[i + 1], bins[i + 2]
        if c == l:
            c = l + 1
        if r == c:
            r = c + 1
        fbank[i, l:c] = (np.arange(l, c) - l) / (c - l)
        fbank[i, c:r] = (r - np.arange(c, r)) / (r - c)
    mel = fbank @ power
    return np.log(mel + 1e-10)


class SoundEventDetector(BaseEngine):
    name = "audio.sound_events"

    TARGET_SOUNDS = {
        "doorbell": "جرس الباب",
        "phone_ring": "رنين الهاتف",
        "fire_alarm": "إنذار حريق",
        "car_horn": "بوق سيارة",
        "knock": "طرق الباب",
        "baby_cry": "بكاء طفل",
        "glass_break": "كسر زجاج",
        "siren": "صافرة إنذار",
    }

    def __init__(self, model_path: str | Path | None = None,
                 energy_threshold: float = 0.02):
        super().__init__()
        self.model_path = Path(model_path) if model_path else \
            models_dir() / "audio" / "sound_classifier.onnx"
        self.energy_threshold = energy_threshold
        self._session = None
        self._labels: list[str] = []

    def _do_load(self) -> None:
        if not self.model_path.exists():
            self._state = EngineState.UNAVAILABLE
            self._detail = ("trained classifier not installed; running "
                            "energy gate + alarm heuristic only")
            log.info(self._detail)
            return  # degraded mode, not an error
        import onnxruntime as ort

        self._session = ort.InferenceSession(str(self.model_path),
                                             providers=["CPUExecutionProvider"])
        meta = self._session.get_modelmeta().custom_metadata_map
        self._labels = json_load_labels(meta.get("labels", "[]"))
        self._detail = f"trained classifier with {len(self._labels)} classes"

    def _do_unload(self) -> None:
        self._session = None

    @property
    def using_trained_model(self) -> bool:
        return self._session is not None

    def detect(self, pcm_int16: np.ndarray, sample_rate: int = 16000,
               timestamp: float = 0.0) -> Optional[SoundEvent]:
        """Analyze one audio chunk. Returns None below the energy gate."""
        x = pcm_int16.astype(np.float32) / 32768.0
        level = float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0
        if level < self.energy_threshold:
            return None
        if self._session is not None and self._labels:
            return self._classify(x, sample_rate, level, timestamp)
        return self._heuristic_alarm(x, sample_rate, level, timestamp)

    def _classify(self, x, sample_rate, level, timestamp) -> Optional[SoundEvent]:
        mel = compute_mel_spectrogram(x, sample_rate)
        # classifier input: fixed-size patch (pad/crop time axis)
        target_t = 96
        if mel.shape[1] < target_t:
            mel = np.pad(mel, ((0, 0), (0, target_t - mel.shape[1])))
        mel = mel[:, :target_t][None, None].astype(np.float32)
        out = self._timed(self._session.run, None,
                          {self._session.get_inputs()[0].name: mel})[0][0]
        probs = softmax(out)
        idx = int(np.argmax(probs))
        label = self._labels[idx] if idx < len(self._labels) else str(idx)
        ar = self.TARGET_SOUNDS.get(label, label)
        return SoundEvent(label, ar, float(probs[idx]), timestamp, level)

    def _heuristic_alarm(self, x, sample_rate, level, timestamp) -> Optional[SoundEvent]:
        """Sustained high-frequency energy heuristic for alarm-like tones."""
        if not _SCIPY or x.size < sample_rate // 4:
            return None
        freqs, psd = sps.welch(x, fs=sample_rate, nperseg=min(1024, x.size))
        band = (freqs >= 1500) & (freqs <= 4500)
        if not band.any():
            return None
        total = float(np.sum(psd)) + 1e-12
        hi_ratio = float(np.sum(psd[band])) / total
        peak = freqs[band][np.argmax(psd[band])]
        if hi_ratio > 0.35 and level > self.energy_threshold * 2:
            return SoundEvent("possible_alarm", ALARM_AR if False else "صوت إنذار محتمل",
                              0.35, timestamp, level, heuristic=True)
        return None


def softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()


def json_load_labels(raw: str) -> list[str]:
    import json
    try:
        return json.loads(raw)
    except Exception:
        return []
