"""Intent routing: map a user request to the right mode and engines."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RouteDecision:
    mode: str                     # vision | sign | hear | connect
    intent: str                   # describe | find | read | vqa | translate | listen | sounds
    engines: list[str]
    language: str = "ar"


VISION_INTENTS = [
    ("find", ["أين", "وين", "find", "where is", "locate"]),
    ("read", ["اقرأ", "مكتوب", "ماذا مكتوب", "read", "written", "text", "نص"]),
    ("count", ["كم", "how many", "عدد"]),
    ("obstacle", ["عائق", "طريقي", "أمان", "obstacle", "path", "safe"]),
    ("describe", ["ماذا يوجد", "ماذا ترى", "صف", "what do you see", "describe",
                  "what is in front", "المشهد"]),
]
HEAR_INTENTS = [
    ("sounds", ["أي صوت", "ما هذا الصوت", "sound", "noise", "تنبيه"]),
    ("listen", ["اسمع", "سجل", "listen", "transcribe", "حول الكلام"]),
]
SIGN_INTENTS = [
    ("translate", ["إشارة", "sign", "ترجم الإشارة"]),
]


class ModeRouter:
    def route(self, request: str, has_camera_frame: bool = True) -> RouteDecision:
        q = request.strip().lower()
        if not q:
            return RouteDecision("vision", "describe",
                                 ["vision.detector", "vision.scene"])

        for intent, kws in VISION_INTENTS:
            if any(k in q for k in kws) and has_camera_frame:
                engines = ["vision.detector", "vision.scene"]
                if intent in ("read",):
                    engines.append("vision.ocr")
                return RouteDecision("vision", intent, engines)

        for intent, kws in HEAR_INTENTS:
            if any(k in q for k in kws):
                return RouteDecision("hear", intent, ["audio.stt", "audio.sounds"])

        for intent, kws in SIGN_INTENTS:
            if any(k in q for k in kws):
                return RouteDecision("sign", intent, ["sign.tracker"])

        # Default: treat as visual question about the scene.
        return RouteDecision("vision", "vqa",
                             ["vision.detector", "vision.scene", "vision.ocr"])
