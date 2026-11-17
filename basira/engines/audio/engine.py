"""AudioEngine: live STT + sound event detection + alerts."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from ...config import models_dir
from ...logging_setup import get_logger
from ..base import BaseEngine
from .alerts import Alert, AlertManager
from .sound_events import SoundEvent, SoundEventDetector
from .stt import SpeechRecognizer, Transcript

log = get_logger("engines.audio")


@dataclass
class AudioResult:
    transcript: Transcript | None = None
    sound_event: SoundEvent | None = None
    alert: Alert | None = None
    meta: dict = field(default_factory=dict)


class AudioEngine(BaseEngine):
    name = "audio"

    def __init__(self, stt_model: str = "base", cooldown_seconds: float = 8.0):
        super().__init__()
        self.stt = SpeechRecognizer(stt_model)
        self.sound_detector = SoundEventDetector()
        self.alerts = AlertManager(
            default_cooldown=cooldown_seconds,
            cooldowns={"sound:fire_alarm": 3.0, "sound:siren": 5.0},
        )
        self._registry = [self.stt, self.sound_detector]

    def _do_load(self) -> None:
        self.sound_detector.load()  # cheap; may be degraded mode
        # STT is loaded lazily on first transcribe (heavy).

    def _do_unload(self) -> None:
        for e in self._registry:
            try:
                e.unload()
            except Exception:
                pass

    # -- speech ------------------------------------------------------------------
    def transcribe_wav(self, wav_path: str | Path, language: str = "ar") -> Transcript:
        return self.stt.transcribe_wav(wav_path, language)

    def transcribe_pcm(self, pcm: np.ndarray, sample_rate: int = 16000,
                       language: str = "ar") -> Transcript:
        return self.stt.transcribe_pcm(pcm, sample_rate, language)

    # -- sounds ---------------------------------------------------------------
    def process_audio_chunk(self, pcm_int16: np.ndarray,
                            sample_rate: int = 16000,
                            timestamp: float = 0.0) -> AudioResult:
        if self.sound_detector.state.value not in ("ready", "unavailable"):
            self.sound_detector.load()
        res = AudioResult()
        event = self.sound_detector.detect(pcm_int16, sample_rate, timestamp)
        if event is None:
            return res
        res.sound_event = event
        ar_name = event.label_ar
        if event.heuristic:
            title = f"تنبيه: {ar_name} (تقديري)"
        else:
            title = f"تنبيه: {ar_name}"
        alert = Alert(
            kind=f"sound:{event.label}",
            title=title,
            body=f"الثقة: {event.confidence:.0%}",
            priority=2 if event.label in ("fire_alarm", "siren", "glass_break") else 1,
        )
        if self.alerts.raise_alert(alert):
            res.alert = alert
        return res
