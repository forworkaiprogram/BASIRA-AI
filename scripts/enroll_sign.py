#!/usr/bin/env python3
"""Enroll a new dynamic sign from a webcam recording session.

Records normalized landmark sequences, requires an explicit consent id,
and appends both a dataset record and a live DTW template.
"""
from __future__ import annotations

import argparse
import time

import cv2
import numpy as np

from basira.config import models_dir
from basira.engines.sign.dataset_tools import SignDatasetWriter
from basira.engines.sign.hand_tracker import HandTracker
from basira.engines.sign.recognizer import normalize_landmarks
from basira.engines.sign.sequence import SequenceRecognizer


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--consent-id", required=True)
    ap.add_argument("--seconds", type=float, default=2.0)
    ap.add_argument("--camera", type=int, default=0)
    args = ap.parse_args()

    tracker = HandTracker(models_dir() / "sign" / "hand_landmarker.task")
    tracker.load()
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print("no camera")
        return 1
    frames = []
    print(f"recording '{args.label}' for {args.seconds}s…")
    t0 = time.time()
    while time.time() - t0 < args.seconds:
        ok, frame = cap.read()
        if not ok:
            break
        hands = tracker.track(frame)
        if hands:
            frames.append(normalize_landmarks(hands[0].landmarks))
        cv2.imshow("BASIRA enroll (q to quit)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()
    if len(frames) < 6:
        print("not enough frames with a visible hand")
        return 1
    arr = np.stack(frames).reshape(len(frames), -1)
    base = models_dir() / "sign"
    SignDatasetWriter(base / "recordings.jsonl").append(
        args.label, arr, args.consent_id)
    rec = SequenceRecognizer.load(base / "sign_templates.json") \
        if (base / "sign_templates.json").exists() else SequenceRecognizer()
    rec.add_template(args.label, arr, source="enroll_sign.py")
    rec.save(base / "sign_templates.json")
    print(f"enrolled '{args.label}' with {len(frames)} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
