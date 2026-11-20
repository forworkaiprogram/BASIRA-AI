#!/usr/bin/env python3
"""Export a YOLO .pt checkpoint to ONNX for the ONNX-Runtime detector."""
import sys
from pathlib import Path

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from basira.config import models_dir


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        models_dir() / "vision" / "yolov8n.pt"
    if not src.exists():
        print(f"checkpoint not found: {src}")
        return 1
    from ultralytics import YOLO

    path = YOLO(str(src)).export(format="onnx", imgsz=640, simplify=True)
    print(f"exported: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
