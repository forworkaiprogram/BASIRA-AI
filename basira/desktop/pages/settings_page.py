"""Settings page: language, theme, text scale, voice, privacy."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from ...config import AppSettings, save_settings
from ...intelligence.orchestrator import BASIRACore
from ...privacy.privacy import PrivacyManager
from ..i18n import I18n
from .common import card


class SettingsPage(QWidget):
    def __init__(self, core: BASIRACore, settings: AppSettings, i18n: I18n,
                 on_changed=None):
        super().__init__()
        self.core, self.settings, self.i18n = core, settings, i18n
        self.on_changed = on_changed
        self.privacy = PrivacyManager(core.db)
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)

        # language & appearance
        cardf, l1 = card(self.i18n("settings"))
        row = QHBoxLayout()
        row.addWidget(QLabel(self.i18n("language")))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("العربية", "ar")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.setCurrentIndex(0 if self.settings.language == "ar" else 1)
        self.lang_combo.accessibleName = self.i18n("language")
        row.addWidget(self.lang_combo)
        row.addWidget(QLabel(self.i18n("theme")))
        self.theme_combo = QComboBox()
        for key, name in [("dark", self.i18n("dark")),
                          ("light", self.i18n("light")),
                          ("high_contrast", self.i18n("high_contrast"))]:
            self.theme_combo.addItem(name, key)
        self.theme_combo.setCurrentIndex(
            ["dark", "light", "high_contrast"].index(self.settings.theme))
        row.addWidget(self.theme_combo)
        l1.addLayout(row)

        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel(self.i18n("text_scale")))
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(85, 200)
        self.scale_slider.setValue(int(self.settings.text_scale * 100))
        self.scale_slider.setAccessibleName(self.i18n("text_scale"))
        scale_row.addWidget(self.scale_slider)
        l1.addLayout(scale_row)
        lay.addWidget(cardf)

        # voice & behavior
        cardf2, l2 = card(self.i18n("voice_output"))
        self.voice_check = QCheckBox(self.i18n("voice_output"))
        self.voice_check.setChecked(self.settings.prefer_voice_output)
        self.voice_check.setAccessibleName(self.i18n("voice_output"))
        l2.addWidget(self.voice_check)
        self.history_check = QCheckBox(self.i18n("save_history"))
        self.history_check.setChecked(self.settings.save_history)
        self.history_check.setAccessibleName(self.i18n("save_history"))
        l2.addWidget(self.history_check)
        self.media_check = QCheckBox(self.i18n("save_media"))
        self.media_check.setChecked(self.settings.save_media)
        self.media_check.setAccessibleName(self.i18n("save_media"))
        l2.addWidget(self.media_check)
        lay.addWidget(cardf2)

        note = QLabel(self.i18n("privacy_note"))
        note.setObjectName("success")
        note.setWordWrap(True)
        lay.addWidget(note)

        save_btn = QPushButton(self.i18n("settings"))
        save_btn.clicked.connect(self.save)
        lay.addWidget(save_btn)

        delete_btn = QPushButton(self.i18n("delete_data"))
        delete_btn.setObjectName("danger")
        delete_btn.clicked.connect(self.delete_data)
        lay.addWidget(delete_btn)
        lay.addStretch(1)

    def save(self) -> None:
        self.settings.language = self.lang_combo.currentData()
        self.settings.theme = self.theme_combo.currentData()
        self.settings.text_scale = self.scale_slider.value() / 100.0
        self.settings.prefer_voice_output = self.voice_check.isChecked()
        self.settings.save_history = self.history_check.isChecked()
        self.settings.save_media = self.media_check.isChecked()
        save_settings(self.settings)
        self.privacy.sync_state_from_settings(self.settings)
        if self.on_changed:
            self.on_changed()

    def delete_data(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        ret = QMessageBox.question(
            self, self.i18n("delete_data"), self.i18n("confirm_delete"))
        if ret == QMessageBox.Yes:
            counts = self.privacy.purge_all_user_data()
            QMessageBox.information(self, self.i18n("delete_data"),
                                    f"OK: {sum(counts.values())}")

    def retranslate(self, i18n: I18n) -> None:
        self.i18n = i18n
        self._build()
