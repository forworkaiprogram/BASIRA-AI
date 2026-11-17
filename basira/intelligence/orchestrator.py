"""BASIRACore: the unified intelligence layer tying all engines together."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from ..config import AppSettings
from ..db.database import Database
from ..engines.base import EngineRegistry
from ..engines.vision.engine import VisionEngine
from ..engines.sign.engine import SignEngine
from ..engines.audio.engine import AudioEngine
from ..engines.language.tts import TextToSpeech
from ..logging_setup import get_logger
from .context_manager import ContextEntry, ContextManager
from .fusion import MultimodalFusion
from .router import ModeRouter

log = get_logger("intelligence")


@dataclass
class CoreResponse:
    mode: str
    intent: str
    text: str                    # user-facing answer/description
    confidence: float = 0.0
    speak: bool = False
    data: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0


class BASIRACore:
    """Single entry point used by the desktop UI and the local backend."""

    def __init__(self, db: Database, settings: AppSettings,
                 vision: VisionEngine | None = None,
                 sign: SignEngine | None = None,
                 audio: AudioEngine | None = None,
                 tts: TextToSpeech | None = None):
        self.db = db
        self.settings = settings
        self.vision = vision or VisionEngine()
        self.sign = sign or SignEngine()
        self.audio = audio or AudioEngine(settings.stt_model,
                                          settings.sound_cooldown_seconds)
        self.tts = tts or TextToSpeech()
        self.context = ContextManager()
        self.fusion = MultimodalFusion()
        self.router = ModeRouter()
        self.registry = EngineRegistry()
        for e in (self.vision, self.sign, self.audio):
            self.registry.register(e)

    # -- lifecycle ---------------------------------------------------------------
    def load_lightweight(self) -> None:
        """Load cheap engines at startup; heavy ones load on first use."""
        try:
            self.audio.load()
        except Exception as e:
            log.warning("audio engine load failed: %s", e)

    def shutdown(self) -> None:
        self.registry.shutdown()

    # -- main request path ---------------------------------------------------------
    def handle_request(self, request: str, frame: np.ndarray | None = None,
                       lang: str | None = None) -> CoreResponse:
        lang = lang or self.settings.language
        t0 = time.perf_counter()
        decision = self.router.route(request, has_camera_frame=frame is not None)
        self.context.current_mode = decision.mode
        self.context.add(ContextEntry("user", "question", request, modality="text"))

        response = CoreResponse(decision.mode, decision.intent, "")
        try:
            if decision.mode == "vision" and frame is not None:
                response = self._handle_vision(request, frame, decision, lang)
            elif decision.mode == "hear":
                response = self._handle_hear(request, decision, lang)
            elif decision.mode == "sign":
                response = self._handle_sign(decision, lang)
            else:
                response.text = (
                    "هذه المهمة تحتاج كاميرا تعمل. شغّل الكاميرا من لوحة التحكم."
                    if lang == "ar" else
                    "This task needs an active camera. Enable it from the dashboard.")
        except Exception as e:
            log.exception("request failed")
            response.text = (
                f"حدث خطأ أثناء المعالجة: {e}" if lang == "ar"
                else f"Processing failed: {e}")

        response.latency_ms = (time.perf_counter() - t0) * 1000
        if response.text:
            self.context.add(ContextEntry("system", "answer", response.text,
                                          response.confidence, decision.mode))
            if self.settings.save_history:
                self.db.add_translation(
                    "text", "text", request, response.text, lang,
                    response.confidence)
        return response

    def _handle_vision(self, request: str, frame: np.ndarray,
                       decision, lang: str) -> CoreResponse:
        result = self.vision.analyze_frame(
            frame, question=request if decision.intent in ("vqa", "describe",
                                                           "read", "find",
                                                           "count", "obstacle") else None,
            lang=lang)
        text = result.answer or result.description
        fused = self.fusion.fuse_scene(
            result.detections, result.ocr.text if result.ocr else "", lang=lang)
        resp = CoreResponse("vision", decision.intent, text,
                            result.answer_confidence,
                            speak=self.settings.prefer_voice_output)
        resp.data = {
            "detections": [
                {"name": d.class_name, "confidence": round(d.confidence, 3),
                 "box": [round(v, 1) for v in d.xyxy]}
                for d in result.detections
            ],
            "ocr": result.ocr.text if result.ocr else "",
            "warnings": result.warnings,
            "fused_summary": fused.summary,
        }
        self.context.add(ContextEntry("engine", "observation", fused.summary,
                                      modality="vision",
                                      data={"detections": resp.data["detections"],
                                            "ocr": resp.data["ocr"]}))
        return resp

    def _handle_hear(self, request: str, decision, lang: str) -> CoreResponse:
        msg = (
            "ابدأ الاستماع من صفحة BASIRA HEAR لتحويل الكلام إلى نص أو لرصد الأصوات."
            if lang == "ar" else
            "Start listening from the BASIRA HEAR page for speech-to-text or "
            "sound detection.")
        return CoreResponse("hear", decision.intent, msg, 0.5)

    def _handle_sign(self, decision, lang: str) -> CoreResponse:
        n = self.sign.vocabulary_size
        if n == 0:
            msg = ("لا توجد مفردات إشارة مثبتة بعد. سجّل إشارات جديدة من صفحة "
                   "BASIRA SIGN قبل الترجمة."
                   if lang == "ar" else
                   "No sign vocabulary enrolled yet. Record signs from the "
                   "BASIRA SIGN page first.")
        else:
            msg = (f"مفردات الإشارة المتوفرة: {n}. افتح صفحة BASIRA SIGN."
                   if lang == "ar" else
                   f"Enrolled sign vocabulary: {n}. Open the BASIRA SIGN page.")
        return CoreResponse("sign", decision.intent, msg, 0.5)

    # -- convenience -------------------------------------------------------------
    def describe_scene(self, frame: np.ndarray, lang: str = "ar") -> CoreResponse:
        return self.handle_request("صف المشهد" if lang == "ar" else "describe",
                                   frame, lang)

    def speak_text(self, text: str, speaker=None) -> bool:
        """Synthesize + play. Returns False when TTS is unavailable."""
        if not self.settings.tts_enabled:
            return False
        try:
            pcm = self.tts.synthesize(text)
        except Exception as e:
            log.warning("TTS unavailable: %s", e)
            return False
        if speaker is None or pcm.size == 0:
            return False
        import io, wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.tts.sample_rate)
            w.writeframes(pcm.tobytes())
        speaker.play_wav(buf.getvalue(), block=False)
        return True
