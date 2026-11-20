"""Speech recognition with faster-whisper (local, offline, ar+en)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...logging_setup import get_logger, ModelNotAvailableError
from ..base import BaseEngine, EngineState

log = get_logger("engines.audio.stt")


@dataclass
class Transcript:
    text: str
    language: str = ""
    language_probability: float = 0.0
    duration_s: float = 0.0
    segments: list[dict] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class SpeechRecognizer(BaseEngine):
    name = "audio.stt"

    def __init__(self, model_size: str = "base", device: str = "cpu",
                 compute_type: str = "int8", download_root: str | Path | None = None):
        super().__init__()
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.download_root = str(download_root) if download_root else None
        self._model = None

    def _do_load(self) -> None:
        try:
            from faster_whisper import WhisperModel
        except Exception as e:
            self._state = EngineState.UNAVAILABLE
            raise ModelNotAvailableError(f"faster-whisper unavailable: {e}") from e
        try:
            self._model = WhisperModel(self.model_size, device=self.device,
                                       compute_type=self.compute_type,
                                       download_root=self.download_root)
        except Exception as e:
            self._state = EngineState.UNAVAILABLE
            raise ModelNotAvailableError(f"STT model unavailable: {e}") from e

    def _do_unload(self) -> None:
        self._model = None

    def transcribe_wav(self, wav_path: str | Path,
                       language: str | None = "ar") -> Transcript:
        """Transcribe a 16 kHz mono WAV file."""
        if self._model is None:
            self.load()
        kwargs = {"beam_size": 1, "vad_filter": False,
                  "condition_on_previous_text": False}
        if language:
            kwargs["language"] = language
        segments, info = self._timed(self._model.transcribe, str(wav_path), **kwargs)
        texts = []
        seg_list = []
        for s in segments:
            texts.append(s.text.strip())
            seg_list.append({"start": s.start, "end": s.end, "text": s.text.strip()})
        return Transcript(
            text=" ".join(t for t in texts if t),
            language=info.language,
            language_probability=float(info.language_probability),
            duration_s=float(info.duration),
            segments=seg_list,
        )

    def transcribe_pcm(self, pcm_int16, sample_rate: int = 16000,
                       language: str | None = "ar") -> Transcript:
        """Transcribe raw int16 PCM (numpy) in memory."""
        import numpy as np
        import tempfile, wave as wavemod

        pcm = np.asarray(pcm_int16, dtype=np.int16)
        if pcm.size == 0:
            return Transcript()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name
        try:
            with wavemod.open(tmp, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sample_rate)
                w.writeframes(pcm.tobytes())
            return self.transcribe_wav(tmp, language)
        finally:
            Path(tmp).unlink(missing_ok=True)
