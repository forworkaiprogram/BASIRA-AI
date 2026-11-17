#!/usr/bin/env python3
"""Download all BASIRA AI models with checksum verification.

Usage: python scripts/download_models.py [--skip-large]
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"

MODELS_TO_DOWNLOAD = [
    # key, url, dest, min_bytes
    ("vision.yolov8n.pt",
     "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt",
     "vision/yolov8n.pt", 6_000_000),
    ("sign.hand_landmarker",
     "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
     "hand_landmarker/float16/latest/hand_landmarker.task",
     "sign/hand_landmarker.task", 7_000_000),
    ("language.piper-ar",
     "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/"
     "kareem/medium/ar_JO-kareem-medium.onnx?download=true",
     "language/ar_JO-kareem-medium.onnx", 60_000_000),
    ("language.piper-ar-config",
     "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/"
     "kareem/medium/ar_JO-kareem-medium.onnx.json?download=true",
     "language/ar_JO-kareem-medium.onnx.json", 1_000),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(key: str, url: str, dest: str, min_bytes: int) -> bool:
    dest_path = MODELS / dest
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists() and dest_path.stat().st_size >= min_bytes:
        print(f"[skip] {key} already present ({dest_path.stat().st_size} bytes)")
        return True
    print(f"[get ] {key} <- {url}")
    try:
        urllib.request.urlretrieve(url, dest_path)
    except Exception as e:
        print(f"[FAIL] {key}: {e}")
        return False
    size = dest_path.stat().st_size
    if size < min_bytes:
        print(f"[FAIL] {key}: file too small ({size} bytes)")
        return False
    print(f"[ok  ] {key} {size} bytes sha256={sha256(dest_path)[:16]}…")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-large", action="store_true",
                    help="skip files larger than 10 MB")
    args = ap.parse_args()
    ok = True
    for key, url, dest, min_bytes in MODELS_TO_DOWNLOAD:
        if args.skip_large and min_bytes > 10_000_000:
            continue
        ok &= download(key, url, dest, min_bytes)

    # EasyOCR models (ar+en) via the library itself
    try:
        import easyocr
        easyocr.Reader(["ar", "en"], gpu=False, verbose=False)
        print("[ok  ] vision.ocr easyocr ar+en models")
    except Exception as e:
        print(f"[FAIL] vision.ocr: {e}")
        ok = False

    # faster-whisper base model
    try:
        from faster_whisper import WhisperModel
        WhisperModel("base", device="cpu", compute_type="int8")
        print("[ok  ] audio.stt whisper base")
    except Exception as e:
        print(f"[FAIL] audio.stt: {e}")
        ok = False

    # export YOLO to ONNX for the runtime detector
    if (MODELS / "vision" / "yolov8n.pt").exists() and \
            not (MODELS / "vision" / "yolov8n.onnx").exists():
        try:
            from ultralytics import YOLO
            YOLO(str(MODELS / "vision" / "yolov8n.pt")).export(
                format="onnx", imgsz=640, simplify=True)
            print("[ok  ] vision.yolov8n.onnx exported")
        except Exception as e:
            print(f"[FAIL] onnx export: {e}")
            ok = False

    print("ALL OK" if ok else "SOME DOWNLOADS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
