"""Multimodal fusion: merge engine outputs and detect conflicts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FusionResult:
    summary: str = ""
    items: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


# Arabic names for COCO classes used in fused summaries.
try:
    from ..engines.vision.detector import COCO_AR
except Exception:  # pragma: no cover
    COCO_AR = {}


class MultimodalFusion:
    """Combines vision/sign/audio results into one consistent report."""

    def fuse_scene(self, detections: list | None = None,
                   ocr_text: str = "",
                   sound_label: str | None = None,
                   sign_text: str = "",
                   lang: str = "ar") -> FusionResult:
        items: list[dict[str, Any]] = []
        conflicts: list[str] = []

        if detections:
            counts: dict[str, int] = {}
            for d in detections:
                counts[d.class_name] = counts.get(d.class_name, 0) + 1
            for name, n in counts.items():
                items.append({"kind": "object", "name": name,
                              "ar": COCO_AR.get(name, name), "count": n,
                              "confidence": max(
                                  d.confidence for d in detections
                                  if d.class_name == name)})
        if ocr_text:
            items.append({"kind": "text", "text": ocr_text})
        if sound_label:
            items.append({"kind": "sound", "label": sound_label})
        if sign_text:
            items.append({"kind": "sign", "text": sign_text})

        # Conflict: sign says something but no person detected to sign it.
        if sign_text and detections is not None and \
                not any(d.class_name == "person" for d in detections):
            conflicts.append(
                "تم التعرف على إشارة دون اكتشاف شخص في المشهد؛ "
                "قد تكون الثقة منخفضة."
                if lang == "ar" else
                "Sign recognized without a detected person; confidence may be low."
            )

        summary = self._summary(items, conflicts, lang)
        return FusionResult(summary=summary, items=items, conflicts=conflicts)

    def _summary(self, items: list[dict], conflicts: list[str], lang: str) -> str:
        parts = []
        objs = [i for i in items if i["kind"] == "object"]
        if objs:
            if lang == "ar":
                parts.append("أشياء: " + "، ".join(
                    f"{i['ar']}" + (f" ({i['count']})" if i["count"] > 1 else "")
                    for i in objs) + ".")
            else:
                parts.append("Objects: " + ", ".join(
                    f"{i['name']}" + (f" x{i['count']}" if i["count"] > 1 else "")
                    for i in objs) + ".")
        texts = [i for i in items if i["kind"] == "text"]
        if texts:
            parts.append(("نص: " if lang == "ar" else "Text: ")
                         + texts[0]["text"][:80])
        sounds = [i for i in items if i["kind"] == "sound"]
        if sounds:
            parts.append(("صوت: " if lang == "ar" else "Sound: ")
                         + sounds[0]["label"])
        signs = [i for i in items if i["kind"] == "sign"]
        if signs:
            parts.append(("إشارة: " if lang == "ar" else "Sign: ")
                         + signs[0]["text"])
        for c in conflicts:
            parts.append(c)
        return " ".join(parts) if parts else (
            "لا توجد نتائج لدمجها." if lang == "ar" else "Nothing to fuse.")
