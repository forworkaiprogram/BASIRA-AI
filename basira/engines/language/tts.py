"""Text-to-speech with Piper (local, offline, Arabic-capable).

Synthesizes int16 PCM at the voice's sample rate. Playback is handled by
hardware.audio_output.AudioOutputManager so synthesis and output stay
decoupled.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ...logging_setup import get_logger, ModelNotAvailableError
from ..base import BaseEngine, EngineState

log = get_logger("engines.language.tts")


class TextToSpeech(BaseEngine):
    name = "language.tts"

    def __init__(self, voice_path: str | Path | None = None,
                 length_scale: float = 1.0):
        super().__init__()
        base = Path(__file__).resolve().parents[2].parent / "models" / "language"
        self.voice_path = Path(voice_path) if voice_path else base / "ar_JO-kareem-medium.onnx"
        self.length_scale = length_scale
        self._voice = None
        self.sample_rate = 22050

    def _do_load(self) -> None:
        json_path = Path(str(self.voice_path) + ".json")
        if not self.voice_path.exists() or not json_path.exists():
            self._state = EngineState.UNAVAILABLE
            raise ModelNotAvailableError(
                f"Piper voice not found: {self.voice_path}. "
                "Run scripts/download_models.py"
            )
        try:
            from piper import PiperVoice, SynthesisConfig
        except Exception as e:
            self._state = EngineState.UNAVAILABLE
            raise ModelNotAvailableError(f"piper unavailable: {e}") from e
        try:
            self._voice = PiperVoice.load(str(self.voice_path))
            self.sample_rate = self._voice.config.sample_rate
        except Exception as e:
            self._state = EngineState.UNAVAILABLE
            raise ModelNotAvailableError(f"failed to load voice: {e}") from e

    def _do_unload(self) -> None:
        self._voice = None

    @property
    def is_available_on_disk(self) -> bool:
        return self.voice_path.exists() and \
            Path(str(self.voice_path) + ".json").exists()

    def synthesize(self, text: str) -> np.ndarray:
        """Synthesize text to int16 PCM numpy array."""
        if self._voice is None:
            self.load()
        if not text.strip():
            return np.zeros(0, dtype=np.int16)
        from piper import SynthesisConfig

        cfg = SynthesisConfig(length_scale=self.length_scale)
        chunks = []
        for chunk in self._voice.synthesize(text.strip(), syn_config=cfg):
            data = chunk.audio_int16_bytes
            chunks.append(np.frombuffer(data, dtype=np.int16).copy())
        if not chunks:
            return np.zeros(0, dtype=np.int16)
        return np.concatenate(chunks)

    def synthesize_to_wav(self, text: str) -> bytes:
        import io
        import wave

        pcm = self.synthesize(text)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            w.writeframes(pcm.tobytes())
        return buf.getvalue()
