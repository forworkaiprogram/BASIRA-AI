"""Privacy controls: media retention, consent, data deletion."""
from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from ..config import app_home
from ..db.database import Database
from ..logging_setup import get_logger

log = get_logger("privacy")


@dataclass
class PrivacyState:
    save_media: bool = False          # default: never store frames/audio
    history_enabled: bool = True
    cloud_enabled: bool = False


class PrivacyManager:
    """Enforces the privacy policy at runtime.

    Guarantees implemented here:
    - frames and audio buffers are never written to disk unless the user
      explicitly enables `save_media`;
    - `purge_all` deletes history, contexts, queue and any stored media;
    - every deletion is recorded as an audit event.
    """

    def __init__(self, db: Database, state: PrivacyState | None = None):
        self.db = db
        self.state = state or PrivacyState()
        self._media_dir = app_home() / "media"

    def can_store_media(self) -> bool:
        return self.state.save_media

    def media_dir(self) -> Path:
        self._media_dir.mkdir(parents=True, exist_ok=True)
        return self._media_dir

    def purge_media(self) -> int:
        n = 0
        if self._media_dir.exists():
            for p in self._media_dir.iterdir():
                try:
                    if p.is_file():
                        p.unlink()
                        n += 1
                    elif p.is_dir():
                        shutil = __import__("shutil")
                        shutil.rmtree(p)
                        n += 1
                except Exception as e:
                    log.warning("purge failed for %s: %s", p, e)
        self.db.add_audit_event("purge_media", f"items={n}")
        return n

    def purge_all_user_data(self) -> dict:
        counts = self.db.wipe_user_data()
        counts["media"] = self.purge_media()
        return counts

    def sync_state_from_settings(self, settings) -> None:
        self.state.save_media = settings.save_media
        self.state.history_enabled = settings.save_history
        self.state.cloud_enabled = settings.cloud_enabled
