"""Spatial understanding from 2D detections.

Estimates relative positions (left/center/right, near/far-ish by apparent
size), computes zones and generates cautious navigation hints. This module
never claims metric distances: 2D bounding boxes alone cannot measure depth,
and the generated text explicitly reflects that limitation.
"""
from __future__ import annotations

from dataclasses import dataclass

from .detector import Detection


@dataclass
class SpatialRelation:
    object: str
    horizontal: str          # left | center | right
    vertical: str            # top | middle | bottom
    size_bucket: str         # small | medium | large (apparent size)
    position: tuple[float, float]  # normalized center 0..1


class SpatialAnalyzer:
    def __init__(self, frame_width: int, frame_height: int):
        self.w = max(1, frame_width)
        self.h = max(1, frame_height)

    def analyze(self, detections: list[Detection]) -> list[SpatialRelation]:
        out = []
        for d in detections:
            cx, cy = d.center
            nx, ny = cx / self.w, cy / self.h
            out.append(SpatialRelation(
                object=d.class_name,
                horizontal="left" if nx < 0.33 else "right" if nx > 0.66 else "center",
                vertical="top" if ny < 0.33 else "bottom" if ny > 0.66 else "middle",
                size_bucket=self._size_bucket(d.area),
                position=(nx, ny),
            ))
        return out

    def _size_bucket(self, area_px: float) -> str:
        frac = area_px / float(self.w * self.h)
        if frac < 0.02:
            return "small"
        if frac < 0.15:
            return "medium"
        return "large"

    def direction_to(self, relation: SpatialRelation, lang: str = "ar") -> str:
        if lang == "ar":
            h = {"left": "على اليسار", "right": "على اليمين", "center": "أمامك مباشرة"}[relation.horizontal]
        else:
            h = {"left": "to your left", "right": "to your right",
                 "center": "straight ahead"}[relation.horizontal]
        return h

    def proximity_hint(self, relation: SpatialRelation, lang: str = "ar") -> str:
        """Apparent-size-based hint. Deliberately NOT a distance estimate."""
        if lang == "ar":
            return {"large": "يبدو قريباً جداً من الكاميرا",
                    "medium": "على مسافة متوسطة ظاهرياً",
                    "small": "يبدو بعيداً أو صغيراً"}[relation.size_bucket]
        return {"large": "appears very close to the camera",
                "medium": "appears at a moderate distance",
                "small": "appears far away or small"}[relation.size_bucket]

    def obstacle_warnings(self, detections: list[Detection], lang: str = "ar") -> list[str]:
        """Cautious hints for large objects in the lower/corridor area.

        Limited by design: this is a hint, never a guarantee that the path
        is clear (absence of detection is not evidence of absence).
        """
        warnings = []
        blocking = {"chair", "couch", "dining table", "person", "bed", "tv"}
        for d in detections:
            if d.class_name not in blocking:
                continue
            nx, ny = d.center[0] / self.w, d.center[1] / self.h
            frac = d.area / float(self.w * self.h)
            if 0.25 < nx < 0.75 and ny > 0.45 and frac > 0.04:
                if lang == "ar":
                    warnings.append(
                        f"انتباه: يوجد {self._ar(d.class_name)} في منتصف الطريق الظاهر أمامك"
                    )
                else:
                    warnings.append(
                        f"Caution: a {d.class_name} appears in the middle of your path"
                    )
        return warnings

    @staticmethod
    def _ar(name: str) -> str:
        from .detector import COCO_AR
        return COCO_AR.get(name, name)
