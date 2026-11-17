"""Models & system status page."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ...intelligence.orchestrator import BASIRACore
from ..i18n import I18n
from .common import card


class ModelsPage(QWidget):
    def __init__(self, core: BASIRACore, i18n: I18n):
        super().__init__()
        self.core, self.i18n = core, i18n
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)

        cardf, lay2 = card(self.i18n("engines"))
        self.engines_label = QLabel()
        self.engines_label.setAccessibleName(self.i18n("engines"))
        lay2.addWidget(self.engines_label)
        reload_btn = QPushButton(self.i18n("loading"))
        reload_btn.setObjectName("secondary")
        reload_btn.clicked.connect(self.refresh)
        lay2.addWidget(reload_btn)
        lay.addWidget(cardf)

        cardf2, lay3 = card(self.i18n("models"))
        self.models_label = QLabel()
        lay3.addWidget(self.models_label)
        lay.addWidget(cardf2)

        note = QLabel(self.i18n("models_missing"))
        note.setObjectName("alert")
        note.setWordWrap(True)
        lay.addWidget(note)
        lay.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        lines = []
        for st in self.core.registry.all_status():
            lines.append(f"{st.name}: {st.state.value} {st.detail}")
        self.engines_label.setText("\n".join(lines) or "—")
        rows = self.core.db.models()
        mlines = []
        for r in rows:
            import os
            exists = os.path.exists(r["file_path"])
            mlines.append(f"{'OK' if exists else 'MISSING'}  {r['key']}  "
                          f"({r['size_bytes'] or 0} bytes)")
        self.models_label.setText("\n".join(mlines) or self.i18n("models_missing"))

    def retranslate(self, i18n: I18n) -> None:
        self.i18n = i18n
