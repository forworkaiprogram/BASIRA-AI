"""Sign language dataset tools.

Records landmark sequences to disk with explicit consent metadata, manages
a vocabulary file, and provides splits + augmentation for training. Data
format: JSONL where each line is one recorded sample:

    {"label": "...", "handedness": "Right", "consent_id": "...",
     "fps": 30, "frames": [[...42 floats...], ...]}

No dataset is bundled with the app. Vocabulary labels are user/dataset
defined; the starter vocabulary is empty on purpose so we never ship
labels we have not trained on.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np

FEATURE_DIM = 42


@dataclass
class Vocabulary:
    entries: dict[str, dict]

    @classmethod
    def load(cls, path: str | Path) -> "Vocabulary":
        p = Path(path)
        if not p.exists():
            return cls(entries={})
        return cls(entries=json.loads(p.read_text(encoding="utf-8")))

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps(self.entries, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add(self, label: str, meaning_ar: str, meaning_en: str,
            category: str = "general") -> None:
        if label in self.entries:
            raise ValueError(f"label already exists: {label}")
        self.entries[label] = {
            "meaning_ar": meaning_ar, "meaning_en": meaning_en,
            "category": category, "samples": 0,
        }

    def record_sample(self, label: str) -> None:
        if label not in self.entries:
            raise ValueError(f"unknown label: {label}")
        self.entries[label]["samples"] += 1


class SignDatasetWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, label: str, frames: np.ndarray, consent_id: str,
               handedness: str = "Right", fps: int = 30,
               source: str = "app_recording") -> int:
        if frames.ndim != 2 or frames.shape[1] != FEATURE_DIM:
            raise ValueError(f"expected (T, {FEATURE_DIM}) frames, got {frames.shape}")
        if not consent_id:
            raise ValueError("consent_id is required to store sign recordings")
        rec = {
            "label": label,
            "consent_id": consent_id,
            "handedness": handedness,
            "fps": fps,
            "source": source,
            "frames": frames.astype(float).tolist(),
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return frames.shape[0]


def load_jsonl(path: str | Path) -> list[dict]:
    out = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def split_dataset(samples: list[dict], train: float = 0.7, val: float = 0.15,
                  seed: int = 42) -> tuple[list[dict], list[dict], list[dict]]:
    """Stratified split by label."""
    rng = random.Random(seed)
    by_label: dict[str, list[dict]] = {}
    for s in samples:
        by_label.setdefault(s["label"], []).append(s)
    tr, va, te = [], [], []
    for _, items in sorted(by_label.items()):
        items = items[:]
        rng.shuffle(items)
        n = len(items)
        n_tr = max(1, int(n * train))
        n_va = max(1 if n >= 3 else 0, int(n * val))
        tr.extend(items[:n_tr])
        va.extend(items[n_tr:n_tr + n_va])
        te.extend(items[n_tr + n_va:] or items[-1:])
    return tr, va, te


def augment_sequence(frames: np.ndarray, rng: random.Random) -> np.ndarray:
    """Jitter + scale augmentation for landmark sequences."""
    out = frames.copy()
    noise = np.random.default_rng(rng.randint(0, 2**31)).normal(
        0, 0.004, out.shape).astype(np.float32)
    out = out + noise
    scale = rng.uniform(0.92, 1.08)
    return (out * scale).astype(np.float32)


def build_templates_from_jsonl(path: str | Path, max_per_label: int = 5,
                               augment: int = 0, seed: int = 42) -> list[tuple[str, np.ndarray]]:
    """Convert dataset samples into DTW templates."""
    samples = load_jsonl(path)
    rng = random.Random(seed)
    by_label: dict[str, list[dict]] = {}
    for s in samples:
        by_label.setdefault(s["label"], []).append(s)
    out = []
    for label, items in sorted(by_label.items()):
        for s in items[:max_per_label]:
            arr = np.array(s["frames"], dtype=np.float32)
            out.append((label, arr))
            for _ in range(augment):
                out.append((label, augment_sequence(arr, rng)))
    return out
