"""Object detection with YOLOv8 via ONNX Runtime (no torch at runtime).

Input: BGR numpy frame. Output: list of Detection objects with COCO class
names, confidence and pixel-space boxes. Model must be exported beforehand
(scripts/export_yolo_onnx.py) or downloaded by scripts/download_models.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ...logging_setup import get_logger, ModelNotAvailableError
from ..base import BaseEngine, EngineState

log = get_logger("engines.vision.detector")

COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
    "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv",
    "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush",
]

# Arabic names for the everyday objects most relevant to accessibility.
COCO_AR = {
    "person": "شخص", "chair": "كرسي", "couch": "أريكة", "bed": "سرير",
    "dining table": "طاولة طعام", "door": "باب", "window": "نافذة",
    "tv": "شاشة", "laptop": "حاسوب محمول", "cell phone": "هاتف",
    "keyboard": "لوحة مفاتيح", "mouse": "فأرة", "book": "كتاب",
    "bottle": "زجاجة", "cup": "كوب", "bowl": "وعاء", "fork": "شوكة",
    "knife": "سكين", "spoon": "ملعقة", "clock": "ساعة", "vase": "مزهرية",
    "backpack": "حقيبة ظهر", "handbag": "حقيبة يد", "suitcase": "حقيبة سفر",
    "umbrella": "مظلة", "potted plant": "نبتة", "refrigerator": "ثلاجة",
    "microwave": "ميكروويف", "oven": "فرن", "sink": "حوض", "toilet": "مرحاض",
    "cat": "قطة", "dog": "كلب", "car": "سيارة", "bus": "حافلة",
    "bicycle": "دراجة", "scissors": "مقص", "teddy bear": "دمية",
    "remote": "ريموت", "apple": "تفاحة", "banana": "موزة", "orange": "برتقالة",
}

# Everyday-indoor classes the prompt asks to prioritize. COCO has no
# door/window classes; those are handled via the extension hook below.
PRIORITY_CLASSES = {
    "person", "chair", "couch", "bed", "dining table", "tv", "laptop",
    "cell phone", "book", "bottle", "cup", "bowl", "keyboard", "clock",
    "refrigerator", "sink", "door", "window",
}


@dataclass
class Detection:
    class_name: str
    confidence: float
    xyxy: tuple[float, float, float, float]  # pixels, (x1, y1, x2, y2)

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.xyxy
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.xyxy
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)


class ObjectDetector(BaseEngine):
    """YOLOv8 ONNX detector running on onnxruntime (CPU by default)."""

    name = "vision.detector"

    def __init__(self, model_path: str | Path, conf_threshold: float = 0.35,
                 iou_threshold: float = 0.45, imgsz: int = 640):
        super().__init__()
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.imgsz = imgsz
        self._session = None
        self._input_name = ""

    def _do_load(self) -> None:
        if not self.model_path.exists():
            self._state = EngineState.UNAVAILABLE
            raise ModelNotAvailableError(
                f"Detector model not found: {self.model_path}. "
                "Run scripts/download_models.py"
            )
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.intra_op_num_threads = 2
        so.inter_op_num_threads = 1
        self._session = ort.InferenceSession(str(self.model_path), so,
                                             providers=["CPUExecutionProvider"])
        self._input_name = self._session.get_inputs()[0].name
        out_shape = self._session.get_outputs()[0].shape
        log.info("detector loaded: %s (output %s)", self.model_path.name, out_shape)

    def _do_unload(self) -> None:
        self._session = None

    # -- inference ------------------------------------------------------------
    def _preprocess(self, frame: np.ndarray) -> tuple[np.ndarray, float, int, int]:
        import cv2

        h, w = frame.shape[:2]
        scale = min(self.imgsz / w, self.imgsz / h)
        nw, nh = int(round(w * scale)), int(round(h * scale))
        resized = cv2.resize(frame, (nw, nh))
        canvas = np.full((self.imgsz, self.imgsz, 3), 114, dtype=np.uint8)
        top, left = (self.imgsz - nh) // 2, (self.imgsz - nw) // 2
        canvas[top:top + nh, left:left + nw] = resized
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        blob = rgb.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        return blob, scale, left, top

    def _postprocess(self, output: np.ndarray, scale: float, pad_x: int,
                     pad_y: int, orig_w: int = 0, orig_h: int = 0) -> list[Detection]:
        # output: (1, 84, N) -> cx, cy, w, h, class scores
        pred = output[0].T  # (N, 84)
        scores = pred[:, 4:]
        class_ids = scores.argmax(axis=1)
        confs = scores.max(axis=1)
        keep = confs >= self.conf_threshold
        pred, class_ids, confs = pred[keep], class_ids[keep], confs[keep]
        boxes_xywh = pred[:, :4]

        boxes_xyxy = np.empty_like(boxes_xywh)
        boxes_xyxy[:, 0] = boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2
        boxes_xyxy[:, 1] = boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2
        boxes_xyxy[:, 2] = boxes_xywh[:, 0] + boxes_xywh[:, 2] / 2
        boxes_xyxy[:, 3] = boxes_xywh[:, 1] + boxes_xywh[:, 3] / 2
        boxes_xyxy = self._nms(boxes_xyxy, confs)

        dets: list[Detection] = []
        W = orig_w if orig_w > 0 else self.imgsz
        H = orig_h if orig_h > 0 else self.imgsz
        for (x1, y1, x2, y2), cid, conf in zip(boxes_xyxy, class_ids, confs):
            # undo letterbox
            x1 = (x1 - pad_x) / scale
            y1 = (y1 - pad_y) / scale
            x2 = (x2 - pad_x) / scale
            y2 = (y2 - pad_y) / scale
            x1, x2 = max(0.0, min(x1, W)), max(0.0, min(x2, W))
            y1, y2 = max(0.0, min(y1, H)), max(0.0, min(y2, H))
            name = COCO_CLASSES[cid] if cid < len(COCO_CLASSES) else str(cid)
            dets.append(Detection(name, float(conf), (float(x1), float(y1),
                                                      float(x2), float(y2))))
        dets.sort(key=lambda d: d.confidence, reverse=True)
        return dets

    @staticmethod
    def _nms(boxes: np.ndarray, scores: np.ndarray) -> np.ndarray:
        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
            iou = inter / np.maximum(areas[i] + areas[order[1:]] - inter, 1e-9)
            order = order[1:][iou <= 0.45]
        return boxes[keep]

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if self._session is None:
            self.load()
        blob, scale, pad_x, pad_y = self._preprocess(frame)
        out = self._timed(self._session.run, None, {self._input_name: blob})[0]
        return self._postprocess(out, scale, pad_x, pad_y,
                                 frame.shape[1], frame.shape[0])

    def find_object(self, frame: np.ndarray, query: str) -> Detection | None:
        """Find a specific object by English or Arabic name."""
        q = query.strip().lower()
        reverse_ar = {v: k for k, v in COCO_AR.items()}
        target = reverse_ar.get(query.strip()) or q
        dets = self.detect(frame)
        exact = [d for d in dets if d.class_name == target]
        if exact:
            return max(exact, key=lambda d: d.area)
        partial = [d for d in dets if target in d.class_name]
        return max(partial, key=lambda d: d.area) if partial else None
