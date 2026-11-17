"""Central configuration and paths for BASIRA AI.

All persistent state lives under a single app data directory so the
application never writes outside a known location. The directory can be
overridden with the BASIRA_HOME environment variable (used by tests).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

APP_NAME = "BASIRA AI"
APP_VERSION = "0.1.0"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def project_root() -> Path:
    return Path(os.environ.get("BASIRA_PROJECT_ROOT", _PROJECT_ROOT))


def app_home() -> Path:
    """User-writable data directory (settings, database, logs, models)."""
    env = os.environ.get("BASIRA_HOME")
    if env:
        p = Path(env)
    else:
        p = Path.home() / ".basira"
    p.mkdir(parents=True, exist_ok=True)
    return p


def models_dir() -> Path:
    p = Path(os.environ.get("BASIRA_MODELS_DIR", project_root() / "models"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def logs_dir() -> Path:
    p = app_home() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def database_path() -> Path:
    return app_home() / "basira.db"


def settings_path() -> Path:
    return app_home() / "settings.json"


@dataclass
class AppSettings:
    """User-changeable application settings, persisted as JSON."""

    language: str = "ar"                      # "ar" | "en"
    theme: str = "dark"                       # "dark" | "light" | "high_contrast"
    text_scale: float = 1.0                   # 0.85 .. 2.0
    rtl: bool = True
    speech_rate: float = 1.0
    speech_volume: float = 1.0
    tts_enabled: bool = True
    prefer_voice_output: bool = True          # blind users: answers are spoken
    high_contrast: bool = False
    save_history: bool = True
    save_media: bool = False                  # never save media by default
    cloud_enabled: bool = False               # offline-first: cloud opt-in only
    camera_index: int | None = None
    camera_width: int = 1280
    camera_height: int = 720
    camera_fps: int = 30
    microphone_index: int | None = None
    speaker_index: int | None = None
    stt_model: str = "base"
    stt_language: str = "ar"
    sound_alerts_enabled: bool = True
    sound_cooldown_seconds: float = 8.0
    haptic_alerts_enabled: bool = False
    backend_token: str = ""                   # loopback service auth token
    backend_port: int = 8765
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "AppSettings":
        data = json.loads(raw)
        known = {f for f in cls.__dataclass_fields__}
        extra = {k: v for k, v in data.items() if k not in known}
        data = {k: v for k, v in data.items() if k in known}
        obj = cls(**data)
        if extra:
            obj.extra.update(extra)
        return obj


def load_settings() -> AppSettings:
    p = settings_path()
    if p.exists():
        try:
            return AppSettings.from_json(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return AppSettings()


def save_settings(settings: AppSettings) -> None:
    settings_path().write_text(settings.to_json(), encoding="utf-8")
