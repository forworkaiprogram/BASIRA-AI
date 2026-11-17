"""Scene description and grounded visual question answering.

Descriptions and answers are generated ONLY from real detector/OCR/spatial
outputs. When the system cannot answer from evidence it says so explicitly
instead of inventing content.
"""
from __future__ import annotations

from ..base import BaseEngine, EngineState
from ...logging_setup import get_logger
from .detector import Detection, COCO_AR
from .ocr import OcrResult
from .spatial import SpatialAnalyzer, SpatialRelation

log = get_logger("engines.vision.scene")


class SceneDescriptor(BaseEngine):
    name = "vision.scene"

    def _do_load(self) -> None:  # pure logic; nothing to load
        pass

    # -- description ----------------------------------------------------------
    def describe(self, detections: list[Detection], ocr: OcrResult | None,
                 frame_shape: tuple[int, int, int], lang: str = "ar") -> str:
        w, h = frame_shape[1], frame_shape[0]
        analyzer = SpatialAnalyzer(w, h)
        relations = analyzer.analyze(detections)
        if lang == "ar":
            return self._describe_ar(detections, ocr, relations)
        return self._describe_en(detections, ocr, relations)

    def _describe_ar(self, detections, ocr, relations) -> str:
        if not detections and (ocr is None or ocr.is_empty):
            return "لا أستطيع التأكد من وجود أشياء يمكن التعرف عليها في المشهد الحالي."
        parts = []
        if detections:
            counts: dict[str, int] = {}
            for d in detections:
                counts[d.class_name] = counts.get(d.class_name, 0) + 1
            names = []
            for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
                ar = COCO_AR.get(name, name)
                names.append(f"{ar} ({n})" if n > 1 else ar)
            parts.append("أرى: " + "، ".join(names) + ".")
            biggest = max(detections, key=lambda d: d.area)
            rel = next(r for r in relations if r.object == biggest.class_name)
            ar_name = COCO_AR.get(biggest.class_name, biggest.class_name)
            parts.append(
                f"أبرز شيء هو {ar_name} {self._dir_ar(rel.horizontal)}"
                f"، {self._size_ar(rel.size_bucket)}."
            )
        if ocr and not ocr.is_empty:
            parts.append(f"نص مرئي: \"{ocr.text[:120]}\".")
        parts.append("ملاحظة: التقديرات مبنية على الكاميرا فقط ولا تشمل مسافات دقيقة.")
        return " ".join(parts)

    def _describe_en(self, detections, ocr, relations) -> str:
        if not detections and (ocr is None or ocr.is_empty):
            return "I cannot confidently identify anything in the current scene."
        parts = []
        if detections:
            counts: dict[str, int] = {}
            for d in detections:
                counts[d.class_name] = counts.get(d.class_name, 0) + 1
            names = [f"{n} x{k}" if k > 1 else n for n, k in counts.items()]
            parts.append("I can see: " + ", ".join(names) + ".")
            biggest = max(detections, key=lambda d: d.area)
            rel = next(r for r in relations if r.object == biggest.class_name)
            dirs = {"left": "on the left", "right": "on the right",
                    "center": "straight ahead"}
            sizes = {"large": "appears close", "medium": "at medium apparent distance",
                     "small": "appears far or small"}
            parts.append(f"The most prominent is a {biggest.class_name} "
                         f"{dirs[rel.horizontal]}, {sizes[rel.size_bucket]}.")
        if ocr and not ocr.is_empty:
            parts.append(f"Visible text: \"{ocr.text[:120]}\".")
        parts.append("Note: estimates come from the camera only; no precise distances.")
        return " ".join(parts)

    @staticmethod
    def _dir_ar(h: str) -> str:
        return {"left": "على اليسار", "right": "على اليمين", "center": "أمامك مباشرة"}[h]

    @staticmethod
    def _size_ar(s: str) -> str:
        return {"large": "يبدو قريباً", "medium": "على مسافة متوسطة ظاهرياً",
                "small": "يبدو بعيداً أو صغيراً"}[s]

    # -- grounded VQA ----------------------------------------------------------
    def answer_question(self, question: str, detections: list[Detection],
                        ocr: OcrResult | None, frame_shape: tuple[int, int, int],
                        lang: str = "ar") -> tuple[str, float]:
        """Answer from evidence only. Returns (answer, confidence)."""
        w, h = frame_shape[1], frame_shape[0]
        analyzer = SpatialAnalyzer(w, h)
        relations = analyzer.analyze(detections)
        q = question.strip().lower()

        # What do you see?
        if any(k in q for k in ["ماذا يوجد", "ماذا ترى", "صف", "what do you see",
                                 "describe", "what is in front"]):
            return self.describe(detections, ocr, frame_shape, lang), 0.8

        # Where is X?
        where_kws = ["أين", "where"]
        if any(k in q for k in where_kws):
            target = self._extract_target(q, detections, lang)
            if target is None:
                no_msg = ("لا أستطيع رؤية هذا العنصر حالياً. عدم رؤيته لا يعني أنه غير موجود."
                          if lang == "ar" else
                          "I cannot see that object right now. Not seeing it does not "
                          "mean it is not there.")
                return no_msg, 0.3
            d, rel = target
            if lang == "ar":
                ar = COCO_AR.get(d.class_name, d.class_name)
                ans = (f"{ar} {analyzer.direction_to(rel, 'ar')}، "
                       f"{analyzer.proximity_hint(rel, 'ar')}.")
            else:
                ans = (f"The {d.class_name} is {analyzer.direction_to(rel, 'en')}, "
                       f"{analyzer.proximity_hint(rel, 'en')}.")
            return ans, min(0.9, d.confidence + 0.2)

        # Read text?
        if any(k in q for k in ["اقرأ", "مكتوب", "read", "written", "text"]):
            if ocr and not ocr.is_empty:
                ans = (f"النص المكتوب: {ocr.text}" if lang == "ar"
                       else f"The text says: {ocr.text}")
                conf = float(sum(ocr.confidences) / len(ocr.confidences)) if ocr.confidences else 0.5
                return ans, conf
            no_msg = ("لا أرى نصاً واضحاً في الصورة." if lang == "ar"
                      else "I do not see clear text in the image.")
            return no_msg, 0.4

        # Count?
        if any(k in q for k in ["كم", "how many"]):
            target = self._extract_target(q, detections, lang)
            if target:
                d, _ = target
                n = sum(1 for x in detections if x.class_name == d.class_name)
                ar = COCO_AR.get(d.class_name, d.class_name)
                ans = (f"أرى {n} {ar}." if lang == "ar" else f"I see {n} {d.class_name}(s).")
                return ans, 0.7
            none_msg = ("لا أستطيع العدّ لأنني لا أرى العنصر المطلوب." if lang == "ar"
                        else "I cannot count it because I do not see that object.")
            return none_msg, 0.3

        # Obstacles / safety
        if any(k in q for k in ["عائق", "طريقي", "obstacle", "path", "safe"]):
            warns = analyzer.obstacle_warnings(detections, lang)
            if warns:
                return " ".join(warns), 0.6
            safe_msg = ("لا أرى عوائق كبيرة في منتصف الطريق الظاهر، لكن هذا لا يضمن خلوّ "
                        "الطريق. استخدم عصاك البيضاء أو مساعدك المعتاد."
                        if lang == "ar" else
                        "I see no large obstacles in the apparent path, but this does not "
                        "guarantee a clear path. Use your cane or usual assistance.")
            return safe_msg, 0.5

        unsupported = ("لا أستطيع الإجابة على هذا السؤال من تحليل الكاميرا الحالي."
                       if lang == "ar" else
                       "I cannot answer this question from the current camera analysis.")
        return unsupported, 0.2

    def _extract_target(self, q: str, detections: list[Detection],
                        lang: str) -> tuple[Detection, SpatialRelation] | None:
        from .detector import COCO_CLASSES
        analyzer = SpatialAnalyzer(640, 480)
        best = None
        for d in detections:
            if d.class_name in q or COCO_AR.get(d.class_name, "") in q:
                rel = SpatialRelation(d.class_name, *self._rel(d, analyzer))
                if best is None or d.area > best[0].area:
                    best = (d, rel)
        return best

    @staticmethod
    def _rel(d: Detection, analyzer: SpatialAnalyzer) -> tuple[str, str, str, tuple]:
        r = analyzer.analyze([d])[0]
        return r.horizontal, r.vertical, r.size_bucket, r.position
