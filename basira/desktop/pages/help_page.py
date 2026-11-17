"""Help page: shortcuts, safety notes, accessibility info."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from ..i18n import I18n
from .common import card


class HelpPage(QWidget):
    def __init__(self, i18n: I18n):
        super().__init__()
        self.i18n = i18n
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        cardf, lay2 = card(self.i18n("help"))
        self.content = QTextEdit()
        self.content.setReadOnly(True)
        self.content.setAccessibleName(self.i18n("help"))
        self.content.setMinimumHeight(300)
        lay2.addWidget(self.content)
        lay.addWidget(cardf)
        lay.addStretch(1)
        self._fill()

    def _fill(self) -> None:
        self.content.setPlainText(
            self.i18n("help_content") + "\n\n" + self.i18n("safety_note"))

    def retranslate(self, i18n: I18n) -> None:
        self.i18n = i18n
        self._fill()
