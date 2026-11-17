"""History page: past translations/queries from the local database."""
from __future__ import annotations

from PySide6.QtWidgets import QListWidget, QVBoxLayout, QWidget

from ...intelligence.orchestrator import BASIRACore
from ..i18n import I18n
from .common import card


class HistoryPage(QWidget):
    def __init__(self, core: BASIRACore, i18n: I18n):
        super().__init__()
        self.core, self.i18n = core, i18n
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        cardf, lay2 = card(self.i18n("history"))
        self.list = QListWidget()
        self.list.setAccessibleName(self.i18n("history"))
        lay2.addWidget(self.list)
        lay.addWidget(cardf)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        rows = self.core.db.translation_history(100)
        if not rows:
            self.list.addItem(self.i18n("history_empty"))
            return
        for r in rows:
            src = (r["source_text"] or "")[:40]
            tgt = (r["target_text"] or "")[:80]
            conf = f"{r['confidence']:.0%}" if r["confidence"] is not None else "-"
            self.list.addItem(f"[{r['created_at']}] {r['source_kind']}->{r['target_kind']} "
                              f"{src} => {tgt} ({conf})")

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)

    def retranslate(self, i18n: I18n) -> None:
        self.i18n = i18n
