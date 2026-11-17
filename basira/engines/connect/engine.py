"""BASIRA CONNECT: bidirectional deaf-hearing communication engine.

Scenario A (deaf -> hearing): sign camera -> text -> TTS.
Scenario B (hearing -> deaf): microphone -> STT -> on-screen text.
Scenario C: mixed conversation with a shared context transcript.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ...logging_setup import get_logger
from ...engines.audio.engine import AudioEngine
from ...engines.language.tts import TextToSpeech
from ...engines.sign.engine import SignEngine, SignFrameResult

log = get_logger("engines.connect")


@dataclass
class ConversationTurn:
    speaker: str          # "sign_user" | "voice_user" | "system"
    modality: str         # sign | speech | text
    text: str
    confidence: float = 0.0
    timestamp: float = 0.0


@dataclass
class ConnectResult:
    turn: ConversationTurn | None = None
    spoken: bool = False
    display_text: str = ""
    meta: dict = field(default_factory=dict)


class ConnectEngine:
    """Orchestrates the two translation directions plus shared transcript."""

    def __init__(self, sign_engine: SignEngine, audio_engine: AudioEngine,
                 tts: TextToSpeech):
        self.sign = sign_engine
        self.audio = audio_engine
        self.tts = tts
        self.transcript: list[ConversationTurn] = []

    # -- scenario A: sign -> text -> speech -------------------------------------
    def process_sign_frame(self, frame_bgr: np.ndarray,
                           speak: bool = True,
                           speaker_output=None) -> ConnectResult:
        sign_res: SignFrameResult = self.sign.process_frame(frame_bgr)
        if not sign_res.text:
            return ConnectResult()
        turn = ConversationTurn("sign_user", "sign", sign_res.text,
                                sign_res.confidence)
        self.transcript.append(turn)
        spoken = False
        if speak and sign_res.confidence >= 0.5:
            try:
                pcm = self.tts.synthesize(sign_res.text)
                if speaker_output is not None and pcm.size:
                    import wave, io
                    buf = io.BytesIO()
                    with wave.open(buf, "wb") as w:
                        w.setnchannels(1); w.setsampwidth(2)
                        w.setframerate(self.tts.sample_rate)
                        w.writeframes(pcm.tobytes())
                    speaker_output.play_wav(buf.getvalue(), block=False)
                    spoken = True
            except Exception as e:
                log.warning("TTS failed in connect: %s", e)
        return ConnectResult(turn=turn, spoken=spoken,
                             display_text=sign_res.text)

    # -- scenario B: speech -> text ----------------------------------------------
    def process_speech_wav(self, wav_path, language: str = "ar") -> ConnectResult:
        t = self.audio.transcribe_wav(wav_path, language)
        if t.is_empty:
            return ConnectResult()
        turn = ConversationTurn("voice_user", "speech", t.text,
                                t.language_probability)
        self.transcript.append(turn)
        return ConnectResult(turn=turn, display_text=t.text)

    # -- scenario C: shared context ------------------------------------------------
    def transcript_text(self, limit: int = 30) -> str:
        lines = []
        for t in self.transcript[-limit:]:
            who = "أصم (إشارة)" if t.speaker == "sign_user" else \
                "أسمع (كلام)" if t.speaker == "voice_user" else t.speaker
            lines.append(f"{who}: {t.text}")
        return "\n".join(lines)

    def clear(self) -> None:
        self.transcript.clear()
