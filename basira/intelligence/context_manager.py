"""Conversation context shared by all modes."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ContextEntry:
    role: str            # user | system | engine
    kind: str            # question | answer | observation | alert
    text: str
    confidence: float = 0.0
    modality: str = ""   # vision | sign | audio | text
    timestamp: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)


class ContextManager:
    """Keeps the last N entries plus a snapshot of the latest scene."""

    def __init__(self, max_entries: int = 30):
        self.max_entries = max_entries
        self.entries: list[ContextEntry] = []
        self.current_mode: str = "dashboard"
        self.last_answer: str = ""
        self.last_scene: dict[str, Any] = {}      # detections summary, ocr text
        self.user_preferences: dict[str, Any] = {}

    def add(self, entry: ContextEntry) -> None:
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries.pop(0)
        if entry.kind == "answer":
            self.last_answer = entry.text
        if entry.kind == "observation" and entry.modality == "vision":
            self.last_scene = entry.data

    def recent(self, n: int = 10) -> list[ContextEntry]:
        return self.entries[-n:]

    def snapshot(self) -> dict[str, Any]:
        return {
            "mode": self.current_mode,
            "last_answer": self.last_answer,
            "last_scene": self.last_scene,
            "recent": [
                {"role": e.role, "kind": e.kind, "text": e.text,
                 "confidence": e.confidence, "modality": e.modality,
                 "timestamp": e.timestamp}
                for e in self.recent(10)
            ],
        }

    def clear(self) -> None:
        self.entries.clear()
        self.last_answer = ""
        self.last_scene = {}
